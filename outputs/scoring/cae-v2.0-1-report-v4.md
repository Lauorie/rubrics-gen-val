# CAE-v2.0-1 RLM Scoring Report

- 候选模型: `deepseek/deepseek-v4-flash`
- 评分模型: `openai/gpt-5.5`
- 总样本: 92 · 评分成功: 92 · 错误: 0
- 生成时间: 2026-05-25T17:27:12.780073+00:00

## 1. 总体得分

| 指标 | 数值 |
|---|---|
| 平均原始分 (raw) | 0.70 |
| 平均锚定分 (anchored) | 0.71 |

## 2. 按题型分组 (question_type)

| 分组 | 数量 | mean (raw) | mean (anchored) |
|---|---|---|---|
| 简答题 | 47 | 0.71 | 0.71 |
| 主观题 | 20 | 0.66 | 0.66 |
| 决策题 | 18 | 0.62 | 0.66 |
| 数值提取题 | 2 | 0.95 | 0.95 |
| 流程描述题 | 2 | 1.00 | 1.00 |
| 对比分析题 | 2 | 0.84 | 0.84 |
| 数值关系题 | 1 | 1.00 | 1.00 |

## 3. 按难度 (difficulty)

| 分组 | 数量 | mean (raw) | mean (anchored) |
|---|---|---|---|
| 困难 | 37 | 0.71 | 0.72 |
| 中等 | 36 | 0.64 | 0.64 |
| 简单 | 19 | 0.80 | 0.80 |

## 4. 失分点 — criterion_type 命中率最低

（仅 sign=positive，按命中率升序）

| criterion_type | 总数 | 命中 | 命中率 |
|---|---|---|---|
| comparative_balance | 35 | 20 | 57.1% |
| factual_anchor | 280 | 198 | 70.7% |
| decision_logic | 64 | 46 | 71.9% |
| mechanism_explanation | 164 | 118 | 72.0% |
| numeric_precision | 26 | 21 | 80.8% |
| process_completeness | 26 | 22 | 84.6% |

## 5. 得分点 — criterion_type 命中率最高

（仅 sign=positive，按命中率降序）

| criterion_type | 总数 | 命中 | 命中率 |
|---|---|---|---|
| process_completeness | 26 | 22 | 84.6% |
| numeric_precision | 26 | 21 | 80.8% |
| mechanism_explanation | 164 | 118 | 72.0% |
| decision_logic | 64 | 46 | 71.9% |
| factual_anchor | 280 | 198 | 70.7% |
| comparative_balance | 35 | 20 | 57.1% |

## 6. Pitfall 触发分析

（仅 criterion_type=anti_hacking 且 met=True，按触发次数降序）

| pitfall | 触发次数 | 占比 |
|---|---|---|
| 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复 | 15 | 16.3% |
| 给出多个 | 5 | 5.4% |
| 回答以套话/开场白/元评论开头而无实质内容 | 1 | 1.1% |

## 7. 最低分 10 题


### #21 (question_id=22, anchored=0.00, raw=0.00)


**问题**: 鱼雷壳体在遭受侧向冲击时，为什么最大等效应变点往往不在正对爆心的位置？


- ❌ `c2` [Essential, factual_anchor, w=5, positive] 指出内部构件（如燃料、炸药）的分布会改变局部刚度
    judge: 候选回答只提到加强筋等结构因素，没有指出燃料、炸药等内部构件分布会改变局部刚度。
- ❌ `c3` [Essential, factual_anchor, w=5, positive] 指出内部构件（如燃料、炸药）的分布会改变局部惯性
    judge: 候选回答未提到燃料、炸药等内部构件的分布及其对局部惯性的影响。
- ❌ `c4` [Essential, factual_anchor, w=5, positive] 指出内部装填炸药会提高该舱段的抗冲击能力
    judge: 候选回答未提到内部装填炸药会提高该舱段抗冲击能力。
- ❌ `c5` [Essential, factual_anchor, w=5, positive] 指出等效应变会向构件边缘或隔板处转移
    judge: 候选回答虽提到破口向壳体边缘扩展，但没有明确指出最大等效应变会向构件边缘或隔板处转移。
