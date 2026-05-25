# CAE-v2.0-1 RLM Scoring Report

- 候选模型: `deepseek/deepseek-v4-flash`
- 评分模型: `openai/gpt-5.5`
- 总样本: 94 · 评分成功: 94 · 错误: 0
- 生成时间: 2026-05-25T08:50:23.044520+00:00

## 1. 总体得分

| 指标 | 数值 |
|---|---|
| 平均原始分 (raw) | 0.63 |
| 平均锚定分 (anchored) | 0.64 |

## 2. 按题型分组 (question_type)

| 分组 | 数量 | mean (raw) | mean (anchored) |
|---|---|---|---|
| 简答题 | 48 | 0.70 | 0.70 |
| 主观题 | 20 | 0.53 | 0.53 |
| 决策题 | 18 | 0.57 | 0.62 |
| 对比分析题 | 3 | 0.33 | 0.33 |
| 数值提取题 | 2 | 0.89 | 0.89 |
| 流程描述题 | 2 | 0.93 | 0.93 |
| 数值关系题 | 1 | 0.00 | 0.00 |

## 3. 按难度 (difficulty)

| 分组 | 数量 | mean (raw) | mean (anchored) |
|---|---|---|---|
| 困难 | 38 | 0.62 | 0.63 |
| 中等 | 37 | 0.61 | 0.62 |
| 简单 | 19 | 0.68 | 0.69 |

## 4. 失分点 — criterion_type 命中率最低

（仅 sign=positive，按命中率升序）

| criterion_type | 总数 | 命中 | 命中率 |
|---|---|---|---|
| comparative_balance | 38 | 12 | 31.6% |
| mechanism_explanation | 167 | 106 | 63.5% |
| factual_anchor | 287 | 189 | 65.9% |
| decision_logic | 64 | 43 | 67.2% |
| numeric_precision | 26 | 18 | 69.2% |
| process_completeness | 27 | 20 | 74.1% |

## 5. 得分点 — criterion_type 命中率最高

（仅 sign=positive，按命中率降序）

| criterion_type | 总数 | 命中 | 命中率 |
|---|---|---|---|
| process_completeness | 27 | 20 | 74.1% |
| numeric_precision | 26 | 18 | 69.2% |
| decision_logic | 64 | 43 | 67.2% |
| factual_anchor | 287 | 189 | 65.9% |
| mechanism_explanation | 167 | 106 | 63.5% |
| comparative_balance | 38 | 12 | 31.6% |

## 6. Pitfall 触发分析

（仅 criterion_type=anti_hacking 且 met=True，按触发次数降序）

| pitfall | 触发次数 | 占比 |
|---|---|---|
| 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复 | 12 | 12.8% |
| 回答以套话/开场白/元评论开头而无实质内容 | 10 | 10.6% |
| 给出多个 | 4 | 4.3% |
| 同时罗列 Lagrangian、Eulerian、ALE 但不做最终选择 | 1 | 1.1% |

## 7. 最低分 10 题


### #7 (question_id=8, anchored=0.00, raw=0.00)


**问题**: 什么是“等效质量法”？它解决的是LS-DYNA在模拟中的什么问题？


- ❌ `c2` [Essential, factual_anchor, w=5, positive] 指出 LS-DYNA 在远场水下爆炸中计算得到的比冲量衰减过快
    judge: 候选回答未提及远场水下爆炸，也未指出LS-DYNA计算得到的比冲量衰减过快。
- ❌ `c3` [Essential, factual_anchor, w=5, positive] 说明等效质量是由爆距处冲击波峰值压力的经验公式反推得到的炸药质量
    judge: 候选回答未说明等效质量由爆距处冲击波峰值压力经验公式反推得到的炸药质量。
- ❌ `c4` [Essential, factual_anchor, w=5, positive] 说明模拟时使用较大的模拟质量来代替较小的实际质量
    judge: 候选回答未说明等效质量法是用较大的模拟质量代替较小的实际质量。
