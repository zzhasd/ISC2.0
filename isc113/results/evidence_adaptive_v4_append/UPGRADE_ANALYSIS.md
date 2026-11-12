# v4 完整比较与研究结论

固定 298 段适应性追加实验。无独立留出集；区间条件于已记录响应，不校正选择或模型采样。

| 指标 | v3 | v4 | 差值（百分点） | 配对 95% 区间（百分点） |
|---|---:|---:|---:|---:|
| precision | 20.1141% | 15.2542% | -4.8599 | [-7.3686, -2.5765] |
| recall | 18.8776% | 21.2585% | +2.3810 | [+0.1658, +4.6106] |
| grounded_recall | 41.2214% | 45.4198% | +4.1985 | [-0.3406, +8.4622] |

目标检查：{'precision': False, 'recall': True, 'grounded_recall': True, 'all_three_accuracy_improved': False, 'precision_leads_frozen_prior_table': False, 'observed_token_lower_bound_decreased': True, 'strict_mean_token_improvement_proven': False, 'generalization_guaranteed': False}

已知 token/段：v3 4024.389262，v4 2823.798658。v4 mean_tokens=None；存在未知 usage 时不能宣称严格第四指标已改善。完整流程已知 841,492 token，其中复用 coverage 404,648，新复核 436,844。排除了未使用的 v2 review。

输出关系：{'none': 478, 'broader': 167, 'equivalent': 126, 'narrower': 55}；空输出 20；逐对话增减 {'true_tp': {'improved': 24, 'worse': 12, 'unchanged': 262}, 'supported_tp': {'improved': 20, 'worse': 10, 'unchanged': 268}}。

严格计数：正确输出 126/826，恢复 125/588，有据恢复 119/262。

研究依据及预设方案见 ../evidence_adaptive_v4_research/RESEARCH.md；完整十二算法严格/宽松四指标见 REPORT.md。

原十算法行没有改动。EFCR v2 仅追加自身已有行，未用其联合重新评价替换原六算法行。未改写任何匹配判断。