# 五算法统一 NJL 评价报告

- 评价模型：`qwen3.8-max`，`enable_thinking=true`，`thinking_budget=8192`，`max_tokens=12288`，`temperature=0.6`。
- **唯一匹配提示词**：`prompts-v2.py`，SHA256：`71938bd23386703e6e1a7d914442f9ea74766c9dc52b2b351a976b4c4cfb7e24`。
- 只重新评价冻结预测，**没有重新推理**。五算法依次串行；每个算法内部最多 6 并发。
- 固定 298 段 A→B 对话，588 条 true 参考；其中 E1/E2 有据参考 262 条。
- Precision = 命中参考的原始输出条数 / 原始输出条数（重复输出仍保留在分母）。
- Recall = 最大一对一命中参考数 / 588；Grounded Recall = E1/E2 最大一对一命中数 / 262。
- 严格：仅 `equivalent`；宽松：`equivalent` 或 `broader`（**不包含** `narrower`）。
- 固定参考集的模型语义匹配指标；非人工逐条验证每条预测的开放世界精确率。

## 严格口径（equivalent）

| 算法 | Precision | Recall | Grounded Recall |
|---|---:|---:|---:|
| Direct thinking | 11.2395% | 18.0272% | 38.1679% |
| Dual (without verifier) | 10.0885% | 21.2585% | 46.1832% |
| Evidence-Adaptive v3 | 19.8288% | 18.7075% | 41.2214% |
| ELARA v1 | 7.2072% | 21.5986% | 47.3282% |
| ELARA v2 | 10.6285% | 19.3878% | 42.3664% |

| 算法 | Precision 分子/分母 | Recall 分子/分母 | Grounded Recall 分子/分母 |
|---|---:|---:|---:|
| Direct thinking | 107/952 | 106/588 | 100/262 |
| Dual (without verifier) | 171/1695 | 125/588 | 121/262 |
| Evidence-Adaptive v3 | 139/701 | 110/588 | 108/262 |
| ELARA v1 | 176/2442 | 127/588 | 124/262 |
| ELARA v2 | 115/1082 | 114/588 | 111/262 |

## 宽松口径（equivalent + broader）

| 算法 | Precision | Recall | Grounded Recall |
|---|---:|---:|---:|
| Direct thinking | 36.6597% | 47.4490% | 72.1374% |
| Dual (without verifier) | 31.0914% | 52.0408% | 75.1908% |
| Evidence-Adaptive v3 | 38.2311% | 32.8231% | 58.0153% |
| ELARA v1 | 21.1302% | 49.4898% | 75.1908% |
| ELARA v2 | 30.0370% | 43.1973% | 66.7939% |

| 算法 | Precision 分子/分母 | Recall 分子/分母 | Grounded Recall 分子/分母 |
|---|---:|---:|---:|
| Direct thinking | 349/952 | 279/588 | 189/262 |
| Dual (without verifier) | 527/1695 | 306/588 | 197/262 |
| Evidence-Adaptive v3 | 268/701 | 193/588 | 152/262 |
| ELARA v1 | 516/2442 | 291/588 | 197/262 |
| ELARA v2 | 325/1082 | 254/588 | 175/262 |

## 请求失败与最终补评统计

| 算法 | 历史失败请求次数 | 首轮跳过对话数 | 最终补评失败对话数 | 格式规范化对话数 |
|---|---:|---:|---:|---:|
| Direct thinking | 19 | 1 | 0 | 2 |
| Dual (without verifier) | 15 | 0 | 0 | 3 |
| Evidence-Adaptive v3 | 26 | 1 | 0 | 4 |
| ELARA v1 | 16 | 1 | 0 | 3 |
| ELARA v2 | 0 | 0 | 0 | 2 |

以上失败次数包含历史已恢复的请求错误；完整原始请求记录见 attempts/，详细统计见 failure_summary.json。