- ❌ `c6` [Important, mechanism_explanation, w=3, positive] 说明该方法通过调整模拟质量来实现特定爆距处的冲击波载荷
    judge: 候选回答未说明等效质量法通过调整模拟质量来实现特定爆距处的冲击波载荷。
- ✅ `c8` [Pitfall, anti_hacking, w=4, negative] 回答以套话/开场白/元评论开头而无实质内容
    judge: 候选回答开头即以语料来源和无法回答的元评论展开，未直接提供等效质量法的实质内容。
- ❌ `c9` [Pitfall, anti_hacking, w=3, negative] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复
    judge: 候选回答较简短，虽提到语料背景但未包含大量无关铺垫或重复内容。

### #9 (question_id=10, anchored=0.00, raw=0.00)


**问题**: 气泡脉动周期与哪些物理因素有关？请给出简化的经验关系。


- ❌ `c1` [Essential, factual_anchor, w=5, positive] 明确指出气泡脉动周期 T 主要取决于炸药药量 W 和静态水压力（或爆炸深度 h）
    judge: 候选回答未指出气泡脉动周期 T 主要取决于炸药药量 W 和静态水压力或爆炸深度 h。
- ❌ `c2` [Important, mechanism_explanation, w=3, positive] 说明静态水压力与爆炸深度 h 对应同一自变量表述
    judge: 候选回答未说明静态水压力与爆炸深度 h 的对应关系或同一自变量表述。
- ❌ `c3` [Essential, numeric_precision, w=5, positive] 给出 T 与炸药药量 W 的 1/3 次方成正比
    judge: 候选回答未给出气泡脉动周期 T 与炸药药量 W 的 1/3 次方成正比的关系。
- ❌ `c4` [Essential, numeric_precision, w=5, positive] 给出 T 与静水压力的 5/6 次方成反比
    judge: 候选回答未给出气泡脉动周期与静水压力的关系，更未说明 T 与静水压力的 5/6 次方成反比。
- ❌ `c5` [Important, numeric_precision, w=4, positive] 用符号关系写出简化经验式 T ∝ W^(1/3) / p^(5/6) 或等价表达
    judge: 候选回答未给出 T ∝ W^(1/3) / p^(5/6) 或任何等价的简化经验式。
- ❌ `c6` [Pitfall, anti_hacking, w=4, negative] 只给出“与药量和水深有关”之类定性表述，而没有写出 1/3 和 5/6 的量化关系
    judge: 候选回答没有给出“与药量和水深有关”的定性表述，也未尝试给出该经验关系，因此不属于该负向规则描述的情况。
- ✅ `c7` [Pitfall, anti_hacking, w=4, negative] 回答以套话/开场白/元评论开头而无实质内容
    judge: 候选回答开头即以“根据提供的8篇英文机器学习研究论文的上下文”等元评论说明无法回答，未直接给出气泡脉动周期的实质内容。
- ❌ `c8` [Pitfall, anti_hacking, w=3, negative] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复
    judge: 候选回答虽提到与题目无关的论文背景，但篇幅较短，未达到“冗长且包含大量无关铺垫或重复”的程度。

### #45 (question_id=46, anchored=0.00, raw=0.00)


**问题**: 混凝土重力坝在水下爆炸中的“内能吸收曲线”呈现什么特征？这说明了什么？


- ❌ `c1` [Essential, factual_anchor, w=5, positive] 指出内能曲线在冲击瞬间迅速攀升
    judge: 候选回答只描述了内能随爆心距增大而递减、贴爆最大，未指出内能曲线在冲击瞬间迅速攀升。
- ❌ `c2` [Essential, factual_anchor, w=5, positive] 指出内能曲线会达到峰值
    judge: 候选回答只说内能随爆心距增大而递减、贴爆面时最大，并未指出内能曲线会达到峰值。
- ❌ `c3` [Essential, factual_anchor, w=5, positive] 指出峰值之后曲线保持在一定水平
    judge: 候选回答只描述了内能随爆心距增大而减小，未指出内能吸收曲线在达到峰值之后保持在一定水平。
