# RLM 评测结果对比报告 (v1 vs v2)

- v1: `outputs/scoring/cae-v2.0-1-scores.json`
- v2: `outputs/scoring/cae-v2.0-1-scores-v4.json`
- 生成时间: 2026-05-25T17:27:50.017961+00:00
- 共 92 项可对比
- 在 v1 但不在 v2: 2 项 (item_idx=[46, 48])

## 1. 总体得分对比

| 指标 | v1 | v2 | Δ |
|---|---|---|---|
| 平均原始分 (raw) | 0.69 | 0.70 | +0.01 |
| 平均锚定分 (anchored) | 0.70 | 0.71 | +0.01 |

## 2. Pitfall 触发对比

（按 v1+v2 总触发次数降序）

| pitfall | v1 触发 | v2 触发 | Δ |
|---|---|---|---|
| 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复 | 31 | 15 | −16 |
| 回答以套话/开场白/元评论开头而无实质内容 | 12 | 1 | −11 |
| 给出多个 | 4 | 5 | +1 |

## 3. 按 criterion_type 命中率对比

（仅 sign=positive；Δ 单位为百分点 pp）

| criterion_type | v1 命中率 | v2 命中率 | Δ (pp) |
|---|---|---|---|
| comparative_balance | 47.4% (18/38) | 57.1% (20/35) | +9.8 |
| decision_logic | 81.2% (52/64) | 71.9% (46/64) | −9.4 |
| factual_anchor | 73.9% (212/287) | 70.7% (198/280) | −3.2 |
| mechanism_explanation | 72.5% (121/167) | 72.0% (118/164) | −0.5 |
| numeric_precision | 84.6% (22/26) | 80.8% (21/26) | −3.8 |
| process_completeness | 81.5% (22/27) | 84.6% (22/26) | +3.1 |

## 4. 按题型分组对比 (mean anchored)

| 题型 | v1 数量 | v1 anchored | v2 数量 | v2 anchored | Δ |
|---|---|---|---|---|---|
| 主观题 | 20 | 0.63 | 20 | 0.66 | +0.02 |
| 决策题 | 18 | 0.66 | 18 | 0.66 | −0.01 |
| 对比分析题 | 3 | 0.52 | 2 | 0.84 | +0.32 |
| 数值关系题 | 1 | 1.00 | 1 | 1.00 | +0.00 |
| 数值提取题 | 2 | 0.89 | 2 | 0.95 | +0.05 |
| 流程描述题 | 2 | 0.87 | 2 | 1.00 | +0.13 |
| 简答题 | 48 | 0.73 | 47 | 0.71 | −0.02 |

## 5. Top winners (按 anchored Δ 降序)


### item_idx=56  Δ=+0.83 (v1 anchored=0.00 → v2 anchored=0.83)

**问题**: 混合理论（Mixture theories）中，平均应变率理论与平均应力理论在能量守恒和物理响应上有何区别？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 明确指出平均应变率混合理论可以精确守恒能量
- [Essential, factual_anchor, w=5] 明确指出平均应力理论不能保证能量守恒
- [Important, mechanism_explanation, w=3] 指出平均应变率理论在含真空的单元中存在缺陷
- [Important, mechanism_explanation, w=3] 指出平均应变率理论无法完全压缩出真空
- [Important, mechanism_explanation, w=3] 指出平均应变率理论的响应可能过硬
- [Important, mechanism_explanation, w=3] 指出平均应力理论会自动优先压缩软物质（如真空），从而避免无限大压力风险
- [Important, factual_anchor, w=3] 指出在钢和真空的混合单元中，钢的应力始终为零

### item_idx=32  Δ=+0.50 (v1 anchored=0.50 → v2 anchored=1.00)

**问题**: 水下爆炸冲击波在远场传播时，为什么可以采用“声学近似”？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 指出传播速度逐渐减小
- [Essential, factual_anchor, w=5] 指出压力分布满足声波的基本线性叠加规律

### item_idx=44  Δ=+0.43 (v1 anchored=0.35 → v2 anchored=0.78)

**问题**: “Zalesak’s Problem”（开槽圆盘旋转）在数值算法测试中主要用来评估什么性能？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 明确指出 Zalesak’s Problem 主要用于评估界面追踪算法
- [Essential, factual_anchor, w=5] 提到 Level Set 作为该问题关注的界面追踪方法示例

