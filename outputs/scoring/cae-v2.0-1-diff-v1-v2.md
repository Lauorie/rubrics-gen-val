# RLM 评测结果对比报告 (v1 vs v2)

- v1: `outputs/scoring/cae-v2.0-1-scores.json`
- v2: `outputs/scoring/cae-v2.0-1-scores-v2.json`
- 生成时间: 2026-05-25T08:50:50.241002+00:00
- 共 94 项可对比

## 1. 总体得分对比

| 指标 | v1 | v2 | Δ |
|---|---|---|---|
| 平均原始分 (raw) | 0.69 | 0.63 | −0.06 |
| 平均锚定分 (anchored) | 0.70 | 0.64 | −0.06 |

## 2. Pitfall 触发对比

（按 v1+v2 总触发次数降序）

| pitfall | v1 触发 | v2 触发 | Δ |
|---|---|---|---|
| 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复 | 31 | 12 | −19 |
| 回答以套话/开场白/元评论开头而无实质内容 | 12 | 10 | −2 |
| 给出多个 | 4 | 4 | 0 |
| 同时罗列 Lagrangian、Eulerian、ALE 但不做最终选择 | 0 | 1 | +1 |

## 3. 按 criterion_type 命中率对比

（仅 sign=positive；Δ 单位为百分点 pp）

| criterion_type | v1 命中率 | v2 命中率 | Δ (pp) |
|---|---|---|---|
| comparative_balance | 47.4% (18/38) | 31.6% (12/38) | −15.8 |
| decision_logic | 81.2% (52/64) | 67.2% (43/64) | −14.1 |
| factual_anchor | 73.9% (212/287) | 65.9% (189/287) | −8.0 |
| mechanism_explanation | 72.5% (121/167) | 63.5% (106/167) | −9.0 |
| numeric_precision | 84.6% (22/26) | 69.2% (18/26) | −15.4 |
| process_completeness | 81.5% (22/27) | 74.1% (20/27) | −7.4 |

## 4. 按题型分组对比 (mean anchored)

| 题型 | v1 数量 | v1 anchored | v2 数量 | v2 anchored | Δ |
|---|---|---|---|---|---|
| 主观题 | 20 | 0.63 | 20 | 0.53 | −0.10 |
| 决策题 | 18 | 0.66 | 18 | 0.62 | −0.05 |
| 对比分析题 | 3 | 0.52 | 3 | 0.33 | −0.19 |
| 数值关系题 | 1 | 1.00 | 1 | 0.00 | −1.00 |
| 数值提取题 | 2 | 0.89 | 2 | 0.89 | +0.00 |
| 流程描述题 | 2 | 0.87 | 2 | 0.93 | +0.07 |
| 简答题 | 48 | 0.73 | 48 | 0.70 | −0.03 |

## 5. Top winners (按 anchored Δ 降序)


### item_idx=56  Δ=+1.00 (v1 anchored=0.00 → v2 anchored=1.00)

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

### item_idx=47  Δ=+0.48 (v1 anchored=0.52 → v2 anchored=1.00)

**问题**: 在处理流体粒子位移时，为什么“Adams-Bashforth”方案比一阶显式欧拉法更优？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 明确指出 Adams-Bashforth 是二阶多步法
- [Essential, factual_anchor, w=5] 明确指出 Adams-Bashforth 适用于长路径流体追踪

### item_idx=44  Δ=+0.43 (v1 anchored=0.35 → v2 anchored=0.78)

**问题**: “Zalesak’s Problem”（开槽圆盘旋转）在数值算法测试中主要用来评估什么性能？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 明确指出 Zalesak’s Problem 主要用于评估界面追踪算法
- [Essential, factual_anchor, w=5] 提到 Level Set 作为该问题关注的界面追踪方法示例

### item_idx=67  Δ=+0.43 (v1 anchored=0.00 → v2 anchored=0.43)

