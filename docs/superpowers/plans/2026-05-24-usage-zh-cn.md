# 中文使用指南（USAGE.md）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `rlm-rubrics` 开源仓库编写一份完整的中文使用指南 `USAGE.md`，覆盖安装、数据格式、Rubric 生成、模型评估、移植到非 CAE 领域、常见问题，让一个对 CAE 领域和本仓库都零认知的用户能在 30 分钟内跑通端到端流程。

**Architecture:** 单文件 `USAGE.md` 放在仓库根目录；从 `README.md` 现有英文 quickstart 链接过去（README 不重写，只在顶部加一行 “👉 完整中文教程见 [USAGE.md](USAGE.md)”）。文档结构按用户旅程组织：先讲它能做什么 → 装起来 → 数据长什么样 → 怎么生成 rubrics → 怎么评估模型 → 怎么换成自己的数据 → 出问题怎么排查。所有命令都基于现有 `run/01..04_*.py` 脚本和 `data/`、`rubrics/items/`、`CAE-MDs/` 目录约定，不引入新代码。

**Tech Stack:** Markdown（GitHub Flavored），不依赖任何渲染插件。代码块标 `bash` / `python` / `json` / `text` 即可。

---

## File Structure

- Create: `USAGE.md`（仓库根目录）— 主要交付物，中文，~600-900 行
- Modify: `README.md` — 在 `## What's here` 上方插入 1 行中文链接，其余不动
- 不创建：图片、子文档、新代码

## 写作原则（每个任务都要遵守）

1. **每条命令都是真命令**：能直接复制粘贴进 bash 跑，路径 / 参数 / 文件名都对得上仓库现状。
2. **每段示例都是真示例**：JSON / JSONL / 评分输出片段必须从 `data/CAE-v2.0-1.json`、`rubrics/items/idx_000.json`、`data/eval_sample.json`、`tests/preds_sample.jsonl` 这些真实文件里截取或简化，禁止编造字段名。
3. **解释 + 命令 + 输出三段式**：先两三句话解释这一步在做什么、为什么；再给命令；再给一段缩略的预期输出（让用户能对照）。
4. **零 CAE 假设**：解释 `Benson`、`HJC`、`流固耦合` 这类术语时不展开，但要给一句话定位（"这是流体-固体相互作用，本仓库的 8 份源文档涉及这个主题"），让非 CAE 读者不被吓退。
5. **不夸张、不灌水**：避免 “革命性”、“强大”、“无与伦比” 之类词，避免英文 em-dash `—`，避免 “overall / comprehensive / robust” 这类无锚点形容词的中译。
6. **不写 TODO / 待补充**：每一段都是成品。

---

## Task 1: 大纲落定 + README 跳转锚点

**Files:**
- Create: `USAGE.md`（先放骨架）
- Modify: `README.md:5`（在 `## What's here` 行前插入一行）

- [ ] **Step 1: 写 `USAGE.md` 顶层大纲（仅 H1/H2，正文留空）**

把下面的大纲一次性写进 `USAGE.md`，之后的任务往里填正文：

```markdown
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
## 2. 30 分钟跑通
## 3. 环境准备
## 4. 数据格式
## 5. 生成 Rubrics
## 6. 评估模型预测
## 7. 移植到非 CAE 领域
## 8. 调参与成本
## 9. 常见问题与排查
## 10. 项目结构索引
```

- [ ] **Step 2: 在 `README.md` 顶部加一行中文跳转**

在 `README.md` 当前第 5 行（`## What's here` 之前）插入一行：

```markdown
> 中文完整教程见 [`USAGE.md`](USAGE.md)。
```

确认插入后该位置上下文形如：
```
RAG-grounded rubric **generation** + LLM-judge **evaluation** for ...

> 中文完整教程见 [`USAGE.md`](USAGE.md)。

## What's here
```

- [ ] **Step 3: 提交**

```bash
git add USAGE.md README.md
git commit -m "docs(zh): scaffold USAGE.md outline + README link"
```

---

## Task 2: §1 这个项目能做什么

**Files:**
- Modify: `USAGE.md`（替换 `## 1. 这个项目能做什么` 占位符）

- [ ] **Step 1: 写正文**

把 `## 1. 这个项目能做什么` 替换为：

```markdown
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
```

