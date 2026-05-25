# RLM 评测结果对比报告 (v1 vs v2)

- v1: `outputs/scoring/cae-v2.0-1-scores-v3.json`
- v2: `outputs/scoring/cae-v2.0-1-scores-v4.json`
- 生成时间: 2026-05-25T17:27:50.141102+00:00
- 共 92 项可对比
- 在 v1 但不在 v2: 2 项 (item_idx=[46, 48])

## 1. 总体得分对比

| 指标 | v1 | v2 | Δ |
|---|---|---|---|
| 平均原始分 (raw) | 0.70 | 0.70 | −0.01 |
| 平均锚定分 (anchored) | 0.71 | 0.71 | −0.01 |

## 2. Pitfall 触发对比

（按 v1+v2 总触发次数降序）

| pitfall | v1 触发 | v2 触发 | Δ |
|---|---|---|---|
| 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复 | 14 | 15 | +1 |
| 给出多个 | 3 | 5 | +2 |
| 回答以套话/开场白/元评论开头而无实质内容 | 5 | 1 | −4 |

## 3. 按 criterion_type 命中率对比

（仅 sign=positive；Δ 单位为百分点 pp）

| criterion_type | v1 命中率 | v2 命中率 | Δ (pp) |
|---|---|---|---|
| comparative_balance | 71.1% (27/38) | 57.1% (20/35) | −13.9 |
| decision_logic | 67.2% (43/64) | 71.9% (46/64) | +4.7 |
| factual_anchor | 73.9% (212/287) | 70.7% (198/280) | −3.2 |
| mechanism_explanation | 67.7% (113/167) | 72.0% (118/164) | +4.3 |
| numeric_precision | 84.6% (22/26) | 80.8% (21/26) | −3.8 |
| process_completeness | 77.8% (21/27) | 84.6% (22/26) | +6.8 |

## 4. 按题型分组对比 (mean anchored)

| 题型 | v1 数量 | v1 anchored | v2 数量 | v2 anchored | Δ |
|---|---|---|---|---|---|
| 主观题 | 20 | 0.63 | 20 | 0.66 | +0.03 |
| 决策题 | 18 | 0.62 | 18 | 0.66 | +0.03 |
| 对比分析题 | 3 | 0.90 | 2 | 0.84 | −0.06 |
| 数值关系题 | 1 | 0.86 | 1 | 1.00 | +0.14 |
| 数值提取题 | 2 | 0.95 | 2 | 0.95 | +0.00 |
| 流程描述题 | 2 | 0.87 | 2 | 1.00 | +0.13 |
| 简答题 | 48 | 0.75 | 47 | 0.71 | −0.04 |

## 5. Top winners (按 anchored Δ 降序)


### item_idx=11  Δ=+1.00 (v1 anchored=0.00 → v2 anchored=1.00)

**问题**: 为什么在水下爆炸仿真中需要引入“人工体积粘性”？其对冲击波波头处理有何作用？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 明确指出水下爆炸中的冲击波属于强间断问题
- [Essential, factual_anchor, w=5] 指出不引入人工体积粘性时，间断界面附近会出现剧烈振荡
- [Important, mechanism_explanation, w=3] 说明人工体积粘性会将冲击波的强间断模糊化
- [Important, numeric_precision, w=3] 说明被模糊化后的冲击波会在几个网格宽度内演变为急剧变化但连续的区域
- [Important, mechanism_explanation, w=3] 说明引入人工体积粘性的目的之一是克服微分方程组在波阵面处的求解困难
- [Optional, process_completeness, w=1] 回答同时覆盖“为什么需要引入”和“其对冲击波波头处理的作用”两部分

### item_idx=85  Δ=+0.87 (v1 anchored=0.00 → v2 anchored=0.87)

**问题**: 若需要模拟潜艇在大范围水域中的远场抗震性，且计算资源极其紧张，应决定采用哪种建模方式？


**翻转的 criteria (❌→✅):**

- [Essential, decision_logic, w=6] 明确给出最终建模方式是 USA（Underwater Shock Analysis）代码联用
- [Essential, factual_anchor, w=5] 指出 USA 基于边界元法（BEM）
- [Essential, mechanism_explanation, w=5] 说明 USA 无需建立庞大的水域有限元模型
- [Essential, decision_logic, w=5] 指出 USA 可作为需要建模大量水体时的替代方案
- [Essential, decision_logic, w=5] 指出在不建水域模型时，计算时间可减少至少一个数量级