- ❌ `c6` [Important, comparative_balance, w=3, positive] 指出在相同冲击波载荷下，不同舱室的动态响应会不同
    judge: 候选回答未指出在相同冲击波载荷下不同舱室会产生不同的动态响应。
- ❌ `c7` [Important, mechanism_explanation, w=3, positive] 解释局部刚度或抗冲击能力提高后，等效应变会在相邻边缘或隔板处集中
    judge: 候选回答仅笼统提到加强筋会影响最大应变位置，未解释局部刚度或抗冲击能力提高后应变会在相邻边缘或隔板处集中。
- ❌ `c8` [Pitfall, anti_hacking, w=4, negative] 回答以套话/开场白/元评论开头而无实质内容
    judge: 候选回答开头直接概括了问题并提出从物理和数值两方面解释，属于实质性引入而非空泛套话或元评论。
- ❌ `c9` [Pitfall, anti_hacking, w=3, negative] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复
    judge: 候选回答篇幅适中，虽有引用和数值原因扩展，但未包含大量无关背景铺垫或重复。

### #45 (question_id=46, anchored=0.00, raw=0.00)


**问题**: 混凝土重力坝在水下爆炸中的“内能吸收曲线”呈现什么特征？这说明了什么？


- ❌ `c1` [Essential, factual_anchor, w=5, positive] 指出内能曲线在冲击瞬间迅速攀升
    judge: 候选回答仅以占位符表示具体内容，未明确指出内能曲线在冲击瞬间迅速攀升。
- ❌ `c2` [Essential, factual_anchor, w=5, positive] 指出内能曲线会达到峰值
    judge: 候选回答未明确指出内能吸收曲线会达到峰值。
- ❌ `c3` [Essential, factual_anchor, w=5, positive] 指出峰值之后曲线保持在一定水平
    judge: 候选回答仅以省略号占位，未明确指出内能吸收曲线在峰值之后保持在一定水平。
- ❌ `c4` [Essential, factual_anchor, w=5, positive] 指出峰值之后曲线伴有小幅震荡
    judge: 候选回答仅以省略号和占位内容描述曲线特征，未明确指出峰值之后曲线伴有小幅震荡。
- ❌ `c5` [Important, mechanism_explanation, w=3, positive] 指出大坝的毁伤主要发生在冲击波作用的极短时间内（毫秒级）
    judge: 候选回答未明确指出大坝毁伤主要发生在冲击波作用的毫秒级极短时间内。
- ❌ `c6` [Important, mechanism_explanation, w=3, positive] 指出后续震荡反映了大坝在平衡位置附近的弹性回弹或振动
    judge: 候选回答仅以省略号占位，未明确指出后续震荡反映大坝在平衡位置附近的弹性回弹或振动。
- ✅ `c7` [Pitfall, anti_hacking, w=4, negative] 回答以套话/开场白/元评论开头而无实质内容
    judge: 候选回答以“根据论文……”等元评论开头，并用占位符代替实质内容。
- ❌ `c8` [Pitfall, anti_hacking, w=3, negative] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复
    judge: 候选回答篇幅很短，未包含大量无关背景铺垫或重复内容。

### #52 (question_id=53, anchored=0.00, raw=0.00)


**问题**: 为什么在包含复杂舱室的MM-ALE（多物质ALE）仿真中需要定义“真空（Vacuum）”？


- ❌ `c1` [Essential, factual_anchor, w=5, positive] 指出在多物质网格中，复杂舱室的空腔部分通常定义为 vacuum
    judge: 候选回答将真空主要描述为标记结构件占据空间，而没有明确指出多物质网格中复杂舱室的空腔部分通常定义为 vacuum。
- ❌ `c4` [Important, mechanism_explanation, w=3, positive] 说明 vacuum 提供了可供其他材料输运和充填的空间
    judge: 候选回答主要强调真空防止材料侵占结构空间，未明确说明真空代表可被其他材料输运并充填的空余空间。
- ❌ `c5` [Important, mechanism_explanation, w=3, positive] 说明受冲击后的水流或结构碎片可以进入该 vacuum 区域
    judge: 候选回答强调真空区域用于阻止流动材料进入结构占据空间，未说明受冲击后的水流或结构碎片可以进入该 vacuum 区域。
