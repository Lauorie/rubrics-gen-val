# RLM 评测结果对比报告 (v1 vs v2)

- v1: `outputs/scoring/cae-v2.0-1-scores-v2.json`
- v2: `outputs/scoring/cae-v2.0-1-scores-v3.json`
- 生成时间: 2026-05-25T10:31:33.474994+00:00
- 共 94 项可对比

## 1. 总体得分对比

| 指标 | v1 | v2 | Δ |
|---|---|---|---|
| 平均原始分 (raw) | 0.63 | 0.70 | +0.07 |
| 平均锚定分 (anchored) | 0.64 | 0.71 | +0.08 |

## 2. Pitfall 触发对比

（按 v1+v2 总触发次数降序）

| pitfall | v1 触发 | v2 触发 | Δ |
|---|---|---|---|
| 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复 | 12 | 14 | +2 |
| 回答以套话/开场白/元评论开头而无实质内容 | 10 | 5 | −5 |
| 给出多个 | 4 | 3 | −1 |
| 同时罗列 Lagrangian、Eulerian、ALE 但不做最终选择 | 1 | 0 | −1 |

## 3. 按 criterion_type 命中率对比

（仅 sign=positive；Δ 单位为百分点 pp）

| criterion_type | v1 命中率 | v2 命中率 | Δ (pp) |
|---|---|---|---|
| comparative_balance | 31.6% (12/38) | 71.1% (27/38) | +39.5 |
| decision_logic | 67.2% (43/64) | 67.2% (43/64) | +0.0 |
| factual_anchor | 65.9% (189/287) | 73.9% (212/287) | +8.0 |
| mechanism_explanation | 63.5% (106/167) | 67.7% (113/167) | +4.2 |
| numeric_precision | 69.2% (18/26) | 84.6% (22/26) | +15.4 |
| process_completeness | 74.1% (20/27) | 77.8% (21/27) | +3.7 |

## 4. 按题型分组对比 (mean anchored)

| 题型 | v1 数量 | v1 anchored | v2 数量 | v2 anchored | Δ |
|---|---|---|---|---|---|
| 主观题 | 20 | 0.53 | 20 | 0.63 | +0.09 |
| 决策题 | 18 | 0.62 | 18 | 0.62 | +0.01 |
| 对比分析题 | 3 | 0.33 | 3 | 0.90 | +0.57 |
| 数值关系题 | 1 | 0.00 | 1 | 0.86 | +0.86 |
| 数值提取题 | 2 | 0.89 | 2 | 0.95 | +0.05 |
| 流程描述题 | 2 | 0.93 | 2 | 0.87 | −0.07 |
| 简答题 | 48 | 0.70 | 48 | 0.75 | +0.05 |

## 5. Top winners (按 anchored Δ 降序)


### item_idx=7  Δ=+1.00 (v1 anchored=0.00 → v2 anchored=1.00)

**问题**: 什么是“等效质量法”？它解决的是LS-DYNA在模拟中的什么问题？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 指出 LS-DYNA 在远场水下爆炸中计算得到的比冲量衰减过快
- [Essential, factual_anchor, w=5] 说明等效质量是由爆距处冲击波峰值压力的经验公式反推得到的炸药质量
- [Essential, factual_anchor, w=5] 说明模拟时使用较大的模拟质量来代替较小的实际质量
- [Important, mechanism_explanation, w=3] 说明该方法通过调整模拟质量来实现特定爆距处的冲击波载荷

### item_idx=68  Δ=+1.00 (v1 anchored=0.00 → v2 anchored=1.00)

**问题**: 在远场水下爆炸模拟中，声学材料对Taylor理论的适用性有何影响？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 指出声学材料具有吸收声波的性质
- [Essential, factual_anchor, w=5] 指出声学材料的反射率不为100%
- [Essential, factual_anchor, w=5] 指出 Taylor 理论假设入射波等于反射波
- [Important, mechanism_explanation, w=3] 说明把 Taylor 理论直接用于声学材料会产生较大误差
- [Important, mechanism_explanation, w=3] 说明误差来源于声学材料的吸收使入射波等于反射波这一假设失效
- [Important, mechanism_explanation, w=3] 指出需要根据特定材料的吸收特性重新推导计算公式
- [Important, process_completeness, w=3] 明确重新推导的是总压力载荷计算公式
- [Optional, comparative_balance, w=1] 对比声学材料与100%反射边界在反射特性上的差异

### item_idx=87  Δ=+1.00 (v1 anchored=0.00 → v2 anchored=1.00)

**问题**: 在执行ALE的Advection（输运）阶段时，若追求在不产生非物理极值的前提下获得最高精度，应选择哪种算法？