- ❌ `c4` [Essential, factual_anchor, w=5, positive] 指出峰值之后曲线伴有小幅震荡
    judge: 候选回答只描述了内能随爆心距增大而递减、贴爆最大，未指出曲线在峰值之后伴有小幅震荡。
- ❌ `c5` [Important, mechanism_explanation, w=3, positive] 指出大坝的毁伤主要发生在冲击波作用的极短时间内（毫秒级）
    judge: 候选回答未指出毁伤主要发生在冲击波作用的极短毫秒级时间内。
- ❌ `c6` [Important, mechanism_explanation, w=3, positive] 指出后续震荡反映了大坝在平衡位置附近的弹性回弹或振动
    judge: 候选回答未提到内能曲线后续震荡，也未解释其反映大坝在平衡位置附近的弹性回弹或振动。
- ✅ `c7` [Pitfall, anti_hacking, w=4, negative] 回答以套话/开场白/元评论开头而无实质内容
    judge: 候选回答开头先讨论论文图题、PDF排版和无法获取正文等元信息，而非直接给出内能吸收曲线特征。
- ❌ `c8` [Pitfall, anti_hacking, w=3, negative] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复
    judge: 回答虽有一定铺垫和来源说明，但主要内容仍围绕内能曲线特征及其含义展开，未达到大量无关背景或重复的程度。

### #46 (question_id=47, anchored=0.00, raw=0.00)


**问题**: 为什么实验测得的结构位移衰减往往比数值模拟快？（排除阻尼设置原因）


- ❌ `c1` [Essential, factual_anchor, w=5, positive] 指出实验中侧壁或支撑装置与结构之间存在小缝隙
    judge: 候选回答未提到实验中侧壁或支撑装置与结构之间存在小缝隙。
- ❌ `c2` [Important, factual_anchor, w=3, positive] 指出数值模拟中常采用对称边界条件
    judge: 候选回答未提到数值模拟中常采用对称边界条件。
- ❌ `c3` [Essential, mechanism_explanation, w=5, positive] 解释小缝隙会产生显著的水力阻尼效应
    judge: 候选回答未提到小缝隙或其导致显著水力阻尼效应的机制。
- ❌ `c4` [Important, mechanism_explanation, w=3, positive] 解释对称边界条件会忽略真实物理环境中的三维能量耗散
    judge: 候选回答未提及对称边界条件，也未解释其会忽略真实三维物理环境中的能量耗散。
- ❌ `c5` [Essential, comparative_balance, w=5, positive] 指出实验与数值模拟的差异都来自边界效应
    judge: 候选回答未指出实验与数值模拟差异来自边界效应，反而表示无法回答并列举了其他可能原因。
- ❌ `c6` [Important, comparative_balance, w=3, positive] 对比实验中的侧壁或支撑装置小缝隙与数值模拟中的对称边界条件
    judge: 候选回答未对比实验中的侧壁或支撑装置小缝隙与数值模拟中的对称边界条件。
- ❌ `c7` [Essential, comparative_balance, w=5, positive] 指出实验中的水力阻尼和三维能量耗散比数值模拟中的理想化边界损失更强
    judge: 候选回答未指出实验中的水力阻尼或三维能量耗散相较数值模拟理想化边界损失更强。
- ✅ `c9` [Pitfall, anti_hacking, w=4, negative] 回答以套话/开场白/元评论开头而无实质内容
    judge: 候选回答一开始即以语料库检索范围和无法回答的元评论展开，而不是直接给出该工程现象的实质性原因分析。
- ✅ `c10` [Pitfall, anti_hacking, w=3, negative] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复
    judge: 候选回答大量列举检索语料、论文清单和搜索过程，篇幅冗长且与直接回答问题关系不大。

### #60 (question_id=61, anchored=0.00, raw=0.00)


**问题**: 与传统的水下爆炸实验相比，数值模拟方法具有哪些主要的优点？


- ❌ `c1` [Essential, factual_anchor, w=5, positive] 明确指出数值模拟的成本低廉
    judge: 候选回答未提到数值模拟成本低廉这一优点。
