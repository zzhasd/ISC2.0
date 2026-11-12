# v5 完整比较与研究结论

固定 298 段适应性追加实验。无独立留出集；区间条件于已记录响应，不校正选择或模型采样。

| 指标 | v3 | v5 | 差值（百分点） | 配对 95% 区间（百分点） |
|---|---:|---:|---:|---:|
| precision | 20.1141% | 18.4496% | -1.6645 | [-4.2167, +0.8202] |
| recall | 18.8776% | 20.0680% | +1.1905 | [-0.9394, +3.2761] |
| grounded_recall | 41.2214% | 43.5115% | +2.2901 | [-2.0496, +6.3437] |

目标检查：{'precision': False, 'recall': True, 'grounded_recall': True, 'all_three_accuracy_improved': False, 'precision_leads_frozen_prior_table': False, 'observed_token_lower_bound_decreased': True, 'strict_mean_token_improvement_proven': False, 'generalization_guaranteed': False}

已知 token/段：v3 4024.389262，v5 3487.154362。v5 mean_tokens=None；存在未知 usage 时不能宣称严格第四指标已改善。完整流程已知 1,039,172 token，其中复用覆盖与重构 841,492，新隐式审查 197,680。排除了未使用的 v2 review。

输出关系：{'none': 358, 'broader': 128, 'equivalent': 119, 'narrower': 40}；空输出 47；逐对话增减 {'true_tp': {'improved': 18, 'worse': 13, 'unchanged': 267}, 'supported_tp': {'improved': 16, 'worse': 11, 'unchanged': 271}}。

严格计数：正确输出 119/645，恢复 118/588，有据恢复 114/262。

研究依据及预设方案见 ../evidence_adaptive_v4_research/RESEARCH.md；完整十三算法严格/宽松四指标见 REPORT.md。

原十算法行没有改动。EFCR v2 仅追加自身已有行，未用其联合重新评价替换原六算法行。未改写任何匹配判断。