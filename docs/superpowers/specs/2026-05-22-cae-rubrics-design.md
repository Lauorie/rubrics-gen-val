# CAE-v2.0-1 Rubrics Generation — Design Spec

**Status:** Approved 2026-05-22
**Owner:** juli
**Related:** RLM project (RL training on `evidence-multi-rlm-sft-simplified-4b`, target > 0.597)

---

## 1. Goal

为 `data/CAE-v2.0-1.json`（94 道中文 CAE 领域专家 QA）生成高质量、双用途（RL reward + eval breakdown）rubric 集合，输出到 `data/CAE-v2.0-1-rubrics.json` 与 `rubrics/items/<编号>.json`。

策略名称：**GroundedRubric-CAE**——一个 RAG-grounded、题型差异化、三阶段生成 + 两阶段过滤的 pipeline。

## 2. Background & Literature Synthesis

文献调研（98 篇 rubric 论文中重点研读 22 篇）在四件事上高度一致：

1. **形式**：weighted binary checklist + signed criteria（HealthBench / RaR / OpenRubrics / ProfBench / PRBench）。Likert 在 RL 里不稳定；binary + per-criterion 权重是工业标准。每题 8-15 条。
2. **生成**：RAG-grounded + 参考答案是专业领域 QA 的最强 baseline（RubricRAG: ρ 0.426 → 0.545；RubricHub principle-guided +2.9 pts/stage）。单 pass 不够，至少需要 dedup + misalignment filter 两道闸。
3. **判分**：`score = Σ(w_i·met_i for w_i>0) / Σ|w_i for w_i>0| - penalty`，clip [0,1]，judge T=0，response 顺序双向打分。
4. **anti-reward-hacking**：必须在 rubric 中显式加入 negative criteria（pitfall），覆盖 opening-praise / verbosity / format-only inflation（Rubicon / RaR / PAPO 都强调）。

关键参考：HealthBench, Rubrics-as-Rewards, OpenRubrics, RubricRAG, AdaRubric, CARMO, Rethinking-Rubric-Generation, RIFT, RubricHub, Auto-Rubric, Checklists-Better-Than-RM, Rubicon, PAPO.

## 3. Inputs

- **题目数据**：`data/CAE-v2.0-1.json`（94 items；字段：`编号`/`问题描述`/`参考答案`/`难度场景`/`语言`/`来源`/`题型`/`难易程度`）
- **源文档**：`CAE-MDs/`（8 个 markdown，对应 `CAE-PDFs/` 中 PDF 转出）
- **题型分布**：简答题 48 / 主观题 20 / 决策题 18 / 对比分析题 3 / 数值提取题 2 / 流程描述题 2 / 数值关系题 1
- **生成 LLM**：`openai/gpt-5.4-mini`（aiberm.com 与 dubrify.com 两个 endpoint 备选）
- **embedding**：BGE-zh-v1.5（本地，免费）

## 4. Architecture (GroundedRubric-CAE)

```
INPUT: CAE-v2.0-1.json (94) + CAE-MDs (8 docs)
   │
   ▼
Stage 0  源文档索引
   - chunk 8 个 MD：400 token，overlap 100
   - 用 BGE-zh-v1.5 建 embedding 索引
   - `来源` 字段解析器：论文名 + 页码 → chunk ids
   │
   ▼  per item (94 次)
Stage 1  初稿生成
   prompt 拼装 = Q + 参考答案 + 题型 template + RAG context(top-k=3) + 3 个 in-context exemplar
   输出：8-15 条 weighted-binary criteria（structured JSON output）
   model = gpt-5.4-mini, T=0.3
   │
   ▼
Stage 2  自审 & 精修
   - atomicity check：拆"AND"复合 criterion 成多条
   - dedup：BGE-zh 余弦相似度 > 0.9 合并
   - 强制注入 ≥2 个 pitfall (anti-hacking)
   │
   ▼
Stage 3  misalignment 过滤
   - 对每条 criterion，judge 对参考答案打分（应 met=1）、对弱合成答案"我不知道"打分（应 met=0）
   - 任一方向不符 → 丢弃该 criterion
   │
   ▼
OUTPUT: data/CAE-v2.0-1-rubrics.json (flat list)
       + rubrics/items/001.json ... 094.json
       + data/rubrics-meta.json (生成日志)
```

不引入 multi-model ensemble (Stage 4) 与 recursive decomposition (Stage 5)：在 94 道题的小规模下，这两步的 ROI 不如前两道闸（文献 +1-2 pts vs +10-15 pts 合计）。可作为未来 v1.1 的可选扩展。

## 5. JSON Schema

### 5.1 Per-item rubric

