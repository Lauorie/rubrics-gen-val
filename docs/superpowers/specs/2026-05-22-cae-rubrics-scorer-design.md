# CAE Rubrics Scorer — Design Spec

**Status:** Approved 2026-05-22
**Owner:** juli
**Depends on:** `2026-05-22-cae-rubrics-design.md` (rubric generation)
**Primary use case:** 离线 eval（test set ~100-1000 候选）；每个 candidate 给一个 [0,1] 分 + per-criterion 明细

---

## 1. Goal

为已有的 94 个 CAE rubric (`rubrics/items/idx_*.json`) 提供一个**离线 eval scorer**：输入 `(item_idx, candidate_answer)` 序列，输出每个候选的 scalar score + per-criterion breakdown，以及聚合统计（按 question_type / difficulty / criterion_type 分桶）。

## 2. Architecture

```
test_predictions.jsonl              rubrics/items/idx_*.json
        │                                    │
        ▼                                    ▼
┌─────────────────────────────────────────────────────────┐
│  Scorer (src/rubrics/scorer.py)                          │
│                                                          │
│  1. RubricStore       一次加载 94 个 rubric              │
│  2. AnchorScorer      给每个 rubric 计算并缓存            │
│                       ref_answer / weak_answer baseline   │
│  3. JudgeRunner       async 并发 per-criterion judge      │
│                       (asyncio + httpx.AsyncClient, k=16) │
│  4. score_response()  复用现有 scoring.py 公式            │
└─────────────────────────────────────────────────────────┘
        │
        ▼
eval_report_<model>.json
├── per_candidate: [{idx, score, breakdown[], anchored}]
└── aggregate: {mean, by_type, by_difficulty, by_criterion_type, ...}
```

**Core choices**：
- **Per-criterion judge** (一条 criterion 一次 LLM call) — 文献中信噪比最高
- **Async 并发** (`asyncio.gather` with semaphore-limited `max_concurrent=16`) — 串行 1.5h → 并发 5-10 min
- **Ref/weak anchor** — 给每个 rubric 预先算两条基线分，并提供 normalized score

## 3. 输入 / 输出 格式

### 3.1 输入 predictions.jsonl

```jsonl
{"item_idx": 0, "answer": "ALE 方法是任意拉格朗日-欧拉..."}
{"item_idx": 1, "answer": "HJC 模型主要考虑高应变率..."}
```

字段：
- `item_idx`：源数组位置 0-93（避免 duplicate 编号）。必填。
- `answer`：候选回答文本。必填。

### 3.2 Per-candidate 输出 (one JSON object per item in `eval_report.per_candidate`)

```json
{
  "item_idx": 0,
  "question_id": "1",
  "question_type": "主观题",
  "difficulty": "困难",
  "candidate_answer": "...",
  "score": 0.78,
  "score_anchored": {
    "ref_score": 0.92,
    "weak_score": 0.04,
    "normalized": 0.84
  },
  "breakdown": [
    {
      "id": "c1",
      "text": "...",
      "category": "Essential",
      "weight": 5,
      "sign": "positive",
      "criterion_type": "factual_anchor",
      "met": true,
      "reason": "candidate 明确写了 added-mass...",
      "contribution": 5
    }
  ],
  "judge_model": "openai/gpt-5.4-mini",
  "scored_at": "2026-05-22T..."
}
```

字段说明：
- `score`：score_response() 给出的 `[0,1]` raw 分
- `score_anchored.normalized`：`(score - weak) / max(ref - weak, ε)`；若 `ref ≤ weak`，置 null + warning
- `contribution`：positive 时 = met * weight；negative 时 = -met * weight；用于 debug

### 3.3 Aggregate 报告 (`eval_report.aggregate`)

