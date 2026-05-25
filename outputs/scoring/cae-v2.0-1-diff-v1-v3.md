# RLM 评测结果对比报告 (v1 vs v2)

- v1: `outputs/scoring/cae-v2.0-1-scores.json`
- v2: `outputs/scoring/cae-v2.0-1-scores-v3.json`
- 生成时间: 2026-05-25T10:31:33.371597+00:00
- 共 94 项可对比

## 1. 总体得分对比

| 指标 | v1 | v2 | Δ |
|---|---|---|---|
| 平均原始分 (raw) | 0.69 | 0.70 | +0.02 |
| 平均锚定分 (anchored) | 0.70 | 0.71 | +0.02 |

## 2. Pitfall 触发对比

（按 v1+v2 总触发次数降序）

| pitfall | v1 触发 | v2 触发 | Δ |
|---|---|---|---|
| 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复 | 31 | 14 | −17 |
| 回答以套话/开场白/元评论开头而无实质内容 | 12 | 5 | −7 |
| 给出多个 | 4 | 3 | −1 |

## 3. 按 criterion_type 命中率对比

（仅 sign=positive；Δ 单位为百分点 pp）

| criterion_type | v1 命中率 | v2 命中率 | Δ (pp) |
|---|---|---|---|
| comparative_balance | 47.4% (18/38) | 71.1% (27/38) | +23.7 |
| decision_logic | 81.2% (52/64) | 67.2% (43/64) | −14.1 |
| factual_anchor | 73.9% (212/287) | 73.9% (212/287) | +0.0 |
| mechanism_explanation | 72.5% (121/167) | 67.7% (113/167) | −4.8 |
| numeric_precision | 84.6% (22/26) | 84.6% (22/26) | +0.0 |
| process_completeness | 81.5% (22/27) | 77.8% (21/27) | −3.7 |

## 4. 按题型分组对比 (mean anchored)

| 题型 | v1 数量 | v1 anchored | v2 数量 | v2 anchored | Δ |
|---|---|---|---|---|---|
| 主观题 | 20 | 0.63 | 20 | 0.63 | −0.00 |
| 决策题 | 18 | 0.66 | 18 | 0.62 | −0.04 |
| 对比分析题 | 3 | 0.52 | 3 | 0.90 | +0.38 |
| 数值关系题 | 1 | 1.00 | 1 | 0.86 | −0.14 |
| 数值提取题 | 2 | 0.89 | 2 | 0.95 | +0.05 |
| 流程描述题 | 2 | 0.87 | 2 | 0.87 | +0.00 |
| 简答题 | 48 | 0.73 | 48 | 0.75 | +0.03 |

## 5. Top winners (按 anchored Δ 降序)


### item_idx=46  Δ=+0.83 (v1 anchored=0.00 → v2 anchored=0.83)

**问题**: 为什么实验测得的结构位移衰减往往比数值模拟快？（排除阻尼设置原因）


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 指出实验中侧壁或支撑装置与结构之间存在小缝隙
- [Essential, mechanism_explanation, w=5] 解释小缝隙会产生显著的水力阻尼效应
- [Important, mechanism_explanation, w=3] 解释对称边界条件会忽略真实物理环境中的三维能量耗散
- [Important, comparative_balance, w=3] 对比实验中的侧壁或支撑装置小缝隙与数值模拟中的对称边界条件
- [Essential, comparative_balance, w=5] 指出实验中的水力阻尼和三维能量耗散比数值模拟中的理想化边界损失更强

### item_idx=56  Δ=+0.73 (v1 anchored=0.00 → v2 anchored=0.73)

**问题**: 混合理论（Mixture theories）中，平均应变率理论与平均应力理论在能量守恒和物理响应上有何区别？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 明确指出平均应变率混合理论可以精确守恒能量
- [Essential, factual_anchor, w=5] 明确指出平均应力理论不能保证能量守恒
- [Important, mechanism_explanation, w=3] 指出平均应变率理论在含真空的单元中存在缺陷
- [Important, mechanism_explanation, w=3] 指出平均应变率理论的响应可能过硬
- [Important, mechanism_explanation, w=3] 指出平均应力理论会自动优先压缩软物质（如真空），从而避免无限大压力风险
- [Important, factual_anchor, w=3] 指出在钢和真空的混合单元中，钢的应力始终为零

### item_idx=84  Δ=+0.67 (v1 anchored=0.19 → v2 anchored=0.85)

**问题**: 在罚函数耦合算法中，若出现流体“穿透（Leakage）”结构的现象，应如何调整参数？


**翻转的 criteria (❌→✅):**

- [Essential, decision_logic, w=6] 明确给出最终调整方向是提高罚函数刚度系数 k
- [Essential, mechanism_explanation, w=5] 说明增大 k 会增大界面罚函数力
- [Important, mechanism_explanation, w=3] 说明更大的界面力可将流体节点推回结构界面
- [Essential, decision_logic, w=4] 指出 k 过大可能导致数值震荡

### item_idx=67  Δ=+0.63 (v1 anchored=0.00 → v2 anchored=0.63)