- ❌ `c6` [Important, mechanism_explanation, w=3, positive] 说明若不定义 vacuum，不相容材料可能在同一时间步内强行占据同一网格，从而引发压力异常升高
    judge: 候选回答说明了未定义 vacuum 会导致材料重叠/占据同一空间，但未提到由此引发压力异常升高。
- ❌ `c7` [Important, mechanism_explanation, w=3, positive] 导致计算不稳定
    judge: 候选回答只提到体积分数矛盾和材料侵占结构位置，未明确说明未定义真空会导致计算不稳定。
- ❌ `c8` [Pitfall, anti_hacking, w=4, negative] 把 vacuum 解释成物理抽真空或吸力机制，而不是数值上的空腔占位
    judge: 候选回答将真空解释为数值上的虚拟材料/空腔占位以防止材料重叠，并未解释为物理抽真空或吸力机制。
- ❌ `c9` [Pitfall, anti_hacking, w=3, negative] 只说 vacuum 是“空的”，但没有提材料输运或材料占据冲突
    judge: 候选回答明确提到了材料输运以及防止材料体积重叠/占据冲突，并非只说 vacuum 是空的。
- ❌ `c10` [Pitfall, anti_hacking, w=4, negative] 回答以套话/开场白/元评论开头而无实质内容
    judge: 候选回答开头即直接说明定义真空的关键作用，包含实质内容，并非套话、开场白或元评论。
- ❌ `c11` [Pitfall, anti_hacking, w=3, negative] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复
    judge: 候选回答虽有一定展开，但内容基本围绕真空定义的作用和机理，没有大量无关背景铺垫或明显重复。

### #90 (question_id=75, anchored=0.00, raw=0.00)


**问题**: 在设计潜艇复合材料面板抗冲击仿真方案时，若需同时精确考量冲击波和气泡脉动的全过程载荷，首选哪种LS-DYNA功能？


- ❌ `c1` [Essential, decision_logic, w=6, positive] 明确给出最终选择是 ALE（Arbitrary Lagrangian-Eulerian）多物质流固耦合
    judge: 候选回答的最终结论是否定语料中存在该功能并建议参考*LOAD_UNDEX或AUTODYN，而未明确选择ALE多物质流固耦合。
- ❌ `c2` [Essential, factual_anchor, w=5, positive] 指出 ALE 的英文全称是 Arbitrary Lagrangian-Eulerian
    judge: 候选回答只提到“ALE”，未指出其英文全称为“Arbitrary Lagrangian-Eulerian”。
- ❌ `c3` [Essential, factual_anchor, w=5, positive] 指出所选功能属于 LS-DYNA 的多物质流固耦合方案
    judge: 候选回答未指出其所选或推荐的LS-DYNA功能属于多物质流固耦合方案。
- ❌ `c4` [Essential, decision_logic, w=5, positive] 说明 ALE 可以同时处理炸药爆轰形成的冲击波
    judge: 候选回答仅提到某论文对比了ALE方法及部分研究涉及冲击波阶段，未说明ALE可以同时处理炸药爆轰形成的冲击波。
- ❌ `c5` [Essential, decision_logic, w=5, positive] 说明 ALE 可以同时处理爆轰产物气泡的脉动全过程载荷
    judge: 候选回答没有说明ALE可以同时处理爆轰产物气泡的脉动全过程载荷，反而称相关ALE论文排除了气泡脉动。
- ❌ `c7` [Important, comparative_balance, w=3, positive] 对比指出 USA 或边界元方法难以处理这种近场全过程载荷
    judge: 候选回答未对比指出 USA 或边界元方法难以处理近场冲击波与气泡脉动全过程载荷。
- ❌ `c8` [Pitfall, anti_hacking, w=4, negative] 回答以套话/开场白/元评论开头而无实质内容
    judge: 候选回答开头直接给出了检索结论和核心判断，并非无实质内容的套话或元评论。
- ✅ `c9` [Pitfall, anti_hacking, w=3, negative] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复
    judge: 候选回答没有直接给出首选功能，而是展开大量文献检索过程和背景说明，篇幅明显冗长且包含与问题无关的铺垫。

### #41 (question_id=42, anchored=0.10, raw=0.10)


**问题**: 在FSI迭代过程中，为什么要引入“Aitken方法”？其核心优势是什么？


