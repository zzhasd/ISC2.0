# PRISM 统一 NJL 附加评测（与五算法同口径）

- 推断模型 `qwen3.8-flash`；匹配模型 `qwen3.8-max`。
- 固定 298 段 A→B、588 条参考、262 条 E1/E2 参考。
- 唯一匹配提示词 `prompts-v2.py`，SHA256 `71938bd23386703e6e1a7d914442f9ea74766c9dc52b2b351a976b4c4cfb7e24`。
- 严格等价（equivalent）或宽松（equivalent+broader），不包含 narrower。
- 原始预测条数计入 Precision 分母；Recall/Grounded Recall 使用一对一二分匹配。
- 本结果仅是对固定参考集的模型语义匹配评估，不是开放世界人工核验。

## 严格

| 算法 | Precision | Recall | Grounded Recall | 预测条数 |
|---|---:|---:|---:|---:|
| Direct Thinking | 11.24% | 18.03% | 38.17% | 952 |
| Dual Without Verifier | 10.09% | 21.26% | 46.18% | 1695 |
| Evidence-Adaptive v3 | 19.83% | 18.71% | 41.22% | 701 |
| ELARA v1 | 7.21% | 21.60% | 47.33% | 2442 |
| ELARA v2 | 10.63% | 19.39% | 42.37% | 1082 |
| PRISM v1 (Scoped Evidence) | 10.64% | 18.03% | 39.31% | 996 |

## 宽松

| 算法 | Precision | Recall | Grounded Recall | 预测条数 |
|---|---:|---:|---:|---:|
| Direct Thinking | 36.66% | 47.45% | 72.14% | 952 |
| Dual Without Verifier | 31.09% | 52.04% | 75.19% | 1695 |
| Evidence-Adaptive v3 | 38.23% | 32.82% | 58.02% | 701 |
| ELARA v1 | 21.13% | 49.49% | 75.19% | 2442 |
| ELARA v2 | 30.04% | 43.20% | 66.79% | 1082 |
| PRISM v1 (Scoped Evidence) | 30.92% | 39.29% | 60.69% | 996 |

## 比较约束

五算法比较使用已冻结的历史评分，不重新推理、不重新匹配。
