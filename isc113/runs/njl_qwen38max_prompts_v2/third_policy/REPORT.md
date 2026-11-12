# 五算法第三种计算口径

复用 qwen3.8-max 已完成的评价结果，无新增 API 请求；按匹配参考的证据等级计分。

- E1、E3、E4：仅 equivalent；E2：equivalent 或 broader；narrower/none 不计命中。
- Precision：正确原始输出数 / 全部原始输出数，保留重复输出。
- Recall：全部参考最大一对一命中数 / 588。
- Grounded Recall：E1/E2 独立最大一对一命中数 / 262。
- 每个算法均覆盖固定的 298 段 A→B 对话。
- 已复算并精确复现原严格、宽松口径的所有计数；逐对话验证第三种口径位于二者之间。

| 算法 | Precision | Recall | Grounded Recall |
|---|---:|---:|---:|
| Direct thinking | 18.0672% | 26.1905% | 56.4885% |
| Dual (without verifier) | 16.5192% | 30.1020% | 66.0305% |
| Evidence-Adaptive v3 | 25.1070% | 23.2993% | 51.5267% |
| ELARA v1 | 11.6298% | 30.4422% | 67.1756% |
| ELARA v2 | 16.0813% | 26.1905% | 57.6336% |

| 算法 | 正确输出/全部输出 | 恢复参考/588 | 恢复有据参考/262 |
|---|---:|---:|---:|
| Direct thinking | 172/952 | 154/588 | 148/262 |
| Dual (without verifier) | 280/1695 | 177/588 | 173/262 |
| Evidence-Adaptive v3 | 176/701 | 137/588 | 135/262 |
| ELARA v1 | 284/2442 | 179/588 | 176/262 |
| ELARA v2 | 174/1082 | 154/588 | 151/262 |

E1/E2 分级召回另见 CSV/JSON，分别独立做最大一对一匹配；分级命中数不应直接相加替代联合匹配。
原始 matches、attempts、manifest 以及严格/宽松报告均保留。
