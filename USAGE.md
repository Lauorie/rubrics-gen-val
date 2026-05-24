# rlm-rubrics 使用指南

> RAG 锚定的 rubric 生成 + LLM-as-judge 评估，面向中文专家问答。
> 英文 quickstart 见 [README.md](README.md)。

## 目录

- [1. 这个项目能做什么](#1-这个项目能做什么)
- [2. 30 分钟跑通](#2-30-分钟跑通)
- [3. 环境准备](#3-环境准备)
- [4. 数据格式](#4-数据格式)
- [5. 生成 Rubrics](#5-生成-rubrics)
- [6. 评估模型预测](#6-评估模型预测)
- [7. 移植到非 CAE 领域](#7-移植到非-cae-领域)
- [8. 调参与成本](#8-调参与成本)
- [9. 常见问题与排查](#9-常见问题与排查)
- [10. 项目结构索引](#10-项目结构索引)

## 1. 这个项目能做什么

给定一份**中文专家问答数据集**（题目 + 参考答案 + 题型 + 难易程度 + 来源文献），本仓库提供两件事：

1. **Rubric 生成**：为每道题自动生成一份加权 0/1 检查清单（rubric），每条 criterion 是一句可被 judge 一眼判定 yes/no 的原子陈述。生成时会从你给的源文档里检索相关段落作为锚点（RAG-grounded），避免凭空捏造事实。
2. **预测评估**：给定任意 QA 系统对这些题目的回答，按每条 criterion 调 LLM judge 打分，再按 `(正向得分 − 陷阱扣分) / 正向满分` 汇总，输出每题明细 + 按题型 / 难度 / criterion 类型分组的聚合报告。

**它适合什么场景**

- 你已经有一批领域专家精心写过参考答案的问答题，想用它给 RAG 系统 / 微调模型 / 大模型直接答题做细粒度评测，但用 BLEU/ROUGE 太粗、用人工打分太慢。
- 你想用 rubric 评分作为 RL 训练的 reward 信号（rubrics-as-rewards）。
- 你想做 LLM-as-judge 的可解释打分：每条 criterion 配一条 judge 给出的中文理由。

**它目前不能做什么**

- 不自动生成题目和参考答案，需要你先准备好。
- 不自带通用领域的源文档，本仓库带的是 CAE / 工程仿真领域的 8 份中文 + 英文文献（默认未提交到 git，需自备）。
- 不评估开放式生成质量（创造力、文体），rubric 评估的是**事实 + 机制 + 决策 + 流程 + 数值**这五类可验证内容。

**仓库自带的样例数据**

- 94 道中文 CAE / 工程仿真专家问答（`data/CAE-v2.0-1.json`），7 种题型混合：简答题、主观题、决策题、对比分析题、数值提取题、流程描述题、数值关系题。
- 已生成的 94 份 rubric（`rubrics/items/idx_*.json`，共 ~94 个文件）和聚合版（`data/CAE-v2.0-1-rubrics.json`）。
- 一份 2 道题的最小评估输入 / 输出（`tests/preds_sample.jsonl` / `data/eval_sample.json`），可用作 smoke test。

## 2. 30 分钟跑通

这一节用仓库自带的 2 题 smoke 输入跑通**评估**全流程，验证环境是否 OK。**不需要源文档、不需要重新生成 rubrics**（94 份已经在 `rubrics/items/` 里）。

```bash
# 1. 装依赖
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. 配 LLM
cp .env.example .env
# 编辑 .env，至少填好 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL
# 默认 LLM_BASE_URL=https://aiberm.com/v1，LLM_MODEL=openai/gpt-5.4-mini

# 3. 跑一次 smoke 评估
python run/04_score_predictions.py \
    --predictions tests/preds_sample.jsonl \
    --out data/eval_smoke.json \
    --concurrency 8

# 4. 看聚合分
jq '.aggregate' data/eval_smoke.json
```

预期输出（数字会略有差异，量级一致即可）：

```json
{
  "n_predictions": 2,
  "n_scored_ok": 2,
  "n_errors": 0,
  "mean_score": 0.86,
  "mean_anchored": 0.86,
  "by_question_type": { "主观题": { "n": 1, "mean": 0.84 }, "数值提取题": { "n": 1, "mean": 0.89 } }
}
```

如果跑通了，恭喜，环境 OK。接下来你可以：

- 想**生成**新的 rubric → 跳到 §5（需要源文档 + embedding 模型）。
- 想**评估**自己的模型 → 跳到 §6（只需要把预测整理成 JSONL）。
- 想**换到非 CAE 数据** → 跳到 §7。

## 3. 环境准备

### 3.1 Python 与依赖

- **Python 3.11+**（`pyproject.toml` 强制）
- 关键依赖：`pydantic>=2.6`、`httpx`、`tenacity`、`python-dotenv`、`sentence-transformers`、`faiss-cpu`、`numpy`、`regex`、`tqdm`
- 开发依赖（可选）：`pytest`、`pytest-asyncio`、`pytest-mock`、`ruff`、`mypy`

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3.2 .env 配置

复制 `.env.example` 为 `.env`，填入 LLM 凭据。仓库默认走 OpenAI 兼容协议，任何提供 `/v1/chat/completions` 的服务（OpenAI、Azure、本地 vLLM、aiberm、dubrify、One-API、LiteLLM 代理…）都可以接：

```bash
LLM_API_KEY=sk-xxxx                              # 必填
LLM_BASE_URL=https://aiberm.com/v1               # 必填，含 /v1
LLM_MODEL=openai/gpt-5.4-mini                    # 必填，模型 ID 由服务方约定
EMBEDDING_MODEL=BAAI/bge-base-zh-v1.5            # 可选，默认值即此
```

`.env.example` 里还有 `LLM_FALLBACK_*` 三项，目前在 `LLMClient` 里**未启用**（保留扩展位），填不填都不影响。

### 3.3 Embedding 模型

`BAAI/bge-base-zh-v1.5` ~400MB，首次 `sentence-transformers` 调用时自动从 HuggingFace 下载。如果网络受限：

- 离线方式：先在外网机器 `huggingface-cli download BAAI/bge-base-zh-v1.5`，把权重拷到 `~/.cache/huggingface/hub/`
- 换模型：在 `.env` 设 `EMBEDDING_MODEL=你的-模型-id`，注意 `src/rubrics/index.py` 里写死了 BGE 的中文 query 前缀 `为这个句子生成表示以用于检索相关文章：`，换非 BGE 模型时需要同步改这个前缀

### 3.4 验证

```bash
pytest tests/rubrics/ -q
```

预期：~57 个测试全过，少数会因为依赖外网 LLM 被 skip 也属正常（看输出里的 `s` 数）。

### 3.5 项目根目录约定

代码用了一些相对路径默认值（`data/`、`rubrics/items/`、`CAE-MDs/`），所有命令请**从仓库根目录运行**，例如 `python run/01_build_index.py` 而不是 `cd run && python 01_build_index.py`。

## 4. 数据格式

本仓库总共涉及 5 种文件格式。你只需要关心**输入**那两种：源数据 JSON 和预测 JSONL；其余 3 种是中间产物。

### 4.1 源数据：`data/CAE-v2.0-1.json`（输入 ①）

JSON 数组，每条是一道题：

```json
{
  "编号": "1",
  "问题描述": "在流固耦合（FSI）仿真中，\"附加质量效应\"为何会导致数值不稳定？",
  "参考答案": "流体与结构密度接近：……（多个要点用中文标点分隔）",
  "题型": "主观题",
  "难易程度": "困难",
  "难度场景": "单文档多段落",
  "语言": "中文",
  "来源": "Benson教材, 第4章, 第166-189页"
}
```

字段说明：

| 字段 | 必填 | 取值 | 说明 |
|---|---|---|---|
| `编号` | 是 | 字符串 | 显示用题号，可以重复（评估时用数组下标 `item_idx` 做唯一键） |
| `问题描述` | 是 | 字符串 | 题面 |
| `参考答案` | 是 | 字符串 | 用于生成 rubric + 计算 ref anchor 分 |
| `题型` | 是 | 7 选 1 | 见下表 |
| `难易程度` | 是 | `简单`/`中等`/`困难` | 用于聚合报告分组 |
| `难度场景` | 否 | 字符串 | 元数据，会原样写入 rubric 文件 |
| `语言` | 否 | 字符串 | 未参与逻辑 |
| `来源` | 是 | 字符串 | RAG 的关键 — 见 §5.3 来源解析 |

**7 种题型**（不能用其它值，否则会找不到 `templates/type_rules/*.txt`）：

`简答题` `主观题` `决策题` `对比分析题` `数值提取题` `流程描述题` `数值关系题`

### 4.2 源文档：`CAE-MDs/*.md`（输入 ②，仅生成 rubric 时需要）

8 份 markdown 文件，用 mineru 从 PDF 转换而来。关键约定：

- **页码靠图片 URL 锚点**：mineru 在每页第一张图片插入形如 `page_000_block_001` 的 URL，`src/rubrics/chunker.py` 用正则 `page_(\d+)_block_\d+` 抽取，**1-indexed 存储**（即 URL 里的 `page_000` 在内部记为第 1 页）。
- **文件名 → 短别名**：`source_parser.py` 里 `DOC_ALIASES` 字典硬编码了 11 个别名（如 `Benson` → `Arbitrary_Lagrangian-Eulerian_..._Benson.md`），`来源` 字段里用别名，文件名用全称。
- 仓库不带这 8 份 md，需自备。文件不存在时，rubric 生成会退化为纯 semantic fallback 检索（仍能跑，只是检索质量下降）。

### 4.3 预测：`*.jsonl`（输入 ③，仅评估时需要）

每行一个 JSON，至少两个字段：

```jsonl
{"item_idx": 0, "answer": "在流固耦合中……"}
{"item_idx": 3, "answer": "JWL 方程的核心参数包括 A 和 B……"}
```

字段说明：

| 字段 | 必填 | 说明 |
|---|---|---|
| `item_idx` | 是 | 整数，与源数据 JSON 数组下标一一对应（从 0 起）。用 `item_idx` 而非 `编号`，因为 `编号` 有重复 |
| `answer` | 是 | 模型给出的回答字符串 |
| 其它 | 否 | 评估器会忽略 |

样例见 `tests/preds_sample.jsonl`。

### 4.4 中间产物：`data/cae_chunk_index.pkl`

`run/01_build_index.py` 输出的 pickle：包含 chunks（每条带 `doc_slug` + 页码范围）和它们的 embedding 矩阵 + 模型名。生成 rubric 时被 `run/02_generate_rubrics.py` 反序列化复用。

### 4.5 中间产物：`rubrics/items/idx_NNN.json` + `data/CAE-v2.0-1-rubrics.json`

每道题一个 `idx_NNN.json`（`NNN` 即 `item_idx` 三位零填充），同时聚合为一个 `CAE-v2.0-1-rubrics.json`。结构对应 `src/rubrics/schema.py:RubricItem`：

```json
{
  "question_id": "1",
  "question": "...",
  "reference_answer": "...",
  "question_type": "主观题",
  "difficulty": "困难",
  "scenario": "...",
  "source": "Benson教材, 第4章, 第166-189页",
  "source_grounding": {
    "parsed_docs": ["Arbitrary_Lagrangian-Eulerian_..._Benson"],
    "pages": [166, 189],
    "retrieved_chunk_ids": ["...:p180-p180:c1097", "..."],
    "ground_status": "page_specific"
  },
  "criteria": [
    {
      "id": "c1",
      "text": "指出流体密度与结构密度接近……",
      "category": "Essential",
      "weight": 5,
      "sign": "positive",
      "criterion_type": "factual_anchor",
      "evidence_quote": null
    }
  ],
  "rubric_metadata": { "generation_model": "...", "n_criteria_final": 12 },
  "item_idx": 0
}
```

字段语义：

- **category** ∈ {`Essential`, `Important`, `Optional`, `Pitfall`}：决定默认权重（5/3/1/3-5）和聚合报告分组
- **sign** ∈ {`positive`, `negative`}：Pitfall 必须 `negative`，其余必须 `positive`（pydantic 模型自动校验）
- **weight** ∈ `[1, 8]`：得分公式里的乘数
- **criterion_type** 7 选 1：`factual_anchor` / `mechanism_explanation` / `numeric_precision` / `decision_logic` / `comparative_balance` / `process_completeness` / `anti_hacking`（`anti_hacking` 只能配 Pitfall）
- **ground_status** 3 选 1：`page_specific`（按页码命中）/ `doc_only`（命中文档但页码不准）/ `fallback_semantic`（来源解析失败，纯语义检索）

### 4.6 评估输出：`data/eval_*.json`

`run/04_score_predictions.py` 的输出，两段：

```json
{
  "per_candidate": [
    {
      "item_idx": 0,
      "score": 0.84,
      "score_anchored": { "ref_score": 1.0, "weak_score": 0.0, "normalized": 0.84 },
      "breakdown": [ { "id": "c1", "met": true, "reason": "...", "contribution": 5 } ]
    }
  ],
  "aggregate": {
    "n_predictions": 2, "n_scored_ok": 2, "mean_score": 0.86,
    "by_question_type": { },
    "by_difficulty": { },
    "by_criterion_type": { }
  }
}
```

## 5. 生成 Rubrics

### 5.1 流程总览

```text
data/CAE-v2.0-1.json   ──┐
                          ▼
CAE-MDs/*.md ──→ chunk_index.pkl ──→ retrieve_context ──→ 3 阶段生成 ──→ rubrics/items/idx_NNN.json
```

三阶段：

1. **Stage 1 — 初稿**（`generator.py`）：把题目 + 参考答案 + 检索到的源文档 chunks + 题型规则 + 3 个 few-shot 示例塞进 prompt，让 LLM 一次性吐 8-12 条 criterion。
2. **Stage 2 — 精炼**（`refiner.py`）：拆复合断言（"X 且 Y" → 两条），按 embedding 相似度（阈值 0.9）去重，注入两条默认 anti-hacking pitfall（套话开场白 + 冗长铺垫）。
3. **Stage 3 — 失准过滤**（`misalignment_filter.py`）：对每条正向 criterion，用 judge 跑两次：在**参考答案**上必须 met=true（否则说明 criterion 写错了），在**"我不知道"**上必须 met=false（否则说明 criterion 太松、能被任何回答触发）。Pitfall 不过滤，靠 template 保证质量。

### 5.2 三步命令

```bash
# 步骤 1：embedding 8 份源 markdown，建索引（~1-2 分钟，BGE-zh 模型首次会下载 ~400MB）
python run/01_build_index.py \
    --mds-dir CAE-MDs \
    --out data/cae_chunk_index.pkl \
    --chunk-size 400 \
    --overlap 100

# 步骤 2：跑生成（94 题串行 ~2.5 小时，gpt-5.4-mini 大约 $0.5）
python run/02_generate_rubrics.py \
    --data data/CAE-v2.0-1.json \
    --index data/cae_chunk_index.pkl \
    --items-dir rubrics/items \
    --out data/CAE-v2.0-1-rubrics.json \
    --resume    # 强烈推荐，断点续跑

# 步骤 3：质检（秒级）
python run/03_validate.py \
    --rubrics data/CAE-v2.0-1-rubrics.json \
    --source-data data/CAE-v2.0-1.json
```

`03_validate.py` 输出形如：

```text
Rubrics: 94 / 94 items
criteria/item: min=5 max=12 mean=8.9
By type: {'主观题': 30, '简答题': 28, ...}
items with <2 Pitfall: 0 → []
ground_status: {'page_specific': 68, 'doc_only': 16, 'fallback_semantic': 10}
dropped/item: mean=0.5 max=4
```

### 5.3 来源字段怎么被解析

`来源` 字段决定 RAG 检索范围。`source_parser.py` 能识别这些写法：

| 写法 | 解析结果 |
|---|---|
| `Benson教材, 第4章, 第166-189页` | doc=Benson, pages=(166,189) |
| `贾宪振博士论文 第17页; ThyssenKrupp论文 第5页` | 两条 ref（分号 / 逗号都行） |
| `ThyssenKrupp论文, 第462, 470, 475页` | doc=ThyssenKrupp, pages=(462,462)（多页列表只取第一段） |
| `贾宪振博士论文，第12、89、90页` | doc=贾宪振, pages=(12,12)（中文逗号 / 顿号同样） |
| `第3章，第38页` | doc 默认推断为 Benson |

合法别名见 `src/rubrics/source_parser.py:DOC_ALIASES`（11 个）。`Souli教材` 这种当前没有 md 文件的会被识别但 retriever 拿不到 chunks，落到 semantic fallback。

### 5.4 常用参数

`02_generate_rubrics.py`：

| 参数 | 默认 | 说明 |
|---|---|---|
| `--limit N` | 无 | 只跑前 N 题，debug 用 |
| `--dry-run` | 关 | 只跑 1 题然后退出 |
| `--resume` | 关 | 跳过 `items-dir` 里已存在的 `idx_NNN.json` |
| `--seed` | 42 | 影响 Python / numpy / hash 种子 |

`01_build_index.py`：

| 参数 | 默认 | 说明 |
|---|---|---|
| `--chunk-size` | 400 | 字符数（≈中文 token 数），别小于 100 |
| `--overlap` | 100 | 相邻 chunk 重叠字符数 |
| `--model` | `BAAI/bge-base-zh-v1.5` | sentence-transformers 模型 ID |

### 5.5 中断了怎么办

`02_generate_rubrics.py` 是按题循环、单题失败 `try/except` 直接跳过（错误打到日志），所以崩了重跑加 `--resume` 即可：

```bash
python run/02_generate_rubrics.py --resume
```

它会扫 `rubrics/items/` 跳过已有的 `idx_NNN.json`，跑完后从所有 per-item 文件重新聚合 `CAE-v2.0-1-rubrics.json`，所以前一次的成果不丢。

## 6. 评估模型预测

_TBD_

## 7. 移植到非 CAE 领域

_TBD_

## 8. 调参与成本

_TBD_

## 9. 常见问题与排查

_TBD_

## 10. 项目结构索引

_TBD_
