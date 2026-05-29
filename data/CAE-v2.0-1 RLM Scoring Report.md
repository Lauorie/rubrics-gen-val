# CAE\-v2\.0\-1 RLM Scoring Report

- 候选模型: `deepseek/deepseek\-v4\-flash`

- 评分模型: `openai/gpt\-5\.4\-mini`

- 总样本: 94 · 评分成功: 94 · 错误: 0

- 生成时间: 2026\-05\-27T04:07:53\.757039\+00:00



```JSON
{
    "question_id": "1",
    "question": "在流固耦合（FSI）仿真中，“附加质量效应”为何会导致数值不稳定？",
    "reference_answer": "流体与结构密度接近： 当流体密度与结构密度在同一数量级时（如生物医疗中的血液与动脉，或水与轻质结构），隐式分区算法的迭代过程极易不收敛。压力偏析： 分区方案本质上属于压力偏析解法，在计算结构域时使用的是上一迭代步的压力，这种滞后在强耦合下会放大误差导致失稳。算法限制： 松散耦合（Loosely coupled）方案在此类问题下通常是不稳定的，必须采用单块（Monolithic）方法或改进的压力投影技术。",
    "question_type": "主观题",
    "difficulty": "困难",
    "scenario": "单文档多段落",
    "source": "Benson教材, 第4章, 第166-189页",
    "source_grounding": {
      "parsed_docs": [
        "Arbitrary_Lagrangian-Eulerian_and_Fluid-Structure_Interaction_Numerical_Simulation_Benson"
      ],
      "pages": [
        166,
        189
      ],
      "retrieved_chunk_ids": [
        "Arbitrary_Lagrangian-Eulerian_and_Fluid-Structure_Interaction_Numerical_Simulation_Benson:p180-p180:c1097",
        "Arbitrary_Lagrangian-Eulerian_and_Fluid-Structure_Interaction_Numerical_Simulation_Benson:p180-p180:c1088",
        "Arbitrary_Lagrangian-Eulerian_and_Fluid-Structure_Interaction_Numerical_Simulation_Benson:p175-p175:c1081"
      ],
      "ground_status": "page_specific"
    },
    "criteria": [
      {
        "id": "c1",
        "text": "指出流体密度与结构密度接近，或二者处于同一数量级时更容易出现 added-mass 问题",
        "category": "Essential",
        "weight": 5,
        "sign": "positive",
        "criterion_type": "factual_anchor",
        "evidence_quote": null
      },
      {
        "id": "c2",
        "text": "指出当 added-mass effect 很重要时，强耦合迭代过程可能变得困难甚至不收敛",
        "category": "Essential",
        "weight": 5,
        "sign": "positive",
        "criterion_type": "factual_anchor",
        "evidence_quote": "the iterative process in the strongly coupled scheme may be difficult (even non-convergent) when the so-called “added-mass effect” is important"
      },
      {
        "id": "c3",
        "text": "指出分区方法在结构域计算时使用的是上一迭代步的压力",
        "category": "Essential",
        "weight": 5,
        "sign": "positive",
        "criterion_type": "factual_anchor",
        "evidence_quote": null
      },
      {
        "id": "c4",
        "text": "解释上一迭代步压力会在流体-结构耦合中引入压力滞后",
        "category": "Important",
        "weight": 3,
        "sign": "positive",
        "criterion_type": "mechanism_explanation",
        "evidence_quote": null
      },
      {
        "id": "c5",
        "text": "解释这种压力滞后会在强耦合条件下放大误差",
        "category": "Important",
        "weight": 3,
        "sign": "positive",
        "criterion_type": "mechanism_explanation",
        "evidence_quote": null
      },
      {
        "id": "c6",
        "text": "引发失稳",
        "category": "Important",
        "weight": 3,
        "sign": "positive",
        "criterion_type": "mechanism_explanation",
        "evidence_quote": null
      },
      {
        "id": "c7",
        "text": "指出松散耦合（Loosely coupled）方案在该类 added-mass 问题下通常不稳定",
        "category": "Important",
        "weight": 3,
        "sign": "positive",
        "criterion_type": "decision_logic",
        "evidence_quote": null
      },
      {
        "id": "c8",
        "text": "指出需要采用单块（Monolithic）方法或改进的压力投影技术来避免数值不稳定",
        "category": "Important",
        "weight": 3,
        "sign": "positive",
        "criterion_type": "decision_logic",
        "evidence_quote": "a monolithic scheme seems to be necessary to avoid numerical instabilities"
      },
      {
        "id": "c9",
        "text": "比较时明确把 monolithic 方法作为 added-mass 显著时比分区/松散耦合更稳的选择",
        "category": "Optional",
        "weight": 1,
        "sign": "positive",
        "criterion_type": "comparative_balance",
        "evidence_quote": null
      },
      {
        "id": "c10",
        "text": "回答以套话/开场白/元评论开头而无实质内容",
        "category": "Pitfall",
        "weight": 4,
        "sign": "negative",
        "criterion_type": "anti_hacking",
        "evidence_quote": null
      },
      {
        "id": "c11",
        "text": "回答篇幅冗长，包含大量与问题无关的背景铺垫或重复",
        "category": "Pitfall",
        "weight": 3,
        "sign": "negative",
        "criterion_type": "anti_hacking",
        "evidence_quote": null
      },
      {
        "id": "c12",
        "text": "把不稳定仅归因于网格粗细、时间步长或一般离散误差，而没有提到 added-mass 或 pressure segregation",
        "category": "Pitfall",
        "weight": 4,
        "sign": "negative",
        "criterion_type": "anti_hacking",
        "evidence_quote": null
      }
    ],
    "rubric_metadata": {
      "generation_model": "openai/gpt-5.4-mini",
      "generation_passes": 3,
      "n_criteria_initial": 11,
      "n_criteria_final": 12,
      "n_dropped_misaligned": 0,
      "ref_answer_self_score": null,
      "weak_answer_self_score": null,
      "generated_at": "2026-05-22T06:24:10.098787+00:00",
      "schema_version": "1.0"
    },
    "item_idx": 0,
    "rlm_answer": "在流固耦合（FSI）仿真中，“附加质量效应”导致数值不稳定的原因可从两个互补的视角加以理解。Benson 论文强调，其根源在于**压力分离（pressure segregation）** 过程中界面耦合信息的丢失。具体地，当采用分区耦合或显式压力投影方法（如 Chorin-Temam 方案）时，流体和固体子问题交替求解，由于界面处流体密度与固体密度相近、固体刚度较低或时间步长过小，界面上的压力梯度在传递过程中会引入类似“附加质量”的惯性效应，使得迭代收敛困难甚至发散。若压力方程中缺失来自固体侧的界面拉普拉斯矩阵（即忽略 β \\(\\overline{\\mathcal{L}}_{\\tau_s}\\) 项），便无法正确反映固体刚度对流体的约束，导致数值振荡。该不稳定性不仅与密度比有关，还与固体弹性模量 \\(E\\) 和时间步长 \\(\\Delta t\\) 密切相关：即便密度比 \\(\\rho_s/\\rho_f=7\\)（如钢与水），若 \\(\\Delta t\\) 过小，忽略 β 项的算法仍会发散，而引入完整的界面拉普拉斯矩阵则可恢复耦合稳定性。另一方面，PhD 论文从一阶逼近方法的推导出发，指出附加质量效应主要表现为低频响应时的主导项。所涉公式为 \\([M_v]\\{\\dot{p}_s\\} + \\rho c [A]\\{p_s\\} = \\rho c [M_v]\\{\\dot{v}_s\\}\\)，其中 \\([M_v]\\) 为附加质量矩阵，\\(\\rho c [A]\\{p_s\\}\\) 为阻尼项。在低频时，等号左侧第二项（附加质量效应）占主导，若在高频响应时错误地保留此项而忽略阻尼，或在不恰当的数值格式中同时考虑两者，会导致系统方程条件数恶化或时间步长限制，从而诱发数值不稳定。因此，该论文主张在水下爆炸等高频响应场景下忽略附加质量效应，将方程简化为 \\(\\dot{p}_s = \\rho c \\dot{v}_s\\) 以避免失稳。综合两者可知，附加质量效应引发数值不稳定的本质在于：当界面耦合的动力学信息（如固体刚度约束或频域主导成分）被不恰当地分离或忽略时，系统的惯性-弹性平衡被打破，导致迭代收敛困难或条件数恶化，必须通过恢复完整的耦合项（如 Benson 论文中的界面拉普拉斯矩阵）或依据频率特征合理简化方程（如 PhD 论文的忽略策略）来维持稳定。\n\n**引用论文：**  \n- 第1篇：Benson 论文  \n- 第2篇：PhD 论文",
    "rlm_error": null
  }
```