### item_idx=91  Δ=+0.48 (v1 anchored=0.35 → v2 anchored=0.84)

**问题**: 若在罚函数耦合分析中发现流体大量“穿透”结构表面，但整体位移趋势正确，应如何调整参数？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 指出罚函数力与穿透深度成比例
- [Essential, mechanism_explanation, w=5] 说明增大刚度系数会增大回复力
- [Essential, mechanism_explanation, w=5] 说明增大的回复力用于把流体节点推回界面或结构表面

### item_idx=92  Δ=+0.44 (v1 anchored=0.09 → v2 anchored=0.53)

**问题**: 在处理包含大型柔性瓣膜（如主动脉瓣）的流固耦合问题时，当瓣膜产生极大转动或位移，应如何决策网格更新？


**翻转的 criteria (❌→✅):**

- [Essential, decision_logic, w=6] 明确给出最终决策为局部或全局重构网格（Re-meshing）
- [Essential, mechanism_explanation, w=5] 指出通过重映射（Remap）保证变量连续

### item_idx=44  Δ=+0.43 (v1 anchored=0.35 → v2 anchored=0.78)

**问题**: “Zalesak’s Problem”（开槽圆盘旋转）在数值算法测试中主要用来评估什么性能？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 明确指出 Zalesak’s Problem 主要用于评估界面追踪算法
- [Essential, factual_anchor, w=5] 提到 Level Set 作为该问题关注的界面追踪方法示例

## 6. Top losers (按 anchored Δ 升序)


### item_idx=21  Δ=−0.69 (v1 anchored=0.69 → v2 anchored=0.00)

**问题**: 鱼雷壳体在遭受侧向冲击时，为什么最大等效应变点往往不在正对爆心的位置？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 指出内部构件（如燃料、炸药）的分布会改变局部惯性
- [Essential, factual_anchor, w=5] 指出内部装填炸药会提高该舱段的抗冲击能力
- [Essential, factual_anchor, w=5] 指出等效应变会向构件边缘或隔板处转移
- [Important, comparative_balance, w=3] 指出在相同冲击波载荷下，不同舱室的动态响应会不同

### item_idx=52  Δ=−0.65 (v1 anchored=0.65 → v2 anchored=0.00)

**问题**: 为什么在包含复杂舱室的MM-ALE（多物质ALE）仿真中需要定义“真空（Vacuum）”？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 指出在多物质网格中，复杂舱室的空腔部分通常定义为 vacuum
- [Important, mechanism_explanation, w=3] 说明若不定义 vacuum，不相容材料可能在同一时间步内强行占据同一网格，从而引发压力异常升高
- [Important, mechanism_explanation, w=3] 导致计算不稳定

### item_idx=27  Δ=−0.62 (v1 anchored=1.00 → v2 anchored=0.38)

**问题**: 对于混合元素（多物质单元），如果包含极硬和极软材料，应采取什么策略防止硬材料被过度压缩？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 指出真空消失后，剩余压缩量才分配给其他材料
- [Essential, factual_anchor, w=5] 提到可以删除极小碎片以提高计算效率
- [Important, mechanism_explanation, w=3] 解释“先压缩真空、后分配给其他材料”的顺序能够避免极硬材料过度压缩

### item_idx=13  Δ=−0.50 (v1 anchored=0.77 → v2 anchored=0.27)

**问题**: 什么是“等效质量法”？其核心计算逻辑是什么？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 指出等效质量法是针对 LS-DYNA 计算远场水下爆炸时冲击波衰减过快而提出的修正方法
- [Essential, factual_anchor, w=5] 说明仿真中使用的是比实际炸药量更大的模拟质量
- [Important, mechanism_explanation, w=3] 说明该方法用来弥补粗网格导致的数值耗散或冲击波峰值衰减过快

### item_idx=65  Δ=−0.42 (v1 anchored=1.00 → v2 anchored=0.58)

**问题**: 水下爆炸的理论解析法在应用中存在哪些局限性？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 指出水下爆炸理论解析法主要用于分析规则结构的响应和破坏
- [Essential, factual_anchor, w=5] 指出即使是简单结构也需要大量简化
- [Important, mechanism_explanation, w=3] 指出理论解析法通常只能在定性层面进行分析
