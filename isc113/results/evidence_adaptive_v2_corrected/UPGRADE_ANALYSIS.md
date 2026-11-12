# Evidence-Adaptive v2 升级分析

依据同一 298 段旧记录诊断后升级，是适应性追加实验。没有独立留出验证，点估计领先不构成样本外精度保证。区间条件于已记录输出，不校正适应性开发或模型采样不确定性。

| 指标 | v1 | v2 | 差值（百分点） | 配对对话 bootstrap 95% 区间（百分点） |
|---|---:|---:|---:|---:|
| precision | 19.8198% | 14.2691% | -5.5507 | [-8.5129, -2.7724] |
| recall | 14.9660% | 20.9184% | +5.9524 | [+3.4034, +8.7720] |
| grounded_recall | 32.8244% | 45.4198% | +12.5954 | [+7.0864, +18.5610] |

点估计目标检查：{'precision_leads_all_previous': False, 'recall_improved': True, 'grounded_recall_improved': True, 'all_point_estimate_targets_met': False, 'out_of_sample_precision_guaranteed': False}

v1 输出 444 条，严格正确 88 条，恢复 88/588、有据恢复 86/262；v2 输出 862 条，严格正确 123 条，恢复 123/588、有据恢复 119/262。

阶段审计：{'coverage_raw': 1032, 'coverage_invalid_before_alignment': 39, 'coverage_whitespace_repaired': 16, 'coverage_invalid_after_alignment': 23, 'review_raw': 895, 'review_invalid_before_alignment': 3, 'review_whitespace_repaired': 0, 'review_invalid_after_alignment': 3}；复核等级：{'E1': 333, 'E2': 532, 'E3': 30}。

逐对话召回计数变化：{'true_tp': {'improved': 44, 'unchanged': 241, 'worse': 13}, 'supported_tp': {'improved': 42, 'unchanged': 244, 'worse': 12}}。

配置：覆盖生成＋独立复核；每阶段 thinking_budget=512、max_tokens=3072、temperature=0。不读取参考或完整 B。精确引用要求保留，只修复唯一空白定位，不对问号做全局硬删除。没有按本轮结果挑选置信度阈值。

完整新轮已知推断 token 915,416，已知用量下界 3071.865772/段。严格平均按原缺失 usage 规则，详见 transport_usage_audit.json。生成＋复核增加调用成本，不能把 token 下界直接当成精确节省。

首批 JSON 示例接口错误的中止轮另有已知推断 token 121,933、7 个未知在途状态，完整保留，不纳入最终模型性能行；开发用量单列于 development_cost_audit.json。

主报告 REPORT.md 包含九算法严格及宽松四指标。原八算法结果未重跑；历史哈希和离线重放单独核验。