**Raw 计算公式**：

$\text{设 criterion 集 } C \text{，正向子集 } C^+ = \{c \in C : \mathrm{sign}(c) = \mathrm{positive}\} \text{，陷阱子集 } C^- = \{c \in C : \mathrm{sign}(c) = \mathrm{negative}\} \text{，} w_c \text{ 为权重，} m_c \in \{0, 1\} \text{ 为 judge 判定：}$



$\text{score} = \mathrm{clip}_{[0,1]}\left( \frac{\displaystyle\sum_{c \in C^+} w_c m_c - \sum_{c \in C^-} w_c m_c}{\displaystyle\sum_{c \in C^+} w_c} \right)$



**公式性质**：

- 分母只取正向满分 $\sum_{c \in C^+} w_c$，所以\&\#34;全对 \+ 不触发陷阱\&\#34;得 1\.0

- \&\#34;全对 \+ 触发所有陷阱\&\#34;得 $\max(0, 1 - \frac{\sum w_{c^-}}{\sum w_{c^+}})$，根据默认 pitfall 权重 \(4\+3\) 和典型正向满分 \~25，约 0\.72

- \&\#34;全错\&\#34; 得 0\.0

- 任何触发了陷阱但正向不满的回答可能被 clip 到 0\.0

    

**为什么不归一化陷阱**：陷阱的设计意图是\&\#34;减分项\&\#34;，不是\&\#34;扣分上限\&\#34;。如果归一化陷阱（如除以 $\sum w_{c^-}$），会模糊\&\#34;触发 1 个 pitfall vs 触发 3 个\&\#34;的差异；当前公式让每个陷阱按其在正向尺度上的相对权重产生线性扣分。



**归一化公式**（`scorer\.py:\_compute\_anchored`）：



$\text{normalized} = \mathrm{clip}_{[0,1]}\left(
\frac{\mathrm{score} - \mathrm{weak\_score}}
{\mathrm{ref\_score} - \mathrm{weak\_score}}
\right)$



退化情况：当 `ref\_score \&lt;= weak\_score` 时（rubric 校准失败，参考答案得分不如\&\#34;我不知道\&\#34;），返回 `normalized=null` 并打 warning。这通常意味着该 rubric 的 criterion 太宽或参考答案太短，需要回到 Stage 3 重新生成。





`score` 是「这道题你拿到的原始权重比例」，`score\_anchored\.normalized` 是「相对 reference\_answer 和 `我不知道。` 两个基准之间你处在哪个位置」。后者才是有意义的横向指标。



**什么时候看哪个**：

|**场景**|**看**|
|---|---|
|单题 debug：「这条凭什么得 0\.5？」|**raw** \+ 该 item 的 `breakdown`（哪条 criterion met/unmet）|
|跨系统横向对比（你的 ReAct vs 历史 RLM）|**anchored**|
|**论文 / 报告里的 headline 数字**|**anchored**|
|检查 rubric 自身质量|看 `data/CAE\-anchor\-scores\.json` 里 `ref\_score` 分布——大量 \&lt; 0\.8 说明 rubric 写得过严，不是候选差|
|`score\_anchored\.normalized == null` 的 item|只能看 **raw**——那条 rubric 的 `ref\_score ≤ weak\_score`，归一化失效，建议不要纳入横向统计|

简单记：**「我系统行不行」用 anchored，「这道题为啥这么打」用 raw \+ breakdown**。



为什么 anchored 不冗余：**judge 是 LLM、有随机性，****`reference\_answer`**** 在自己 rubric 上的 ****`ref\_score`**** 经常不是 1\.0（落在 0\.85–0\.95 居多），不同 rubric 的「自然天花板」也不一致；anchored 把每条 rubric 的实际区间 ****`\[weak, ref\]`**** 拉成 ****`\[0,1\]`****，让 94 题求平均才有意义**。



