# 主体归属专项审计

结论：本次输出中存在跨测试组的反复主体误归，不能视为两个孤立例子。全量自动筛查和助手逐条复核应分别看待。原始预测、人数误差和聚类指标均未更改。

## 固定随机样本逐条复核（主结论）

在每个测试组均匀抽一段，共 20 段、349 条；由本助手逐条阅读全部 A 侧上下文、claim 和 attribute，复核时未查看自动筛查标签。

- 保守确认主体/说话行为误归 65/349（18.6%），涉及 16/20 段（80.0%）。
- 其中直接 A→B 信息转移 60/349（17.2%），涉及 15/20 段。
- 确认误归中，原审核判 supported 的有 51 条，其中 supported 且 E1/E2 的有 50 条。

这不是人工金标。未确认错误的条目不保证正确，可能仍有问题无答案、泛化过度、模态错误或主体歧义。18.6% 是这 349 条的保守确认比例，不是全量 3,195 条的精确错误率。按原始输出条目计数，近义重复条目仍分别计数；对话级结果可以补充判断是否反复出现。

此处的错误判断是：可见证据实际描述 A，却据此给 B 赋予相应事实，或把 A 的说话行为写成 B 的行为。它不等于断言 B 在现实中绝对不符合该事实；偶合为真不能补足 A-only 推断的证据。

| 设置 | 样本条目 | 确认误归条目 | 涉及对话（每设置抽十段） | A→B 条目 |
|---|---:|---:|---:|---:|
| same_a | 165 | 39 | 8/10 | 36 |
| different_a | 184 | 26 | 8/10 | 24 |

## 全量自动筛查（模型标签，不等于确认错误率）

模型为 qwen3.8-flash thinking，采用专门主体规则；不提供原 E1–E4 标签、审核理由、B 发言、persona 或真实 B 身份。claim 和 attribute 分开判定。严格误归只包括 A_TO_B、THIRD_TO_B 和 SPEAKER_REVERSAL；一般事实个体化、主体歧义及其他支持不足分列。

- 全量 3195 条、200 段、20 组均完成筛查。
- 严格类别标记 983/3195（30.8%），涉及 163/200 段和 20/20 组。
- A→B 标记 877 条，涉及 154 段。
- 标记严格误归中，原 supported+E1/E2 的有 727 条。
- 只在短 attribute 字段触发严格标记、claim 未触发的有 4 条。

| 设置 | 总条目 | 严格类别标记 | 涉及对话 | A→B 标记 |
|---|---:|---:|---:|---:|
| same_a | 1643 | 570 | 83/100 | 505 |
| different_a | 1552 | 413 | 80/100 | 372 |

样本中助手确认的 65 条里，筛查器标记了 56 条；另外有 58 条筛查标记未被助手保守确认，不能把这些未确认条目直接叫作错误或把筛查比例当真值。

筛查器与原抽取器是同系列同模型，错误可能相关；这次是独立提示词复审，不是独立人工或跨模型验证。一段对话六次未满足输出 schema，保留失败响应后按七条候选分两批补齐；规则、完整 A 上下文及模型参数未改，增加了 ID/schema 提醒。

## 你指出的两例

### same_a、K=1、D1、c4

claim：B mentioned or agreed that the aroma of roasted sweet potatoes is nice.

attribute：B appreciates the aroma of roasted sweet potatoes

原审核：E2 / supported

本次机器筛查：claim=A_TO_B，attribute=A_TO_B；'好きです'是A自身对烤红薯香气的喜好，被错误归为B的欣赏。

### different_a、K=1、D1、c5

claim：B is located in or associated with 関西 (Kansai), specifically 大阪 (Osaka).

attribute：located in Osaka Kansai

原审核：E2 / supported

本次机器筛查：claim=NO_SUBJECT_TRANSFER，attribute=NO_SUBJECT_TRANSFER；A确认B所在地为关西大阪，是A对B信息的复述确认，非A自身信息转移

