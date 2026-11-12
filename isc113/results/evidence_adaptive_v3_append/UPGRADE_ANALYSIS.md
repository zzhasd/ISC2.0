# Evidence-Adaptive v3 升级分析

依据同一 298 段旧记录诊断后升级，是适应性追加实验。没有独立留出验证，点估计领先不构成样本外精度保证。区间条件于已记录输出，不校正适应性开发或模型采样不确定性。

| 指标 | v1 | v3 | 差值（百分点） | 配对对话 bootstrap 95% 区间（百分点） |
|---|---:|---:|---:|---:|
| precision | 19.8198% | 20.1141% | +0.2943 | [-1.9281, +2.5027] |
| recall | 14.9660% | 18.8776% | +3.9116 | [+1.9855, +5.8520] |
| grounded_recall | 32.8244% | 41.2214% | +8.3969 | [+4.2105, +12.7124] |

点估计目标检查：{'precision_leads_all_previous': True, 'recall_improved': True, 'grounded_recall_improved': True, 'all_point_estimate_targets_met': True, 'out_of_sample_precision_guaranteed': False}

v1 输出 444 条，严格正确 88 条，恢复 88/588、有据恢复 86/262；v3 输出 701 条，严格正确 141 条，恢复 111/588、有据恢复 108/262。

阶段审计：{'anchor_hypothetical_whitespace_recoverable': 96, 'anchor_raw': 646, 'anchor_invalid_before_alignment': 137, 'anchor_whitespace_repaired': 0, 'anchor_invalid_after_alignment': 137, 'coverage_raw': 1032, 'coverage_invalid_before_alignment': 39, 'coverage_whitespace_repaired': 16, 'coverage_invalid_after_alignment': 23, 'review_raw': 895, 'review_invalid_before_alignment': 3, 'review_whitespace_repaired': 0, 'review_invalid_after_alignment': 3}；复核等级：{'E1': 333, 'E2': 532, 'E3': 30}。

逐对话召回计数变化：{'true_tp': {'improved': 27, 'unchanged': 266, 'worse': 5}, 'supported_tp': {'improved': 26, 'unchanged': 267, 'worse': 5}}。

配置：v1 主干（256/1536）＋v2 覆盖生成及独立复核（每阶段 512/3072）；仅追加 E1，temperature=0。不读取参考或完整 B。v1 主干保持原引用和问号过滤；只有 v2 覆盖分支使用唯一空白定位与语义问句复核。anchor_hypothetical_whitespace_recoverable 仅为诊断潜力，不是 v1 实际修复。没有按本轮结果挑选置信度阈值。

完整新轮已知推断 token 1,199,268，已知用量下界 4024.389262/段。严格平均按原缺失 usage 规则，详见 transport_usage_audit.json。完整三阶段计入成本，推断复用已有同请求响应但本轮独立重评融合输出；这增加部署时的调用成本，不能把 token 下界直接当成精确节省。

首批 JSON 示例接口错误的中止轮另有已知推断 token 121,933、7 个未知在途状态，完整保留，不纳入最终模型性能行；开发用量单列于 development_cost_audit.json。

E1/E2 分层属于本轮完成后诊断，v3 是再次适应性修订；不能据此声称独立泛化保证。

主报告 REPORT.md 包含十算法严格及宽松四指标。原八算法及失败的 v2 覆盖扩张版均保留；历史哈希和离线重放单独核验。