- ❌ `c2` [Essential, factual_anchor, w=5, positive] 只需相应的计算硬件和程序即可实现模拟
    judge: 候选回答未提到数值模拟只需相应计算硬件和程序即可实现模拟这一优点。
- ❌ `c3` [Essential, factual_anchor, w=5, positive] 明确指出数值模拟的可重复性，即对水下爆炸这种破坏性过程可以多次重复进行
    judge: 候选回答未提及数值模拟可重复、可多次模拟破坏性水下爆炸过程这一优点。
- ❌ `c4` [Essential, factual_anchor, w=5, positive] 明确指出数值模拟可以获得大量过程量数据及曲线
    judge: 候选回答未提到数值模拟可以获得大量过程量数据及曲线。
- ❌ `c5` [Important, mechanism_explanation, w=3, positive] 解释数值模拟在室内计算平台完成，而实验通常需在外场进行
    judge: 候选回答未提及数值模拟可在室内计算平台完成、传统实验通常需在外场进行这一点。
- ❌ `c6` [Important, mechanism_explanation, w=3, positive] 耗费大量人力物力
    judge: 候选回答未提及传统水下爆炸实验耗费大量人力物力或数值模拟可降低这类消耗。
- ❌ `c7` [Important, mechanism_explanation, w=3, positive] 说明数值模拟能够直观展现物理过程和模型各部分响应
    judge: 候选回答未说明数值模拟能够直观展现物理过程和模型各部分响应。
- ❌ `c8` [Important, mechanism_explanation, w=3, positive] 说明实验受测试系统局限只能获得部分图景，而数值模拟可用于再现更完整的物理图景
    judge: 候选回答未说明实验只能获得部分图景以及数值模拟可再现更完整物理图景的优点。
- ❌ `c9` [Important, process_completeness, w=3, positive] 回答至少覆盖 4 项不同优点：成本低廉、可重复性、易操作性、物理图景再现性、过程参量数据丰富
    judge: 候选回答未列出任何数值模拟相对传统水下爆炸实验的优点，更未覆盖至少4项指定优点。
- ❌ `c10` [Optional, comparative_balance, w=1, positive] 回答明确以“与传统水下爆炸实验相比”的对照方式呈现数值模拟优点
    judge: 候选回答未列举或对照呈现数值模拟相较传统水下爆炸实验的优点，而是表示无法回答。
- ✅ `c11` [Pitfall, anti_hacking, w=4, negative] 回答以套话/开场白/元评论开头而无实质内容
    judge: 候选回答以关于所给语料不相关、无法回答的元评论开头，并未提供题目所问的实质内容。
- ❌ `c12` [Pitfall, anti_hacking, w=3, negative] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复
    judge: 候选回答很简短，没有包含大量无关背景铺垫或重复内容。

### #62 (question_id=63, anchored=0.00, raw=0.00)


**问题**: 在进行鱼雷壳体结构的数值模拟分析时，为什么必须在模型中考虑内部构件的影响？


- ❌ `c1` [Important, factual_anchor, w=3, positive] 提到鱼雷内部构件的具体实例，包括战斗部装药或燃料舱
    judge: 候选回答未提到鱼雷内部构件的具体实例，如战斗部装药或燃料舱。
- ❌ `c2` [Important, factual_anchor, w=3, positive] 提到内部构件的惯性效应会使壳体局部、尤其隔板附近出现有效应力集中
    judge: 候选回答未提到内部构件的惯性效应，也未说明其会导致壳体局部尤其隔板附近的有效应力集中。
- ❌ `c4` [Essential, comparative_balance, w=5, positive] 对比同一冲击工况下考虑内部构件与不考虑内部构件时的壳体毁伤程度，指出不考虑时毁伤程度更小
    judge: 候选回答未对比考虑与不考虑内部构件时的壳体毁伤程度，也未指出不考虑内部构件时毁伤程度更小。
