# 单侧对话中推断 B：文献依据与可执行设计

检索与阅读日期：2026-11-01。以下区分原论文结论与本项目的设计推断；没有把这些工作称为“只看 A、完整自然对话、推断隐藏 B”的现成解决方案，也不宣称新颖性已获系统检索证明。

## 直接相关的属性推断研究

1. **Tigunova et al., 2020, CHARM: Inferring Personal Attributes from Conversations.** 采用线索识别与外部文档检索/值排序，处理开放职业、爱好等长尾属性。启发是先定位线索再形成属性候选；其 Reddit 用户自身话语设置与本项目的“旁听 A 推断 B”不同。本轮不引入外部用户搜索或人物信息，避免改变观测条件。[原论文](https://aclanthology.org/2020.emnlp-main.434.pdf)
2. **Wang et al., 2022, Extracting and Inferring Personal Attributes from Dialogue.** 区分显式属性抽取与需要词汇/常识推断的属性推理，提出生成与判别重排的结合。其主要形式是句子到预定义关系三元组，不能直接当作本轮完整对话基线。启发是候选生成与支持验证分离，而不是把生成数量当质量。[原论文](https://aclanthology.org/2022.nlp4convai-1.6.pdf)
3. **Staab et al., 2024 版本, Beyond Memorization: Violating Privacy Via Inference with Large Language Models.** 研究从推理时文本推断个人属性的风险，支持把“文本内推断”与“训练数据记忆提取”分开。本项目只测公开编写对话的场景内信息，不把该论文的真实用户结果或准确率迁移到 DailyDialog。[作者论文](https://arxiv.org/abs/2310.07298)

## 语言学与表示层依据

4. **Roberts, 1996 / amended 1998; later published 2012, Information Structure in Discourse.** 以待讨论问题 QUD 组织话语语境，区分正在询问的内容与已接受背景。本轮用它设计“未知槽位 + 可投射背景”的分离表示；词法规则并没有实现该理论的完整形式语义。[作者稿](https://semanticsarchive.net/Archive/WYzOTRkO/InfoStructure.pdf)
5. **de Marneffe, Simons & Tonhauser, 2019, The CommitmentBank.** 在否定、疑问等环境中研究嵌入命题是否仍表达说话人承诺，显示投射需要结合语境研究。启发是给预设/承诺单独标记，并允许取消，不能把所有问句都排除，也不能把所有问句前提都当真。[论文与资源页](https://ojs.ub.uni-konstanz.de/sub/index.php/sub/article/view/601)
6. **Jiang & de Marneffe, 2019, Do You Know That Florence Is Packed with Visitors?** 在 CommitmentBank 上分析说话人承诺模型与语言构式错误，涉及事实性、条件、模态等环境。启发是在候选验证时检查嵌入词与辖域，而不是只看有没有问号；本轮不声称已训练其承诺分类器。[原论文](https://aclanthology.org/P19-1412.pdf)
7. **Clark & Brennan, 1991, Grounding in Communication.** 讨论对话中的共同背景、理解证据与修复。对本项目的重要限制是：看不到 B 时，不应把 A 的一般反馈当作已经观察到了具体 B 回答。采用已访问的原文扫描副本；作者网站链接本次抓取超时。[原文副本](https://worrydream.com/refs/Clark_H_1991_-_Grounding_in_Communication.pdf)
8. **Rückert et al., 2022, A Unified Approach to Entity-Centric Context Tracking in Social Conversations.** 以逐轮更新的实体仓库存储指代、属性和关系。启发是显式记录 A/B/第三方及指代依赖；本轮实现的是 Qwen 生成的账本与本地溯源检查，不是 Contrack 网络的复现。[原论文](https://aclanthology.org/2022.lrec-1.136.pdf)

## 验证与预算对照

9. **Dhuliawala et al., 2024, Chain-of-Verification Reduces Hallucination in Large Language Models.** 将草稿、核查问题、独立回答与最终修订分开。启发是验证器不能把草稿当新增事实；本轮两次调用仅借鉴验证思路，没有复现 CoVe 的全部分解调用。[原论文](https://aclanthology.org/2024.findings-acl.212.pdf)
10. **Madaan et al., 2023, Self-Refine.** 展示用同一模型反馈与修订的推理时方法。它要求比较“结构化模块”是否超出普通自检；本轮用两次调用的普通 SelfCheck 控制额外推理预算，非该论文官方完整复现。[作者论文](https://arxiv.org/abs/2303.17651)

## 具体算法：语用证据账本 + 验证

输入是完整有序的 A 话语 `A_1,...,A_K`，原始 B 永远不可见。每条候选记录：

`(持有者, 命题/属性值, 肯否, 时间/模态, 言语作用, 证据位置, 指代依赖, 未知前提, 修正状态)`。

1. 本地词法编译器只标注可能的疑问、所有格、事实性/变化词、附加词、否定/修复、模态、指令/计划和指示人称。它不直接输出个人事实；标签可能误报。
2. Qwen 根据完整有序 A 建立实体、命题节点、指代/支持/取代边和开放属性候选，保留问句正在询问的未知槽位。
3. 本地程序检查真实位置与悬空引用，沿指代/支持边收集证据闭包，标记被修正节点。它只构造溯源与风险提示，不凭参考标注判事实真伪。
4. 第二次 Qwen 在新上下文中，用同一 A 检查候选持有者、投射辖域、未观测前提、时间及撤回；保留可支持的较粗结论，将无法确定的细节置入 hypotheses，并扫描遗漏。
5. 所有方法统一按证据位置从本地源文取原文，避免因模型复制标点的差别制造伪改进。最终仍需语义审核，位置合法不能证明结论成立。

示例均为机制说明，不是给模型提供测试答案：

| 可见 A 的表达 | 可尝试的推断 | 应保持未知的内容 |
| --- | --- | --- |
| “你妻子到场了吗？” | 通常预设 B 有妻子；检查条件、引用及否认语境 | 妻子是否到场 |
| “如果你将来结婚，你妻子也能参加。” | 假设场景 | B 目前是否已婚 |
| “你在那里待了多久？” | B 曾在某地停留的背景；需先解析“那里” | 时长及未解析地点 |
| “我也经常做这件事。” | 在合适前文中可寻找附加前提 | 缺少锚点时不能猜“这件事”及前提持有者 |
| “我记错了，那是另一个人的资料。” | 撤回旧归属 | 不能继续把旧资料贴给 B |
| “每天按处方服药。” | B 获得某用药指示 | 是否实际服药、未提及的疾病 |

数学上可把目标写成在经验无支持断言比例受控时，最大化恢复的去重属性数；阈值必须用独立校准集选取。当前样本与 AI 标注不足以保证统计风险，因此本轮不承诺 FDR 或自报置信度校准。

## 本轮验证能回答和不能回答的问题

实现和调用采用 `ISC5_PROTOCOL.md`。比较一次 Direct、两次普通 SelfCheck、两次 LedgerVerify。旧 32 段做开发诊断；新增 16 段从未用候选中随机选择，参考在查看本轮结果前冻结。所有方法只看 A，不接收完整参考、B、旧错误清单或源数据 ID 的私人语义。

新增 Direct 同样允许合理预设，避免靠给基线加上“所有问句一律不算”的不合理限制制造模块优势。即使结果改善，仍须通过去掉 QUD、投射、实体、修正边的消融来验证各组件贡献；本轮未做消融，不能把整个流程的收益因果归给某条语言学理论。

这是 API 推理流程，无权重训练。若未来做可训练模块，可在独立训练部分监督持有者归属、投射状态、指代链接、证据选择和撤回，教师只标训练集；不把测试集的完整 B 或 GPT 参考输入给 Qwen。不应在未核实目标服务支持时声称完成模型微调。

## 补充检索：更直接的单侧与图画像工作

以下补充在本轮调用结束后完成，只用于相关工作定位，没有用来修改已冻结提示或选择性重跑。

11. **Ebert et al., 2025/2026, Reading Between the Lines: The One-Sided Conversation Problem（1SC）.** 研究缺失说话人话语重建与单侧摘要，包含 DailyDialog；观察到摘要可以不经过完整缺失话语重建生成。本项目直接恢复属性、保留未知槽位的选择与其任务有所区别，但不能把“单侧对话推理”本身当作新贡献。若后续做重建对照，应严格限制其观测范围：本轮完整 A-only 允许看到后续 A，前缀评价则不得看到前缀外的 A 或任何隐藏 B 长度。[作者原论文](https://homes.cs.washington.edu/~gshyam/Papers/onesided.pdf)；[项目页](https://1sc.cs.washington.edu/)
12. **Khan et al., 2026, GraphProfiler: Source-Linked Sensitive Attribute Inference via Personal Knowledge Graphs.** 从个人帖子构建来源可追踪图，进行属性定向推断和证据解析，并有证据删除检验。因此，“图+引用+属性推断”已经有直接先例，单凭加图不能主张方法新颖。本项目可能的区别是缺失 B 时的预设/未知答案分离、A/B/第三方归属与修正承诺；这些区别还需要消融和更完整相关工作审查。[作者原论文全文](https://arxiv.org/html/2609.12448)
13. **Srivastava et al., 2026, Listening Alone, Understanding Together（CONCORD）.** 通过单侧捕获和受控的助手间查询协商恢复缺口。它引入额外信息交换，不符合本轮“只能使用已经给出的 A”条件，不能把其准确率直接作为本轮基线或照搬查询步骤。[作者论文](https://arxiv.org/abs/2604.13348)

参考评分中的部分政策边界也值得人审：确认式疑问的 at-issue 命题未必像所有格预设那样投射；办公室问句中的头衔也可能需要跨轮身份锚定。本轮沿用已冻结参考，另做排除 `test_91_broadcast` 和 `test_39_profession` 的敏感性分析，不将其自动弃答简单解释为模型能力退化。