## 1\. 总体得分

|指标|数值|
|---|---|
|平均原始分 \(raw\)|0\.70|
|平均锚定分 \(anchored\)|0\.71|



## 2\. 按题型分组 \(question\_type\)

|分组|数量|mean \(raw\)|mean \(anchored\)|
|---|---|---|---|
|简答题|48|0\.74|0\.74|
|主观题|20|0\.64|0\.64|
|决策题|18|0\.59|0\.64|
|对比分析题|3|0\.85|0\.85|
|数值提取题|2|0\.86|0\.86|
|流程描述题|2|0\.87|0\.87|
|数值关系题|1|0\.86|0\.86|



## 3\. 按难度 \(difficulty\)

|分组|数量|mean \(raw\)|mean \(anchored\)|
|---|---|---|---|
|困难|38|0\.72|0\.73|
|中等|37|0\.61|0\.62|
|简单|19|0\.84|0\.84|



## 4\. 失分点 — criterion\_type 命中率最低

（仅 sign=positive，按命中率升序）

|criterion\_type|总数|命中|命中率|
|---|---|---|---|
|decision\_logic|64|43|67\.2%|
|mechanism\_explanation|167|115|68\.9%|
|comparative\_balance|38|27|71\.1%|
|factual\_anchor|287|210|73\.2%|
|process\_completeness|27|21|77\.8%|
|numeric\_precision|26|22|84\.6%|



## 5\. 得分点 — criterion\_type 命中率最高

（仅 sign=positive，按命中率降序）

|criterion\_type|总数|命中|命中率|
|---|---|---|---|
|numeric\_precision|26|22|84\.6%|
|process\_completeness|27|21|77\.8%|
|factual\_anchor|287|210|73\.2%|
|comparative\_balance|38|27|71\.1%|
|mechanism\_explanation|167|115|68\.9%|
|decision\_logic|64|43|67\.2%|



## 6\. Pitfall 触发分析

（仅 criterion\_type=anti\_hacking 且 met=True，按触发次数降序）

|pitfall|触发次数|占比|
|---|---|---|
|回答篇幅冗长，包含大量与问题无关的背景铺垫或重复|16|17\.0%|
|回答以套话/开场白/元评论开头而无实质内容|5|5\.3%|
|给出多个备选答案而不做最终决策|1|1\.1%|



## 7\. 最低分 10 题



### \#11 \(question\_id=12, anchored=0\.00, raw=0\.00\)

**问题**: 为什么在水下爆炸仿真中需要引入“人工体积粘性”？其对冲击波波头处理有何作用？



- ❌ `c1` \[Essential, factual\_anchor, w=5, positive\] 明确指出水下爆炸中的冲击波属于强间断问题

judge: 候选回答未指出水下爆炸中的冲击波属于强间断问题，只是说明语料库无相关内容。

- ❌ `c2` \[Essential, factual\_anchor, w=5, positive\] 指出不引入人工体积粘性时，间断界面附近会出现剧烈振荡

judge: 候选回答未指出不引入人工体积粘性时会在间断界面附近出现剧烈振荡。

- ❌ `c4` \[Important, mechanism\_explanation, w=3, positive\] 说明人工体积粘性会将冲击波的强间断模糊化

judge: 候选回答未说明人工体积粘性会将冲击波的强间断模糊化，而是表示无法回答该问题。

- ❌ `c5` \[Important, numeric\_precision, w=3, positive\] 说明被模糊化后的冲击波会在几个网格宽度内演变为急剧变化但连续的区域

judge: 候选回答未说明人工体积粘性会使模糊化后的冲击波在几个网格宽度内演变为急剧变化但连续的区域。

- ❌ `c6` \[Important, mechanism\_explanation, w=3, positive\] 说明引入人工体积粘性的目的之一是克服微分方程组在波阵面处的求解困难

judge: 候选回答未说明人工体积粘性用于克服波阵面处微分方程组求解困难，而是表示无法回答。

- ❌ `c7` \[Optional, process\_completeness, w=1, positive\] 回答同时覆盖“为什么需要引入”和“其对冲击波波头处理的作用”两部分

judge: 候选回答未实际说明人工体积粘性的引入原因，也未说明其对冲击波波头处理的作用。

- ✅ `c8` \[Pitfall, anti\_hacking, w=4, negative\] 回答以套话/开场白/元评论开头而无实质内容

judge: 候选回答开头即讨论所提供论文语料与问题无关，属于元评论且未给出人工体积粘性或冲击波处理的实质内容。

- ✅ `c9` \[Pitfall, anti\_hacking, w=3, negative\] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复

judge: 候选回答列举了大量与水下爆炸仿真无关的论文和语料背景，属于无关铺垫。

- ❌ `c10` \[Pitfall, anti\_hacking, w=3, negative\] 将人工体积粘性解释为真实物理黏性或材料本构黏性

judge: 候选回答未将人工体积粘性解释为真实物理黏性或材料本构黏性，而是表示无法回答。



### \#45 \(question\_id=46, anchored=0\.00, raw=0\.00\)

**问题**: 混凝土重力坝在水下爆炸中的“内能吸收曲线”呈现什么特征？这说明了什么？



- ❌ `c1` \[Essential, factual\_anchor, w=5, positive\] 指出内能曲线在冲击瞬间迅速攀升

judge: 候选回答没有指出内能曲线在冲击瞬间迅速攀升，反而表示无法得知其特征。

- ❌ `c2` \[Essential, factual\_anchor, w=5, positive\] 指出内能曲线会达到峰值

judge: 候选回答未指出内能吸收曲线会达到峰值，反而表示无法得知其特征。

- ❌ `c3` \[Essential, factual\_anchor, w=5, positive\] 指出峰值之后曲线保持在一定水平

judge: 候选回答未指出内能吸收曲线在峰值之后保持在一定水平，而是称无法得知曲线特征。

- ❌ `c4` \[Essential, factual\_anchor, w=5, positive\] 指出峰值之后曲线伴有小幅震荡

judge: 候选回答未指出内能吸收曲线在峰值之后伴有小幅震荡，反而称无法得知其特征。