- ❌ `c5` [Essential, comparative_balance, w=5, positive] 对比考虑内部构件与不考虑内部构件时的壳体毁伤区域分布，指出分布会显著变化
    judge: 候选回答未对比考虑与不考虑内部构件时壳体毁伤区域分布，也未指出其会显著变化。
- ❌ `c6` [Important, comparative_balance, w=3, positive] 指出战斗部装药和燃料会增大对应舱段壳体的抗冲击性能
    judge: 候选回答未提及战斗部装药和燃料会增大对应舱段壳体的抗冲击性能。
- ❌ `c7` [Essential, decision_logic, w=5, positive] 给出结论：鱼雷壳体数值模拟的有限元模型必须考虑内部构件影响
    judge: 候选回答表示无法回答，并未明确给出有限元模型必须考虑内部构件影响的结论。
- ✅ `c8` [Pitfall, anti_hacking, w=4, negative] 回答以套话/开场白/元评论开头而无实质内容
    judge: 候选回答以关于语料库内容的元评论开头，并未提供关于鱼雷壳体内部构件影响的实质性技术回答。
- ❌ `c9` [Pitfall, anti_hacking, w=3, negative] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复
    judge: 候选回答较简短，虽提到与题目无关的语料库背景，但未包含大量冗长铺垫或重复内容。
- ❌ `c10` [Pitfall, anti_hacking, w=4, negative] 只描述考虑内部构件或不考虑内部构件中的单一一方，未形成对比
    judge: 候选回答未描述考虑或不考虑内部构件的任何一方，而是表示无法基于语料回答，因此未触发该负向规则。

### #68 (question_id=69, anchored=0.00, raw=0.00)


**问题**: 在远场水下爆炸模拟中，声学材料对Taylor理论的适用性有何影响？


- ❌ `c1` [Essential, factual_anchor, w=5, positive] 指出声学材料具有吸收声波的性质
    judge: 候选回答未指出声学材料具有吸收声波的性质。
- ❌ `c2` [Essential, factual_anchor, w=5, positive] 指出声学材料的反射率不为100%
    judge: 候选回答未提到声学材料的反射率不为100%。
- ❌ `c3` [Essential, factual_anchor, w=5, positive] 指出 Taylor 理论假设入射波等于反射波
    judge: 候选回答未提及Taylor理论假设入射波等于反射波。
- ❌ `c4` [Important, mechanism_explanation, w=3, positive] 说明把 Taylor 理论直接用于声学材料会产生较大误差
    judge: 候选回答仅表示无法回答并建议提供文献，没有说明将 Taylor 理论直接用于声学材料会产生较大误差。
- ❌ `c5` [Important, mechanism_explanation, w=3, positive] 说明误差来源于声学材料的吸收使入射波等于反射波这一假设失效
    judge: 候选回答未说明声学材料吸收导致入射波等于反射波的假设失效这一误差机制。
- ❌ `c6` [Important, mechanism_explanation, w=3, positive] 指出需要根据特定材料的吸收特性重新推导计算公式
    judge: 候选回答仅表示无法回答并建议提供文献，未指出需根据特定材料的吸收特性重新推导计算公式。
- ❌ `c7` [Important, process_completeness, w=3, positive] 明确重新推导的是总压力载荷计算公式
    judge: 候选回答未重新推导或提及总压力载荷计算公式，而是表示无法回答。
- ❌ `c8` [Optional, comparative_balance, w=1, positive] 对比声学材料与100%反射边界在反射特性上的差异
    judge: 候选回答未对比声学材料与100%反射边界在反射特性上的差异，只是说明无法回答。
- ✅ `c9` [Pitfall, anti_hacking, w=4, negative] 回答以套话/开场白/元评论开头而无实质内容
    judge: 候选回答以关于语料库不包含相关内容的元评论开头，并未直接给出题目所问的实质性技术回答。
- ❌ `c10` [Pitfall, anti_hacking, w=3, negative] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复
    judge: 候选回答较简短，没有大量无关背景铺垫或重复内容。

### #75 (question_id=60, anchored=0.00, raw=0.00)