- [ ] **Step 2: 提交**

```bash
git add USAGE.md
git commit -m "docs(zh): write §1 project overview"
```

---

## Task 3: §2 30 分钟跑通

**Files:**
- Modify: `USAGE.md`

- [ ] **Step 1: 写正文**

替换 `## 2. 30 分钟跑通` 为：

```markdown
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
```

注意：上面代码块的内层 ` ``` ` 会和外层 markdown 冲突 — 写入文件时把内层换成 4 空格缩进，或写完后用 `cat USAGE.md | head -200` 自检一下渲染。**推荐做法**：内层代码块照常用 ` ``` `，因为 Markdown 解析器对最外层 fenced block 不嵌套（这一段的最外层 fenced block 我们用 ` ``` ` 包裹的是“写入 USAGE.md 的整段示例”，本步骤的实际文件写入只写入示例内的内容）。

- [ ] **Step 2: 自检**

跑一次：

```bash
grep -n "^## " USAGE.md
```

预期看到 10 个章节标题按顺序出现。

- [ ] **Step 3: 提交**

```bash
git add USAGE.md
git commit -m "docs(zh): write §2 30-min smoke test"
```

---

## Task 4: §3 环境准备

**Files:**
- Modify: `USAGE.md`

- [ ] **Step 1: 写正文**

替换 `## 3. 环境准备` 为：

```markdown
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
```

- [ ] **Step 2: 提交**

```bash
git add USAGE.md
git commit -m "docs(zh): write §3 environment setup"
```

---

## Task 5: §4 数据格式

**Files:**
- Modify: `USAGE.md`

- [ ] **Step 1: 写正文**

替换 `## 4. 数据格式` 为：

```markdown
## 4. 数据格式

本仓库总共涉及 5 种文件格式。你只需要关心**输入**那两种：源数据 JSON 和预测 JSONL；其余 3 种是中间产物。

### 4.1 源数据：`data/CAE-v2.0-1.json`（输入 ①）

JSON 数组，每条是一道题：

```json
{
  "编号": "1",
  "问题描述": "在流固耦合（FSI）仿真中，"附加质量效应"为何会导致数值不稳定？",
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
  "rubric_metadata": { "generation_model": "...", "n_criteria_final": 12, ... },
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
      "breakdown": [ { "id": "c1", "met": true, "reason": "...", "contribution": 5 }, ... ]
    }
  ],
  "aggregate": {
    "n_predictions": 2, "n_scored_ok": 2, "mean_score": 0.86,
    "by_question_type": { ... },
    "by_difficulty": { ... },
    "by_criterion_type": { ... }
  }
}
```
```

- [ ] **Step 2: 提交**

```bash
git add USAGE.md
git commit -m "docs(zh): write §4 data formats"
```

---

## Task 6: §5 生成 Rubrics

**Files:**
- Modify: `USAGE.md`

- [ ] **Step 1: 写正文**

替换 `## 5. 生成 Rubrics` 为：

```markdown
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
```

- [ ] **Step 2: 提交**

```bash
git add USAGE.md
git commit -m "docs(zh): write §5 rubric generation"
```

---

## Task 7: §6 评估模型预测

**Files:**
- Modify: `USAGE.md`

- [ ] **Step 1: 写正文**

替换 `## 6. 评估模型预测` 为：

```markdown
## 6. 评估模型预测

### 6.1 三步流程

```text
predictions.jsonl ──┐
                    ├─→ anchor 缓存（ref/weak 各跑 1 遍 judge）