- ❌ `c5` \[Important, mechanism\_explanation, w=3, positive\] 指出大坝的毁伤主要发生在冲击波作用的极短时间内（毫秒级）

judge: 候选回答未指出大坝毁伤主要发生在冲击波作用的毫秒级极短时间内。

- ❌ `c6` \[Important, mechanism\_explanation, w=3, positive\] 指出后续震荡反映了大坝在平衡位置附近的弹性回弹或振动

judge: 候选回答未指出后续震荡反映大坝在平衡位置附近的弹性回弹或振动，而是称无法得知曲线特征及意义。

- ✅ `c7` \[Pitfall, anti\_hacking, w=4, negative\] 回答以套话/开场白/元评论开头而无实质内容

judge: 候选回答开头即讨论“所给语料”和相关论文情况，属于元评论式开场，未直接给出题目所问的实质特征。

- ❌ `c8` \[Pitfall, anti\_hacking, w=3, negative\] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复

judge: 候选回答篇幅适中，内容主要围绕无法从语料判断曲线特征及意义，并未包含大量无关背景或重复。



### \#61 \(question\_id=62, anchored=0\.00, raw=0\.00\)

**问题**: 在使用ABAQUS程序模拟水下爆炸时，其主要特点和局限性是什么？





- ❌ `c1` \[Essential, factual\_anchor, w=5, positive\] 明确指出 ABAQUS 是把经验公式或试验得到的水下爆炸载荷直接施加到结构上，而不是由程序自行求爆轰载荷

judge: 候选回答未指出ABAQUS通过经验公式或试验载荷直接施加到结构上，也未说明其不自行求解爆轰载荷。

- ❌ `c2` \[Essential, factual\_anchor, w=5, positive\] 明确指出 ABAQUS 不计算炸药爆轰过程

judge: 候选回答未明确指出ABAQUS不计算炸药爆轰过程。

- ❌ `c3` \[Essential, factual\_anchor, w=5, positive\] 明确指出 ABAQUS 不计算载荷传播过程

judge: 候选回答未明确指出ABAQUS不计算载荷传播过程。

- ❌ `c4` \[Essential, factual\_anchor, w=5, positive\] 明确指出计算模型中不包含炸药，只包含结构及其周围流场

judge: 候选回答未提到计算模型不包含炸药、只包含结构及其周围流场这一内容。

- ❌ `c5` \[Important, factual\_anchor, w=3, positive\] 提到 ABAQUS 的 Standard 与 Explicit 两个主模块

judge: 候选回答只提到了 Abaqus/Explicit，未提到 ABAQUS/Standard 及二者作为主要模块。

- ❌ `c6` \[Important, process\_completeness, w=3, positive\] 提到 Standard 与 Explicit 之间可以进行结果传递

judge: 候选回答未提到 ABAQUS/Standard 与 ABAQUS/Explicit 之间可以进行结果传递。

- ❌ `c7` \[Important, process\_completeness, w=3, positive\] 提到 ABAQUS 会自动计算结构的动态响应与流场压力分布

judge: 候选回答未提到ABAQUS会自动计算结构动态响应与流场压力分布。

- ❌ `c8` \[Important, mechanism\_explanation, w=3, positive\] 解释省略爆轰计算步骤和炸药模型是计算速度快的原因

judge: 候选回答未提到省略爆轰计算步骤或炸药模型，也未解释其导致计算速度快。

- ❌ `c9` \[Pitfall, anti\_hacking, w=4, negative\] 回答以套话/开场白/元评论开头而无实质内容

judge: 候选回答开头虽涉及给定文献范围的元说明，但立即给出了实质性判断，并非无实质内容的套话或空泛开场。

- ❌ `c10` \[Pitfall, anti\_hacking, w=3, negative\] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复

judge: 候选回答虽未直接回答问题且包含文献范围说明，但篇幅不算冗长，也没有大量无关背景铺垫或重复内容。



### \#85 \(question\_id=70, anchored=0\.00, raw=0\.00\)

**问题**: 若需要模拟潜艇在大范围水域中的远场抗震性，且计算资源极其紧张，应决定采用哪种建模方式？





- ❌ `c1` \[Essential, decision\_logic, w=6, positive\] 明确给出最终建模方式是 USA（Underwater Shock Analysis）代码联用

judge: 候选回答将最终建模方式确定为 LS\-DYNA 等效质量法，而不是明确给出 USA（Underwater Shock Analysis）代码联用。

- ❌ `c2` \[Essential, factual\_anchor, w=5, positive\] 指出 USA 基于边界元法（BEM）

judge: 候选回答未指出 USA 建模方式，也未提及其基于边界元法（BEM）。

- ❌ `c3` \[Essential, mechanism\_explanation, w=5, positive\] 说明 USA 无需建立庞大的水域有限元模型

judge: 候选回答说明的是等效质量法无需建立大范围流体网格，但未提及或解释 USA 无需建立庞大水域有限元模型。

- ❌ `c4` \[Essential, decision\_logic, w=5, positive\] 指出 USA 可作为需要建模大量水体时的替代方案

judge: 候选回答推荐的是等效质量法，未指出 USA 可作为需要建模大量水体时的替代方案。

- ❌ `c5` \[Essential, decision\_logic, w=5, positive\] 指出在不建水域模型时，计算时间可减少至少一个数量级

judge: 候选回答提到不建立大范围水域网格、计算量很小，但没有明确指出计算时间可减少至少一个数量级。

- ❌ `c6` \[Important, numeric\_precision, w=4, positive\] 给出计算时间仅需几百秒

judge: 候选回答只说计算量很小，并未明确给出计算时间仅需几百秒这一数值信息。

- ❌ `c8` \[Pitfall, anti\_hacking, w=4, negative\] 回答以套话/开场白/元评论开头而无实质内容

judge: 候选回答开头直接给出建模方式“等效质量法”，属于实质内容而非套话或元评论。

- ❌ `c9` \[Pitfall, anti\_hacking, w=3, negative\] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复

judge: 候选回答虽有一定解释细节，但内容基本围绕建模方式及其适用原因展开，不属于大量无关背景铺垫或重复。



### \#90 \(question\_id=75, anchored=0\.00, raw=0\.00\)

**问题**: 在设计潜艇复合材料面板抗冲击仿真方案时，若需同时精确考量冲击波和气泡脉动的全过程载荷，首选哪种LS\-DYNA功能？





