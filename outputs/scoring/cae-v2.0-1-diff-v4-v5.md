# RLM 评测结果对比报告 (v1 vs v2)

- v1: `outputs/scoring/cae-v2.0-1-scores-v4.json`
- v2: `outputs/scoring/cae-v2.0-1-scores-v5.json`
- 生成时间: 2026-05-26T03:49:24.126311+00:00
- 共 92 项可对比

## 1. 总体得分对比

| 指标 | v1 | v2 | Δ |
|---|---|---|---|
| 平均原始分 (raw) | 0.70 | 0.68 | −0.02 |
| 平均锚定分 (anchored) | 0.71 | 0.69 | −0.01 |

## 2. Pitfall 触发对比

（按 v1+v2 总触发次数降序）

| pitfall | v1 触发 | v2 触发 | Δ |
|---|---|---|---|
| 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复 | 15 | 19 | +4 |
| 回答以套话/开场白/元评论开头而无实质内容 | 1 | 10 | +9 |
| 给出多个 | 5 | 5 | 0 |

## 3. 按 criterion_type 命中率对比

（仅 sign=positive；Δ 单位为百分点 pp）

| criterion_type | v1 命中率 | v2 命中率 | Δ (pp) |
|---|---|---|---|
| comparative_balance | 57.1% (20/35) | 60.0% (21/35) | +2.9 |
| decision_logic | 71.9% (46/64) | 78.1% (50/64) | +6.2 |
| factual_anchor | 70.7% (198/280) | 70.0% (196/280) | −0.7 |
| mechanism_explanation | 72.0% (118/164) | 75.0% (123/164) | +3.0 |
| numeric_precision | 80.8% (21/26) | 80.8% (21/26) | +0.0 |
| process_completeness | 84.6% (22/26) | 88.5% (23/26) | +3.8 |

## 4. 按题型分组对比 (mean anchored)

| 题型 | v1 数量 | v1 anchored | v2 数量 | v2 anchored | Δ |
|---|---|---|---|---|---|
| 主观题 | 20 | 0.66 | 20 | 0.76 | +0.10 |
| 决策题 | 18 | 0.66 | 18 | 0.68 | +0.03 |
| 对比分析题 | 2 | 0.84 | 2 | 0.91 | +0.06 |
| 数值关系题 | 1 | 1.00 | 1 | 1.00 | +0.00 |
| 数值提取题 | 2 | 0.95 | 2 | 0.89 | −0.05 |
| 流程描述题 | 2 | 1.00 | 2 | 0.93 | −0.07 |
| 简答题 | 47 | 0.71 | 47 | 0.64 | −0.08 |

## 5. Top winners (按 anchored Δ 降序)


### item_idx=52  Δ=+0.71 (v1 anchored=0.00 → v2 anchored=0.71)

**问题**: 为什么在包含复杂舱室的MM-ALE（多物质ALE）仿真中需要定义“真空（Vacuum）”？


**翻转的 criteria (❌→✅):**

- [Important, mechanism_explanation, w=3] 说明 vacuum 提供了可供其他材料输运和充填的空间
- [Important, mechanism_explanation, w=3] 说明受冲击后的水流或结构碎片可以进入该 vacuum 区域
- [Important, mechanism_explanation, w=3] 说明若不定义 vacuum，不相容材料可能在同一时间步内强行占据同一网格，从而引发压力异常升高
- [Important, mechanism_explanation, w=3] 导致计算不稳定

### item_idx=61  Δ=+0.69 (v1 anchored=0.16 → v2 anchored=0.84)

**问题**: 在使用ABAQUS程序模拟水下爆炸时，其主要特点和局限性是什么？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 明确指出 ABAQUS 是把经验公式或试验得到的水下爆炸载荷直接施加到结构上，而不是由程序自行求爆轰载荷
- [Essential, factual_anchor, w=5] 明确指出 ABAQUS 不计算载荷传播过程
- [Important, factual_anchor, w=3] 提到 ABAQUS 的 Standard 与 Explicit 两个主模块
- [Important, process_completeness, w=3] 提到 Standard 与 Explicit 之间可以进行结果传递
- [Important, process_completeness, w=3] 提到 ABAQUS 会自动计算结构的动态响应与流场压力分布
- [Important, mechanism_explanation, w=3] 解释省略爆轰计算步骤和炸药模型是计算速度快的原因