### item_idx=49  Δ=+0.42 (v1 anchored=0.19 → v2 anchored=0.62)

**问题**: 在进行远场水下爆炸仿真时，使用“2D到3D映射（Mapping）”技术的主要优势是什么？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 回答明确指出该方法避免了直接建立全尺度 3D 流体网格
- [Important, mechanism_explanation, w=3] 解释 2D-ALE 到 3D 的映射能更好描述冲击波的球面扩散或球形传播
- [Important, mechanism_explanation, w=3] 解释效率提升来自只需计算 2D 源场而不必对整个 3D 水域进行离散建模

### item_idx=84  Δ=+0.41 (v1 anchored=0.19 → v2 anchored=0.59)

**问题**: 在罚函数耦合算法中，若出现流体“穿透（Leakage）”结构的现象，应如何调整参数？


**翻转的 criteria (❌→✅):**

- [Essential, decision_logic, w=6] 明确给出最终调整方向是提高罚函数刚度系数 k
- [Essential, mechanism_explanation, w=5] 说明增大 k 会增大界面罚函数力
- [Important, mechanism_explanation, w=3] 说明更大的界面力可将流体节点推回结构界面

## 6. Top losers (按 anchored Δ 升序)


### item_idx=21  Δ=−0.69 (v1 anchored=0.69 → v2 anchored=0.00)

**问题**: 鱼雷壳体在遭受侧向冲击时，为什么最大等效应变点往往不在正对爆心的位置？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 指出内部构件（如燃料、炸药）的分布会改变局部惯性
- [Essential, factual_anchor, w=5] 指出内部装填炸药会提高该舱段的抗冲击能力
- [Essential, factual_anchor, w=5] 指出等效应变会向构件边缘或隔板处转移
- [Important, comparative_balance, w=3] 指出在相同冲击波载荷下，不同舱室的动态响应会不同

### item_idx=61  Δ=−0.66 (v1 anchored=0.81 → v2 anchored=0.16)

**问题**: 在使用ABAQUS程序模拟水下爆炸时，其主要特点和局限性是什么？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 明确指出 ABAQUS 是把经验公式或试验得到的水下爆炸载荷直接施加到结构上，而不是由程序自行求爆轰载荷
- [Essential, factual_anchor, w=5] 明确指出 ABAQUS 不计算载荷传播过程
- [Essential, factual_anchor, w=5] 明确指出计算模型中不包含炸药，只包含结构及其周围流场
- [Important, factual_anchor, w=3] 提到 ABAQUS 的 Standard 与 Explicit 两个主模块
- [Important, mechanism_explanation, w=3] 解释省略爆轰计算步骤和炸药模型是计算速度快的原因

### item_idx=27  Δ=−0.62 (v1 anchored=1.00 → v2 anchored=0.38)

**问题**: 对于混合元素（多物质单元），如果包含极硬和极软材料，应采取什么策略防止硬材料被过度压缩？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 指出真空消失后，剩余压缩量才分配给其他材料
- [Essential, factual_anchor, w=5] 提到可以删除极小碎片以提高计算效率
- [Important, mechanism_explanation, w=3] 解释“先压缩真空、后分配给其他材料”的顺序能够避免极硬材料过度压缩

### item_idx=52  Δ=−0.53 (v1 anchored=0.53 → v2 anchored=0.00)

**问题**: 为什么在包含复杂舱室的MM-ALE（多物质ALE）仿真中需要定义“真空（Vacuum）”？


**翻转的 criteria (✅→❌):**

- [Important, mechanism_explanation, w=3] 说明 vacuum 提供了可供其他材料输运和充填的空间
- [Important, mechanism_explanation, w=3] 说明受冲击后的水流或结构碎片可以进入该 vacuum 区域
- [Important, mechanism_explanation, w=3] 导致计算不稳定

### item_idx=14  Δ=−0.48 (v1 anchored=0.97 → v2 anchored=0.48)

**问题**: 在HJC本构模型中，混凝土的损伤（Damage）主要来源于什么？其演化过程如何描述？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 指出 HJC 本构模型中混凝土损伤主要源自塑性体积应变
- [Essential, numeric_precision, w=5] 指出损伤度 D 的取值范围为 0 到 1
- [Important, mechanism_explanation, w=3] 说明材料凝聚力丧失与损伤演化相关
- [Important, mechanism_explanation, w=3] 说明损伤度 D 从 0（完整）向 1（破碎）演化