**问题**: 在LS-DYNA中模拟复合材料夹层板（FRP Sandwich）时，常用的各向同性材料模型是否适用？


- ❌ `c1` [Essential, decision_logic, w=6, positive] 明确指出在 LS-DYNA 中模拟 FRP Sandwich 时，常用的各向同性材料模型不适用
    judge: 候选回答未明确指出常用各向同性材料模型在LS-DYNA模拟FRP Sandwich时不适用，而是表示无法判断。
- ❌ `c2` [Essential, factual_anchor, w=5, positive] 指出 GFRP 面层具有显著的各向异性
    judge: 候选回答未提及GFRP面层或其显著各向异性。
- ❌ `c3` [Essential, mechanism_explanation, w=5, positive] 指出复合材料建模需要定义不同方向的模量
    judge: 候选回答未提到复合材料建模需要定义不同方向的模量。
- ❌ `c4` [Important, factual_anchor, w=4, positive] 提到面层常用复合材料模型 Mat 22/54
    judge: 候选回答未提到面层常用的复合材料模型 Mat 22/54。
- ❌ `c5` [Important, factual_anchor, w=4, positive] 提到芯材硬质泡沫常用 Mat 63
    judge: 候选回答未提到芯材硬质泡沫常用 Mat 63。
- ❌ `c6` [Important, mechanism_explanation, w=3, positive] 解释 Mat 63 用于描述芯材的压溃吸能特性
    judge: 候选回答未提及 Mat 63，也未解释其用于描述芯材压溃吸能特性。
- ❌ `c7` [Important, process_completeness, w=3, positive] 说明 FRP 面层与泡沫芯材应采用不同的材料模型而不是单一模型
    judge: 候选回答未说明FRP面层与泡沫芯材应采用不同材料模型，而只是表示无法判断。
- ❌ `c8` [Optional, decision_logic, w=2, positive] 答案提到“是否适用”时给出明确否定结论，而不是只描述材料性质
    judge: 候选回答没有明确给出各向同性材料模型不适用的否定结论，而是表示无法判断。
- ✅ `c9` [Pitfall, anti_hacking, w=4, negative] 回答以套话/开场白/元评论开头而无实质内容
    judge: 候选回答开头即以语料来源的元评论展开，并未直接提供关于各向同性材料模型适用性的实质性判断。
- ❌ `c10` [Pitfall, anti_hacking, w=3, negative] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复
    judge: 候选回答较简短，虽提到无关语料背景，但未包含大量无关铺垫或重复内容。

### #87 (question_id=72, anchored=0.00, raw=0.00)


**问题**: 在执行ALE的Advection（输运）阶段时，若追求在不产生非物理极值的前提下获得最高精度，应选择哪种算法？


- ❌ `c1` [Essential, decision_logic, w=6, positive] 明确给出最终选择是 MUSCL 算法
    judge: 候选回答明确选择的是 PPM 算法，而不是 MUSCL 算法。
- ❌ `c2` [Essential, decision_logic, w=5, positive] 说明在追求最高精度时，MUSCL 因为提供二阶精度而优先于低阶输运格式
    judge: 候选回答选择并论证的是 PPM，而未说明 MUSCL 因提供二阶精度而优先于低阶输运格式。
- ❌ `c3` [Essential, decision_logic, w=5, positive] 说明 MUSCL 的单调限幅器用于抑制数值震荡或非物理极值
    judge: 候选回答未说明MUSCL的单调限幅器及其用于抑制数值震荡或非物理极值的作用。
- ❌ `c4` [Important, factual_anchor, w=3, positive] 指出 MUSCL 采用线性逼近
    judge: 候选回答仅提到MUSCL作为对比方案，未指出MUSCL采用线性逼近。
- ❌ `c5` [Important, factual_anchor, w=3, positive] 指出 Donor Cell 算法采用常数逼近
    judge: 候选回答未提到 Donor Cell 算法，也未指出其采用常数逼近。
