# RLM 评测结果对比报告 (v1 vs v2)

- v1: `outputs/scoring/cae-v2.0-1-scores.json`
- v2: `outputs/scoring/cae-v2.0-1-scores-v5.json`
- 生成时间: 2026-05-26T03:49:23.913369+00:00
- 共 92 项可对比
- 在 v1 但不在 v2: 2 项 (item_idx=[46, 48])

## 1. 总体得分对比

| 指标 | v1 | v2 | Δ |
|---|---|---|---|
| 平均原始分 (raw) | 0.69 | 0.68 | −0.01 |
| 平均锚定分 (anchored) | 0.70 | 0.69 | −0.01 |

## 2. Pitfall 触发对比

（按 v1+v2 总触发次数降序）

| pitfall | v1 触发 | v2 触发 | Δ |
|---|---|---|---|
| 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复 | 31 | 19 | −12 |
| 回答以套话/开场白/元评论开头而无实质内容 | 12 | 10 | −2 |
| 给出多个 | 4 | 5 | +1 |

## 3. 按 criterion_type 命中率对比

（仅 sign=positive；Δ 单位为百分点 pp）

| criterion_type | v1 命中率 | v2 命中率 | Δ (pp) |
|---|---|---|---|
| comparative_balance | 47.4% (18/38) | 60.0% (21/35) | +12.6 |
| decision_logic | 81.2% (52/64) | 78.1% (50/64) | −3.1 |
| factual_anchor | 73.9% (212/287) | 70.0% (196/280) | −3.9 |
| mechanism_explanation | 72.5% (121/167) | 75.0% (123/164) | +2.5 |
| numeric_precision | 84.6% (22/26) | 80.8% (21/26) | −3.8 |
| process_completeness | 81.5% (22/27) | 88.5% (23/26) | +7.0 |

## 4. 按题型分组对比 (mean anchored)

| 题型 | v1 数量 | v1 anchored | v2 数量 | v2 anchored | Δ |
|---|---|---|---|---|---|
| 主观题 | 20 | 0.63 | 20 | 0.76 | +0.13 |
| 决策题 | 18 | 0.66 | 18 | 0.68 | +0.02 |
| 对比分析题 | 3 | 0.52 | 2 | 0.91 | +0.39 |
| 数值关系题 | 1 | 1.00 | 1 | 1.00 | +0.00 |
| 数值提取题 | 2 | 0.89 | 2 | 0.89 | +0.00 |
| 流程描述题 | 2 | 0.87 | 2 | 0.93 | +0.07 |
| 简答题 | 48 | 0.73 | 47 | 0.64 | −0.09 |

## 5. Top winners (按 anchored Δ 降序)


### item_idx=56  Δ=+0.87 (v1 anchored=0.00 → v2 anchored=0.87)

**问题**: 混合理论（Mixture theories）中，平均应变率理论与平均应力理论在能量守恒和物理响应上有何区别？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 明确指出平均应变率混合理论可以精确守恒能量
- [Essential, factual_anchor, w=5] 明确指出平均应力理论不能保证能量守恒
- [Essential, factual_anchor, w=5] 指出部分代码会按质量权重分配功来消除平均应力理论的能量不一致性
- [Important, mechanism_explanation, w=3] 指出平均应变率理论在含真空的单元中存在缺陷
- [Important, mechanism_explanation, w=3] 指出平均应变率理论无法完全压缩出真空
- [Important, mechanism_explanation, w=3] 指出平均应变率理论的响应可能过硬
- [Important, mechanism_explanation, w=3] 指出平均应力理论会自动优先压缩软物质（如真空），从而避免无限大压力风险
- [Important, factual_anchor, w=3] 指出在钢和真空的混合单元中，钢的应力始终为零

### item_idx=67  Δ=+0.63 (v1 anchored=0.00 → v2 anchored=0.63)

**问题**: 在对鱼雷进行水下爆炸模拟时，为何必须考虑其内部构件？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 明确指出鱼雷内部构件包括大质量构件，例如战斗部或燃料
- [Essential, factual_anchor, w=5] 指出这些内部大质量构件在水下爆炸作用下会产生惯性效应
- [Important, mechanism_explanation, w=3] 说明内部填充物或内部构件能够减小壳体变形
- [Important, mechanism_explanation, w=3] 说明不考虑鱼雷内部构件会使模拟出的毁伤程度显著降低
- [Important, mechanism_explanation, w=3] 说明不考虑鱼雷内部构件会使毁伤区域分布发生错误

### item_idx=84  Δ=+0.56 (v1 anchored=0.19 → v2 anchored=0.74)

**问题**: 在罚函数耦合算法中，若出现流体“穿透（Leakage）”结构的现象，应如何调整参数？


**翻转的 criteria (❌→✅):**

- [Essential, decision_logic, w=6] 明确给出最终调整方向是提高罚函数刚度系数 k
- [Essential, mechanism_explanation, w=5] 说明增大 k 会增大界面罚函数力
- [Essential, decision_logic, w=4] 指出 k 过大可能导致数值震荡

