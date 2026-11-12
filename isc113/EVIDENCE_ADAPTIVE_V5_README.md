# Evidence-Adaptive v5：选择性隐式审查

完整模块为 `Evidence-Adaptive v5.py`。通过 importlib.import_module('isc113.Evidence-Adaptive v5') 加载；pipeline(client,item) 接收 A-only 标准记录并返回一个 evidence_adaptive_v5 结果。

先执行 v4 两阶段覆盖/重构，保持 explicit 分支；仅当存在非 explicit 候选时，调用新的逐条蕴含审查（thinking_budget=128、max_tokens=1536），只 keep/reject，不允许改写或新增。keep 必须有精确原文证据，无效引用直接拒绝，不重采样。没有置信度阈值或按样本 ID 的规则。

本轮复用 v2 coverage 与 v4 reconstruction 相同请求原始响应，新增选择性审查在线调用；最终文本是 v4 的不变子集，因此复用经完整请求绑定验证的 v4 逐条匹配，不做新的随机评审。prompt 仍为 prompts-v2.py；评分、588/262 分母及最大一对一匹配不变。另在 v3/v4 联合匹配下对相同子集计算稳健性对照。历史表和所有不成功实验均保留。

```powershell
python -B -m 'isc113.Evidence-Adaptive v5' --workers 6
python -B -m 'isc113.Evidence-Adaptive v5' --replay
python -B -m isc113.analyze_evidence_adaptive_v5
python -B -m unittest isc113.test_evidence_adaptive_v5
```

产物位于 runs/evidence_adaptive_v5_append 和 results/evidence_adaptive_v5_append。成本按完整覆盖、重构及实际触发的隐式审查计入，排除未使用的旧 v2 review；复用不表示零部署成本，缺失 usage 时严格 mean_tokens 仍为 null。65/69 项测试与调用重放分别保留于各版本目录。

这是依据同一 298 段再次适应性修订的实验，没有独立留出验证，也不保证各项必然同时提高。新论文及评价稳定性诊断见 results/evidence_adaptive_v4_research。独立进行的 EFCR 研究以及本次联合评审的活跃文件不参与本轮旧基线保护，但它们的输入与结果来源另有绑定审计；未改动其他实验。