**问题**: 在对鱼雷进行水下爆炸模拟时，为何必须考虑其内部构件？


**翻转的 criteria (❌→✅):**

- [Essential, factual_anchor, w=5] 明确指出鱼雷内部构件包括大质量构件，例如战斗部或燃料
- [Essential, factual_anchor, w=5] 指出这些内部大质量构件在水下爆炸作用下会产生惯性效应
- [Important, mechanism_explanation, w=3] 说明不考虑鱼雷内部构件会使模拟出的毁伤程度显著降低

### item_idx=84  Δ=+0.41 (v1 anchored=0.19 → v2 anchored=0.59)

**问题**: 在罚函数耦合算法中，若出现流体“穿透（Leakage）”结构的现象，应如何调整参数？


**翻转的 criteria (❌→✅):**

- [Essential, decision_logic, w=6] 明确给出最终调整方向是提高罚函数刚度系数 k
- [Essential, mechanism_explanation, w=5] 说明增大 k 会增大界面罚函数力

## 6. Top losers (按 anchored Δ 升序)


### item_idx=9  Δ=−1.00 (v1 anchored=1.00 → v2 anchored=0.00)

**问题**: 气泡脉动周期与哪些物理因素有关？请给出简化的经验关系。


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 明确指出气泡脉动周期 T 主要取决于炸药药量 W 和静态水压力（或爆炸深度 h）
- [Important, mechanism_explanation, w=3] 说明静态水压力与爆炸深度 h 对应同一自变量表述
- [Essential, numeric_precision, w=5] 给出 T 与炸药药量 W 的 1/3 次方成正比
- [Essential, numeric_precision, w=5] 给出 T 与静水压力的 5/6 次方成反比
- [Important, numeric_precision, w=4] 用符号关系写出简化经验式 T ∝ W^(1/3) / p^(5/6) 或等价表达

### item_idx=68  Δ=−0.89 (v1 anchored=0.89 → v2 anchored=0.00)

**问题**: 在远场水下爆炸模拟中，声学材料对Taylor理论的适用性有何影响？


**翻转的 criteria (✅→❌):**

- [Essential, factual_anchor, w=5] 指出声学材料具有吸收声波的性质
- [Essential, factual_anchor, w=5] 指出声学材料的反射率不为100%
- [Essential, factual_anchor, w=5] 指出 Taylor 理论假设入射波等于反射波
- [Important, mechanism_explanation, w=3] 说明把 Taylor 理论直接用于声学材料会产生较大误差
- [Important, mechanism_explanation, w=3] 说明误差来源于声学材料的吸收使入射波等于反射波这一假设失效
- [Important, mechanism_explanation, w=3] 指出需要根据特定材料的吸收特性重新推导计算公式
- [Important, process_completeness, w=3] 明确重新推导的是总压力载荷计算公式
- [Optional, comparative_balance, w=1] 对比声学材料与100%反射边界在反射特性上的差异

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

### item_idx=62  Δ=−0.75 (v1 anchored=0.75 → v2 anchored=0.00)

**问题**: 在进行鱼雷壳体结构的数值模拟分析时，为什么必须在模型中考虑内部构件的影响？


**翻转的 criteria (✅→❌):**

- [Important, factual_anchor, w=3] 提到鱼雷内部构件的具体实例，包括战斗部装药或燃料舱
- [Important, factual_anchor, w=3] 提到内部构件的惯性效应会使壳体局部、尤其隔板附近出现有效应力集中
- [Essential, comparative_balance, w=5] 对比同一冲击工况下考虑内部构件与不考虑内部构件时的壳体毁伤程度，指出不考虑时毁伤程度更小
- [Essential, comparative_balance, w=5] 对比考虑内部构件与不考虑内部构件时的壳体毁伤区域分布，指出分布会显著变化
- [Essential, decision_logic, w=5] 给出结论：鱼雷壳体数值模拟的有限元模型必须考虑内部构件影响