烤红薯例的原 claim 实际为“B 提到或赞同香味好”，短 attribute 则直接写 B 欣赏香味。可见文本中后半句是 A 的喜好自述，前半句附和不足以建立 B 的这项具体喜好。大阪例是 A 的位置回答；原审核把 ですよ 强行解释为 A 确认 B 的位置，随后 A 想去参观别处也不能逆推大阪就是 B 的位置。
专项筛查仍将大阪例判作 NO_SUBJECT_TRANSFER，重复了原审核的错误解释。它没有见过原审核理由，因此这进一步显示同模型的角色偏差和漏报风险；983 条只能称机器筛查标记，不能当成确证错误数。
在样本复核和全部机器标签固定之后，仅对这两个既知例子另查完整 A+B 原记录作旁证：大阪前一条确实是 B 问 A“お住まいって関西ではないですよね？”，A 才回答“関西ですよ。大阪です。”；烤红薯例中，B 随后也说“いい香りしますよねー。”，说明 B 可能同样欣赏香味，但这条隐藏 B 发言不是 ELARA 当时可见的证据。旁证保存在 secondary_full_context_examples.json，未送入机器筛查、未用于随机样本标签或修改统计。

## 随机样本中的其他明确例子

| 设置/K/对话 | A 的原话 | 被归给 B 的内容 | 原审核 |
|---|---|---|---|
| same_a/K=2/D6 | 弟も修学旅行がなくなってしまってかわいそうでした。 | B has a younger brother whose school trip was cancelled. | E3/uncertain |
| same_a/K=4/D5 | シチューでした | B had stew (シチュー) for lunch | E3/uncertain |
| same_a/K=9/D2 | ネトフリとか、ユーチューブプライムとか入っています。 | B subscribes to Netflix. | E1/supported |
| different_a/K=1/D5 | 最近タイドラマにはまっており推し俳優を追っかけるのを楽しんでます。 | B is interested in Thai dramas and watches them on YouTube and Unext | E1/supported |
| different_a/K=3/D2 | 麦茶です。ノンカフェインの。 | B drinks caffeine-free barley tea (麦茶) instead of something else | E1/supported |
| different_a/K=6/D8 | こっちさむいです！ | B's location or environment is cold enough that A felt compelled to remark on it, prompting A to clarify that it is specifically the wind (風) that makes it cold. | E2/supported |
| different_a/K=5/D6 | 私も珈琲好きで毎日飲みますよ。 | B drinks coffee every day | E3/uncertain |

## 机制与结果解释

可复核的模式包括：日语零主语的自述/回答被当成 B 的属性；自家亲属和持有物的领属关系被搬给 B；把 はい、ですよね、そうですね 等附和词升级为某个具体 B 事实；claim 的限定表述在 attribute 中变成更强的属性；原审核同样接受了这些主体转换。
原审核理由中有 19 条匹配到明确的 B’s turn N 或 B’s response in turn N 字样；实际所有可见行都是 A。这是角色表述混乱的附加证据，但不等于这些最终事实一定全部错误，逐条保留在 original_audit_role_wording.json。

原关联输出共 36 条合并证据边，其中 25 条引用了自动筛查标记属性，5 条引用了本随机样本中助手确认的误归属性。未被作为合并理由引用的属性也可能影响拆分判断，因此不能由这个交集完整衡量影响。

本次审计足以说明属性库存在反复的主体污染，不能把原实验结果仅解释为身份关联模块能力不足。它尚未证明主体污染是聚类失败的唯一原因或主要原因，也没有通过过滤重跑证明可以改善指标。本次不改变 ELARA v1、原预测或原评分。

## 文件与复现

- all_claims_screening.csv / .json：全量自动标签、原判定、引用与两字段标签。
- assistant_review_349.csv：固定随机样本的全部条目；assistant_confirmed_errors.csv：65 条保守确认条目。
- assistant_review_conservative_v2.json：冻结复核结果，含两个边界条目的保守排除说明；初版笔记另保留。
- review_sample.json、review_packet_1..4.txt：抽样 seed、清单及不含自动标签的原文阅读包。
- attempts.jsonl、decisions/、manifest.json、format_recovery.json：请求原始记录、冻结数据哈希与格式恢复记录。
- secondary_full_context_examples.json：统计固定后，仅针对两个用户已指出例子的完整对话旁证。
- 运行 python -B -m isc113.identity_linkage.subject_audit_report 可离线重算本报告。
