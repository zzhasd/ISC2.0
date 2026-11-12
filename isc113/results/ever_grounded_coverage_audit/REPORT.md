# 历次最终预测的 E1/E2 覆盖并集审计

固定 588 参考库；E1 136 条，E2 126 条。仅检查相同对话的 A→B 最终输出。
严格=equivalent；宽松=equivalent+broader。任一算法任一缓存命中过即算曾命中；原始失败响应和中间候选不算最终输出。
“未命中”表示已有缓存和精确同文检查未发现命中，不等于人工确认所有预测均无语义对应。

| 等级 | 总数 | 严格曾命中 | 严格从未命中 | 宽松曾命中 | 宽松从未命中 | 连 narrower 边也没有 |
|---|---:|---:|---:|---:|---:|---:|
| E1 | 136 | 133 | 3 | 136 | 0 | 0 |
| E2 | 126 | 109 | 17 | 123 | 3 | 1 |

扫描 26 个方法、6256 个匹配文件；去重后 11477 条对话内预测，其中 142 条没有任何已存语义判断。

## 宽松仍从未命中的属性

| 等级 | 参考 ID | 参考属性 |
|---|---|---|
| E2 | train_2859_A_to_B_a1_1 | B would like to attend a concert tonight. |
| E2 | train_3954_A_to_B_a2_1 | B enjoys natural scenery and wants more time in nature. |
| E2 | train_447_A_to_B_a2_1 | B is upset and angry. |

## 严格从未命中的全部属性

| 等级 | 参考 ID | 参考属性 | 对话内未评价预测数 |
|---|---|---|---:|
| E1 | train_10891_A_to_B_a2_3 | B is offered consultancy work on Japanese market expansion. | 2 |
| E2 | train_1455_A_to_B_a1_1 | B is unavailable for cinema Saturday and Sunday but free Friday. | 2 |
| E2 | train_1455_A_to_B_a2_1 | B is available to go out on Friday but has weekend engagements. | 2 |
| E1 | train_2184_A_to_B_a1_2 | B is late and mother is worried. | 0 |
| E2 | train_2709_A_to_B_a1_1 | B has made a decision about a romantic partner. | 1 |
| E2 | train_2859_A_to_B_a1_1 | B would like to attend a concert tonight. | 0 |
| E2 | train_3954_A_to_B_a1_1 | B enjoys spending time in natural scenery. | 0 |
| E2 | train_3954_A_to_B_a2_1 | B enjoys natural scenery and wants more time in nature. | 0 |
| E2 | train_4204_A_to_B_a1_2 | B is departing Beijing by plane. | 1 |
| E2 | train_447_A_to_B_a2_1 | B is upset and angry. | 0 |
| E1 | train_4807_A_to_B_a1_2 | B failed exams and must retake them. | 0 |
| E2 | train_4972_A_to_B_a1_2 | B is hesitant to learn tango for fear of mistakes. | 0 |
| E2 | train_5518_A_to_B_a1_1 | B provides international postal service. | 0 |
| E2 | train_5518_A_to_B_a2_1 | B provides registered international airmail services. | 0 |
| E2 | train_6424_A_to_B_a1_1 | B works as a realtor in the community. | 0 |
| E2 | train_7366_A_to_B_a2_3 | B is bored with work and plans to quit. | 1 |
| E2 | train_7781_A_to_B_a2_1 | B represents a textiles import/export business. | 1 |
| E2 | train_8644_A_to_B_a2_1 | B handles restaurant food complaints. | 0 |
| E2 | train_9076_A_to_B_a1_1 | B represents a company hosting A's visit. | 1 |
| E2 | validation_801_A_to_B_a2_1 | B handles hotel-room damage reports. | 0 |

## 对宽松未命中项的文本检查

- train_2859_A_to_B_a1_1：参考是想今晚去音乐会；多个算法输出已同意/接受今晚去音乐会，部分缓存判为 narrower。因此是原计分规则下未命中，不能称完全未提到音乐会。
- train_3954_A_to_B_a2_1：参考同时包含喜欢自然景色和希望增加亲近自然的时间；已有输出描述一同出游、受益于自然景色或出游不频繁，未有缓存 equivalent/broader 命中该完整参考。
- train_447_A_to_B_a2_1：参考为 upset and angry；已有输出主要为 worried/anxious 和 finger-pointing。原可见证据明确有 worried，但没有直接写 angry，建议另行复核参考 E2 标注；本审计不修改参考或历史判断。

142 条独特最终预测尚无任何已存评价，主要来自未完成的追加运行；上述三个宽松未命中对话没有此类未评价预测。
上述条目按原始参考 ID 计数，不合并参考库中的近义或复合命题。