### item_idx=78  Δ=+0.68 (v1 anchored=0.24 → v2 anchored=0.91)

**问题**: 在模拟炸药爆轰瞬间的大变形流体运动时，如果计算频繁报错“负体积（Negative Volume）”，应如何调整建模描述方式？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 指出 Lagrangian 描述中网格随材料运动
- [Essential, mechanism_explanation, w=5] 指出大变形会使网格畸变，Jacobian 变为负，从而触发 Negative Volume
- [Essential, mechanism_explanation, w=5] 指出 Eulerian 描述中网格固定、材料在网格间输运
- [Essential, decision_logic, w=5] 明确说明不应继续使用纯 Lagrangian 作为该问题的建模描述方式
- [Important, comparative_balance, w=3] 对比 Lagrangian 与 Eulerian/ALE 时，点出前者易发生单元畸变，后者通过固定网格或混合网格避免同类负体积问题

### item_idx=93  Δ=+0.65 (v1 anchored=0.35 → v2 anchored=1.00)

**问题**: 当计算包含真空（Vacuum）的多物质单元时，应采取哪种混合理论以提高效率？


**翻转的 criteria (❌→✅):**

- [Essential, decision_logic, w=5] 说明程序先让真空承担所有体积变化
- [Essential, decision_logic, w=5] 说明剩余体积变化要等真空消失后再分配给硬物质

### item_idx=27  Δ=+0.62 (v1 anchored=0.38 → v2 anchored=1.00)

**问题**: 对于混合元素（多物质单元），如果包含极硬和极软材料，应采取什么策略防止硬材料被过度压缩？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 指出真空消失后，剩余压缩量才分配给其他材料
- [Essential, factual_anchor, w=5] 提到可以删除极小碎片以提高计算效率
- [Important, mechanism_explanation, w=3] 解释“先压缩真空、后分配给其他材料”的顺序能够避免极硬材料过度压缩

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

### item_idx=7  Δ=−0.83 (v1 anchored=0.83 → v2 anchored=0.00)

**问题**: 什么是“等效质量法”？它解决的是LS-DYNA在模拟中的什么问题？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 指出 LS-DYNA 在远场水下爆炸中计算得到的比冲量衰减过快
- [Essential, factual_anchor, w=5] 说明等效质量是由爆距处冲击波峰值压力的经验公式反推得到的炸药质量
- [Essential, factual_anchor, w=5] 说明模拟时使用较大的模拟质量来代替较小的实际质量
- [Important, mechanism_explanation, w=3] 说明该方法通过调整模拟质量来实现特定爆距处的冲击波载荷

### item_idx=28  Δ=−0.81 (v1 anchored=0.81 → v2 anchored=0.00)

**问题**: 什么是输运算法中的“一致性条件（Consistency Condition）”？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 指出输运前物体具有均匀的速度场
- [Essential, factual_anchor, w=5] 指出输运前密度在空间上变化
- [Essential, factual_anchor, w=5] 指出输运后速度场应保持均匀且不变
- [Important, mechanism_explanation, w=3] 解释其含义是：当仅密度发生空间变化时，输运过程不应引入速度场的非均匀性
- [Important, mechanism_explanation, w=3] 说明一致性条件约束的是质量重分布后速度场仍保持原有均匀状态，而不是让速度随密度变化而改变

### item_idx=16  Δ=−0.81 (v1 anchored=0.84 → v2 anchored=0.03)

**问题**: 在USA（Underwater Shock Analysis）代码中，为什么不需要对流体域进行有限元建模？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 明确指出 USA 代码基于双渐近近似法（DAA）
- [Essential, factual_anchor, w=5] 明确指出 USA 代码采用边界元法（BEM）描述流体
- [Essential, factual_anchor, w=5] 明确指出只需要在结构的湿表面定义流体-结构耦合面
- [Important, mechanism_explanation, w=3] 解释边界元法与湿表面耦合面处理会减少自由度
- [Important, mechanism_explanation, w=3] 解释减少自由度会节省大范围流体域的计算时间
