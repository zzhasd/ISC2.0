# 同一轮的 broader 宽松计分对照

范围为 A→B 的 298 段、588 条真实参考、262 条 E1/E2 参考。算法输出与默认严格主表完全相同。该目录保留以前已经计算的宽松口径，默认评价器仍使用 equivalent。

接受 equivalent 或 broader 且指向有效真实参考的边；narrower、none 和无有效参考 ID 的 broader 不计分。Precision 按原始输出断言计数，两种 Recall 使用最大一对一匹配。Grounded Recall 继承参考的证据等级，未重新审核宽命题本身的支持。

| 方法 | 正确输出/全部输出 | 恢复参考/588 | 恢复有据参考/262 |
|---|---:|---:|---:|
| direct_thinking | 300/952 | 261/588 | 173/262 |
| direct_multisample_verifier | 463/1379 | 275/588 | 187/262 |
| route1_only | 238/651 | 221/588 | 158/262 |
| route2_only | 299/1087 | 255/588 | 150/262 |
| dual_without_verifier | 516/1695 | 330/588 | 204/262 |
| dual_with_verifier | 418/1255 | 277/588 | 185/262 |

平均 token 与默认表一致。分数变化来自计分规则，不能解释为模型重新运行后的能力提高。

- four_metrics.json / four_metrics.csv：完整主表、旧值、增量及分子分母。
- per_input.json：1,788 条逐方法逐输入计数。
- unlinked_broader_predictions.json：缺少有效参考边的 31 次输出。
- calculation_recipe.md：当前可执行复现入口。

python -B -m isc113 reproduce 会对本表四指标及基础计数逐项精确核验，不重新调用模型。