```json
{
  "question_id": "1",
  "question": "在流固耦合（FSI）仿真中，"附加质量效应"为何会导致数值不稳定？",
  "reference_answer": "...(从原 JSON 复制)...",
  "question_type": "主观题",
  "difficulty": "困难",
  "scenario": "单文档多段落",
  "source": "Benson教材, 第4章, 第166-189页",

  "source_grounding": {
    "parsed_docs": ["Arbitrary_Lagrangian-Eulerian_..._Benson"],
    "pages": [166, 189],
    "retrieved_chunk_ids": ["benson:p166-p180:c3", "benson:p180-p189:c1"],
    "ground_status": "page_specific"
  },

  "criteria": [
    {
      "id": "c1",
      "text": "明确指出当流体密度与结构密度同数量级时，隐式分区算法的迭代过程极易不收敛",
      "category": "Essential",
      "weight": 5,
      "sign": "positive",
      "criterion_type": "factual_anchor",
      "evidence_quote": "(可选，源自 retrieved chunk)"
    },
    {
      "id": "c8",
      "text": "回答以套话/开场白/元评论开头而无实质内容",
      "category": "Pitfall",
      "weight": 4,
      "sign": "negative",
      "criterion_type": "anti_hacking"
    }
  ],

  "rubric_metadata": {
    "generation_model": "openai/gpt-5.4-mini",
    "generation_passes": 3,
    "n_criteria_initial": 12,
    "n_criteria_final": 10,
    "n_dropped_misaligned": 2,
    "ref_answer_self_score": 0.94,
    "weak_answer_self_score": 0.05,
    "generated_at": "2026-05-22T...",
    "schema_version": "1.0"
  }
}
```

### 5.2 Category → weight 默认映射

| Category | Weight | Sign |
|---|---|---|
| Essential | 5 | positive |
| Important | 3 | positive |
| Optional | 1 | positive |
| Pitfall | 3-5 | negative |

生成器可在 ±1 范围内微调 weight（写入 prompt 允许约束）。

### 5.3 Criterion type 词表（限定 7 个）

| criterion_type | 含义 |
|---|---|
| `factual_anchor` | 必须正确陈述的具体事实/术语/数据 |
| `mechanism_explanation` | 解释某物理/算法机制的因果链 |
| `numeric_precision` | 数值/单位/精度匹配 |
| `decision_logic` | 选择正确选项 + 给出逻辑论据 |
| `comparative_balance` | 比较多个对象的同异、不偏废 |
| `process_completeness` | 流程步骤齐备 + 顺序正确 |
| `anti_hacking` | 反 reward-hacking 的负向规则 |

## 6. Scoring Formula

```python
positive_score = sum(w_i * met_i for c_i if c_i.sign == "positive")
positive_max   = sum(c_i.weight   for c_i if c_i.sign == "positive")
penalty        = sum(w_i * met_i for c_i if c_i.sign == "negative")
raw            = (positive_score - penalty) / positive_max
final          = max(0.0, min(1.0, raw))
```

- `final ∈ [0,1]` → RL reward
- `criteria[].met_i` 全列表 → eval breakdown

## 7. 题型 × Criterion 类别矩阵

每 cell = 该 category 在该题型 rubric 中的**条目数（min-max） / 总权重占比 (positive 部分)**。