- ❌ `c1` [Essential, factual_anchor, w=5, positive] 明确指出 Aitken 方法用于显式分区耦合的 FSI 迭代过程
    judge: 候选回答提到了FSI迭代和分区耦合方案，但没有明确指出是“显式分区耦合”。
- ❌ `c2` [Essential, factual_anchor, w=5, positive] 明确指出 Aitken 方法作用于流固界面的位移传递
    judge: 候选回答提到位移差值和松弛因子，但未明确指出 Aitken 方法作用于流固界面的位移传递。
- ❌ `c3` [Essential, factual_anchor, w=5, positive] 明确指出位移传递需要通过松弛因子进行平滑
    judge: 候选回答提到自适应欠松弛和位移差值计算松弛因子，但没有明确指出“位移传递”需要通过松弛因子进行平滑。
- ❌ `c4` [Essential, factual_anchor, w=5, positive] 明确指出 Aitken 方法是一种向量外推技术
    judge: 候选回答将 Aitken 方法描述为自适应欠松弛策略，但未明确指出其是一种向量外推技术。
- ✅ `c5` [Important, mechanism_explanation, w=3, positive] 解释 Aitken 方法通过自适应确定 under-relaxation factor 来提高迭代收敛速度
    judge: 候选回答明确说明Aitken方法通过动态/自适应确定欠松弛因子来稳定并加速FSI迭代收敛。
- ❌ `c6` [Important, comparative_balance, w=3, positive] 指出 Aitken 方法在流固交互剧烈的动态过程中尤其有效
    judge: 候选回答只提到初始大变形和迭代不稳定，并未指出 Aitken 方法在流固交互剧烈的动态过程中尤其有效。
- ❌ `c7` [Important, comparative_balance, w=3, positive] 指出 Aitken 方法比固定松弛因子更高效
    judge: 候选回答说明了Aitken可自适应调整并提升收敛效率，但未明确指出其相较于固定松弛因子更高效。
- ❌ `c8` [Pitfall, anti_hacking, w=4, negative] 回答以套话/开场白/元评论开头而无实质内容
    judge: 候选回答开头直接说明引入Aitken方法的目的，包含实质性技术内容，并非套话或元评论。
- ❌ `c9` [Pitfall, anti_hacking, w=3, negative] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复
    judge: 候选回答篇幅适中，内容基本围绕引入Aitken方法的原因和核心优势展开，没有大量无关背景或重复。

### #61 (question_id=62, anchored=0.16, raw=0.16)


**问题**: 在使用ABAQUS程序模拟水下爆炸时，其主要特点和局限性是什么？


- ❌ `c1` [Essential, factual_anchor, w=5, positive] 明确指出 ABAQUS 是把经验公式或试验得到的水下爆炸载荷直接施加到结构上，而不是由程序自行求爆轰载荷
    judge: 候选回答只提到ABAQUS不提供炸药爆轰过程模拟能力，但未明确说明其将经验公式或试验得到的水下爆炸载荷直接施加到结构上。
- ✅ `c2` [Essential, factual_anchor, w=5, positive] 明确指出 ABAQUS 不计算炸药爆轰过程
    judge: 候选回答在局限性中明确写到“程序本身不提供炸药爆轰过程的模拟能力”。
- ❌ `c3` [Essential, factual_anchor, w=5, positive] 明确指出 ABAQUS 不计算载荷传播过程
    judge: 候选回答只提到不模拟炸药爆轰过程，未明确指出ABAQUS不计算载荷传播过程。
- ❌ `c4` [Essential, factual_anchor, w=5, positive] 明确指出计算模型中不包含炸药，只包含结构及其周围流场
    judge: 候选回答提到不模拟炸药爆轰过程并讨论结构/水域建模，但未明确指出计算模型中不包含炸药且只包含结构及其周围流场。
- ❌ `c5` [Important, factual_anchor, w=3, positive] 提到 ABAQUS 的 Standard 与 Explicit 两个主模块
    judge: 候选回答未提到 ABAQUS 的 Standard 与 Explicit 两个主模块。
- ❌ `c6` [Important, process_completeness, w=3, positive] 提到 Standard 与 Explicit 之间可以进行结果传递
    judge: 候选回答未提到 ABAQUS/Standard 与 ABAQUS/Explicit 之间可以进行结果传递。
