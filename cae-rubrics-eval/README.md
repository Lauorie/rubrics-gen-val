# cae-rubrics-eval

针对 CAE-v2.0-1（94 题中文 CAE/工程仿真专家 QA）的**独立打分工具包**。
你用任何算法（ReAct、CoT、纯 LLM、RAG、Agent…）生成答案，本包用 rubric + LLM judge 给你打分，并把分数归一化到与已有 RLM 实验直接可比的尺度。

打分原理与生成流程的完整设计见主仓库的 `ALGORITHMS.md` 与 `EXPERIMENTS.md`。本 README 只讲怎么用。



## 1. 快速开始（5 步）

```bash
# 1) 安装
cd cae-rubrics-eval
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e .

# 2) 配置 LLM 凭证
cp .env.example .env
# 编辑 .env，填入你的 LLM_API_KEY https://aiberm.com/v1

# 3) 在 94 题上跑你的算法，生成 predictions.jsonl（格式见 §3）

# 4) 打分
python score.py --predictions predictions.jsonl --out eval.json

# 5) 看结果
python -c "import json; print(json.dumps(json.load(open('eval.json'))['aggregate'], ensure_ascii=False, indent=2))"
```



## 2. 数据集：`data/CAE-v2.0-1-rubrics.json`

94 条 rubric，每条字段：

| 字段 | 含义 | 你跑算法时是否要读 |
|---|---|---|
| `item_idx` | 唯一 id，0–93 | **要**（写到你 predictions 里） |
| `question_id` | 原数据集 id（"1"…"94"），与 item_idx 不一定相等 | 参考 |
| `question` | 题目原文 | **要**（喂给你的模型） |
| `question_type` | 简答题/主观题/决策题/对比分析题/数值提取题/流程描述题/数值关系题 | 参考 |
| `difficulty` | 简单 / 中等 / 困难 | 参考 |
| `scenario` | 题目场景 | 参考 |
| `source` | 题目来源（教材+页码） | 参考 |
| `reference_answer` | **标准答案** | ⚠️ **不能喂给被评模型** |
| `criteria` | 打分细则 | ⚠️ **不能喂给被评模型** |
| `source_grounding` | RAG 检索元数据 | 评分内部用 |
| `rubric_metadata` | rubric 生成元数据 | 评分内部用 |

> ⚠️ **重要**：`reference_answer`、`criteria`、`source_grounding`、`rubric_metadata` 是评分系统的「金标准」和「打分细则」。**把它们直接喂进被评模型 = 作弊**，分数会失去意义。你的算法只能看 `question`（最多再加 `question_type`、`scenario`、`source` 作为类型提示）。

简化代码示例：

```python
import json
rubrics = json.load(open("data/CAE-v2.0-1-rubrics.json"))
for r in rubrics:
    answer = my_react_algorithm(r["question"])  # 只看 question
    save({"item_idx": r["item_idx"], "answer": answer})
```



## 3. Predictions 文件格式

JSONL（每行一个 JSON 对象）：

```jsonl
{"item_idx": 0, "answer": "在流固耦合中..."}
{"item_idx": 1, "answer": "..."}
...
```

- `item_idx`（**int**，必填）：从 `data/CAE-v2.0-1-rubrics.json` 里取，**不要写成 `question_id`**
- `answer`（**str**，必填）：你算法生成的答案
- 其他字段会被忽略（你可以塞自己的 trace、token 数、retrieval log 等）
- 漏掉某些 item_idx → 那几题不会被打分，aggregate 里 `n_predictions` 反映你实际提交了多少



## 4. 打分

```bash
python score.py \
    --predictions predictions.jsonl \
    --out eval.json \
    --concurrency 16
```

可选参数：
- `--rubrics PATH`：默认 `data/CAE-v2.0-1-rubrics.json`
- `--anchors PATH`：默认 `data/CAE-anchor-scores.json`
- `--concurrency N`：默认 16，越高越快但更容易撞 LLM 限流
- `--judge-model NAME`：**不推荐**。换 judge 模型会破坏与已有 RLM 实验的分数可比性（详见 §6）



## 5. 输出 `eval.json` 怎么看

```json
{
  "per_candidate": [
    {
      "item_idx": 0,
      "question_type": "主观题",
      "difficulty": "困难",
      "score": 0.78,
      "score_anchored": {
        "ref_score": 1.0,
        "weak_score": 0.0,
        "normalized": 0.78
      },
      "breakdown": [
        {"id": "c1", "text": "...", "category": "Essential", "weight": 5,
         "sign": "positive", "met": true, "contribution": 5, "reason": "..."}
      ]
    }
  ],
  "aggregate": {
    "n_predictions": 94,
    "n_scored_ok": 94,
    "n_errors": 0,
    "mean_score": 0.71,
    "mean_anchored": 0.62,
    "by_question_type": {},
    "by_difficulty": {},
    "by_criterion_type": {},
    "judge_model": "openai/gpt-5.4-mini",
    "rubric_version": "1.0"
  }
}
```

**主指标**：`aggregate.mean_anchored`。它把每道题的原始分按 `(score − weak_score) / (ref_score − weak_score)` 归一化，确保不同 rubric 的「自然天花板」差异不影响系统级对比。

`score` 是「这道题你拿到的原始权重比例」，`score_anchored.normalized` 是「相对 reference_answer 和 `我不知道。` 两个基准之间你处在哪个位置」。后者才是有意义的横向指标。

**什么时候看哪个**：