- ❌ `c1` \[Essential, decision\_logic, w=6, positive\] 明确给出最终选择是 ALE（Arbitrary Lagrangian\-Eulerian）多物质流固耦合

judge: 候选回答明确否定选择 LS\-DYNA 的 ALE 多物质流固耦合，并建议改用 AUTODYN，因此未给出 criterion 要求的最终选择。

- ❌ `c2` \[Essential, factual\_anchor, w=5, positive\] 指出 ALE 的英文全称是 Arbitrary Lagrangian\-Eulerian

judge: 候选回答只提到“ALE 方法”，未指出 ALE 的英文全称是 Arbitrary Lagrangian\-Eulerian。

- ❌ `c3` \[Essential, factual\_anchor, w=5, positive\] 指出所选功能属于 LS\-DYNA 的多物质流固耦合方案

judge: 候选回答否认存在可选的 LS\-DYNA 功能并建议改用 AUTODYN，未指出任何所选功能属于 LS\-DYNA 的多物质流固耦合方案。

- ❌ `c4` \[Essential, decision\_logic, w=5, positive\] 说明 ALE 可以同时处理炸药爆轰形成的冲击波

judge: 候选回答只说ALE可模拟冲击波阶段，未说明ALE可以同时处理炸药爆轰形成的冲击波。

- ❌ `c5` \[Essential, decision\_logic, w=5, positive\] 说明 ALE 可以同时处理爆轰产物气泡的脉动全过程载荷

judge: 候选回答明确否认 LS\-DYNA 的 ALE 能同时模拟冲击波和气泡脉动全过程载荷，未满足该 criterion。

- ❌ `c7` \[Important, comparative\_balance, w=3, positive\] 对比指出 USA 或边界元方法难以处理这种近场全过程载荷

judge: 候选回答未对比提及 USA 或边界元方法，也未指出其难以处理近场全过程载荷。

- ❌ `c8` \[Pitfall, anti\_hacking, w=4, negative\] 回答以套话/开场白/元评论开头而无实质内容

judge: 候选回答虽以“根据本语料库的文献核查”作引入，但紧接着给出了实质性判断和依据，并非无实质内容的套话开头。

- ❌ `c9` \[Pitfall, anti\_hacking, w=3, negative\] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复

judge: 候选回答虽有一定引用和说明，但内容基本围绕LS\-DYNA是否能同时模拟冲击波和气泡脉动展开，并未大量无关铺垫或重复。



### \#93 \(question\_id=78, anchored=0\.00, raw=0\.00\)

**问题**: 当计算包含真空（Vacuum）的多物质单元时，应采取哪种混合理论以提高效率？





- ❌ `c1` \[Essential, decision\_logic, w=6, positive\] 明确给出最终选择是平均应变率混合理论

judge: 候选回答将最终选择表述为简化混合规则，而未明确给出平均应变率混合理论。

- ❌ `c2` \[Essential, factual\_anchor, w=5, positive\] 提到平均应变率混合理论这一名称

judge: 候选回答只提到简化混合规则/simple mixture rule，未提到“平均应变率混合理论”这一名称。

- ❌ `c3` \[Important, mechanism\_explanation, w=3, positive\] 说明优先压缩或扩展真空部分

judge: 候选回答只提到能量由非真空材料持有和简化混合规则，未说明优先压缩或扩展真空部分。

- ❌ `c4` \[Essential, decision\_logic, w=5, positive\] 说明程序先让真空承担所有体积变化

judge: 候选回答只提到能量由非真空材料持有、真空不参与能量分配，没有说明程序先让真空承担所有体积变化。

- ❌ `c5` \[Essential, decision\_logic, w=5, positive\] 说明剩余体积变化要等真空消失后再分配给硬物质

judge: 候选回答只提到能量由非真空材料持有，未说明剩余体积变化需在真空消失后再分配给硬物质。

- ❌ `c6` \[Important, comparative\_balance, w=3, positive\] 相较于直接让硬物质先承受体积变化，该方法更能避免钢的虚假压缩

judge: 候选回答只说明了真空单元采用简化混合规则以提高效率，未比较“硬物质先承受体积变化”的方法，也未提到避免钢的虚假压缩。

- ❌ `c7` \[Pitfall, anti\_hacking, w=5, negative\] 给出多个备选答案而不做最终决策

judge: 候选回答明确给出了简化混合规则作为推荐混合理论，并未列出多个备选答案且不做最终决策。

- ❌ `c8` \[Pitfall, anti\_hacking, w=5, negative\] 列选项而不明确选择平均应变率混合理论

judge: 候选回答没有列出多个选项，而是明确给出了“simple mixture rule”，因此未触发该负向规则。

- ❌ `c9` \[Pitfall, anti\_hacking, w=4, negative\] 回答以套话/开场白/元评论开头而无实质内容

judge: 候选回答开头即直接给出具体技术内容，没有以无实质的套话、开场白或元评论开头。

- ❌ `c10` \[Pitfall, anti\_hacking, w=3, negative\] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复

judge: 候选回答较为简洁，直接说明包含真空时采用简化混合规则，并未包含大量无关背景或重复内容。



### \#49 \(question\_id=50, anchored=0\.12, raw=0\.12\)

**问题**: 在进行远场水下爆炸仿真时，使用“2D到3D映射（Mapping）”技术的主要优势是什么？





- ✅ `c1` \[Essential, factual\_anchor, w=5, positive\] 回答明确指出 2D 到 3D 映射（Mapping）的主要优势同时包括“效率”和“精度”两个方面

judge: 候选回答明确列出了映射技术的优势包括“计算效率大幅提升”和“计算精度得以保证”，并将其与2D到3D映射原理关联。

- ✅ `c2` \[Essential, factual\_anchor, w=5, positive\] 回答明确指出该方法避免了直接建立全尺度 3D 流体网格

judge: 候选回答明确提到无需在整个流场和结构区域构建高维网格、避免全程高维模拟，等同于指出避免直接建立全尺度3D流体网格。

- ❌ `c3` \[Essential, factual\_anchor, w=5, positive\] 回答明确指出先在 2D 轴对称 ALE 模型中使用精细网格模拟炸药爆轰和冲击波的球形扩展