- ❌ `c7` [Important, process_completeness, w=3, positive] 提到 ABAQUS 会自动计算结构的动态响应与流场压力分布
    judge: 候选回答未提到ABAQUS会自动计算结构动态响应与流场压力分布。
- ❌ `c8` [Important, mechanism_explanation, w=3, positive] 解释省略爆轰计算步骤和炸药模型是计算速度快的原因
    judge: 候选回答虽提到不包含炸药爆轰步骤，但未解释省略爆轰计算步骤和炸药模型是计算速度快的原因。
- ❌ `c9` [Pitfall, anti_hacking, w=4, negative] 回答以套话/开场白/元评论开头而无实质内容
    judge: 候选回答开头即进入“主要特点”的实质内容，并非套话、开场白或元评论。
- ❌ `c10` [Pitfall, anti_hacking, w=3, negative] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复
    judge: 候选回答结构清晰且内容基本围绕ABAQUS模拟水下爆炸的特点和局限性展开，没有大量无关背景铺垫或重复。

### #64 (question_id=65, anchored=0.18, raw=0.18)


**问题**: 简述水下爆炸研究的主要学术领域及其关注重点。


- ❌ `c1` [Essential, factual_anchor, w=5, positive] 明确提到“爆轰物理学”是水下爆炸研究的一个主要学术领域
    judge: 候选回答未明确提到“爆轰物理学”作为水下爆炸研究的主要学术领域。
- ✅ `c2` [Essential, factual_anchor, w=5, positive] 明确提到“流固耦合”是水下爆炸研究的一个主要学术领域
    judge: 候选回答明确将“流固耦合”列为水下爆炸研究的主要学术领域之一。
- ❌ `c3` [Essential, factual_anchor, w=5, positive] 明确提到“结构冲击动力学”是水下爆炸研究的一个主要学术领域
    judge: 候选回答提到了结构响应与毁伤效应等内容，但未明确提到“结构冲击动力学”这一主要学术领域。
- ❌ `c4` [Important, mechanism_explanation, w=3, positive] 说明爆轰物理学关注炸药从固体转变为高温高压气体的过程
    judge: 候选回答未说明爆轰物理学及炸药由固体转变为高温高压气体的过程。
- ❌ `c5` [Important, mechanism_explanation, w=3, positive] 说明爆轰物理学关注由状态突跃产生冲击波的形成
    judge: 候选回答虽提到冲击波模拟，但未说明爆轰物理学及其关注由状态突跃产生冲击波的形成机制。
- ❌ `c6` [Important, mechanism_explanation, w=3, positive] 说明流固耦合包含“冲击波作用于结构引起运动，结构运动反过来影响流场压力分布”这一双向作用链
    judge: 候选回答仅泛称流体与结构界面相互作用，未明确说明冲击波致结构运动及结构运动反过来影响流场压力分布的双向作用链。
- ❌ `c7` [Important, mechanism_explanation, w=3, positive] 说明结构冲击动力学关注结构在爆炸载荷下的弹性、弹塑性直至断裂响应
    judge: 候选回答提到结构动态响应和破坏模式，但未明确说明结构冲击动力学关注弹性、弹塑性直至断裂的响应过程。
- ❌ `c8` [Optional, comparative_balance, w=1, positive] 说明结构冲击动力学关注材料/几何非线性和应变率效应对响应的影响
    judge: 候选回答虽提到结构动态响应与破坏模式，但未说明材料/几何非线性及应变率效应对响应的影响。
- ❌ `c9` [Pitfall, anti_hacking, w=4, negative] 回答以套话/开场白/元评论开头而无实质内容
    judge: 候选回答开头直接概述主要学术领域，包含实质内容，并非套话、开场白或元评论。
- ❌ `c10` [Pitfall, anti_hacking, w=3, negative] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复
    judge: 候选回答围绕水下爆炸研究领域及关注重点展开，虽有一定细节但不属于冗长无关铺垫或重复。

### #81 (question_id=66, anchored=0.18, raw=0.15)


**问题**: 在进行混凝土重力坝抗爆性能评估时，若起爆深度从10m增加到40m（深水），破坏模式应如何预测变化？


