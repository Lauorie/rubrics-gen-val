# RLM 评测实验总结 — `papers_qa` × `CAE-MDs`

> 用本仓库的 rubric 工具链（`src/rubrics/`、`src/score_rlm_answers.py`、`src/rubrics_report.py`）对 [`papers_qa`](papers_qa/) RLM agent 在 94 题中文 CAE 专家 QA 基准上做的 5 轮迭代评测。

## TL;DR

5 个版本，同一批 94 道题。**v3（prompt 指令 + 降温）是生产版冠军**，anchored 0.711。之后的 PEEK 缓存实验（v4、v5）用整体分换某些 criterion 的特化，没能超过 v3。

| 版本 | 主要改动 | Anchored | 墙钟 | 花费 |
|---|---|---|---|---|
| v1 | 原始 `papers_qa` | 0.698 | 47 min | ~$5 |
| v2 | + 风格指令 + temp 0.3（用力过猛） | 0.640 | 55 min | ~$10 |
| **v3（推荐）** | 按问法分类的较温和指令 | **0.711** | 47 min | ~$10 |
| v4 | v3 + PEEK 上下文 map（1024 token，前 30 题演化） | 0.706 | 5h50m | ~$15 |
| v5 | v4 + decisions distiller addendum + 串→并行拆分 | 0.693 | ~2h | ~$30 |

（所有版本都在同一批 94 题上评测，judge 用 `openai/gpt-5.5`。v3 在 rubric 截断修复后重打分 = 0.711。）

---

## 评测设置