judge: 候选回答主要描述1D到高维映射，并未明确指出先在2D轴对称ALE模型中用精细网格模拟炸药爆轰和冲击波球形扩展。

- ❌ `c4` \[Essential, factual\_anchor, w=5, positive\] 回答明确指出将 2D 计算得到的压力场作为边界载荷或分布压力载荷映射到 3D 模型

judge: 候选回答主要描述1D结果向2D/3D传递压力场，未明确指出将2D计算得到的压力场作为边界载荷或分布压力载荷映射到3D模型。

- ❌ `c5` \[Important, mechanism\_explanation, w=3, positive\] 解释 2D\-ALE 到 3D 的映射能更好描述冲击波的球面扩散或球形传播

judge: 候选回答虽说明了映射的效率和精度优势，但未解释2D\-ALE到3D映射能更好描述冲击波的球面扩散或球形传播。

- ❌ `c6` \[Important, mechanism\_explanation, w=3, positive\] 解释效率提升来自只需计算 2D 源场而不必对整个 3D 水域进行离散建模

judge: 候选回答解释了低维到高维映射可避免全程三维建模，但主要表述为1D源场而非明确说明只需计算2D源场、无需离散整个3D水域。

- ✅ `c7` \[Pitfall, anti\_hacking, w=4, negative\] 回答以套话/开场白/元评论开头而无实质内容

judge: 候选回答开头以“根据该博士论文的论述”等来源/元评论式引入开始，尚未直接给出实质优势内容。

- ✅ `c8` \[Pitfall, anti\_hacking, w=3, negative\] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复

judge: 候选回答用多条展开论述并反复说明低维到高维映射的效率、精度和流程，篇幅明显超过问题所需且包含一定重复内容。



### \#64 \(question\_id=65, anchored=0\.18, raw=0\.18\)

**问题**: 简述水下爆炸研究的主要学术领域及其关注重点。





- ❌ `c1` \[Essential, factual\_anchor, w=5, positive\] 明确提到“爆轰物理学”是水下爆炸研究的一个主要学术领域

judge: 候选回答未明确提到“爆轰物理学”是水下爆炸研究的主要学术领域。

- ✅ `c2` \[Essential, factual\_anchor, w=5, positive\] 明确提到“流固耦合”是水下爆炸研究的一个主要学术领域

judge: 候选回答在第一点中明确将“流固耦合技术”列为水下爆炸研究内容，并多次提到流固耦合算法。

- ❌ `c3` \[Essential, factual\_anchor, w=5, positive\] 明确提到“结构冲击动力学”是水下爆炸研究的一个主要学术领域

judge: 候选回答提到“结构动态响应与毁伤效应”，但未明确提到“结构冲击动力学”这一主要学术领域。

- ❌ `c4` \[Important, mechanism\_explanation, w=3, positive\] 说明爆轰物理学关注炸药从固体转变为高温高压气体的过程

judge: 候选回答未提及爆轰物理学，也未说明炸药由固体转变为高温高压气体的过程。

- ❌ `c5` \[Important, mechanism\_explanation, w=3, positive\] 说明爆轰物理学关注由状态突跃产生冲击波的形成

judge: 候选回答虽提到冲击波模拟与传播，但未说明爆轰物理学关注由状态突跃产生冲击波的形成。

- ❌ `c6` \[Important, mechanism\_explanation, w=3, positive\] 说明流固耦合包含“冲击波作用于结构引起运动，结构运动反过来影响流场压力分布”这一双向作用链

judge: 候选回答仅列举了流固耦合方法和模拟对象，未说明冲击波致结构运动及结构运动反向影响流场压力分布的双向作用链。

- ❌ `c7` \[Important, mechanism\_explanation, w=3, positive\] 说明结构冲击动力学关注结构在爆炸载荷下的弹性、弹塑性直至断裂响应

judge: 候选回答提到结构动态响应和破坏模式，但未明确说明结构冲击动力学关注弹性、弹塑性直至断裂的响应过程。

- ❌ `c8` \[Optional, comparative\_balance, w=1, positive\] 说明结构冲击动力学关注材料/几何非线性和应变率效应对响应的影响

judge: 候选回答虽提到结构动态响应与毁伤效应，但未说明材料非线性、几何非线性或应变率效应对响应的影响。

- ❌ `c9` \[Pitfall, anti\_hacking, w=4, negative\] 回答以套话/开场白/元评论开头而无实质内容

judge: 候选回答开头直接列出具体学术领域和关注重点，未以套话、开场白或元评论开头。

- ❌ `c10` \[Pitfall, anti\_hacking, w=3, negative\] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复

judge: 候选回答篇幅较简洁，内容围绕水下爆炸研究领域及关注重点展开，没有明显无关背景铺垫或重复。



### \#92 \(question\_id=77, anchored=0\.25, raw=0\.25\)

**问题**: 在处理包含大型柔性瓣膜（如主动脉瓣）的流固耦合问题时，当瓣膜产生极大转动或位移，应如何决策网格更新？





- ❌ `c1` \[Essential, decision\_logic, w=6, positive\] 明确给出最终决策为局部或全局重构网格（Re\-meshing）

judge: 候选回答虽提到在ALE失效时执行remeshing，但最终决策表述为优先ALE且未明确给出局部或全局重构网格作为该情形下的决策。

- ✅ `c2` \[Essential, mechanism\_explanation, w=5, positive\] 指出极大转动或位移会使初始 ALE 网格质量恶化

judge: 候选回答明确提到极大位移会导致ALE网格畸变、网格平滑失效并无法维持网格质量。

- ❌ `c3` \[Essential, decision\_logic, w=5, positive\] 指出需要定期调用自动网格生成器

judge: 候选回答提到在ALE失效时调用自动网格生成器，但没有指出需要定期调用自动网格生成器。

- ❌ `c4` \[Essential, decision\_logic, w=5, positive\] 指出需要进行拓扑重排（topology reordering）

judge: 候选回答仅提到ALE、remeshing/rezoning和新拓扑网格，并未明确指出需要进行拓扑重排（topology reordering）。

- ❌ `c5` \[Essential, mechanism\_explanation, w=5, positive\] 指出通过重映射（Remap）保证变量连续

judge: 候选回答虽提到映射精度和重网格/rezoning，但未明确指出通过Remap将变量重映射以保证变量连续。

