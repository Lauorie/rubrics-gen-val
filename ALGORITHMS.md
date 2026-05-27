# rlm-rubrics 算法说明

> 本文档面向**研究者 / 贡献者**，从方法学角度描述本仓库两条核心管线的算法细节。
> 想要"装上就用"，请看 [`USAGE.md`](USAGE.md)。
> 想要英文 quickstart，请看 [`README.md`](README.md)。

## 目录

- [1. 总览](#1-总览)
- [2. Rubric 生成算法](#2-rubric-生成算法)
  - [2.1 输入与输出](#21-输入与输出)
  - [2.2 Stage 0 — 源文档 RAG 检索](#22-stage-0--源文档-rag-检索)
  - [2.3 Stage 1 — RAG 锚定的初稿生成](#23-stage-1--rag-锚定的初稿生成)
  - [2.4 Stage 2 — 复合拆分 + 去重 + Pitfall 注入](#24-stage-2--复合拆分--去重--pitfall-注入)
  - [2.5 Stage 3 — 失准过滤](#25-stage-3--失准过滤)
  - [2.6 Schema 校验](#26-schema-校验)
- [3. 评估算法](#3-评估算法)
  - [3.1 输入与输出](#31-输入与输出)
  - [3.2 Per-criterion Judge](#32-per-criterion-judge)
  - [3.3 加权二值得分公式](#33-加权二值得分公式)
  - [3.4 Anchor 归一化](#34-anchor-归一化)
  - [3.5 聚合报告](#35-聚合报告)
  - [3.6 并发模型](#36-并发模型)
- [4. 设计取舍](#4-设计取舍)
- [5. 参考文献](#5-参考文献)

---

## 1. 总览

仓库实现两条独立但共享 schema 的管线：

```text
┌────────────────────────────────────────────────────────────────────┐
│  Pipeline A — Rubric 生成                                          │
│                                                                    │
│  源题 + 参考答案 + 源文档 markdown                                 │
│              │                                                     │
│              ▼                                                     │
│       Stage 0  RAG 检索：(doc, page) → 相关 chunks                 │
│       Stage 1  LLM 初稿：title + ref + chunks + 题型规则 + few-shot │
│       Stage 2  精炼：拆复合断言 / embedding 去重 / 注入默认 pitfall│
│       Stage 3  失准过滤：在 ref 上必中 + 在 weak 上必不中           │
│       Schema   pydantic v2 强校验                                  │
│              │                                                     │
│              ▼                                                     │
│       rubrics/items/idx_NNN.json （每题一个加权二值检查清单）      │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│  Pipeline B — 评估                                                 │
│                                                                    │
│  rubrics/items/* + 任意模型的预测 JSONL                            │
│              │                                                     │
│              ▼                                                     │
│       Anchor 计算：rubric × {ref, weak} → 缓存 (ref, weak) 分数    │
│       Per-criterion judge：对每个 (题, 候选, criterion) 三元组打分 │
│       Scoring：(正向得分 − 陷阱扣分) / 正向满分 → clip 到 [0,1]     │
│       Anchor 归一化：(score − weak) / (ref − weak)                  │
│       Aggregate：按 question_type / difficulty / criterion_type 分组│
│              │                                                     │
│              ▼                                                     │
│       eval_*.json  （per_candidate 明细 + aggregate 报告）         │
└────────────────────────────────────────────────────────────────────┘
```

两条管线在代码中分别由 `src/rubrics/pipeline.py:build_rubric_for_item` 和 `src/rubrics/scorer.py:Scorer` 编排。Schema 由 `src/rubrics/schema.py` 统一约束。

---

## 2. Rubric 生成算法

### 2.1 输入与输出

**输入**（每题）：

```python
item = {
    "编号": "1",
    "问题描述": "在流固耦合（FSI）仿真中，'附加质量效应'为何会导致数值不稳定？",
    "参考答案": "流体与结构密度接近：……",
    "题型": "主观题",        # ∈ {简答题, 主观题, 决策题, 对比分析题, 数值提取题, 流程描述题, 数值关系题}
    "难易程度": "困难",       # ∈ {简单, 中等, 困难}
    "难度场景": "...",
    "来源": "Benson教材, 第4章, 第166-189页",
}
```

**输出**：一个 `RubricItem`（`schema.py`），核心字段是 `criteria: List[Criterion]`，每个 `Criterion` 形如：

```python
Criterion(
    id="c1",
    text="指出流体密度与结构密度接近……",
    category="Essential",          # ∈ {Essential, Important, Optional, Pitfall}
    weight=5,                       # ∈ [1, 8]
    sign="positive",                # ∈ {positive, negative}；Pitfall 必须 negative
    criterion_type="factual_anchor",
    evidence_quote=None,            # 可选：来自源文档的支撑短语
)
```

### 2.2 Stage 0 — 源文档 RAG 检索

**步骤 1：分块（`chunker.py:chunk_markdown`）**

对每份 mineru 转出来的 markdown 滑窗：

```text
chunk_size = 400 字符（≈ 中文 token 数）
overlap    = 100 字符
step       = chunk_size − overlap = 300
```

页码靠 mineru 在图片 URL 里埋的锚点 `page_(\d+)_block_\d+` 解析（0-indexed → 内部存为 1-indexed）。每个 chunk 用 `_page_at_offset` 二分查找它所在的页码范围 `[page_start, page_end]`，生成稳定的 `chunk_id`：

```text
{doc_slug}:p{page_start}-p{page_end}:c{chunk_index}
```

**步骤 2：embedding 索引（`index.py:ChunkIndex.build`）**

```python
model = SentenceTransformer("BAAI/bge-base-zh-v1.5")
embeddings = model.encode([c.text for c in chunks], normalize_embeddings=True)
```

L2 归一化后的向量直接做点积即余弦相似度。

**步骤 3：query encoding 用 BGE 非对称前缀**

BGE-zh 模型要求 query 加专用前缀，document 不加：

```python
prefix = "为这个句子生成表示以用于检索相关文章："
qv = model.encode([prefix + question], normalize_embeddings=True)
```

这是 `index.py` 中**当前唯一一处硬编码语言**的位置。换非中文模型时这里需要同步改。

**步骤 4：page-first 检索 + semantic fallback（`retriever.py:retrieve_context`）**

来源字段先用 `source_parser.py:parse_source` 解析成 `List[SourceRef]`，每个 `SourceRef` 含 `(doc_alias, pages)`。检索按下面顺序回退：

```python
def retrieve_context(question, refs, index, k=3):
    if refs:
        hits = []
        had_pages = False
        for ref in refs:
            doc_slug = lookup(ref.doc_alias)
            if ref.pages is not None:        # 第 N-M 页约束
                had_pages = True
                hits += index.search_within(question, k, doc_slug, ref.pages, score_threshold=0.0)
            else:                              # 仅文档约束
                hits += index.search_within(question, k, doc_slug, pages=None, score_threshold=0.0)
        hits = dedup(hits)[:k]
        if hits:
            return hits, "page_specific" if had_pages else "doc_only"
    return index.search(question, k), "fallback_semantic"   # 兜底全库检索
```

注意：`search_within` 在显式 `doc_slug` / `pages` 约束下把 `score_threshold` 设为 0，意思是**只要在约束范围内就取**，不再因相似度低而过滤；fallback 全库检索时才用默认 0.3 阈值。这是因为来源是人写的"硬约束"，应当优先满足。

**实测分布**（CAE 94 题）：

| ground_status | 数量 | 占比 |
|---|---|---|
| page_specific | 68 | 72% |
| doc_only | 16 | 17% |
| fallback_semantic | 10 | 11% |

### 2.3 Stage 1 — RAG 锚定的初稿生成

调用 `generator.py:generate_initial_rubric`，向 LLM 发一次请求。Prompt 由 system + user message 两段构成，user message 内部分 8 个标注区块（外加末尾一句"请直接输出 JSON"指令）：

```text
[system_prompt.txt]               ← 总规则（schema、category、weight、criterion_type 7 选 1）
[user message]
  ├ [Q] {问题}
  ├ [参考答案] {ref}
  ├ [题型] {题型}（请遵循该题型的 rubric 结构）
  ├ [难易程度] {difficulty}
  ├ [来源] {source}
  ├ [领域上下文 — 来自源文档]
  │   [chunk 1 | {doc_slug} p{page_start}-p{page_end}]
  │   ...
  ├ [题型规则]   ← templates/type_rules/{题型}.txt
  └ [few-shot 示例]   ← exemplars/gold_rubrics.json 随机 3 条（含同类 + 异类）
```

**总规则（system prompt）核心约束**：

1. 每条 criterion **原子化**，可被 judge 一眼判定 yes/no
2. 禁止"X 且 Y"复合断言
3. category ∈ {Essential, Important, Optional, Pitfall}，sign 对应 ∈ {positive, negative}
4. weight 默认值：Essential=5 / Important=3 / Optional=1 / Pitfall=3-5，允许 ±1 微调
5. criterion_type 7 选 1
6. **至少 2 条 Pitfall (anti_hacking)**
7. **严禁形容词**：`good / clear / comprehensive / 合理 / 适当` 等无锚点词被明确禁用，强制写具体术语、参数名、数值、单位、步骤
8. **优先从参考答案和领域上下文中提炼**，不要凭空捏造参考答案未涉及的事实

**题型规则差异**（`type_rules/{7种题型}.txt`），简表：

| 题型 | 总条目数 | 关键 criterion_type 配比 |
|---|---|---|
| 主观题 | 10-12 | factual_anchor 2-3 / mechanism_explanation 3-4 |
| 决策题 | 8-11 | decision_logic 3-4（含 1 条"明确给出选择"） + 建议 1 条 pitfall"给出多个并列选项而不做决定" |
| 对比分析题 | 8-10 | comparative_balance + factual_anchor 多条 |
| 数值提取题 | 6-8 | numeric_precision 主导（每个关键数值 1 条）+ pitfall"写出数值但缺单位/含义" |
| 简答题 | 8-10 | factual_anchor + mechanism_explanation |
| 流程描述题 | 7-9 | process_completeness 主导（每个步骤 1 条）|
| 数值关系题 | 6-8 | numeric_precision 主导（关注比例 / 指数 / 单位） |

**few-shot 采样策略**（`generator.py:_format_exemplars`）：

```python
def _format_exemplars(question_type):
    raw = load("exemplars/gold_rubrics.json")
    same = [r for r in raw if r["question_type"] == question_type]
    others = [r for r in raw if r["question_type"] != question_type]
    return same[:1] + others[:max(0, 3 - len(same[:1]))]
```

优先选 1 条同题型 + 2 条异题型，避免 LLM 过度模仿同题型的结构而失去 diversity。

**输出协议**：要求 LLM 返回严格 JSON（`llm_client.py:_extract_json_block` 会先剥 markdown fence 再解析）：

```json
{
  "criteria": [
    { "id": "c1", "text": "...", "category": "Essential", "weight": 5, "sign": "positive", "criterion_type": "factual_anchor" }
  ]
}
```

### 2.4 Stage 2 — 复合拆分 + 去重 + Pitfall 注入

`refiner.py:refine_criteria` 三个串行步骤：

**步骤 1：复合断言拆分（`_split_compound`）**

正则匹配中文/英文连接词，把"X 且 Y"拆成两条：

```python
_COMPOUND_SPLIT_RE = re.compile(
    r"\s*[，,]\s*并\s*|\s*[，,]\s*同时\s*|\s*[，,]\s*且\s*|\s*并\s*"
)
```

拆出来的每个子句保留原 criterion 的 weight / category / sign / criterion_type（即一拆为多，每条权重不变）。这是有意的设计 — 拆完后总权重虽然变大，但 Stage 3 的失准过滤会丢掉那些在参考答案上不命中的子句，最终留下的都是真正可验证的。子句长度 < 4 字符的丢弃（避免拆出 "并" 这种残片）。

**步骤 2：embedding 去重（`_dedup_by_embedding`）**

```python
def _dedup_by_embedding(criteria, embed_fn, threshold=0.9):
    emb = normalize(embed_fn([c["text"] for c in criteria]))
    keep = []
    seen_vecs = []
    for c, v in zip(criteria, emb):
        if not any(np.dot(v, sv) > threshold for sv in seen_vecs):
            keep.append(c)
            seen_vecs.append(v)
    return keep
```

贪心 O(N²)（N 通常 ≤ 15）。**阈值 0.9 较保守**，倾向保留近似但表述不同的 criterion；调到 0.85 会更激进但可能误伤同义复述。`embed_fn` 由 `02_generate_rubrics.py` 注入，复用 BGE-zh，在 `pipeline.py` 调 `pipeline.build_rubric_for_item(embed_fn=embed_fn)` 时传入。如果 `embed_fn is None`，跳过去重（用于测试）。

**步骤 3：默认 Pitfall 注入（`_ensure_default_pitfalls`）**

无论 LLM 是否生成，强制至少有这两条 anti-hacking pitfall：

```python
DEFAULT_PITFALLS = [
    {
        "text": "回答以套话/开场白/元评论开头而无实质内容",
        "category": "Pitfall", "weight": 4, "sign": "negative",
        "criterion_type": "anti_hacking",
    },
    {
        "text": "回答篇幅冗长，包含大量与问题无关的背景铺垫或重复",
        "category": "Pitfall", "weight": 3, "sign": "negative",
        "criterion_type": "anti_hacking",
    },
]
```

按 `text` 严格匹配去重（如果 LLM 已生成同文本就不重复加）。题型规则可能追加题型特定的 pitfall（如决策题的"给出多个并列选项而不做决定"），由 Stage 1 的 LLM 生成。

**步骤 4：重新编号**

`_renumber` 把 id 重置为 `c1, c2, ..., cN`，保证最终 id 连续。

### 2.5 Stage 3 — 失准过滤

`misalignment_filter.py:filter_misaligned` 用一个独立的 judge LLM 对每条**正向**（非 Pitfall）criterion 跑两轮：

```python
WEAK_ANSWER = "我不知道。"

for c in criteria:
    if c["category"] == "Pitfall":
        keep.append(c)              # Pitfall 不过滤
        continue
    met_ref  = judge(question, reference_answer, c)
    met_weak = judge(question, WEAK_ANSWER,      c)
    if not met_ref:
        drop(c, reason="not met on reference answer")     # criterion 写错了
        continue
    if met_weak:
        drop(c, reason="triggered on weak answer")        # criterion 太松
        continue
    keep.append(c)
```

**判别逻辑**：

- `met_ref == False`：参考答案都满足不了 → criterion 与参考答案脱节 → 删
- `met_weak == True`："我不知道。" 都能触发 → criterion 太宽，会给任何回答送分 → 删
- 否则：criterion 既能识别正确答案，又能拒绝空白答案 → 留

**Pitfall 跳过**的原因：Pitfall 是 negative 信号，在 ref 上应当不触发（ref 是优质答案），在 weak 上"我不知道。" 也不会触发"开场白套话"或"冗长铺垫"，所以两边都 met=false，按上面的逻辑都会被删 — 这显然不对。Pitfall 的质量由 Stage 2 的默认模板 + Stage 1 的 LLM 在题型规则约束下生成保证，不走过滤。

**Judge 调用约定**（`judge.py:judge_one_sync`）：

```python
def _build_user_message(question, candidate, criterion):
    return (
        f"[题目] {question}\n"
        f"[候选回答] {candidate}\n"
        f"[criterion] {criterion['text']}\n"
        f"[criterion 类型] {criterion['criterion_type']}"
    )
```

System prompt（`templates/misalignment_judge_prompt.txt`）要求严格 JSON `{met: bool, reason: str}`，边界情形严格判 `met=false`。

**容错策略**：judge 调用 3 次重试都失败时，过滤器的 `_judge_one` 用保守默认：

```python
if "error" in result:
    return True if criterion["sign"] == "positive" else False
```

即：正向 criterion 默认通过（不误删），负向默认不触发（不误判 pitfall）。

**实测**（CAE 94 题，gpt-5.4-mini）：平均每题被丢 0.5 条，最大 4 条。

### 2.6 Schema 校验

`schema.py` 用 pydantic v2 做最终强校验，关键不变量：

```python
class Criterion(BaseModel):
    weight: int = Field(ge=1, le=8)

    @model_validator(mode="after")
    def check_sign_matches_category(self):
        if self.category == "Pitfall" and self.sign != "negative":
            raise ValueError("Pitfall must have sign=negative")
        if self.category != "Pitfall" and self.sign == "negative":
            raise ValueError(f"{self.category} must have sign=positive")
        return self
```

`category` / `sign` / `criterion_type` / `question_type` / `difficulty` / `ground_status` 全部是 `Literal[...]`，任何超出枚举的值在反序列化时直接报错。这是端到端最后一道防线 — 即使 LLM 输出了不合法值，写盘前会被拦截。

---

## 3. 评估算法

### 3.1 输入与输出

**输入**：

- `rubrics/items/idx_NNN.json` — 一批 rubric（由 Pipeline A 生成或第三方提供，需符合 schema）
- 预测 `*.jsonl`：每行 `{"item_idx": int, "answer": str}`
- 可选：anchor 缓存 `data/CAE-anchor-scores.json`

**输出**（`data/eval_*.json`）：

```json
{
  "per_candidate": [
    {
      "item_idx": 0,
      "question_id": "1",
      "question_type": "主观题",
      "difficulty": "困难",
      "candidate_answer": "...",
      "score": 0.84,
      "score_anchored": { "ref_score": 1.0, "weak_score": 0.0, "normalized": 0.84 },
      "breakdown": [
        { "id": "c1", "text": "...", "category": "Essential", "weight": 5, "sign": "positive",
          "criterion_type": "factual_anchor", "met": true, "reason": "...", "contribution": 5 }
      ],
      "judge_model": "openai/gpt-5.4-mini",
      "scored_at": "2026-05-22T10:38:06+00:00"
    }
  ],
  "aggregate": { "n_predictions": 94, "mean_anchored": 0.81, ... }
}
```

### 3.2 Per-criterion Judge

复用 Stage 3 的 `judge.py:judge_one_async`（async 版本），prompt 和 system 完全相同。每个 `(question, candidate, criterion)` 三元组发一次 LLM 请求，返回 `{met: bool, reason: str}`。

**关键设计**：judge 一次只看**一个** criterion，不让它"打总分"。这是 rubric 评估对比传统 LLM-as-judge（让 judge 给出 0-10 分）的核心区别 —

- 单 criterion 是二值判断，judge 之间方差小、可解释性强
- 总分由确定性公式（§3.3）算出，judge 不参与权重决策
- judge 的偏置（如总爱打高分）在每条 criterion 上独立体现，可通过 anchor 归一化（§3.4）抹掉

### 3.3 加权二值得分公式

`scoring.py:score_response`：

```python
def score_response(criteria, met_by_text):
    pos_score, pos_max, penalty = 0, 0, 0
    for c in criteria:
        met = met_by_text.get(c.text, False)
        if c.sign == "positive":
            pos_max += c.weight
            if met:
                pos_score += c.weight
        else:                          # Pitfall
            if met:
                penalty += c.weight
    if pos_max == 0:
        return 0.0
    raw = (pos_score - penalty) / pos_max
    return max(0.0, min(1.0, raw))     # clip 到 [0, 1]
```

$$
\text{设 criterion 集 } C \text{，正向子集 } C^+ = \{c \in C : \mathrm{sign}(c) = \mathrm{positive}\} \text{，陷阱子集 } C^- = \{c \in C : \mathrm{sign}(c) = \mathrm{negative}\} \text{，} w_c \text{ 为权重，} m_c \in \{0, 1\} \text{ 为 judge 判定：}
$$

$$
\text{score} = \mathrm{clip}_{[0,1]}\left( \frac{\displaystyle\sum_{c \in C^+} w_c m_c - \sum_{c \in C^-} w_c m_c}{\displaystyle\sum_{c \in C^+} w_c} \right)
$$

**几个性质**：

- 分母只取正向满分 $\sum_{c \in C^+} w_c$，所以"全对 + 不触发陷阱"得 1.0
- "全对 + 触发所有陷阱"得 $\max(0, 1 - \frac{\sum w_{c^-}}{\sum w_{c^+}})$，根据默认 pitfall 权重 (4+3) 和典型正向满分 ~25，约 0.72
- "全错" 得 0.0
- 任何触发了陷阱但正向不满的回答可能被 clip 到 0.0

**为什么不归一化陷阱**：陷阱的设计意图是"减分项"，不是"扣分上限"。如果归一化陷阱（如除以 $\sum w_{c^-}$），会模糊"触发 1 个 pitfall vs 触发 3 个"的差异；当前公式让每个陷阱按其在正向尺度上的相对权重产生线性扣分。

### 3.4 Anchor 归一化

不同 rubric 的"天花板"不一致：有的题 ref 答案能拿满分 1.0，有的题 ref 答案因为 criterion 写得严只拿 0.85。要做跨题 / 跨数据集的横向比较，必须重标到统一尺度。

**Anchor 定义**（`anchor.py:compute_anchor_for_rubric`）：

```python
async def compute_anchor_for_rubric(rubric, judge_client, weak_answer="我不知道。"):
    question = rubric["question"]
    ref_answer = rubric["reference_answer"]
    ref_met  = await _judge_all(ref_answer)            # 对所有 criterion 跑一遍
    weak_met = await _judge_all(weak_answer)
    return {
        "ref_score":  score_response(criteria, ref_met),
        "weak_score": score_response(criteria, weak_met),
        ...
    }
```

**归一化公式**（`scorer.py:_compute_anchored`）：


$$
\text{normalized} = \mathrm{clip}_{[0,1]}\left(
\frac{\mathrm{score} - \mathrm{weak\_score}}
{\mathrm{ref\_score} - \mathrm{weak\_score}}
\right)
$$

退化情况：当 `ref_score <= weak_score` 时（rubric 校准失败，参考答案得分不如"我不知道"），返回 `normalized=null` 并打 warning。这通常意味着该 rubric 的 criterion 太宽或参考答案太短，需要回到 Stage 3 重新生成。

**Anchor 缓存**（`anchor.py:AnchorCache`）：JSON-backed，按 `item_idx` 字符串做 key，避免重复计算 — 同一批 rubric 在评估多个候选模型时复用一份 anchor。改了 rubric 必须 `--refresh-anchors`，否则 anchor 与 rubric 不一致。



## 通俗语言解释一下这套打分系统，其实就两步：**先算原始分，再做归一化**。



## 第一步：算原始分（加权二值得分）

想象你在参加一场考试，但这场考试有点特殊：

**1. 题目分两种：**
- **加分题**（positive）：答对加分，答错不扣分。比如"回答是否提到了关键概念A"，提到了就加分。
- **陷阱题**（pitfall）：踩到就扣分。比如"回答是否出现了明显的事实错误"，出现了就扣分。

**2. 每道题权重不同：**
- 有的加分题很重要（权重高），有的不太重要（权重低）
- 陷阱题也一样，有的错误很严重（扣得多），有的小问题（扣得少）

**3. 打分公式：**

```
原始分 = (加分题得分 - 陷阱题扣分) / 加分题总分
```

**举个例子：**
- 加分题总分 25 分，你答对了 20 分的内容
- 陷阱题你踩了一个，扣 4 分
- 原始分 = (20 - 4) / 25 = 0.64

**特殊情况：**
- 如果你加分题全对，也没踩陷阱 → 得 1.0（满分）
- 如果你加分题全错 → 得 0.0
- 如果你踩了很多陷阱，扣分超过加分 → 也会被"截断"到 0.0（不会出现负分）

---

## 第二步：归一化（Anchor 归一化）

**问题来了：** 不同的题目，难度不一样。

比如：
- 题目A：参考答案能拿满分 1.0
- 题目B：参考答案因为标准太严，只能拿 0.85

如果你直接比较两个模型在不同题目上的原始分，就不公平了。

**怎么办？用"锚点"来校准。**

系统会找两个"参照物"：
1. **学霸答案**（ref_score）：标准参考答案的得分
2. **学渣答案**（weak_score）：一个很差的回答（比如"我不知道"）的得分

**归一化公式：**

```
归一化分数 = (你的原始分 - 学渣分数) / (学霸分数 - 学渣分数)
```

**这样一换算：**
- 学霸答案 → 归一化后一定是 1.0
- 学渣答案 → 归一化后一定是 0.0
- 你的答案 → 在 0 到 1 之间，表示"你比学渣好多少，离学霸还差多少"

**再举个例子：**
- 题目B的学霸答案原始分 0.85，学渣答案原始分 0.1
- 你的原始分是 0.6
- 归一化后 = (0.6 - 0.1) / (0.85 - 0.1) = 0.5 / 0.75 ≈ 0.67

这样不管题目难度如何，归一化后的分数就可以跨题目比较了。

---

## 为什么要这么设计？

1. **加分题和陷阱题分开**：鼓励模型"做对的事"，同时惩罚"犯严重错误"。踩一个陷阱和踩三个陷阱，扣分是不一样的。

2. **不归一化陷阱**：陷阱是"减分项"，不是"扣分上限"。如果归一化陷阱，就看不出"踩1个坑"和"踩3个坑"的区别了。

3. **Anchor 归一化**：解决"不同题目天花板不同"的问题，让分数可以横向比较。

---

**总结一下：**
- 先算原始分：做对的加分，踩坑的扣分，除以满分
- 再做归一化：用学霸和学渣当尺子，把分数拉到统一的 0-1 刻度上

这样就能公平地比较不同模型在不同题目上的表现了。




### 3.5 聚合报告

`aggregate.py:build_aggregate` 对 `per_candidate` 列表做无 weight 算术平均，分组维度有三：

```python
{
  "n_predictions":   len(results),
  "n_scored_ok":     count(r.score is not None),
  "n_errors":        n_predictions - n_scored_ok,
  "mean_score":      mean(scores),                          # 原始分均值
  "mean_anchored":   mean(anchored.normalized),             # anchor 归一化均值
  "by_question_type": {
      qt: {"n": k, "mean": ..., "mean_anchored": ...}
      for qt in {简答题, 主观题, 决策题, 对比分析题, 数值提取题, 流程描述题, 数值关系题}
  },
  "by_difficulty": {
      d: {"n": k, "mean": ..., "mean_anchored": ...}
      for d in {简单, 中等, 困难}
  },
  "by_criterion_type": {
      ct: {"n_criteria": k, "met_rate": k_met / k}          # 注意：这是 criterion 维度，不是题目维度
      for ct in {factual_anchor, mechanism_explanation, ...}
  },
}
```

**关键约定**：

- `mean_score` / `mean_anchored` 都是**简单算术平均**，不按 weight 加权。各题之间默认等权。如果你的数据集有"重要题"加权需求，需在 aggregate 外层自己处理。
- `by_criterion_type` 用 `met_rate`（criterion 维度），不是 mean score。这让你能直接看到 "anti_hacking 的 met_rate" — 越低越好（陷阱越少被触发）。
- 空列表用 `_safe_mean` 兜底返回 `None`，避免 `mean([])` 抛 `StatisticsError`。

### 3.6 并发模型

`scorer.py:Scorer` 用 `asyncio.Semaphore` 控制并发：

```python
class Scorer:
    def __init__(self, rubrics, judge_client, concurrency=16, anchors=None):
        self.semaphore = asyncio.Semaphore(concurrency)

    async def _judge_criterion(self, question, candidate, criterion):
        async with self.semaphore:
            return await judge_one_async(self.judge_client, question, candidate, criterion)

    async def score_one(self, item_idx, candidate):
        tasks = [self._judge_criterion(rubric["question"], candidate, c)
                 for c in rubric["criteria"]]
        verdicts = await asyncio.gather(*tasks)
        ...

    async def score_batch(self, predictions):
        tasks = [self.score_one(p["item_idx"], p["answer"]) for p in predictions]
        raw = await asyncio.gather(*tasks, return_exceptions=True)
        ...
```

**两级并发**：

- `score_batch` 把所有候选回答 fire-and-gather
- 每个 `score_one` 内部把该题的所有 criterion 再 fire-and-gather
- Semaphore 在底层 `_judge_criterion` 收口，所以**总活跃 LLM call ≤ concurrency**

**单候选崩溃容错**：`score_batch` 用 `return_exceptions=True`，单题 judge 全崩了不会拖累其他题；崩溃的题在结果里写 `{score: None, error: "..."}`，被 aggregate 计入 `n_errors`。

**rate-limit 调优**：

```text
concurrency_safe ≈ (RPM / 60) × avg_latency_sec × 0.6
```

例如 600 RPM、平均 5s/call → `(600/60) × 5 × 0.6 ≈ 30`。默认 16 是保守值。

---

## 4. 设计取舍

下面列出几个**有意为之的非平凡选择**，方便贡献者理解"为什么这样"而不是"看起来怪"。

### 4.1 为什么 rubric 用 LLM 生成而不是人工写

人工写一份高质量 rubric 通常需要 30-60 分钟 × 领域专家。94 题需 50-100 人时。LLM 在有"题目 + 参考答案 + 源文档片段 + 题型规则 + few-shot"五重锚定下，**初稿可用率 ~80%**（剩余靠 Stage 2 拆分 + Stage 3 过滤兜底）。成本对比：

| | 人工 | LLM (gpt-5.4-mini) |
|---|---|---|
| 94 题成本 | 50-100 工时 | 2.5h 串行 + ~$0.5 |
| 一致性 | 因人而异 | 由 system prompt + 题型规则保证 |
| 可复现 | 否 | 是（seed=42 + 同模型 + 同源文档） |

代价是要接受一些"LLM 写得比人工糙"的 criterion，所以引入 Stage 3 的 ref/weak 双向校验过滤明显坏的那部分。

### 4.2 为什么 Stage 3 用 ref + weak 两边卡

只卡 ref（criterion 必须命中参考答案）不够：会留下"任何回答都能触发"的废话 criterion。只卡 weak（criterion 不能命中"我不知道"）也不够：会留下"和参考答案脱节"的幻觉 criterion。两边都卡 ≈ criterion 必须**能区分**参考答案和空白答案 — 这是单题层面"能区分能力"的最低要求。

类似设计在 HealthBench、Rubrics-as-Rewards 里都有出现，本仓库的差异是把它做成**生成期的硬过滤**（不通过的直接丢），而不是后处理的软评分。

### 4.3 为什么 weak answer 选 "我不知道。"

理论上 weak answer 应是"一个明显错的回答"。但"明显错"在不同题型下是不同的：

- 简答题的"明显错"是错误的事实
- 决策题的"明显错"是反向决策
- 数值提取题的"明显错"是错误的数字

构造跨题型通用的"明显错"很难，且容易引入新偏置（如某 judge 偏好长答案，错答案如果短反而被打 met=false）。"我不知道。" 是**信息量为零**的统一基线 —

- 对所有 fact / mechanism / numeric / decision / process criterion 都应当 met=false
- 对 anti_hacking pitfall 也应当不触发
- 长度极短，避免 judge 因长度产生偏置

实测下来这个基线 weak_score 在大多数 rubric 上 ≈ 0.0，符合预期。

### 4.4 为什么 anchor 归一化用 (score − weak) / (ref − weak) 而不是 score / ref

`score / ref` 只能把 score 缩到 `[0, 1]` 但不抹掉 judge 的**整体偏置**。例如 judge 偏松（所有回答都多打 0.1），三个候选都被加 0.1，相对排序不变但绝对分数失真。

`(score − weak) / (ref − weak)` 是**两点定标线性变换**：

- weak_score 对应 0（无效回答）
- ref_score 对应 1（参考答案）
- 候选回答在这条线上的相对位置，正是"它比无效回答好多少、距参考答案差多少"的归一化度量

类似 vBench / HELM 里的"normalized score" 设计，对 judge 偏置鲁棒。

### 4.5 为什么不让 judge 一次性看整份 rubric 打总分

让 judge 一次看 N 条 criterion + 候选，输出 N 个 bool —

- **prompt 长**：token 增加 ~3-5×，成本上升
- **判定漂移**：长 prompt 下 judge 容易在末尾几条 criterion 上潦草
- **不可定位**：单条 criterion 出错时无法独立重试

按 criterion 拆 + asyncio 并发后，**总耗时不增加**（受 concurrency 限制，与拆不拆同阶），但单条可重试 + reason 独立 + cost 略低。

### 4.6 为什么去重阈值是 0.9 而不是 0.85

实测两条 criterion 余弦相似度 ≈ 0.85-0.88 时常是"同义但不同侧重"，例如：

- "明确指出 USA 基于边界元法 (BEM)"
- "解释 USA 无需对水域进行有限元建模"

这两条 BGE-zh 相似度约 0.86，但分别检查了 USA 的"方法名"和"实现属性"。0.9 阈值倾向保留，0.85 会误并。

### 4.7 为什么 chunk_size = 400 字符而不是按句子 / 按段落切

按句子切：中文标点处理 + 跨句子的指代/连贯性丢失，BGE 检索效果下降。按段落切：mineru 转出来的 markdown 段落长度方差很大（几十到几千字），embedding 时短段噪声大、长段被截。

定长 400 字符 + overlap 100 在中文专业文档上**经验最优**（来自 LangChain / LlamaIndex 默认值的多次实验微调）。是粗糙但鲁棒的选择。

---

## 5. 参考文献

本仓库的策略综合自约 22 篇 rubric / LLM-as-judge 文献，主要影响：

| 文献 | 影响 |
|---|---|
| HealthBench (OpenAI, 2025) | 加权二值 checklist 的总体范式；ref/weak 双向锚定的灵感 |
| RubricRAG | RAG 锚定生成 rubric；page-first + semantic fallback 双轨检索 |
| Rubrics-as-Rewards (Anthropic, 2024) | rubric 评分作为 RL reward signal 的可行性论证 |
| OpenRubrics, AdaRubric | 题型相关的 rubric 结构 + 题型规则模板化 |
| Auto-Rubric | LLM 自动生成 + 多阶段精炼的工程化拆解 |
| RIFT | Pitfall / anti-reward-hacking criterion 的必要性 |
| RubricHub | 跨任务复用 rubric 的 schema 设计 |

完整列表与每篇的设计贡献见 [`docs/superpowers/specs/2026-05-22-cae-rubrics-design.md`](docs/superpowers/specs/2026-05-22-cae-rubrics-design.md) 和 [`docs/superpowers/specs/2026-05-22-cae-rubrics-scorer-design.md`](docs/superpowers/specs/2026-05-22-cae-rubrics-scorer-design.md)。