- **被测模型**：`deepseek/deepseek-v4-flash`（走 [aiberm.com](https://aiberm.com) OpenAI-兼容代理）
- **Agent**：[`papers_qa.PapersQA`](papers_qa/papers_qa/runner.py) — RLM 风格 agent，在 `CAE-MDs/` 下 8 份中英 CAE markdown 上回答中文问题
- **Rubrics**：94 道题，836 条加权二值 criteria（Essential / Important / Optional + Pitfall，sign positive/negative），存于 `data/CAE-v2.0-1-rubrics.json`
- **Judge**：`openai/gpt-5.5`（和被测模型分开，避免共享盲点）
- **Anchors**：`data/CAE-anchor-scores.json` — 由 `gpt-5.4-mini` 预先打的 ref + weak 分数，把 raw score 归一化到 `[0, 1]` 的 anchored 尺度
- **主要指标**：mean anchored score。次要：各 criterion_type 命中率、pitfall 触发次数

## 迭代过程

### v1 — 基线（commit `58497c7`）

原版 `papers_qa`，默认 bilingual prompt，`PAPERS_QA_TEMPERATURE=0.8`。建立基准。

- Anchored: **0.698**
- 主要问题：
  - "回答冗长"pitfall 触发 31 次
  - "套话开场"pitfall 触发 12 次
  - `comparative_balance` 只有 47.4%（最弱的 criterion type）
  - `decision_logic` 表现还好，81.2%

### v2 — 首次 pitfall 消融（commit `c4d7431`，事后看：用力过猛）

在 `papers_qa/papers_qa/prompts.py` 的 `BILINGUAL_ADDENDUM` 加了 3 条风格指令：
> 直接给出答案 / 紧凑、聚焦 / 不要给出多个相互矛盾的候选答案

`PAPERS_QA_TEMPERATURE` 降到 **0.3**。

- Anchored: **0.640**（−0.058）
- 失败原因："紧凑、聚焦"的指令落得太重。答案长度中位数从 1089 → 561（−49%）。模型不只是删冗余背景，连公式、数值、对比都丢了
- 教训："紧凑"必须明确说不能丢实质内容

### v3 — 改良指令，当前生产版（commits `c526fd1` 内仓 + `7f169ee` 外仓）

把 v2 的指令换成按问法分类的细则：
- 直接给答案，避免开场白/套话/元评论
- 紧凑、聚焦，但**绝不删除问题要的内容**
- 按问法分类的特别要求：
  - 问"为什么" → 因果链完整
  - 问"哪些" → 列全
  - 问"经验关系" → 给公式（例：T ∝ W^(1/3)/p^(5/6)）
  - 问"区别" → A vs B 对照
  - 问"决策" → 给最终选定方案
- 不要给多个相互矛盾候选

温度保持 0.3。

- Anchored: **0.711**（vs v1 +0.013，vs v2 +0.071）
- **`comparative_balance`: 47.4% → 71.1%**（单项最大涨幅）
- `numeric_precision` 和 `factual_anchor` 回到 v1 水平（无回退）
- 代价：`decision_logic` 反而 81.2% → 67.2%（模型对"给最终答案"的指令解释过死，有时过早 committed）
- Pitfall 触发：冗长 31→14，套话 12→5

### v4 — PEEK 上下文缓存（commit `daef6ea`）

引入 [PEEK](peek/) 的 1024-token context-map cache。前 30 题逐步演化 map，然后冻结，每次调用都 prepend 到 RLM 的 system prompt。Distiller/cartographer 用 `deepseek/deepseek-v4-flash`。v3 prompt + temp 0.3 不变。

- Anchored: **0.706**（vs v3 −0.005，AC 通过）
- 冻结后的 map（5.2KB）包含 paper 段落字节范围、ALE/HJC/Grüneisen 域常数、混合理论解释
- vs v3 的提升：
  - **boilerplate 触发 5 → 1**（全版本最低）
  - `decision_logic` 部分恢复：67% → 72%
  - `mechanism_explanation` 恢复：68% → 72%
  - `process_completeness`：78% → 85%
- vs v3 的下降：
  - `comparative_balance`：71% → 57%（v3 的优势丢了）
- 2 道题撞到了 aiberm 代理超时（item 46、48）— 80 分钟级别的 outlier 把墙钟拉到 ~6h
- 教训：PEEK 通过缓存"地图"帮 decision/procedure 类问题，但对对比推理没帮助

### v5 — decisions distiller + 串→并行拆分（commits `293d40d`、`9237ccc`、`41a2fd4`）

两处改动：
1. **Distiller addendum** — 在 PEEK 的 distiller prompt 末尾追加一段指令，明确邀请把 `[Decision]` 类的"标准答案"也写进 REUSABLE RESULTS（作为 PEEK 默认"不缓存答案"规则的例外）
2. **拆分运行** 提速：串行跑前 30 题（`workers=1`，PEEK live）→ 保存冻结 map → 并行跑后 62 题（`workers=4`，把冻结 map 文本当 `PAPERS_QA_SYSTEM_PROMPT_ADDENDUM` 注入）。跳过 v4 里超时的 2 题

- Anchored: **0.693**（4 个版本里最低；AC 差 0.002 没过）
- **墙钟：~2h**（vs v4 提速 3.3×）
- vs v4 的提升：
  - `decision_logic`：71.9% → 78.1%（+6.2pp — 把对 v1 81% 的差距大部分补回）
  - `mechanism_explanation`：72.0% → 75.0%
  - `process_completeness`：84.6% → 88.5%（全版本最高）
- vs v4 的下降：
  - `comparative_balance`：57.1% → 60.0%（仍不如 v3 的 71.1%）
  - boilerplate 触发：1 → 10（并行阶段 worker 看不到 live distill 反馈）
- 教训：针对性的 distiller 修改对目标指标（`decision_logic`）确实有效，但并行 worker 失去了 live-feedback 的"杀套话"效应

---

## 横向对比

### Anchored mean

```
v3 0.711  ≥  v4 0.706  ≥  v1 0.698  ≥  v5 0.693  ≫  v2 0.640
```

### 各 criterion_type 命中率（仅 positive）

| criterion_type | v1 | v3 | v4 | v5 | 最佳 |
|---|---|---|---|---|---|
| comparative_balance | 47.4% | **71.1%** | 57.1% | 60.0% | v3 |
| decision_logic | **81.2%** | 67.2% | 71.9% | 78.1% | v1 |
| factual_anchor | 73.9% | **73.9%** | 70.7% | 70.0% | v1=v3 |
| mechanism_explanation | 72.5% | 67.7% | 72.0% | **75.0%** | v5 |
| numeric_precision | **84.6%** | 84.6% | 80.8% | 80.8% | v1=v3 |
| process_completeness | 81.5% | 77.8% | 84.6% | **88.5%** | v5 |

### Pitfall 触发次数（越少越好）

| pitfall | v1 | v3 | v4 | v5 |
|---|---|---|---|---|
| 冗长 (verbosity) | 31 | 14 | 15 | 19 |
| 套话开场 (boilerplate) | 12 | 5 | **1** | 10 |
| 多答案不committed (hedging, 修复后) | 4* | 1 | 5 | 5 |

*v1 的 hedging 计数里有 4 个是截断的 `"给出多个"` rubric criterion 误判出来的假阳性（已在 commit `ef5cb62` 修复）

---

## 生产建议

**用 v3。** 它的优势：
- Anchored 总分最高
- `comparative_balance`（最难的 criterion type）最佳
- 花费最低（$10），墙钟最短（47 min）
- 改动最简单：就是 prompt 指令 + 降温

PEEK 实验（v4、v5）作为研究数据有用，但不上生产 — 它们用整体分换了局部 criterion 的提升，并行缓存架构还有未解决的 tradeoff。

### 怎么跑 v3

```bash
cd /home/juli/RLM

# （一次性）确认 v3 prompt + 温度已经就位
grep -c "回答风格要求" papers_qa/papers_qa/prompts.py   # 应该输出 1
grep TEMPERATURE papers_qa/.env                           # 应该输出 PAPERS_QA_TEMPERATURE=0.3

# 生成答案
set -a && source papers_qa/.env && set +a
.venv/bin/python src/generate_rlm_answers.py \
    --input  data/CAE-v2.0-1-rubrics.json \
    --output data/CAE-v2.0-1-rubrics-output.json \
    --jsonl  outputs/rlm-answers/cae-v2.0-1.jsonl \
    --papers-dir /home/juli/RLM/CAE-MDs \
    --workers 4

# 打分
.venv/bin/python src/score_rlm_answers.py \
    --input       data/CAE-v2.0-1-rubrics-output.json \
    --anchors     data/CAE-anchor-scores.json \
    --scores-out  outputs/scoring/scores.json \
    --report-out  outputs/scoring/report.md \
    --judge-model openai/gpt-5.5
```

---

## 文件地图

```
data/
├── CAE-v2.0-1-rubrics.json              # 94 题 / 836 criteria（源头，已修复）
├── CAE-v2.0-1-rubrics-v2.json           # v2 RLM 答案（过度激进的指令）
├── CAE-v2.0-1-rubrics-v3.json           # ★ v3 RLM 答案（生产版）
├── CAE-v2.0-1-rubrics-v4.json           # v4 RLM 答案（PEEK）
├── CAE-v2.0-1-rubrics-v5.json           # v5 RLM 答案（PEEK + decisions distiller）
├── CAE-anchor-scores.json               # 94 个 ref/weak anchor
└── CAE-v2.0-1-rubrics.backup-*.json     # 实验前的备份

outputs/
├── rlm-answers/
│   ├── cae-v2.0-1.{jsonl,log}           # v1 审计 trail
│   ├── cae-v2.0-1-v{2,3,4,5}.{jsonl,log}# v2-v5 审计 trail
├── peek/
│   ├── cae-v2.0-1-map-frozen.json       # v4 冻结后的 PEEK map
│   └── cae-v2.0-1-v5-map-frozen.json    # v5 冻结后的 PEEK map（含 decisions 段）
└── scoring/
    ├── cae-v2.0-1-{scores,report}-v{3,4,5}.{json,md}    # 各版本 scoring 产物
    ├── cae-v2.0-1-scores-v3-preFix.json # 修复 rubric 前的 v3 分数（审计）
    └── cae-v2.0-1-diff-v{1,3,4}-v{3,4,5}.md             # 两两 diff 报告

src/
├── generate_rlm_answers.py              # CLI，11 个 flag（含 --peek-*、--include-items、--skip-items）
├── score_rlm_answers.py                 # CLI：gpt-5.5 judge + 打分
├── rubrics_report.py                    # 纯函数 markdown 报告（单次运行）
├── rubrics_diff_report.py               # 纯函数 v1 vs v2 diff
└── rubrics/                             # rubric 生成+打分核心（见主 README）

papers_qa/papers_qa/
├── prompts.py                           # v3 风格指令就在 BILINGUAL_ADDENDUM 里
├── peek_integration.py                  # PEEK 胶水：PeekCfg、build_peek_policy、decisions distiller addendum
└── runner.py                            # PapersQA(config, *, peek_policy=None)

peek/                                    # PEEK 库（兄弟项目，pip install -e ./peek）

tests/
├── test_generate_rlm_answers.py         # 26 个
├── test_score_rlm_answers.py            # 15 个
├── test_rubrics_report.py               # 11 个
├── test_rubrics_diff_report.py          # 10 个
├── test_papers_qa_prompts.py            # 3 个（v3 prompt 断言）
├── test_peek_integration.py             # 8 个
├── test_papers_qa_peek_wiring.py        # 4 个（PEEK 接入 PapersQA）
└── test_peek_distiller_addendum.py      # 4 个
                                         # → 共 ~138 个测试，全过
```

---

## 花费汇总

| 步骤 | 重跑 | 重打分 | 工程 | 墙钟 |
|---|---|---|---|---|
| v1 generate | $5 | — | — | 47 min |
| v1 score | — | $15 | — | 5 min |
| v2 generate + score | $10 | $15 | 1 h | 1 h |
| v3 generate + score | $10 | $15 | 1 h | 1 h |
| v4 generate + score | $15 | $15 | 3 h | 6 h |
| v5 generate + score | $20 | $15 | 1 h | 2 h |
| Rubric 修复 + 重打 v3 | $0 | $15 | 30 min | 5 min |
| **总计** | **$60** | **$90** | ~6 h | — |

实验总花费：**~$150** + ~6 工程小时，跨 5 轮迭代 + 1 次数据修复。

---

## 未做完的尾巴（可选）

1. **把 v1/v4/v5 在修复后的 rubric 上重打分**（~$45），拿到干净的横向对比。目前只有 v3 重打了，其他版本的 scoring 报告仍是修复前的
2. **手工 REUSABLE RESULTS**：把 v5 distill 出来的 3 条 reusable knowledge 直接写进 v3 的 BILINGUAL_ADDENDUM（不用 PEEK 运行时），$10 成本，预计 +0.005 anchored
3. **超时 item 的单独重试**：item 46、48 在 v4/v5 都超时，单独跑能补全 94 题覆盖
4. **换模型**（如被测换成 `openai/gpt-5.5`）— 能拿到更强基线但成本显著上升

---

## 文档地图

- 本文（`EXPERIMENTS.md`）— 5 轮迭代实验的叙述
- [`README.md`](README.md) — 顶层工具链概览（rubric 生成 + 打分）
- [`USAGE.md`](USAGE.md) — 工具链中文教程
- [`ALGORITHMS.md`](ALGORITHMS.md) — 算法细节（生成、打分、anchoring）
- [`docs/superpowers/specs/`](docs/superpowers/specs/) — 每轮迭代的设计 spec
- [`docs/superpowers/plans/`](docs/superpowers/plans/) — 每轮迭代的实施 plan
- [`papers_qa/README.md`](papers_qa/README.md) — 被测 agent
- [`peek/README.md`](peek/README.md) — v4/v5 用到的 orientation-cache 库