rubrics/items/*  ──┘
                    │
                    ▼
              per-criterion judge（异步 + semaphore）
                    │
                    ▼
              得分公式 + anchor 归一化
                    │
                    ▼
              eval_*.json
```

### 6.2 一条命令跑评估

```bash
# 1. 准备预测 JSONL（每行 {"item_idx": N, "answer": "..."}）
cat > my_preds.jsonl <<'EOF'
{"item_idx": 0, "answer": "..."}
{"item_idx": 1, "answer": "..."}
EOF

# 2. 跑评估
python run/04_score_predictions.py \
    --predictions my_preds.jsonl \
    --rubrics-dir rubrics/items \
    --anchor-cache data/CAE-anchor-scores.json \
    --out data/eval_modelA.json \
    --concurrency 16
```

### 6.3 参数速查

| 参数 | 默认 | 说明 |
|---|---|---|
| `--predictions` | 必填 | JSONL 文件路径 |
| `--rubrics-dir` | `rubrics/items` | 含 `idx_*.json` 的目录 |
| `--anchor-cache` | `data/CAE-anchor-scores.json` | ref/weak anchor 分数缓存 |
| `--out` | 必填 | 输出 JSON 路径 |
| `--concurrency` | 16 | judge 异步并发上限（semaphore） |
| `--judge-model` | 跟 `.env` | 评估时单独覆盖 LLM_MODEL |
| `--refresh-anchors` | 关 | 强制重算 anchor 缓存（rubric 改了就开） |
| `--no-anchors` | 关 | 跳过 anchor 归一化（更快但失去可比性） |
| `--resume` | 关 | 跳过 `--out` 里已有 `score!=null` 的样本 |

### 6.4 Anchor 缓存机制

每道题的 rubric 会先跑两遍 judge：

- **ref 分**：用题目自带 `reference_answer` 当 candidate。理想情况下接近 1.0。
- **weak 分**：用字符串 `"我不知道。"` 当 candidate。理想情况下接近 0.0。

结果缓存到 `data/CAE-anchor-scores.json`，按 `item_idx` 做 key：

```json
{
  "0": { "ref_score": 1.0, "weak_score": 0.0, "judge_model": "openai/gpt-5.4-mini", "computed_at": "..." }
}
```

后续评估同一批 rubric 时自动命中缓存。**改了 rubric 一定要 `--refresh-anchors`**，否则 anchor 和 rubric 不一致。

### 6.5 得分公式

每题的原始分（`scoring.py:score_response`）：

```text
raw_score = (Σ w_i · met_i  for positive  −  Σ w_i · met_i  for pitfall) / Σ w_i  for positive
clipped   = max(0, min(1, raw_score))
```

举例：一条 rubric 有正向权重 `[5, 5, 5, 3, 3, 3, 3]`（合计 27），陷阱 `[4, 3]`。某回答命中前 5 条正向、未触发陷阱：

```text
pos_score = 5+5+5+3+3 = 21
penalty   = 0
score     = 21 / 27 ≈ 0.78
```

如果还触发了"开场白套话"（weight 4）：

```text
score = (21 − 4) / 27 ≈ 0.63
```

### 6.6 Anchor 归一化

不同 rubric 的"天花板"不同（有的 ref 答案只能拿 0.85，有的能拿 1.0），所以聚合时用 anchor 重标：

```text
normalized = (score − weak) / (ref − weak)
```

clip 到 `[0, 1]`。`ref ≤ weak`（rubric 校准失败）时 `normalized=null` 并打 warning。

聚合报告里 `mean_score` 是 raw，`mean_anchored` 是归一化后的，**建议横向比较模型时看 `mean_anchored`**。

### 6.7 读懂聚合报告

```bash
jq '.aggregate' data/eval_modelA.json
```

字段含义：

```json
{
  "n_predictions": 94,                           // 输入预测条数
  "n_scored_ok": 92,                             // 成功打分条数（n_predictions - n_errors）
  "n_errors": 2,                                 // 失败条数（item_idx 对不上 rubric 或 judge 崩了）
  "mean_score": 0.74,                            // 原始分均值
  "mean_anchored": 0.81,                         // anchor 归一化均值（推荐看这个）
  "by_question_type": {
    "决策题": { "n": 12, "mean": 0.68, "mean_anchored": 0.75 }
  },
  "by_difficulty": {
    "困难": { "n": 30, "mean": 0.62, "mean_anchored": 0.71 }
  },
  "by_criterion_type": {
    "anti_hacking": { "n_criteria": 188, "met_rate": 0.05 }   // pitfall 触发率，越低越好
  }
}
```

### 6.8 看单题明细

```bash
# 看第 0 题的所有 criterion 判定
jq '.per_candidate[] | select(.item_idx == 0)' data/eval_modelA.json

# 列出所有未命中的 Essential criterion，按贡献度排序
jq '.per_candidate[].breakdown[] | select(.category == "Essential" and .met == false)' \
   data/eval_modelA.json
```
```

- [ ] **Step 2: 提交**

```bash
git add USAGE.md
git commit -m "docs(zh): write §6 prediction evaluation"
```

---

## Task 8: §7 移植到非 CAE 领域

**Files:**
- Modify: `USAGE.md`

- [ ] **Step 1: 写正文**

替换 `## 7. 移植到非 CAE 领域` 为：

```markdown
## 7. 移植到非 CAE 领域

仓库默认绑定 CAE 数据，但核心代码（generator / refiner / judge / scorer / aggregate）是领域无关的。要把它换成你自己的领域（医疗 QA、法律 QA、金融 QA 等），按下面 6 步改：

### 7.1 准备同 schema 的源数据 JSON

把你的题目转成跟 `data/CAE-v2.0-1.json` **完全一样的中文字段名**：`编号 / 问题描述 / 参考答案 / 题型 / 难易程度 / 来源`（其它字段可有可无）。题型必须是 7 种之一（见 §4.1），否则 `generator.py` 找不到 `templates/type_rules/{题型}.txt` 会崩。

- 如果你的题型不在这 7 种里，**两个选项**：
  - **快**：把每道题映射到最接近的现有题型（如 "翻译题" → "简答题"）
  - **正经**：复制 `src/rubrics/templates/type_rules/简答题.txt` 改成你自己的 `templates/type_rules/翻译题.txt`，同时在 `schema.py:QuestionType` 的 `Literal` 里加 `"翻译题"`，pydantic 才会放行

### 7.2 准备源文档 + 别名映射

如果你的题目能追溯到具体文档：

1. 把文档转成 markdown 放进 `CAE-MDs/`（建议改个目录名如 `source-mds/`，命令里用 `--mds-dir source-mds`）
2. **改 `src/rubrics/source_parser.py:DOC_ALIASES`**：把 11 条 CAE 别名换成你自己的，例如：
   ```python
   DOC_ALIASES = {
       "GINA2024": "Global_Initiative_for_Asthma_2024.md",
       "GOLD指南": "GOLD_Report_2024.md",
   }
   ```
3. 你的 `来源` 字段就可以写 `GINA2024, 第12-15页`、`GOLD指南 第5页` 等。页码格式支持中文 `第N页` / `第N-M页` 和英文 `pN` / `pN-M`，详见 §5.3。

**没有源文档怎么办**：把 `来源` 字段留空字符串，`retriever.py` 会全部走 `fallback_semantic`，效果会差一些但能跑。如果连 markdown 都没有，跳过 `01_build_index.py`，但 `02_generate_rubrics.py` 仍然需要一个空 index（手动跑一遍 build_index 把空 `CAE-MDs/` 喂进去会生成 0-chunk 的 pkl，可用）。

### 7.3 处理页码标记

`chunker.py` 用正则 `page_(\d+)_block_\d+` 抽页码（mineru 转出来的 markdown 自带）。如果你的 markdown 没有这种锚点：

- **方案 A**：用 mineru 转一遍 PDF，自动带上
- **方案 B**：手动按页拆成多个 md 文件，每个文件第一行加 `<!-- page_NNN_block_001 -->` 注释（被正则匹配）
- **方案 C**：放弃页码精度，所有页码字段留空，`ground_status` 全部是 `doc_only` 或 `fallback_semantic`

### 7.4 换 embedding 模型

如果你的领域是英文 / 多语言：

- 在 `.env` 里改 `EMBEDDING_MODEL`，例如 `BAAI/bge-base-en-v1.5` 或 `BAAI/bge-m3`
- **同时改 `src/rubrics/index.py:_encode_query` 里的中文 prefix**，BGE-en 用 `Represent this sentence for searching relevant passages:`，BGE-m3 不需要 prefix（直接传空字符串）。这是当前唯一一处硬编码语言的位置

### 7.5 调整 system prompt

`src/rubrics/templates/system_prompt.txt` 写死了 "CAE / 工程仿真领域的高级评审专家"。换领域时建议：

1. 把第一段 "CAE / 工程仿真" 换成你的领域名
2. 第 7 条 "严禁形容词" 列表里的 `good / clear / comprehensive` 可以保留，再补几条领域无关的 hedging 词
3. **不要动 JSON schema 段落和 7 种 criterion_type 定义**，下游代码依赖这些

### 7.6 重写 few-shot 示例

`src/rubrics/templates/exemplars/gold_rubrics.json` 是 3 个 CAE 题的"金标 rubric"，会被 `generator.py:_format_exemplars` 随机选 3 条塞进 prompt。换领域时务必改：

```json
[
  {
    "question_type": "简答题",
    "question": "（你的领域里一道有代表性的简答题）",
    "reference_answer": "（参考答案）",
    "criteria": [
      { "id": "c1", "text": "...", "category": "Essential", "weight": 5, "sign": "positive", "criterion_type": "factual_anchor" }
    ]
  }
]
```

7 种题型每种至少 1 条，避免某些题型完全没有 few-shot。生成质量极大依赖这份示例的质量，**值得花时间手工打磨**。

### 7.7 改完之后

跑一遍 smoke test：

```bash
python run/02_generate_rubrics.py --limit 2 --dry-run
```

确认 1 题能跑通、生成的 rubric 字段都合法，再放开 `--limit` 跑全量。
```

- [ ] **Step 2: 提交**

```bash
git add USAGE.md
git commit -m "docs(zh): write §7 porting to non-CAE domains"
```

---

## Task 9: §8 调参与成本

**Files:**
- Modify: `USAGE.md`

- [ ] **Step 1: 写正文**

替换 `## 8. 调参与成本` 为：

```markdown
## 8. 调参与成本

### 8.1 LLM 选型

| 角色 | 默认模型 | 备注 |
|---|---|---|
| Generator（Stage 1） | `LLM_MODEL`（默认 `openai/gpt-5.4-mini`） | 主要成本，建议用便宜模型 |
| Misalignment judge（Stage 3） | 同 generator | 跑 2N 次（ref + weak），是 generator 调用数的 ~2 倍 |
| Score judge（评估期） | `--judge-model` 或 `LLM_MODEL` | 跑 M × C 次（M 个回答 × C 条 criterion） |

**省钱建议**：generation 可以用便宜模型（`gpt-5.4-mini` / `qwen2.5-7b` / `glm-4-flash`），score judge 用更强的模型（`gpt-5.4` / `claude-sonnet-4-6`）。命令上：

```bash
# 评估时单独换 judge 模型
python run/04_score_predictions.py --judge-model anthropic/claude-sonnet-4-6 ...
```

### 8.2 并发与 rate limit

- `04_score_predictions.py --concurrency 16` 是 asyncio.Semaphore 上限。你的 LLM 服务如果限 RPM/TPM，根据限额估算上限：例如 600 RPM 平均 5s 一次响应，理论上限 `600/60 * 5 ≈ 50`，留余量取 20-30。
- `02_generate_rubrics.py` 是**纯串行**（94 题循环），单题 ~3 次 LLM call（generator + ref-judge × N + weak-judge × N）。94 题串行约 2.5h，可以容忍。如果嫌慢，可以拆批跑（如分两台机器 `--limit 47` 各跑一半）+ `--resume` 合并。

### 8.3 成本估算（94 题样例）

| 步骤 | LLM 调用次数 | gpt-5.4-mini 成本 |
|---|---|---|
| Generator | 94 × 1 = 94 | ~$0.05 |
| Misalignment filter | 94 × N_criteria × 2 ≈ 94 × 9 × 2 = 1692 | ~$0.20 |
| Anchor 计算 | 94 × N_criteria × 2 = 1692 | ~$0.10 |
| Score（评估 1 模型） | 94 × N_criteria = 846 | ~$0.10 |
| **合计** | **~4300 calls** | **~$0.5** |

实测同模型在 CAE 数据上 ~$0.5，跨数据集线性外推：题数 × 平均 criterion 数 × 4。

### 8.4 关键阈值

| 位置 | 参数 | 默认 | 改它的影响 |
|---|---|---|---|
| `chunker.py` | `chunk_size` / `overlap` | 400 / 100 | 太小检索碎、太大召回少 |
| `refiner.py` | `dedup_threshold` | 0.9 | 越低越激进去重；0.85 可能误伤 |
| `retriever.py` | `score_threshold` | 0.3（fallback 时）| 越高越保守、越容易退到 semantic fallback |
| `retriever.py` | `k` | 3 | 上下文 chunk 数，调大会显著增加 generation token |
| `pipeline.py` | `generation_passes` | 3（固定）| 改不了，写在 metadata 里只是记账 |
| `llm_client.py` | `temperature` | 0.3 | rubric 生成需要稳定，不建议提高 |
| `anchor.py` | `WEAK_ANSWER` | `"我不知道。"` | 想加强 anti-hacking 检测可换成 `"这个问题很有意思，让我从多个角度来回答……"` 之类的灌水回答 |
```

- [ ] **Step 2: 提交**

```bash
git add USAGE.md
git commit -m "docs(zh): write §8 tuning and cost"
```

---

## Task 10: §9 常见问题与排查

**Files:**
- Modify: `USAGE.md`

- [ ] **Step 1: 写正文**

替换 `## 9. 常见问题与排查` 为：

```markdown
## 9. 常见问题与排查

### Q1: `KeyError: 'LLM_API_KEY'`

`.env` 没复制 / 没填 / 不在仓库根目录。`python-dotenv` 只从当前工作目录读 `.env`。**从仓库根目录运行命令**。

### Q2: `FileNotFoundError: CAE-MDs/...`

源 markdown 不在仓库（默认 gitignore），需要自备。如果只想跑评估不重新生成，**完全不需要 CAE-MDs**（rubric 已经在 `rubrics/items/`）。

### Q3: `pydantic.ValidationError: Pitfall must have sign=negative`

LLM 返回了不合法的 criterion（如把 Essential 标成 negative）。`schema.py` 在最后一关拦截。检查日志看 prompt 出在哪一题，必要时改 prompt 再 `--resume` 重试该题（删掉对应的 `rubrics/items/idx_NNN.json` 即可）。

### Q4: `LLM did not return valid JSON: ...`

LLM 输出夹了文字解释或 markdown fence。`llm_client.py:_extract_json_block` 会先尝试剥 ` ```json ... ``` ` 围栏，失败再原样解析。常见原因：

- 模型太弱不稳定 → 换大一点的模型
- temperature 太高 → 默认 0.3 已经够低，别调高
- 该模型不支持中文 system prompt → 换中文友好模型（gpt-5.4-mini / qwen / glm 都 OK）

### Q5: 生成出来 `ground_status` 全是 `fallback_semantic`

说明 `来源` 字段没被 `source_parser.py` 识别。检查：

1. 别名是否在 `DOC_ALIASES` 字典里
2. 别名前后是否有正确的中文标点（"Benson教材,第5页" 没空格也行，但 "Benson 教材 第 5 页" 有的版本会断错）
3. md 文件是否在 `--mds-dir` 指向的目录

跑一行 Python 直接看解析结果：

```python
from rubrics.source_parser import parse_source
print(parse_source("Benson教材, 第4章, 第166-189页"))
# [SourceRef(doc_alias='Benson', pages=(166, 189))]
```

### Q6: 评估时 `n_errors > 0`

可能原因：

- 预测 JSONL 里的 `item_idx` 在 `rubrics/items/` 里没有对应 `idx_NNN.json` → 报错信息：`no rubric found for item_idx=N`
- 某条 judge 调用 3 次重试都失败 → 看日志里的 `Scorer crashed on item_idx=N`
- 网络抖动 → 单纯 `--resume` 重跑

### Q7: `score_anchored.normalized == null` + warning "ref_score <= weak_score"

参考答案在 rubric 上的分数不高于 "我不知道"。说明这道题的 rubric **校准失败**，criterion 太宽松或参考答案太短。两个修复方向：

- 删掉对应的 `rubrics/items/idx_NNN.json` + `--resume` 重新生成
- 在 `data/CAE-v2.0-1.json` 里扩写 `参考答案` 字段，让它涵盖更多 criterion

### Q8: `pickle.UnpicklingError` 加载 chunk_index.pkl

不同机器 / 不同 sentence-transformers 版本之间 pickle 不兼容。删掉重建：

```bash
rm data/cae_chunk_index.pkl
python run/01_build_index.py
```

### Q9: 想看每条 criterion 的判定理由

```bash
jq '.per_candidate[0].breakdown[] | {id, text, met, reason}' data/eval_modelA.json
```

每行带 judge 给的中文 reason，方便排查 false negative。

### Q10: judge 模型偏好特定文风（如总打高分）

LLM-as-judge 都有这个问题。两个缓解办法：

- **anchor 归一化**（默认开）：`(score - weak) / (ref - weak)` 抹掉 judge 的整体偏置
- **换 judge 模型**：用更严的模型（如 `claude-sonnet-4-6`），同一 rubric 跑两遍取均值 / 取严的那次
```

- [ ] **Step 2: 提交**

```bash
git add USAGE.md
git commit -m "docs(zh): write §9 FAQ"
```

---

## Task 11: §10 项目结构索引

**Files:**
- Modify: `USAGE.md`

- [ ] **Step 1: 写正文**

替换 `## 10. 项目结构索引` 为：

```markdown
## 10. 项目结构索引

```text
rlm-rubrics/
├── README.md                      # 英文 quickstart
├── USAGE.md                       # 本文档
├── pyproject.toml                 # Python 3.11+ 依赖
├── .env.example                   # 环境变量模板
│
├── data/
│   ├── CAE-v2.0-1.json            # 94 道 CAE 源题（输入）
│   ├── cae_chunk_index.pkl        # 源文档 embedding 索引（中间产物）
│   ├── CAE-v2.0-1-rubrics.json    # 94 份 rubric 聚合（输出）
│   ├── CAE-anchor-scores.json     # anchor 缓存
│   └── eval_*.json                # 评估输出
│
├── CAE-MDs/                       # 8 份源文档（gitignore，自备）
├── CAE-PDFs/                      # 对应 PDF（gitignore，自备）
│
├── rubrics/items/
│   └── idx_NNN.json               # 每题一个 rubric 文件
│
├── src/rubrics/                   # 核心包
│   ├── schema.py                  # Pydantic 模型 + 7 题型 + 4 category + 7 criterion_type
│   ├── chunker.py                 # markdown 分块 + 页码抽取
│   ├── source_parser.py           # 来源 字段 → (doc, pages)
│   ├── index.py                   # BGE-zh embedding 索引
│   ├── retriever.py               # page-first + semantic fallback
│   ├── llm_client.py              # OpenAI 兼容客户端（sync + async + tenacity 重试）
│   ├── generator.py               # Stage 1 初稿
│   ├── refiner.py                 # Stage 2 拆分 + 去重 + 默认 pitfall
│   ├── misalignment_filter.py     # Stage 3 ref/weak 过滤
│   ├── pipeline.py                # 端到端 build_rubric_for_item
│   ├── judge.py                   # 通用 per-criterion judge（sync + async）
│   ├── anchor.py                  # ref/weak anchor + 缓存
│   ├── scorer.py                  # 异步评分主类（semaphore）
│   ├── scoring.py                 # 权重公式
│   ├── aggregate.py               # 聚合报告
│   └── templates/
│       ├── system_prompt.txt          # generator 总 prompt
│       ├── misalignment_judge_prompt.txt
│       ├── type_rules/{7种题型}.txt    # 每题型一份 rubric 结构规则
│       └── exemplars/gold_rubrics.json # 3 条 few-shot 示例
│
├── run/                           # 4 个入口脚本
│   ├── 01_build_index.py          # 建索引
│   ├── 02_generate_rubrics.py     # 跑生成
│   ├── 03_validate.py             # QC
│   └── 04_score_predictions.py    # 评估
│
├── tests/rubrics/                 # 57 个测试
│   └── preds_sample.jsonl         # 2 条 smoke 预测
│
└── docs/superpowers/
    ├── specs/                     # 设计文档（中文）
    │   ├── 2026-05-22-cae-rubrics-design.md           # 生成管线设计
    │   └── 2026-05-22-cae-rubrics-scorer-design.md    # 评分管线设计
    └── plans/                     # 实现计划（中文）
```

### 阅读顺序建议

想搞清楚某个模块：

- 想懂得分公式 → `scoring.py` + `aggregate.py`（< 100 行）
- 想懂生成管线 → `pipeline.py` → `generator.py` → `refiner.py` → `misalignment_filter.py`
- 想懂 RAG → `chunker.py` → `index.py` → `source_parser.py` → `retriever.py`
- 想看设计动机 → `docs/superpowers/specs/2026-05-22-cae-rubrics-design.md`

### 学术参考

策略综合自约 22 篇 rubric / LLM-as-judge 文献：HealthBench、RubricRAG、Rubrics-as-Rewards、OpenRubrics、AdaRubric、Auto-Rubric、RIFT、RubricHub 等。完整理由见 `docs/superpowers/specs/2026-05-22-cae-rubrics-design.md`。

### License

代码：MIT。`CAE-MDs/`、`CAE-PDFs/`、`rubrics-papers-md/` 默认不入库（版权原因），需自备。
```

- [ ] **Step 2: 自检完整性**

```bash
# 章节数应为 10
grep -c "^## " USAGE.md

# 无遗留 TODO/待补充/{{}}
grep -n "TODO\|待补充\|{{" USAGE.md

# 行数应在 600-900 之间
wc -l USAGE.md
```

预期：第一个 ≥10、第二个空、第三个 600-900。

- [ ] **Step 3: 提交**

```bash
git add USAGE.md
git commit -m "docs(zh): write §10 project structure index"
```

---

## Task 12: 终检 — 端到端通读 + 验证关键命令

**Files:**
- 不修改文件，仅验证

- [ ] **Step 1: 通读 USAGE.md 检查格式**

```bash
# 标题层级一致
grep -E "^#{1,3} " USAGE.md | head -40

# 代码块成对
grep -c '^```' USAGE.md
```

代码块计数应为偶数。

- [ ] **Step 2: 抽样验证文档里的命令真能跑**

按顺序在干净 shell 里跑：

```bash
# §2 smoke test
python run/04_score_predictions.py \
    --predictions tests/preds_sample.jsonl \
    --out /tmp/eval_smoke_doctest.json \
    --concurrency 4

jq '.aggregate.n_scored_ok' /tmp/eval_smoke_doctest.json   # 期望 2

# §3 测试
pytest tests/rubrics/ -q --timeout=60   # 期望大部分 pass，部分 LLM 测试可能 skip

# §5.3 source parser 单元自查
python -c "from rubrics.source_parser import parse_source; print(parse_source('Benson教材, 第4章, 第166-189页'))"
# 期望: [SourceRef(doc_alias='Benson', pages=(166, 189))]

# §9 Q5 自查
python -c "from rubrics.source_parser import parse_source; print(parse_source('贾宪振博士论文 第17页; ThyssenKrupp论文 第5页'))"
# 期望: 两条 SourceRef
```

如果任何一条失败，回到对应章节修文档（不是改代码）。

- [ ] **Step 3: 检查 README 跳转生效**

```bash
head -10 README.md | grep -n USAGE
```

预期看到 `> 中文完整教程见 [`USAGE.md`](USAGE.md)。` 这一行。

- [ ] **Step 4: 最终提交 + 推送（如需要）**

```bash
git log --oneline -15   # 应看到 11 条 docs(zh) commits
# 如果你打算推到远端：
# git push origin main
```

---

## Self-Review

完成以上 12 个任务后对照下面 checklist 自检：

**1. 覆盖度（对照用户问的"如何生成 rubrics 以及如何评估"）**
- [x] 生成入口命令 → Task 6
- [x] 生成的三阶段拆解 → Task 6
- [x] 来源字段解析规则 → Task 6
- [x] 评估入口命令 → Task 7
- [x] anchor 机制 → Task 7
- [x] 得分公式 + 举例 → Task 7
- [x] 聚合报告字段说明 → Task 7

**2. 开源友好度**
- [x] 30 分钟跑通（无源文档也能验证安装） → Task 3
- [x] 完整环境准备 → Task 4
- [x] 数据格式契约 → Task 5
- [x] 移植到非 CAE → Task 8
- [x] 调参 / 成本 → Task 9
- [x] FAQ → Task 10
- [x] 项目结构索引 → Task 11

**3. 无占位符** — Task 12.1 grep 验证

**4. 命令真实可跑** — Task 12.2 抽样跑

**5. 风格** — 全文中文，无 em-dash 滥用，无"强大/无与伦比/革命性"等灌水词，代码块标语言

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-24-usage-zh-cn.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task (Task 2 → 11 one each, then Task 12 验证 one), review between tasks. 适合这种"按章节独立写"的文档活，每个 subagent 上下文小、不互相干扰。

2. **Inline Execution** — 我在当前会话里按 Task 顺序连写 11 章 + 验证，中途按 §1/§5/§7 三个 checkpoint 暂停让你 review。会话长但你能实时看到内容，方便随时调整语气和细节。

Which approach?