- ✅ `c6` \[Important, factual\_anchor, w=3, positive\] 答案使用了“局部或全局重构网格（Re\-meshing）”这一术语

judge: 候选回答多次使用了“remeshing”及“网格重构”相关表述，包含了该术语的核心内容。

- ✅ `c7` \[Important, comparative\_balance, w=3, positive\] 在极大转动或位移场景下，不应仅依赖原始 ALE 网格继续变形而不做重构

judge: 候选回答明确指出极大位移导致ALE网格平滑失效或网格质量无法维持时应启动remeshing/rezoning，而不是仅依赖原始ALE网格继续变形。

- ❌ `c8` \[Pitfall, anti\_hacking, w=4, negative\] 回答以套话/开场白/元评论开头而无实质内容

judge: 候选回答开头直接给出了网格更新决策建议，包含实质内容，并非套话、开场白或元评论。

- ✅ `c9` \[Pitfall, anti\_hacking, w=3, negative\] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复

judge: 候选回答篇幅明显偏长，并加入案例引用、精度比较和附加质量效应等与“如何决策网格更新”不直接相关的背景内容。

- ❌ `c10` \[Pitfall, anti\_hacking, w=5, negative\] 给出多个备选答案而不做最终决策

judge: 候选回答虽列出ALE、代数/椭圆网格移动和remeshing等备选方案，但明确给出了优先使用ALE、失效后再remeshing的决策流程。

- ❌ `c11` \[Pitfall, anti\_hacking, w=5, negative\] 列选项而不做决定

judge: 候选回答明确给出了优先使用ALE、失效后再remeshing/rezoning的决策流程，并非只列选项不做决定。



### \#30 \(question\_id=31, anchored=0\.31, raw=0\.31\)

**问题**: 为什么Volume of Fluid \(VOF\) 方法在处理多物质界面时最为流行？





- ❌ `c1` \[Essential, factual\_anchor, w=5, positive\] 指出 VOF 方法以每个单元内各物质的体积分数进行计算

judge: 候选回答强调了VOF的守恒性和单元级质量守恒，但没有明确指出其以每个单元内各物质的体积分数进行计算。

- ✅ `c2` \[Essential, factual\_anchor, w=5, positive\] 指出 VOF 方法在算法构建上天然满足质量守恒

judge: 候选回答明确指出 VOF 是 conservative by construction，并说明其在算法构建上天然保证质量守恒。

- ❌ `c3` \[Essential, factual\_anchor, w=5, positive\] 指出 VOF 方法允许界面在不同单元之间是不连续的

judge: 候选回答只强调守恒性、质量守恒和工业成熟性，没有指出 VOF 允许界面在不同单元之间不连续。

- ❌ `c4` \[Essential, factual\_anchor, w=5, positive\] 指出 VOF 方法对包含剧烈变形的工程仿真具有稳健性

judge: 候选回答强调了守恒性和工业成熟度，但没有明确指出 VOF 对包含剧烈变形的工程仿真具有稳健性。

- ✅ `c5` \[Important, mechanism\_explanation, w=3, positive\] 解释 VOF 之所以流行，是因为体积分数输运形式有利于保持质量守恒

judge: 候选回答明确指出 VOF 流行的根本原因是其构造上守恒、能精确保持质量守恒，符合该机制解释。

- ❌ `c6` \[Important, mechanism\_explanation, w=3, positive\] 解释 VOF 之所以流行，是因为它能处理界面剧烈变形而仍保持数值稳健

judge: 候选回答主要将VOF流行归因于构造守恒和工业成熟性，并未明确说明其能处理界面剧烈变形且保持数值稳健。

- ❌ `c7` \[Pitfall, anti\_hacking, w=4, negative\] 回答以套话/开场白/元评论开头而无实质内容

judge: 候选回答开头即直接说明VOF流行的核心原因（守恒性），不是无实质内容的套话或元评论。

- ❌ `c8` \[Pitfall, anti\_hacking, w=3, negative\] 回答篇幅冗长，包含大量与问题无关的背景铺垫或重复

judge: 候选回答较为简洁，主要围绕VOF流行原因（守恒性、工程成熟性）展开，没有大量无关背景铺垫或重复。




---

# 8. RAG 对比实验 — Hybrid-Retrieval RAG vs RLM v3

> 新增：在**同一 94 题、同一知识库（`CAE-MDs/`）、同一生成模型（`deepseek/deepseek-v4-flash`）**上，搭建了一个混合检索 RAG，并用**同一套 `cae-rubrics-eval`（judge `openai/gpt-5.4-mini`，相同 anchors）**对 RAG 答案与 RLM v3 答案分别打分，做 apples-to-apples 对比。代码见 `cae-rag/`，设计/计划见 `docs/superpowers/{specs,plans}/2026-05-26-cae-rag-hybrid-retrieval*`。

## 8.1 系统设置

| 项 | RAG | ReAct | RLM v3 |
|---|---|---|---|
| 检索/编排 | Milvus Lite 稠密 + BM25(jieba) 稀疏，**RRF 融合取 top-5** | 同 RAG 索引；ReAct 循环最多 6 步自主 search/read | `papers_qa` agent 在文档上自主探索 |
| 向量模型 | `openai/text-embedding-3-small`（1536 维） | 同左 | — |
| chunk | 512 token（tiktoken `cl100k_base`），overlap 64 | 同左 | — |
| 生成模型 | `deepseek/deepseek-v4-flash`（temp 0） | `deepseek/deepseek-v4-flash`（temp 0） | `deepseek/deepseek-v4-flash` |
| 知识库 | 8 篇 `CAE-MDs` → 657 chunks | 同左 | 同 8 篇 `CAE-MDs` |
| 打分 | `cae-rubrics-eval`，judge `gpt-5.4-mini` | 同左 | 同左（本次重新打分） |

**唯一自变量 = 上下文获取方式**（单轮 top-5 chunk vs 迭代 ReAct 检索 vs agent 自主阅读）。

## 8.2 总体得分（同一 judge + 同一 anchors，可直接对比）

