# 四指标计算与计数边界

默认范围为 298 个 DailyDialog A→B 输入；参考 588 条，真实 E1/E2 共 262 条。使用固定参考完整且正确的评测假设。算法只读取 A；完整 A+B 仅供建立参考与审核。

1. Precision = 等价命中真实参考的原始输出断言数 / 全部输出断言数。同一参考的重复正确表述分别计入分子和分母。
2. Recall = 最大一对一匹配恢复的不同真实参考属性数 / 全部真实参考属性数。
3. Grounded Recall = 最大一对一匹配恢复的真实 E1/E2 参考属性数 / 全部真实 E1/E2 参考属性数。E3/E4 猜中可计入 Precision 和 Recall，不计有据召回。
4. Mean tokens = 完整推断流程的实际 total_tokens 合计 / 单边输入数。计入生成、采样、验证及重试；不计 GPT 建参考、人工审核和语义匹配成本。不同算法共享调用时，各算法按完整组成流程计账，不能把六方法成本直接相加当成供应商总账。

先合计分子分母，再求比值，即微平均。Precision 计输出，两个 Recall 计参考，正确输出数可大于恢复参考数。保留空参考、空预测及失败弃答。分母为零时返回 null；usage 或任务成本缺失时 mean_tokens 返回 null，已知 token 仅作已观测部分。

默认仅 equivalent 且指向有效真实参考的边计分；broader、narrower、none 均不计命中。主体、时间、否定、模态及粒度须一致。未命中在固定完整参考假设下不得分；这不证明该命题在开放世界中为假。

## 指定一轮的默认结果

| 算法 | Precision 分子/分母 | Recall 分子/分母 | Grounded Recall 分子/分母 | 平均 token |
|---|---:|---:|---:|---:|
| Direct thinking | 162/952 | 155/588 | 130/262 | 1186.067114 |
| Direct multisample verifier | 246/1379 | 166/588 | 149/262 | 4488.439597 |
| Route 1 | 147/651 | 145/588 | 128/262 | 1069.674497 |
| Route 2 | 128/1087 | 123/588 | 99/262 | 1238.238255 |
| Dual without verifier | 261/1695 | 183/588 | 154/262 | 2307.912752 |
| Dual with verifier | 221/1255 | 160/588 | 142/262 | 4281.906040 |

## 同轮宽松计分对照

results/broader_counted_as_hit 保留 equivalent+broader 的旧统计。仅有有效真实参考 ID 的 broader 才获得匹配边；无有效 ID 的 31 次输出仍不计分。分母及 token 成本不变，Grounded Recall 仍继承参考的 E1/E2 层级，未重新判断宽命题本身的证据。

该对照与默认严格指标都能通过 python -B -m isc113 reproduce 核验。不能将其上涨解释为模型重新运行后的能力提高。具体计数见该目录 README.md 与 four_metrics.json。

## 实现入口

- evaluation.score_item：原始输出正确数、全参考匹配、有据参考匹配、成本。
- statistics.matching：最大基数二分图匹配。
- statistics.four_metrics：四指标微平均。
- evaluation.analyze：生成逐输入结果及 CSV/JSON 汇总。
- reproduction.reproduce：比较所有原始计数、指标和 token，无容差放宽。