**翻转的 criteria (❌→✅):**

- [Essential, decision_logic, w=6] 明确给出最终选择是 MUSCL 算法
- [Essential, decision_logic, w=5] 说明在追求最高精度时，MUSCL 因为提供二阶精度而优先于低阶输运格式
- [Essential, decision_logic, w=5] 说明 MUSCL 的单调限幅器用于抑制数值震荡或非物理极值
- [Important, factual_anchor, w=3] 指出 MUSCL 采用线性逼近
- [Important, comparative_balance, w=3] 比较 MUSCL 与 Donor Cell 时，说明 MUSCL 更能捕捉梯度

### item_idx=62  Δ=+0.88 (v1 anchored=0.00 → v2 anchored=0.88)

**问题**: 在进行鱼雷壳体结构的数值模拟分析时，为什么必须在模型中考虑内部构件的影响？


**翻转的 criteria (❌→✅):**

- [Important, factual_anchor, w=3] 提到鱼雷内部构件的具体实例，包括战斗部装药或燃料舱
- [Essential, comparative_balance, w=5] 对比同一冲击工况下考虑内部构件与不考虑内部构件时的壳体毁伤程度，指出不考虑时毁伤程度更小
- [Essential, comparative_balance, w=5] 对比考虑内部构件与不考虑内部构件时的壳体毁伤区域分布，指出分布会显著变化
- [Important, comparative_balance, w=3] 指出战斗部装药和燃料会增大对应舱段壳体的抗冲击性能
- [Essential, decision_logic, w=5] 给出结论：鱼雷壳体数值模拟的有限元模型必须考虑内部构件影响

### item_idx=9  Δ=+0.86 (v1 anchored=0.00 → v2 anchored=0.86)

**问题**: 气泡脉动周期与哪些物理因素有关？请给出简化的经验关系。


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 明确指出气泡脉动周期 T 主要取决于炸药药量 W 和静态水压力（或爆炸深度 h）
- [Essential, numeric_precision, w=5] 给出 T 与炸药药量 W 的 1/3 次方成正比
- [Essential, numeric_precision, w=5] 给出 T 与静水压力的 5/6 次方成反比
- [Important, numeric_precision, w=4] 用符号关系写出简化经验式 T ∝ W^(1/3) / p^(5/6) 或等价表达

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

### item_idx=11  Δ=−0.60 (v1 anchored=0.60 → v2 anchored=0.00)

**问题**: 为什么在水下爆炸仿真中需要引入“人工体积粘性”？其对冲击波波头处理有何作用？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 明确指出水下爆炸中的冲击波属于强间断问题
- [Important, mechanism_explanation, w=3] 说明人工体积粘性会将冲击波的强间断模糊化
- [Important, mechanism_explanation, w=3] 说明引入人工体积粘性的目的之一是克服微分方程组在波阵面处的求解困难
- [Optional, process_completeness, w=1] 回答同时覆盖“为什么需要引入”和“其对冲击波波头处理的作用”两部分

### item_idx=90  Δ=−0.55 (v1 anchored=0.72 → v2 anchored=0.17)

**问题**: 在设计潜艇复合材料面板抗冲击仿真方案时，若需同时精确考量冲击波和气泡脉动的全过程载荷，首选哪种LS-DYNA功能？


**翻转的 criteria (✅→❌):**

- [Essential, decision_logic, w=6] 明确给出最终选择是 ALE（Arbitrary Lagrangian-Eulerian）多物质流固耦合
- [Essential, factual_anchor, w=5] 指出所选功能属于 LS-DYNA 的多物质流固耦合方案
- [Essential, decision_logic, w=5] 说明 ALE 可以同时处理爆轰产物气泡的脉动全过程载荷

### item_idx=91  Δ=−0.48 (v1 anchored=0.84 → v2 anchored=0.35)

**问题**: 若在罚函数耦合分析中发现流体大量“穿透”结构表面，但整体位移趋势正确，应如何调整参数？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 指出罚函数力与穿透深度成比例
- [Essential, mechanism_explanation, w=5] 说明增大刚度系数会增大回复力
- [Essential, mechanism_explanation, w=5] 说明增大的回复力用于把流体节点推回界面或结构表面

### item_idx=93  Δ=−0.47 (v1 anchored=0.47 → v2 anchored=0.00)

**问题**: 当计算包含真空（Vacuum）的多物质单元时，应采取哪种混合理论以提高效率？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 提到平均应变率混合理论这一名称
- [Important, mechanism_explanation, w=3] 说明优先压缩或扩展真空部分