```json
{
  "n_predictions": 100,
  "n_scored_ok": 99,
  "n_errors": 1,
  "mean_score": 0.71,
  "mean_anchored": 0.78,
  "by_question_type": {
    "简答题": {"n": 48, "mean": 0.74, "mean_anchored": 0.80},
    "决策题": {"n": 18, "mean": 0.65, "mean_anchored": 0.71}
  },
  "by_difficulty": {
    "简单": {"n": 19, "mean": 0.82, "mean_anchored": 0.88},
    "中等": {"n": 37, "mean": 0.71, "mean_anchored": 0.77},
    "困难": {"n": 38, "mean": 0.62, "mean_anchored": 0.69}
  },
  "by_criterion_type": {
    "factual_anchor": {"met_rate": 0.85, "n_criteria": 240},
    "decision_logic": {"met_rate": 0.72, "n_criteria": 71},
    "anti_hacking":   {"met_rate": 0.06, "n_criteria": 188}
  },
  "judge_model": "openai/gpt-5.4-mini",
  "rubric_version": "1.0",
  "scored_at": "2026-05-22T...",
  "elapsed_seconds": 360
}
```

## 4. Anchor 机制

### 4.1 缓存文件

`data/CAE-anchor-scores.json`：
```json
{
  "0": {"ref_score": 0.92, "weak_score": 0.04, "computed_at": "...", "judge_model": "..."},
  "1": {"ref_score": 0.88, "weak_score": 0.05, "computed_at": "...", "judge_model": "..."}
}
```

### 4.2 计算逻辑

对每个 rubric：
1. 取 `reference_answer` 与固定 weak answer `"我不知道。"`
2. 对每个 criterion 调 judge → met
3. 调 `score_response()` → ref_score / weak_score
4. 缓存 keyed on `item_idx`

### 4.3 使用规则

- 启动 scorer 时检查 anchor cache 是否完整（94 条）；缺失自动补算
- `--refresh-anchors`：强制重算所有 anchor（例如更换 judge model 时）
- ref_score < 0.7 的 rubric → 报告里 flag 为 `low_ref_score_warning`
- weak_score > 0.2 的 rubric → flag 为 `high_weak_score_warning`（可能 pitfall 不灵）

## 5. Judge Prompt（复用 misalignment_filter 模板）

直接用 `src/rubrics/templates/misalignment_judge_prompt.txt`，输出：
```json
{"met": true/false, "reason": "一句话理由"}
```

判定原则（与生成阶段一致）：
- 只看候选回答内容，不假设作者意图
- 对 Pitfall criterion（sign=negative）：`met=true` 表示触发了负向规则
- 边界以严格态度判 `met=false`

## 6. 失败处理

| 情况 | 处理 |
|---|---|
| Judge HTTP 5xx | tenacity 重试 3 次（exp backoff） |
| Judge 返回非 JSON | 该 criterion 视为 `met=false`，记录 `errors[]` |
| `item_idx` 不在 rubric store | 跳过该 candidate，`n_errors+=1`，记 warning |
| 整个 candidate 处理崩 | 写入 per_candidate `{score: null, error: "..."}`，不影响 batch |
| Anchor 计算失败 | 该 rubric 的 `score_anchored.normalized = null`，但 raw score 仍输出 |

## 7. 新增 / 修改文件

| 文件 | 类型 | 作用 |
|---|---|---|
| `src/rubrics/llm_client.py` | **修改** | 增加 `async complete_json_async()` 用 `httpx.AsyncClient`，复用 retry 装饰器 |
| `src/rubrics/judge.py` | **新增** | 抽出 per-criterion judge 函数，sync + async 双版本；`misalignment_filter` 改用此模块 |
| `src/rubrics/anchor.py` | **新增** | `compute_anchors()` + `AnchorCache` 读写 |
| `src/rubrics/scorer.py` | **新增** | `Scorer` 类：`score_one()` (async) / `score_batch()` (并发) |
| `src/rubrics/aggregate.py` | **新增** | 聚合统计：`build_aggregate(per_candidate, rubrics) -> dict` |
| `run/04_score_predictions.py` | **新增** | CLI 入口 |
| `tests/rubrics/test_judge.py` | **新增** | sync + async judge 测试 |
| `tests/rubrics/test_anchor.py` | **新增** | anchor 计算 + cache 测试 |
| `tests/rubrics/test_scorer.py` | **新增** | mocked scorer 测试 |
| `tests/rubrics/test_aggregate.py` | **新增** | 聚合统计测试 |

