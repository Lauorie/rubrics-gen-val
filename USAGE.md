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

_TBD_

## 5. 生成 Rubrics

_TBD_

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