- ✅ `c1` [Essential, decision_logic, w=6, positive] 明确给出最终结论：破坏重心从坝头转向下游折坡处
    judge: 候选回答明确总结了破坏位置/重心从坝头向下游折坡处转移。
- ❌ `c2` [Essential, decision_logic, w=5, positive] 说明起爆深度增大后，挡水坝段颈部抗爆性能增强
    judge: 候选回答只说明破坏范围先增大后减小及坝颈/下游折坡为薄弱部位，并未说明起爆深度增大后挡水坝段颈部抗爆性能增强。
- ❌ `c3` [Essential, decision_logic, w=5, positive] 说明深水工况下的主导破坏判断依据是下游面反射引起的受损区
    judge: 候选回答虽提到深水时破坏集中在下游折坡附近，但未说明主导破坏的判断依据是下游面反射引起的受损区。
- ❌ `c5` [Important, mechanism_explanation, w=4, positive] 指出深水下冲击波受水压影响，能量主要通过应力波传递
    judge: 候选回答未指出深水下冲击波受水压影响，也未说明能量主要通过应力波传递。
- ❌ `c6` [Important, mechanism_explanation, w=4, positive] 指出下游面反射会引起震塌和下游折坡处开裂
    judge: 候选回答提到了下游面震塌和下游折坡处开裂，但未指出其由下游面反射引起。
- ✅ `c7` [Important, comparative_balance, w=3, positive] 与10 m工况相比，40 m深水下的主导破坏部位从坝头转向下游折坡处
    judge: 候选回答明确指出10 m时坝头/上游面等处开裂，而40 m时仅或主要在下游折坡处开裂，破坏位置从坝头向下游折坡转移。
- ✅ `c8` [Pitfall, anti_hacking, w=5, negative] 给出多个
    judge: 候选回答以编号条目列出了多个变化趋势和多种破坏模式，触发了“给出多个”的负向规则。
- ❌ `c9` [Pitfall, anti_hacking, w=5, negative] 列破坏部位或多个备选答案而不做最终判断
    judge: 候选回答虽列举了多个破坏部位，但明确给出了随起爆深度增加的最终变化判断，并非只列备选而不判断。
- ❌ `c10` [Pitfall, anti_hacking, w=4, negative] 回答以套话/开场白/元评论开头而无实质内容
    judge: 候选回答开头即给出依据论文、工况参数和变化趋势，包含实质内容，并非套话或元评论。
- ❌ `c11` [Pitfall, anti_hacking, w=3, negative] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复
    judge: 候选回答虽较详细且有少量重复，但内容基本围绕起爆深度变化下的破坏模式预测展开，并未包含大量无关背景铺垫。

### #78 (question_id=63, anchored=0.24, raw=0.24)


**问题**: 在模拟炸药爆轰瞬间的大变形流体运动时，如果计算频繁报错“负体积（Negative Volume）”，应如何调整建模描述方式？


- ✅ `c1` [Essential, decision_logic, w=6, positive] 明确给出将描述方式从 Lagrangian 改为 Eulerian 或 ALE
    judge: 候选回答多次明确要求使用 ALE 方法及相关 *CONTROL_ALE 设置，满足改为 ALE 描述方式的要求。
- ❌ `c2` [Essential, factual_anchor, w=5, positive] 指出 Lagrangian 描述中网格随材料运动
    judge: 候选回答讨论了 ALE 将材料运动与网格运动解耦，但未明确指出 Lagrangian 描述中网格随材料一起运动。
- ❌ `c3` [Essential, mechanism_explanation, w=5, positive] 指出大变形会使网格畸变，Jacobian 变为负，从而触发 Negative Volume
    judge: 候选回答多次提到大变形导致单元/网格畸变并触发负体积，但未明确指出单元 Jacobian 变为负这一机制。
- ❌ `c4` [Essential, mechanism_explanation, w=5, positive] 指出 Eulerian 描述中网格固定、材料在网格间输运
    judge: 候选回答主要讨论 ALE 重映射和平滑，并未明确指出 Eulerian 描述中网格固定、材料在网格间输运这一机制。
- ❌ `c5` [Essential, decision_logic, w=5, positive] 明确说明不应继续使用纯 Lagrangian 作为该问题的建模描述方式
    judge: 候选回答虽大量建议使用 ALE 设置，但未明确说明不应继续使用纯 Lagrangian 建模描述方式。
