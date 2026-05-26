# RLM 评测结果对比报告 (v1 vs v2)

- v1: `outputs/scoring/cae-v2.0-1-scores-v3.json`
- v2: `outputs/scoring/cae-v2.0-1-scores-v5.json`
- 生成时间: 2026-05-26T03:49:24.022283+00:00
- 共 92 项可对比
- 在 v1 但不在 v2: 2 项 (item_idx=[46, 48])

## 1. 总体得分对比

| 指标 | v1 | v2 | Δ |
|---|---|---|---|
| 平均原始分 (raw) | 0.70 | 0.68 | −0.02 |
| 平均锚定分 (anchored) | 0.71 | 0.69 | −0.02 |

## 2. Pitfall 触发对比

（按 v1+v2 总触发次数降序）

| pitfall | v1 触发 | v2 触发 | Δ |
|---|---|---|---|
| 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复 | 14 | 19 | +5 |
| 回答以套话/开场白/元评论开头而无实质内容 | 5 | 10 | +5 |
| 给出多个 | 3 | 5 | +2 |

## 3. 按 criterion_type 命中率对比

（仅 sign=positive；Δ 单位为百分点 pp）

| criterion_type | v1 命中率 | v2 命中率 | Δ (pp) |
|---|---|---|---|
| comparative_balance | 71.1% (27/38) | 60.0% (21/35) | −11.1 |
| decision_logic | 67.2% (43/64) | 78.1% (50/64) | +10.9 |
| factual_anchor | 73.9% (212/287) | 70.0% (196/280) | −3.9 |
| mechanism_explanation | 67.7% (113/167) | 75.0% (123/164) | +7.3 |
| numeric_precision | 84.6% (22/26) | 80.8% (21/26) | −3.8 |
| process_completeness | 77.8% (21/27) | 88.5% (23/26) | +10.7 |

## 4. 按题型分组对比 (mean anchored)

| 题型 | v1 数量 | v1 anchored | v2 数量 | v2 anchored | Δ |
|---|---|---|---|---|---|
| 主观题 | 20 | 0.63 | 20 | 0.76 | +0.13 |
| 决策题 | 18 | 0.62 | 18 | 0.68 | +0.06 |
| 对比分析题 | 3 | 0.90 | 2 | 0.91 | +0.01 |
| 数值关系题 | 1 | 0.86 | 1 | 1.00 | +0.14 |
| 数值提取题 | 2 | 0.95 | 2 | 0.89 | −0.05 |
| 流程描述题 | 2 | 0.87 | 2 | 0.93 | +0.07 |
| 简答题 | 48 | 0.75 | 47 | 0.64 | −0.12 |

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

### item_idx=93  Δ=+1.00 (v1 anchored=0.00 → v2 anchored=1.00)

**问题**: 当计算包含真空（Vacuum）的多物质单元时，应采取哪种混合理论以提高效率？


**翻转的 criteria (❌→✅):**

- [Essential, decision_logic, w=6] 明确给出最终选择是平均应变率混合理论
- [Essential, factual_anchor, w=5] 提到平均应变率混合理论这一名称
- [Important, mechanism_explanation, w=3] 说明优先压缩或扩展真空部分
- [Essential, decision_logic, w=5] 说明程序先让真空承担所有体积变化
- [Essential, decision_logic, w=5] 说明剩余体积变化要等真空消失后再分配给硬物质

### item_idx=61  Δ=+0.84 (v1 anchored=0.00 → v2 anchored=0.84)

**问题**: 在使用ABAQUS程序模拟水下爆炸时，其主要特点和局限性是什么？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 明确指出 ABAQUS 是把经验公式或试验得到的水下爆炸载荷直接施加到结构上，而不是由程序自行求爆轰载荷
- [Essential, factual_anchor, w=5] 明确指出 ABAQUS 不计算炸药爆轰过程
- [Essential, factual_anchor, w=5] 明确指出 ABAQUS 不计算载荷传播过程
- [Important, factual_anchor, w=3] 提到 ABAQUS 的 Standard 与 Explicit 两个主模块
- [Important, process_completeness, w=3] 提到 Standard 与 Explicit 之间可以进行结果传递
- [Important, process_completeness, w=3] 提到 ABAQUS 会自动计算结构的动态响应与流场压力分布
- [Important, mechanism_explanation, w=3] 解释省略爆轰计算步骤和炸药模型是计算速度快的原因