| 场景 | 看 |
|---|---|
| 单题 debug：「这条凭什么得 0.5？」 | **raw** + 该 item 的 `breakdown`（哪条 criterion met/unmet） |
| 跨系统横向对比（你的 ReAct vs 历史 RLM） | **anchored** |
| 论文 / 报告里的 headline 数字 | **anchored** |
| 检查 rubric 自身质量 | 看 `data/CAE-anchor-scores.json` 里 `ref_score` 分布——大量 < 0.8 说明 rubric 写得过严，不是候选差 |
| `score_anchored.normalized == null` 的 item | 只能看 **raw**——那条 rubric 的 `ref_score ≤ weak_score`，归一化失效，建议不要纳入横向统计 |

简单记：**「我系统行不行」用 anchored，「这道题为啥这么打」用 raw + breakdown**。

为什么 anchored 不冗余：judge 是 LLM、有随机性，`reference_answer` 在自己 rubric 上的 `ref_score` 经常不是 1.0（落在 0.85–0.95 居多），不同 rubric 的「自然天花板」也不一致；anchored 把每条 rubric 的实际区间 `[weak, ref]` 拉成 `[0,1]`，让 94 题求平均才有意义。



## 6. 打分原理（一段话）

- **rubric** = 加权二值清单：每个 criterion 有 `category ∈ {Essential, Important, Optional, Pitfall}`、`weight ∈ [1,8]`、`sign ∈ {positive, negative}`
- **judge** = 用 LLM 逐条判断「这个 candidate answer 是否满足该 criterion」
- **score** = `(Σ w_i · met_i [positive] − Σ w_i · met_i [pitfall]) / Σ w_i [positive_max]`，clip 到 `[0,1]`
- **anchor 归一化** = `(score − weak_score) / (ref_score − weak_score)`，其中 `ref_score` = 用同样 rubric 给 reference_answer 打分得到的分数（≈1.0），`weak_score` = 用同样 rubric 给 `"我不知道。"` 打分得到的分数（≈0.0）

anchor 分数预先算好放在 `data/CAE-anchor-scores.json`，**判别模型固定为 `openai/gpt-5.4-mini`**。换 judge 必须重算 anchor，否则归一化分会偏。



## 7. 成本与时长

| 阶段 | LLM 调用数 | 估算成本 (gpt-5.4-mini) | 时长 (concurrency=16) |
|---|---|---|---|
| 打分 94 题 | 94 题 × 平均 8.9 条 criterion ≈ 836 calls | ≲ $0.5 | 5–10 分钟 |
| 重算 anchor（不推荐） | 94 × 2 答案 × 8.9 ≈ 1672 calls | ≲ $1 | ~10 分钟 |

`anchor` 已经预算好，正常使用只会触发「打分 94 题」那一行。



## 8. 常见问题

**Q: 我写错了，把 `question_id` 当成 `item_idx` 了**
→ `score.py` 会跑完但所有 `item_idx` 都对不上 rubric，输出里全是 `error: no rubric found for item_idx=X`。改成正确字段即可。`question_id` 是字符串 `"1"`–`"94"`，`item_idx` 是整数 `0`–`93`。

**Q: LLM 限流了**
→ `score.py` 用 tenacity 自动重试 3 次（指数退避 1–8s）。还是失败的话单条 criterion 会在 `breakdown` 里挂一个 `error` 字段但不影响其他条目。可以降 `--concurrency`，从 16 降到 4。

**Q: 我想换 judge 模型**
→ 不推荐。如果非换不可：

```bash
# 1) 删掉旧 anchor 缓存
rm data/CAE-anchor-scores.json
# 2) 用新模型重跑（脚本会自动重算 anchor 再开始打分）
python score.py --predictions preds.jsonl --out eval.json --judge-model your/model
```

但要清楚：你的 `mean_anchored` 不再能和我们用 `openai/gpt-5.4-mini` 跑的历史结果直接对比。

**Q: 我中途断了**
→ 重新跑 `python score.py ...` 即可，anchor cache 是命中复用的，不会重复消耗。`per_candidate` 不支持断点续传——重跑会重新打分所有 item。如果你的预算紧，预先把 predictions 分成两份分别跑、输出两个 eval.json 自己合并。

**Q: 一些 item 的 `score_anchored.normalized` 是 null**
→ 那条 rubric 的 `ref_score <= weak_score`，说明 rubric 可能有问题或者 reference 太弱。breakdown 里会有 `warning` 字段。这种 item 仅在 `score`（原始分）层面比较即可。



## 9. 包结构

```
cae-rubrics-eval/
├── README.md                          # 本文件
├── pyproject.toml
├── .env.example
├── score.py                           # CLI 入口
├── cae_eval/                          # Python 包
│   ├── schema.py                      # pydantic 模型
│   ├── scoring.py                     # 评分公式
│   ├── llm_client.py                  # OpenAI-compatible HTTP 客户端
│   ├── judge.py                       # 单 criterion judge
│   ├── anchor.py                      # ref/weak anchor 缓存
│   ├── scorer.py                      # 异步批量打分
│   ├── aggregate.py                   # 汇总报告
│   └── templates/
│       └── misalignment_judge_prompt.txt
├── data/
│   ├── CAE-v2.0-1-rubrics.json        # 94 条 rubric（rlm_answer 已剥除）
│   └── CAE-anchor-scores.json         # 94 条 anchor（gpt-5.4-mini 跑出来的）
└── examples/
    ├── predictions_example.jsonl      # 3 条示例：好答案 / "我不知道。" / 离题废话
    └── eval_example.json              # 用上面跑出来的 eval 报告，给你对照输出格式
```



## License

代码 MIT，rubric 数据用于研究目的。