- ✅ `c6` [Essential, decision_logic, w=5, positive] 明确说明 Eulerian 或 ALE 是针对爆轰瞬间大变形流体运动的替代描述方式
    judge: 候选回答多处明确建议使用并设置 ALE 方法来处理爆轰大变形流体问题，说明其作为避免负体积的建模描述方式。
- ❌ `c7` [Important, comparative_balance, w=3, positive] 对比 Lagrangian 与 Eulerian/ALE 时，点出前者易发生单元畸变，后者通过固定网格或混合网格避免同类负体积问题
    judge: 候选回答虽多次提到 ALE 可通过重映射缓解畸变，但未明确对比 Lagrangian 描述易因网格随材料运动而单元畸变、Eulerian/ALE 通过固定或混合网格避免负体积。
- ❌ `c8` [Pitfall, anti_hacking, w=4, negative] 回答以套话/开场白/元评论开头而无实质内容
    judge: 候选回答开头虽有标题和依据说明，但紧接着进入具体建模调整建议，并非以无实质内容的套话或元评论开头。
- ✅ `c9` [Pitfall, anti_hacking, w=3, negative] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复
    judge: 候选回答篇幅很长，包含大量具体参数、公式、引用和设置细节，明显超出题目仅询问建模描述方式调整的范围。
- ❌ `c10` [Pitfall, anti_hacking, w=5, negative] 同时罗列 Lagrangian、Eulerian、ALE 但不做最终选择
    judge: 候选回答明确围绕 ALE 方法给出设置建议，并未同时罗列 Lagrangian、Eulerian、ALE 后不做最终选择。

### #13 (question_id=14, anchored=0.27, raw=0.27)


**问题**: 什么是“等效质量法”？其核心计算逻辑是什么？


- ❌ `c1` [Essential, factual_anchor, w=5, positive] 指出等效质量法是针对 LS-DYNA 计算远场水下爆炸时冲击波衰减过快而提出的修正方法
    judge: 候选回答虽提到远场水下爆炸修正，但未明确指出针对 LS-DYNA 计算且冲击波衰减过快这一提出背景。
- ✅ `c2` [Essential, factual_anchor, w=5, positive] 明确说明等效质量的求法是根据冲击波峰值压力的经验公式反推炸药质量
    judge: 候选回答明确指出将数值模拟得到的峰值压力代入Zamyshlyaev峰值压力经验公式反算得到等效药量。
- ❌ `c3` [Important, factual_anchor, w=3, positive] 提到经验公式可举例为 Cole 公式
    judge: 候选回答仅提到 Zamyshlyaev 经验公式，未提到 Cole 公式作为经验公式示例。
- ❌ `c4` [Essential, factual_anchor, w=5, positive] 说明仿真中使用的是比实际炸药量更大的模拟质量
    judge: 候选回答未说明仿真中使用的模拟质量比实际炸药量更大，只定义了模拟质量和等效质量。
- ✅ `c5` [Essential, decision_logic, w=5, positive] 说明调整模拟质量的目标是使目标爆距处的冲击波峰值压力达到实验或理论水平
    judge: 候选回答明确说通过修正药量参数使数值结果匹配经验公式，并在各爆距处用峰值压力反算等效质量，体现了调整质量以使目标爆距峰值压力达到理论水平的目标。
- ❌ `c6` [Important, mechanism_explanation, w=3, positive] 说明该方法用来弥补粗网格导致的数值耗散或冲击波峰值衰减过快
    judge: 候选回答仅提到网格离散误差导致峰值压力偏差，未明确说明等效质量法是为弥补粗网格引起的数值耗散或冲击波峰值衰减过快。
- ❌ `c8` [Pitfall, anti_hacking, w=4, negative] 回答以套话/开场白/元评论开头而无实质内容
    judge: 候选回答开头为主题标题并随即进入实质性背景与定义说明，不属于无实质内容的套话或元评论。
- ✅ `c9` [Pitfall, anti_hacking, w=3, negative] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复
    judge: 候选回答篇幅明显偏长，包含验证数据表、适用范围、论文引用等大量超出“定义与核心计算逻辑”所需的信息。