### item_idx=47  Δ=+0.48 (v1 anchored=0.52 → v2 anchored=1.00)

**问题**: 在处理流体粒子位移时，为什么“Adams-Bashforth”方案比一阶显式欧拉法更优？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 明确指出 Adams-Bashforth 是二阶多步法
- [Essential, factual_anchor, w=5] 明确指出 Adams-Bashforth 适用于长路径流体追踪

### item_idx=0  Δ=+0.39 (v1 anchored=0.52 → v2 anchored=0.90)

**问题**: 在流固耦合（FSI）仿真中，“附加质量效应”为何会导致数值不稳定？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 指出分区方法在结构域计算时使用的是上一迭代步的压力
- [Important, mechanism_explanation, w=3] 解释上一迭代步压力会在流体-结构耦合中引入压力滞后
- [Important, mechanism_explanation, w=3] 解释这种压力滞后会在强耦合条件下放大误差
- [Optional, comparative_balance, w=1] 比较时明确把 monolithic 方法作为 added-mass 显著时比分区/松散耦合更稳的选择

## 6. Top losers (按 anchored Δ 升序)


### item_idx=34  Δ=−1.00 (v1 anchored=1.00 → v2 anchored=0.00)

**问题**: 在多物质ALE（MM-ALE）单元中，处理界面重建（Interface Reconstruction）的三种基本策略是什么？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 明确列出 MM-ALE 中界面重建的三种基本策略为 Lagrangian、Level Set、VOF
- [Essential, factual_anchor, w=5] 指出 Lagrangian 方法使用粒子和线段连接来表示界面
- [Essential, factual_anchor, w=5] 指出 Level Set 方法通过零等值面函数定义界面
- [Essential, factual_anchor, w=5] 指出 VOF 方法是基于各物质体积分数构造界面
- [Important, comparative_balance, w=3] 明确区分 Level Set 的零等值面函数表示与 VOF 的体积分数表示

### item_idx=36  Δ=−1.00 (v1 anchored=1.00 → v2 anchored=0.00)

**问题**: 在ALE算法中，“一致性条件（Consistency Condition）”对于速度场的输运有何要求？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 明确指出一致性条件要求：在输运/Advection 后，速度场仍保持均匀
- [Essential, factual_anchor, w=5] 明确指出初始状态可以是“均匀速度场 + 空间变化的密度”
- [Essential, factual_anchor, w=5] 明确指出输运后速度场应保持“不变”
- [Essential, factual_anchor, w=5] 明确指出密度的空间变化不应改变速度场的均匀性
- [Important, mechanism_explanation, w=3] 解释一致性条件的作用是避免输运步骤引入虚假的速度梯度或速度变化

### item_idx=28  Δ=−0.88 (v1 anchored=0.88 → v2 anchored=0.00)

**问题**: 什么是输运算法中的“一致性条件（Consistency Condition）”？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 指出输运前物体具有均匀的速度场
- [Essential, factual_anchor, w=5] 指出输运前密度在空间上变化
- [Essential, factual_anchor, w=5] 指出输运后速度场应保持均匀且不变
- [Essential, factual_anchor, w=5] 指出该条件用于保证动量输运与质量输运在逻辑上的匹配
- [Important, mechanism_explanation, w=3] 解释其含义是：当仅密度发生空间变化时，输运过程不应引入速度场的非均匀性
- [Important, mechanism_explanation, w=3] 说明一致性条件约束的是质量重分布后速度场仍保持原有均匀状态，而不是让速度随密度变化而改变

### item_idx=87  Δ=−0.86 (v1 anchored=0.86 → v2 anchored=0.00)

**问题**: 在执行ALE的Advection（输运）阶段时，若追求在不产生非物理极值的前提下获得最高精度，应选择哪种算法？


**翻转的 criteria (✅→❌):**

- [Essential, decision_logic, w=6] 明确给出最终选择是 MUSCL 算法
- [Essential, decision_logic, w=5] 说明在追求最高精度时，MUSCL 因为提供二阶精度而优先于低阶输运格式
- [Essential, decision_logic, w=5] 说明 MUSCL 的单调限幅器用于抑制数值震荡或非物理极值
- [Important, factual_anchor, w=3] 指出 MUSCL 采用线性逼近
- [Important, comparative_balance, w=3] 比较 MUSCL 与 Donor Cell 时，说明 MUSCL 更能捕捉梯度

### item_idx=7  Δ=−0.83 (v1 anchored=0.83 → v2 anchored=0.00)

**问题**: 什么是“等效质量法”？它解决的是LS-DYNA在模拟中的什么问题？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 指出 LS-DYNA 在远场水下爆炸中计算得到的比冲量衰减过快
- [Essential, factual_anchor, w=5] 说明等效质量是由爆距处冲击波峰值压力的经验公式反推得到的炸药质量
- [Essential, factual_anchor, w=5] 说明模拟时使用较大的模拟质量来代替较小的实际质量
- [Important, mechanism_explanation, w=3] 说明该方法通过调整模拟质量来实现特定爆距处的冲击波载荷
