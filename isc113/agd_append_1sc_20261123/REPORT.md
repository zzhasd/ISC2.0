# DailyDialog 逐轮重建与 AGD 追加评价

在 298 段冻结对话中，Qwen3.8-Flash 重建了 1,172 个 B 话轮。A+B 生成 1,224 条属性预测，其中 1,009 条通过 Qwen3.8-Max 的 A-only 有据审核。

## 方法

采用 Ebert 等人论文表 2 中 DailyDialog 无词数设置下的最佳重建条件。论文该条件使用 Claude-4-Sonnet，本次实验按要求使用 Qwen3.8-Flash。独立预测每个 B 话轮，输入包括此前完整的 A 单侧历史、历史遮盖位置和紧随其后的 A 话轮。未知具体信息用 XXXXXXX。末尾 B 无后续 A 时使用已有历史。完整语料仅用于核对 A 及确定遮盖位置，模型请求未包含真实 B 发言或任何遮盖话轮的词数。

随后按原顺序合并原始 A 和明确标注为假设的重建 B，再用 Qwen3.8-Flash 提取属性。Qwen3.8-Max 使用原 AGD 提示词审查较原预测库新增的候选文本，并将有据原子映射到冻结字段。已有同文候选复用原审核及映射。原 1,630 个事实、3,985 个字段及原映射逐项校验通过。

## 结果

| 算法 | P_raw | R_full | E1 Recall | E2 Recall | Slot Coverage | Useful Yield |
| --- | --- | --- | --- | --- | --- | --- |
| Direct Thinking | 86.34% | 20.49% | 28.96% | 16.62% | 36.27% | 69.01% |
| Dual Without Verifier | 84.07% | 31.35% | 33.27% | 30.47% | 48.93% | 51.03% |
| Evidence-Adaptive v3 | 90.58% | 17.18% | 35.23% | 8.94% | 26.73% | 69.19% |
| ELARA v1 | 84.89% | 66.26% | 75.73% | 61.93% | 80.64% | 54.63% |
| ELARA v2 | 93.72% | 27.85% | 34.25% | 24.93% | 46.35% | 74.58% |
| PRISM | 95.78% | 23.37% | 37.57% | 16.89% | 41.34% | 72.39% |
| 1SC A + reconstructed B | 82.43% | 27.98% | 36.01% | 24.31% | 44.85% | 61.85% |

A+B 完整覆盖 456/1,630 个事实，E1 为 184/511，E2 为 272/1,119。加权字段覆盖为 2,849/6,352。完整召回率的对话 bootstrap 95% 区间为 25.70%–30.33%（2,000 次）。

有据率低于 AGD 的 90% 门槛。未通过的 215 条预测中，148 条含有证据不足的 E3 原子。池外有据原子出现 70 次，这些原子保留有据判定。池内召回与字段覆盖的分母保持固定。六个历史算法指标全部复核一致，可用于描述性参照。本轮只有一个新条件，无法单独估计重建带来的增益。评价为自动裁定，尚未经人工校准。

## 用量与复现

正式 Flash 重建与推理合计返回 1,006,575 token。Max 评价合计返回 1,614,365 token，以上均包含已记录的重试用量。

已停止的先期 A-only 对照记录 100 次请求，服务返回用量 126,483 token。该对照未进入正式评分。停止时仍在途的请求与两次连通性探测没有完整计量。

在仓库根目录依次运行以下命令。在线步骤从进程环境或终端隐藏输入读取凭据。

    python -B -m isc113.agd_append_1sc_20261123.infer
    python -B -m isc113.agd_append_1sc_20261123.evaluate judge
    python -B -m isc113.agd_append_1sc_20261123.evaluate score

[论文原文](https://aclanthology.org/2026.findings-acl.1757/) · [A+B 重建对话](work/exports/reconstructed_dialogues.json) · [指标表](work/results/combined_metrics.csv) · [分子分母](work/results/aggregate_counts.csv) · [逐条预测](work/results/per_prediction.csv) · [字段明细](work/results/per_slot_append.csv) · [池外有据原子](work/results/outside_pool_grounded_atoms.csv) · [模型用量](work/results/model_usage.json)