## 8. CLI

```bash
python run/04_score_predictions.py \
    --predictions tests/preds_modelA.jsonl \
    --rubrics-dir rubrics/items/ \
    --anchor-cache data/CAE-anchor-scores.json \
    --out eval_modelA.json \
    --concurrency 16

# 可选 flag:
#   --refresh-anchors       重算 anchor cache
#   --judge-model NAME      覆盖默认 LLM model
#   --resume                跳过已在 out 文件中的 idx（断点续评）
#   --no-anchors            跳过 anchor，仅 raw score
```

## 9. 并发与速率控制

- `asyncio.Semaphore(args.concurrency)` 控制最大并发判分
- 每个 candidate 自身的 N 个 criterion 全部并发提交（典型 N=8-12）
- 全局并发数 = `concurrency`（默认 16），与 endpoint rate limit 协调
- httpx.AsyncClient `timeout=120s`、retry 3 次（继承现有 tenacity 配置）

## 10. 复用与不复用

| 模块 | 复用？ |
|---|---|
| `src/rubrics/scoring.py` | ✅ 完全复用 |
| `src/rubrics/schema.py` | ✅ Criterion / RubricItem 字段 |
| `src/rubrics/templates/misalignment_judge_prompt.txt` | ✅ Judge prompt |
| `src/rubrics/llm_client.py` 同步版 | ✅ 新增 async 版本并存 |
| `src/rubrics/misalignment_filter._judge_one` | ❌ 抽到 `judge.py` 公用化 |
| `src/rubrics/pipeline.py` | ❌ 不动（generation only） |

## 11. 成本估算

- **Anchor**（一次性，重运行只在 cache miss 时）：94 × 2 × ~9 ≈ 1700 calls ≈ **$0.5** ≈ 3 min
- **Eval 100 candidates**：100 × ~9 ≈ 900 calls ≈ **$0.27** ≈ 5 min（concurrency=16）
- **Eval 1000 candidates**：≈ $2.7 ≈ 30-50 min
- gpt-5.4-mini 单价假设：~$0.0003/call

## 12. 不做（YAGNI）

- ❌ Multi-judge ensemble（文献显示 +1.4% 不抵 5× cost）
- ❌ 流式 server endpoint（离线足够）
- ❌ Token-level reward shaping（属于 RL，不在 eval scope）
- ❌ 给 candidate 自动算 BLEU/ROUGE 等 surface metric（rubric 已替代）
- ❌ 历史评测对比 dashboard（生成 JSON 报告即可，可视化 v1.1）
- ❌ Batch RL reward mode（独立 spec，不在本 spec 范围）

## 13. 成功指标

- **覆盖**：100% candidate 给出非 null score（除非 candidate idx 错）
- **一致性**：在 reference_answer 上 mean(ref_score) ≥ 0.85（anchor 自检）
- **判分稳定**：相同 (rubric, candidate, judge_model) 重跑差异 ≤ 5%（T=0 + retry 同一 seed）
- **延迟**：100 candidates 在 16 并发下 ≤ 10 min
- **失败容错**：单 candidate 异常不影响 batch 其他 candidate

## 14. 安全

- API key 走 `os.environ["LLM_API_KEY"]`，不写死
- `.env` 已在 `.gitignore`
- candidate 内容可能含模型输出 — 不做内容审计，写到 eval report 时直接保存

## 15. Open Decisions（默认已选）

| ID | Decision | 默认 |
|---|---|---|
| D1 | Judge model | 与生成一致 `openai/gpt-5.4-mini` |
| D2 | Concurrency 默认 | 16 |
| D3 | Anchor weak answer | `"我不知道。"` 与生成阶段保持一致 |
| D4 | 输入格式 | JSONL（每行一条 record） |
| D5 | 输出文件 | 单个 JSON（per_candidate + aggregate） |
| D6 | 重跑策略 | `--resume` 跳过已打分的 idx |