| 系统 | 平均原始分 (raw) | 平均锚定分 (anchored) | 评分成功 | 错误 | Δ vs RLM v3 |
|---|---|---|---|---|---|
| **RAG**（hybrid top-5） | 0.422 | **0.427** | 94/94 | 0 | −0.248 |
| **ReAct**（iterative） | 0.418 | **0.422** | 94/94 | 0 | −0.253 |
| **RLM v3**（重新打分） | 0.664 | **0.675** | 94/94 | 0 | — |

**Δ (RAG − RLM v3) anchored = −0.248；Δ (ReAct − RLM v3) anchored = −0.253** — ReAct 迭代检索与单轮 RAG 几乎持平（差距仅 0.005），两者均大幅落后于智能体式 RLM v3。

> **打分口径说明**：本报告第 1 节给出的 RLM v3 headline 为 anchored **0.71**（2026-05-27 由主仓库 `src/score_rlm_answers.py` 打分）。本节为做严格 apples-to-apples，把 RLM v3 答案重新经 `cae-rubrics-eval` 包打分得 **0.675**。两者 judge 同为 `gpt-5.4-mini`，约 0.035 的差异来自 LLM judge 的逐次随机性 + 两套打分工具链的细微差异。**RAG-vs-RLM 的 Δ 必须用同一次、同一管线产出的数对**（0.427 vs 0.675），不要拿 RAG 0.427 去比第 1 节的 0.71。

## 8.3 按题型 (question_type) — anchored

| 题型 | n | RAG | ReAct | RLM v3 | Δ(ReAct−RLM) |
|---|---|---|---|---|---|
| 数值提取题 | 2 | 0.089 | 0.357 | 0.946 | −0.589 |
| 数值关系题 | 1 | 0.227 | 0.000 | 0.636 | −0.636 |
| 对比分析题 | 3 | 0.500 | 0.278 | 0.767 | −0.489 |
| 简答题 | 48 | 0.448 | 0.494 | 0.698 | −0.204 |
| 主观题 | 20 | 0.409 | 0.402 | 0.644 | −0.242 |
| 决策题 | 18 | 0.389 | 0.293 | 0.576 | −0.283 |
| 流程描述题 | 2 | 0.758 | 0.553 | 0.935 | −0.382 |

RAG 和 ReAct 差距最大的均是**数值提取 / 数值关系**：检索系统难以稳定召回精确数字与经验公式，而 RLM agent 能逐步定位到含具体数值的段落。ReAct 在**简答题**（0.494）上略优于 RAG（0.448），但在**对比分析题**和**决策题**上反而弱于 RAG，说明 ReAct 的迭代步骤并不总能有效聚焦多维度比较。

## 8.4 按难度 (difficulty) — anchored

| 难度 | n | RAG | ReAct | RLM v3 | Δ(ReAct−RLM) |
|---|---|---|---|---|---|
| 简单 | 19 | 0.498 | 0.434 | 0.806 | −0.372 |
| 中等 | 37 | 0.409 | 0.429 | 0.608 | −0.179 |
| 困难 | 38 | 0.408 | 0.409 | 0.675 | −0.266 |

ReAct 在**中等难度**（0.429）上略优于 RAG（0.409），在**困难**上与 RAG 基本持平，但在**简单题**上反而明显低于 RAG（0.434 vs 0.498），可能是迭代步骤引入了多余的噪声导致。

## 8.5 按 criterion_type 命中率（仅 positive，越高越好；anti_hacking 为 pitfall，越低越好）

| criterion_type | RAG | ReAct | RLM v3 |
|---|---|---|---|
| factual_anchor (n=287) | 43.2% | 45.3% | 69.7% |
| mechanism_explanation (n=167) | 38.3% | 40.1% | 67.7% |
| decision_logic (n=64) | 42.2% | 48.4% | 65.6% |
| comparative_balance (n=38) | 44.7% | 26.3% | 65.8% |
| numeric_precision (n=26) | 26.9% | 30.8% | 84.6% |
| process_completeness (n=27) | 48.1% | 48.1% | 77.8% |
| anti_hacking *(pitfall, 越低越好)* | **4.8%** | **6.6%** | 13.2% |

ReAct 在大多数 positive 维度略优于 RAG，尤其 `decision_logic`（48.4% vs 42.2%）和 `factual_anchor`（45.3% vs 43.2%），说明迭代检索在定位事实依据和决策推理上有一定帮助。但 `comparative_balance` 显著下滑（26.3% vs 44.7%），印证了 ReAct 在多维对比题上的劣势。`numeric_precision` 两者均大幅落后于 RLM v3（分别 26.9%、30.8% vs 84.6%）。RAG 和 ReAct 的 pitfall 触发率（4.8%、6.6%）均低于 RLM v3（13.2%），体现了检索系统”有约束”的作答风格。

## 8.6 结论

在本基准上，**智能体式 RLM（0.675）显著优于单轮混合检索 RAG（0.427，Δ = −0.248）和 ReAct 迭代检索（0.422，Δ = −0.253）**。**ReAct 与 RAG 几乎持平（差距仅 0.005）**，说明在相同知识库和生成模型下，仅靠增加检索迭代步骤（平均 2.81 步）并不能显著突破单轮检索的上限——关键瓶颈在于知识库覆盖和模型的答案组织能力，而非检索次数。RAG 和 ReAct 的共同短板集中在需要精确数值（numeric_precision 约 27–31%）、机制推导和多要点完整覆盖的题型；ReAct 在 `decision_logic` 上略有改善（+6.2 pp），但在 `comparative_balance` 上明显退步（−18.4 pp）。两者”拒绝编造”的特性虽降低了陷阱触发，却无法弥补检索召回不足导致的要点缺失。

**复现**：
```bash
cd /home/juli/RLM/cae-rag
.venv/bin/python scripts/build_index.py          # 构建 Milvus Lite + BM25 索引
.venv/bin/python scripts/run_rag.py --workers 8  # 94 题作答 -> outputs/predictions.jsonl
.venv/bin/python scripts/run_react.py --workers 8 # 94 题 ReAct 作答 -> outputs/predictions_react.jsonl
.venv/bin/python scripts/compare_results.py --react-predictions outputs/predictions_react.jsonl
                                                  # 打分三方 -> outputs/{eval_react.json, comparison.md}
```
原始评分产物：`cae-rag/outputs/{eval_rag.json, eval_rlm_v3.json, eval_react.json, comparison.md}`。