**问题**: 在对鱼雷进行水下爆炸模拟时，为何必须考虑其内部构件？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 明确指出鱼雷内部构件包括大质量构件，例如战斗部或燃料
- [Essential, factual_anchor, w=5] 指出这些内部大质量构件在水下爆炸作用下会产生惯性效应
- [Important, mechanism_explanation, w=3] 说明不考虑鱼雷内部构件会使模拟出的毁伤程度显著降低
- [Important, mechanism_explanation, w=3] 说明不考虑鱼雷内部构件会使毁伤区域分布发生错误
- [Important, comparative_balance, w=3] 指出不同舱段由于内部组分或构件分布不同，其毁伤响应不同，不能按同一舱段响应处理

### item_idx=0  Δ=+0.39 (v1 anchored=0.52 → v2 anchored=0.90)

**问题**: 在流固耦合（FSI）仿真中，“附加质量效应”为何会导致数值不稳定？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 指出分区方法在结构域计算时使用的是上一迭代步的压力
- [Important, mechanism_explanation, w=3] 解释上一迭代步压力会在流体-结构耦合中引入压力滞后
- [Important, mechanism_explanation, w=3] 解释这种压力滞后会在强耦合条件下放大误差
- [Optional, comparative_balance, w=1] 比较时明确把 monolithic 方法作为 added-mass 显著时比分区/松散耦合更稳的选择

## 6. Top losers (按 anchored Δ 升序)


### item_idx=85  Δ=−1.00 (v1 anchored=1.00 → v2 anchored=0.00)

**问题**: 若需要模拟潜艇在大范围水域中的远场抗震性，且计算资源极其紧张，应决定采用哪种建模方式？


**翻转的 criteria (✅→❌):**

- [Essential, decision_logic, w=6] 明确给出最终建模方式是 USA（Underwater Shock Analysis）代码联用
- [Essential, factual_anchor, w=5] 指出 USA 基于边界元法（BEM）
- [Essential, mechanism_explanation, w=5] 说明 USA 无需建立庞大的水域有限元模型
- [Essential, decision_logic, w=5] 指出 USA 可作为需要建模大量水体时的替代方案
- [Essential, decision_logic, w=5] 指出在不建水域模型时，计算时间可减少至少一个数量级
- [Important, numeric_precision, w=4] 给出计算时间仅需几百秒

### item_idx=61  Δ=−0.81 (v1 anchored=0.81 → v2 anchored=0.00)

**问题**: 在使用ABAQUS程序模拟水下爆炸时，其主要特点和局限性是什么？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 明确指出 ABAQUS 是把经验公式或试验得到的水下爆炸载荷直接施加到结构上，而不是由程序自行求爆轰载荷
- [Essential, factual_anchor, w=5] 明确指出 ABAQUS 不计算炸药爆轰过程
- [Essential, factual_anchor, w=5] 明确指出 ABAQUS 不计算载荷传播过程
- [Essential, factual_anchor, w=5] 明确指出计算模型中不包含炸药，只包含结构及其周围流场
- [Important, factual_anchor, w=3] 提到 ABAQUS 的 Standard 与 Explicit 两个主模块
- [Important, mechanism_explanation, w=3] 解释省略爆轰计算步骤和炸药模型是计算速度快的原因

### item_idx=11  Δ=−0.70 (v1 anchored=0.70 → v2 anchored=0.00)

**问题**: 为什么在水下爆炸仿真中需要引入“人工体积粘性”？其对冲击波波头处理有何作用？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 明确指出水下爆炸中的冲击波属于强间断问题
- [Essential, factual_anchor, w=5] 指出不引入人工体积粘性时，间断界面附近会出现剧烈振荡
- [Important, mechanism_explanation, w=3] 说明人工体积粘性会将冲击波的强间断模糊化
- [Important, mechanism_explanation, w=3] 说明引入人工体积粘性的目的之一是克服微分方程组在波阵面处的求解困难
- [Optional, process_completeness, w=1] 回答同时覆盖“为什么需要引入”和“其对冲击波波头处理的作用”两部分

### item_idx=93  Δ=−0.65 (v1 anchored=0.65 → v2 anchored=0.00)

**问题**: 当计算包含真空（Vacuum）的多物质单元时，应采取哪种混合理论以提高效率？


**翻转的 criteria (✅→❌):**

- [Essential, decision_logic, w=6] 明确给出最终选择是平均应变率混合理论
- [Essential, factual_anchor, w=5] 提到平均应变率混合理论这一名称
- [Important, mechanism_explanation, w=3] 说明优先压缩或扩展真空部分

### item_idx=71  Δ=−0.59 (v1 anchored=1.00 → v2 anchored=0.41)

**问题**: 相比于Level Set方法，为什么VOF（体积分数法）在多物质ALE仿真中更受欢迎？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 指出 VOF 是按单元内体积分数（volume fraction）进行输运
- [Essential, factual_anchor, w=5] 指出 VOF 在剧烈界面变形或拓扑改变时更鲁棒
- [Important, mechanism_explanation, w=3] 解释 VOF 在界面拉伸、卷曲、破碎等大变形场景下更稳定
- [Important, comparative_balance, w=3] 解释工程上更看重守恒律而不是界面几何的光滑性