### item_idx=91  Δ=+0.65 (v1 anchored=0.35 → v2 anchored=1.00)

**问题**: 若在罚函数耦合分析中发现流体大量“穿透”结构表面，但整体位移趋势正确，应如何调整参数？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 指出罚函数力与穿透深度成比例
- [Essential, mechanism_explanation, w=5] 说明增大刚度系数会增大回复力
- [Essential, mechanism_explanation, w=5] 说明增大的回复力用于把流体节点推回界面或结构表面
- [Essential, decision_logic, w=5] 提到增大惩罚因子或刚度系数可能使时间步长下降

### item_idx=85  Δ=+0.53 (v1 anchored=0.00 → v2 anchored=0.53)

**问题**: 若需要模拟潜艇在大范围水域中的远场抗震性，且计算资源极其紧张，应决定采用哪种建模方式？


**翻转的 criteria (❌→✅):**

- [Essential, mechanism_explanation, w=5] 说明 USA 无需建立庞大的水域有限元模型
- [Essential, decision_logic, w=5] 指出 USA 可作为需要建模大量水体时的替代方案
- [Essential, decision_logic, w=5] 指出在不建水域模型时，计算时间可减少至少一个数量级
- [Important, numeric_precision, w=4] 给出计算时间仅需几百秒

## 6. Top losers (按 anchored Δ 升序)


### item_idx=7  Δ=−1.00 (v1 anchored=1.00 → v2 anchored=0.00)

**问题**: 什么是“等效质量法”？它解决的是LS-DYNA在模拟中的什么问题？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 指出 LS-DYNA 在远场水下爆炸中计算得到的比冲量衰减过快
- [Essential, factual_anchor, w=5] 说明等效质量是由爆距处冲击波峰值压力的经验公式反推得到的炸药质量
- [Essential, factual_anchor, w=5] 说明模拟时使用较大的模拟质量来代替较小的实际质量
- [Important, mechanism_explanation, w=3] 说明该方法通过调整模拟质量来实现特定爆距处的冲击波载荷

### item_idx=28  Δ=−1.00 (v1 anchored=1.00 → v2 anchored=0.00)

**问题**: 什么是输运算法中的“一致性条件（Consistency Condition）”？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 指出输运前物体具有均匀的速度场
- [Essential, factual_anchor, w=5] 指出输运前密度在空间上变化
- [Essential, factual_anchor, w=5] 指出输运后速度场应保持均匀且不变
- [Essential, factual_anchor, w=5] 指出该条件用于保证动量输运与质量输运在逻辑上的匹配
- [Important, mechanism_explanation, w=3] 解释其含义是：当仅密度发生空间变化时，输运过程不应引入速度场的非均匀性
- [Important, mechanism_explanation, w=3] 说明一致性条件约束的是质量重分布后速度场仍保持原有均匀状态，而不是让速度随密度变化而改变

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

### item_idx=87  Δ=−1.00 (v1 anchored=1.00 → v2 anchored=0.00)

**问题**: 在执行ALE的Advection（输运）阶段时，若追求在不产生非物理极值的前提下获得最高精度，应选择哪种算法？


**翻转的 criteria (✅→❌):**

- [Essential, decision_logic, w=6] 明确给出最终选择是 MUSCL 算法
- [Essential, decision_logic, w=5] 说明在追求最高精度时，MUSCL 因为提供二阶精度而优先于低阶输运格式
- [Essential, decision_logic, w=5] 说明 MUSCL 的单调限幅器用于抑制数值震荡或非物理极值
- [Important, factual_anchor, w=3] 指出 MUSCL 采用线性逼近
- [Important, comparative_balance, w=3] 比较 MUSCL 与 Donor Cell 时，说明 MUSCL 更能捕捉梯度