- ❌ `c6` [Important, comparative_balance, w=3, positive] 比较 MUSCL 与 Donor Cell 时，说明 MUSCL 更能捕捉梯度
    judge: 候选回答未比较 MUSCL 与 Donor Cell，也未说明 MUSCL 更能捕捉梯度。
- ❌ `c7` [Pitfall, anti_hacking, w=4, negative] 回答以套话/开场白/元评论开头而无实质内容
    judge: 候选回答开头直接给出了应选择PPM算法的实质性答案，并非无实质内容的套话或元评论。
- ❌ `c8` [Pitfall, anti_hacking, w=3, negative] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复
    judge: 候选回答虽包含一些论文背景和引用，但整体篇幅不算冗长，也没有大量无关铺垫或重复。
- ❌ `c9` [Pitfall, anti_hacking, w=5, negative] 给出多个
    judge: 候选回答明确选择了单一算法PPM，虽提及MUSCL等作为对比，但未给出多个候选答案。
- ❌ `c10` [Pitfall, anti_hacking, w=5, negative] 列算法选项而不做最终选择
    judge: 候选回答明确最终选择了PPM算法，并非只列出算法选项而不做选择。

### #61 (question_id=62, anchored=0.16, raw=0.16)


**问题**: 在使用ABAQUS程序模拟水下爆炸时，其主要特点和局限性是什么？


- ❌ `c1` [Essential, factual_anchor, w=5, positive] 明确指出 ABAQUS 是把经验公式或试验得到的水下爆炸载荷直接施加到结构上，而不是由程序自行求爆轰载荷
    judge: 候选回答说明需外部提供爆炸载荷、不能自行完成爆轰模拟，但未明确指出载荷来自经验公式或试验并直接施加到结构上。
- ✅ `c2` [Essential, factual_anchor, w=5, positive] 明确指出 ABAQUS 不计算炸药爆轰过程
    judge: 候选回答明确写到“不包含炸药爆轰模块”，需外部提供爆炸载荷，不能独立完成全过程模拟。
- ❌ `c3` [Essential, factual_anchor, w=5, positive] 明确指出 ABAQUS 不计算载荷传播过程
    judge: 候选回答提到需外部提供爆炸载荷、不能完成全过程模拟，但未明确指出ABAQUS不计算载荷传播过程。
- ❌ `c4` [Essential, factual_anchor, w=5, positive] 明确指出计算模型中不包含炸药，只包含结构及其周围流场
    judge: 候选回答提到不包含炸药爆轰模块、需外部提供载荷，但未明确说明计算模型只包含结构及其周围流场。
- ❌ `c5` [Important, factual_anchor, w=3, positive] 提到 ABAQUS 的 Standard 与 Explicit 两个主模块
    judge: 候选回答未提到 ABAQUS 的 Standard 与 Explicit 两个主模块。
- ❌ `c6` [Important, process_completeness, w=3, positive] 提到 Standard 与 Explicit 之间可以进行结果传递
    judge: 候选回答未提到ABAQUS/Standard与ABAQUS/Explicit之间可以进行结果传递。
- ❌ `c7` [Important, process_completeness, w=3, positive] 提到 ABAQUS 会自动计算结构的动态响应与流场压力分布
    judge: 候选回答只提到可进行结构动态响应分析，未明确提到ABAQUS会自动计算流场压力分布。
- ❌ `c8` [Important, mechanism_explanation, w=3, positive] 解释省略爆轰计算步骤和炸药模型是计算速度快的原因
    judge: 候选回答提到ABAQUS不包含炸药爆轰模块、需外部提供爆炸载荷，但未明确解释省略爆轰计算步骤和炸药模型是计算速度快的原因。
- ❌ `c9` [Pitfall, anti_hacking, w=4, negative] 回答以套话/开场白/元评论开头而无实质内容
    judge: 候选回答开头即进入ABAQUS模拟水下爆炸的特点，属于实质内容而非套话或元评论。
- ❌ `c10` [Pitfall, anti_hacking, w=3, negative] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复
    judge: 候选回答结构清晰、篇幅适中，未包含大量无关背景铺垫或明显重复内容。