| 题型 (#items) | factual_anchor | mechanism_explanation | numeric_precision | decision_logic | comparative_balance | process_completeness | anti_hacking | 总条目 |
|---|---|---|---|---|---|---|---|---|
| **简答题 (48)** | 3-5 / 50% | 1-2 / 20% | – | – | – | – | 2 / 15% (neg) | 8-10 |
| **主观题 (20)** | 2-3 / 25% | 3-4 / 40% | – | – | 0-1 / 10% | – | 2 / 15% (neg) | 10-12 |
| **决策题 (18)** | 1-2 / 15% | 1-2 / 15% | – | 3-4 / 50% | 1 / 10% | – | 2 / 15% (neg) | 8-11 |
| **对比分析题 (3)** | 1-2 / 15% | 1 / 10% | – | – | 3-4 / 55% | – | 2 / 15% (neg) | 8-10 |
| **数值提取题 (2)** | 1 / 10% | 0-1 | 3-4 / 65% | – | – | – | 2 / 15% (neg) | 6-8 |
| **流程描述题 (2)** | 1 / 10% | 1 / 10% | – | – | – | 3-4 / 55% | 2 / 15% (neg) | 7-9 |
| **数值关系题 (1)** | 1 / 10% | 1 / 15% | 2-3 / 50% | – | – | – | 2 / 15% (neg) | 6-8 |

**默认 anti_hacking 模板（写死，每题都有）：**

1. *"回答以套话/开场白/元评论开头而无实质内容"* — weight 4
2. *"回答篇幅冗长，包含大量与问题无关的背景铺垫或重复"* — weight 3

生成器可追加题型相关 pitfall（如决策题的 "给出多个并列选项而不做选择"）。

## 8. Source Grounding (RubricRAG-style)

**Chunking**：8 个 MD 文件按 400 token / overlap 100 切分，预计 200–400 chunks 总数。chunk id 格式：`<doc_slug>:p<start>-p<end>:c<i>`。

**`来源` 字段解析器**（regex + 规则）：
- "Benson教材, 第4章, 第166-189页" → `{doc: "Arbitrary_Lagrangian-Eulerian...Benson", pages: [166, 189]}`
- "贾宪振博士论文, 第85-88页" → `{doc: "PhD 基于通用程序的水下爆炸...", pages: [85, 88]}`
- "ThyssenKrupp论文 第5页" → `{doc: "oezarmut_thyssenkrupp...", pages: [5, 5]}`
- 多源（用 `;` 分隔）→ 多组 `(doc, pages)`
- 未识别 / 无页码 → `ground_status: "fallback_semantic"`，改用问题文本对全语料做 top-k=3 检索

**Retrieval**：
- 优先：从被解析出的 `(doc, pages)` 内 chunks 中取 top-k=3（按 question embedding 相似度）
- Fallback：BGE-zh 全语料 top-k=3
- chunk 内容拼成 `domain_context` 注入 generator prompt

## 9. Few-shot Exemplars (gold rubrics)

人工预写 **3 条 gold rubric** 作为 in-context exemplar，覆盖：

- 1 条简答题（最常见，48 道）
- 1 条决策题（结构最特别）
- 1 条数值提取题（数值精度规则需示范）

存放于 `rubrics/exemplars/gold_rubrics.json`，每条同 §5.1 schema。生成时按题型动态选取 1-3 条作为 prompt 内 few-shot。

## 10. Prompt Templates

### 10.1 Stage 1 Generator Prompt（伪 prompt，最终在代码里组装）

```
SYSTEM:
你是一位 CAE / 工程仿真领域的高级评审专家。你的任务是为一道专家问答题
生成一份高质量的 rubric，用于（a）RL 训练的 reward 信号 与（b）模型评测
的细粒度打分。

RUBRIC 要求：
1. 输出 weighted binary checklist：每条 criterion 是一条独立、原子化、可被
   judge 在阅读候选答案后 yes/no 判定的陈述。
2. criterion 数量：见 [题型规则]。
3. category ∈ {Essential, Important, Optional, Pitfall}，sign ∈ {positive, negative}。
   Pitfall 的 sign 必须为 negative。
4. weight：Essential=5, Important=3, Optional=1, Pitfall=3-5（你可以 ±1 微调）。
5. criterion_type 必须从如下 7 种中选择：[列表]。
6. 至少包含 [题型规则要求的最小数量] 条 Pitfall。
7. 严禁出现「good」「clear」「comprehensive」等无锚点形容词；必须引用具体的
   术语、参数名、机制、数值或步骤。
8. 输出 JSON，schema 见下方。

USER:
[Q] {question}
[参考答案] {reference_answer}
[题型] {question_type}（请遵循该题型的 rubric 结构）
[难易程度] {difficulty}
[来源] {source}
[领域上下文 — 来自源文档]
{retrieved_chunks}
[few-shot 示例]
{exemplars}

[题型规则] {rule_for_this_type}

请直接输出 JSON，不要任何前后缀。
```

### 10.2 Stage 3 Misalignment Judge Prompt

```
SYSTEM:
你是 CAE 领域的严格 judge。给定一道题、一个候选回答、一条 rubric criterion，
判断该候选回答是否满足该 criterion。只输出 JSON: {"met": true/false, "reason": "..."}。

USER:
[题目] {question}
[候选回答] {candidate}
[criterion] {criterion_text}
[criterion 类型] {criterion_type}
```

对每条 criterion 都用两个 candidate 调用：
- candidate_A = 参考答案 → 期望 `met=true`
- candidate_B = `"我不知道。"` → 期望 `met=false`（对 Pitfall criterion 应为 `met=false`，因为太短并非套话）

**判定**：
- positive criterion：A 必须 met=true 且 B 必须 met=false；否则丢弃
- Pitfall criterion：**不参与 misalignment filter**。Pitfalls 主要是 template-injected 的 anti-hacking 规则（见 §7 末尾的两条默认 pitfall），生成器追加的 pitfall 信任 generator。Pitfall 的质量在 §16 success criteria 中通过"每题 ≥ 2 条 Pitfall"硬性保证。

为减少 cost，本步骤对**所有 positive criteria**都做 misalignment check（每题平均 8 条 positive × 2 calls = 16 calls × 94 items ≈ 1500 calls，仍在 $0.15 内）。这是保证 rubric 质量最关键的一步，不应削减。

## 11. Implementation Layout

```
src/rubrics/
├── __init__.py
├── chunker.py             # MD chunking + chunk id
├── index.py               # BGE-zh embedding index (in-memory FAISS)
├── source_parser.py       # 「来源」字段 → (doc, pages)
├── retriever.py           # page-filtered + semantic fallback
├── templates/
│   ├── system_prompt.txt
│   ├── type_rules/
│   │   ├── 简答题.txt
│   │   ├── 主观题.txt
│   │   ├── 决策题.txt
│   │   ├── 对比分析题.txt
│   │   ├── 数值提取题.txt
│   │   ├── 流程描述题.txt
│   │   └── 数值关系题.txt
│   └── exemplars/
│       └── gold_rubrics.json
├── llm_client.py          # aiberm/dubrify endpoint wrapper, structured output
├── generator.py           # Stage 1
├── refiner.py             # Stage 2 (atomicity + dedup + pitfall injection)
├── misalignment_filter.py # Stage 3
├── scoring.py             # scoring formula + judge wrapper (供后续使用)
└── schema.py              # pydantic models

run/
├── 01_build_index.py      # 一次性建索引
├── 02_generate_rubrics.py # 主入口
└── 03_validate.py         # 跑 misalignment + 输出报告

tests/rubrics/
├── test_chunker.py
├── test_source_parser.py
├── test_retriever.py
├── test_schema.py
├── test_scoring.py
└── test_pipeline_smoke.py  # 1 条 item end-to-end
```

## 12. Reproducibility

- `set_seed(42)` 在所有 LLM call / sampling 前调用（虽然 T=0.3 仍有少量噪声，依赖 endpoint）
- 所有 LLM call 记录 `(prompt_hash, response, model, timestamp)` 到 `data/rubrics-meta.json`
- 记录 `pip freeze`、`git rev-parse HEAD`、retrieval index hash 到 `rubrics_metadata`
- `--dry-run` 模式只跑 1 条 item，便于调试
- 失败重试：每个 LLM call 最多重试 3 次（exp backoff）

## 13. Security

- API key 走 `os.environ["LLM_API_KEY"]`，**不写死**在代码或 config
- 提供 `.env.example` 但不提交 `.env`
- 8 个源文档已在仓内，无新增外部依赖

## 14. Open Decisions (已确认默认值)

| ID | Decision | 默认 |
|---|---|---|
| D1 | Embedding model | BGE-zh-v1.5（本地、离线、免费） |
| D2 | Stage 3 judge 是否换模型 | 同模型（gpt-5.4-mini），省 cost |
| D3 | Few-shot exemplar 数量 | 人工预写 3 条 gold rubric |
| D4 | 双语 criterion | 仅中文 |
| D5 | Multi-model ensemble | 不做，作为 v1.1 |
| D6 | Recursive decomposition | 不做，作为 v1.1 |

## 15. Cost & Time Estimate

| Stage | per-item tokens (in/out) | total cost | wall time |
|---|---|---|---|
| 0 build index | – | $0 (本地) | 1 min |
| 1 初稿 | ~1500 / ~800 | ~$0.09 | 5-8 min |
| 2 精修 | ~600 / ~200 | ~$0.04 | 2 min |
| 3 misalignment | ~500 / ~80 × ~1500 calls (positive criteria 100%) | ~$0.15 | 8-10 min |
| **Total** | | **~$0.3-0.5** | **15-20 min** |

## 16. Success Criteria

- **覆盖**：94/94 items 各自有 final rubric（生成失败可重试，无 silent skip）
- **schema 一致性**：所有输出通过 pydantic 校验
- **判分自洽**：参考答案在自己 rubric 上的 `ref_answer_self_score ≥ 0.85`（均值），弱答案 `≤ 0.20`
- **anti-hacking**：每个 item ≥ 2 条 Pitfall criterion
- **criterion 数量**：每个 item 6-15 条，平均 10
- **可重跑**：固定 seed + 索引 hash 下，第二次运行差异 ≤ 5%

## 17. Non-Goals

- 不训练 reward model
- 不跑 RL 训练（这是下游任务）
- 不评测现有模型在 rubrics 上的表现（后续单独任务）
- 不为 `data/merge.json`（4.8 MB 大文件）生成 rubrics — 仅 CAE-v2.0-1
