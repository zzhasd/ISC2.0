# V3：原双路的证据修订

当前实现独立于原算法。复用原A-only dual_on缓存，再新增一次证据修订/补漏；同时报告refined和召回优先的retain_union模式。

```powershell
python -B -m isc112_v3 prepare
python -B -m isc112_v3 run
python -B -m isc112_v3 review --mode refined
# 当前对话助手实际逐包审核，保存decisions_*.json
python -B -m isc112_v3 analyze --mode refined
python -B -m isc112_v3 review --mode retain_union
# 已审断言精确复用，剩余才新审核
python -B -m isc112_v3 analyze --mode retain_union
python -B -m isc112_v3 check --mode refined
python -B -m isc112_v3 check --mode retain_union
# 在两个模式都已完成审核后，执行独立的确定性保守保护：
python -B -m isc112_v3.guarded
python -B -m isc112_v3 review --mode guarded
python -B -m isc112_v3 reuse --mode guarded
python -B -m isc112_v3 analyze --mode guarded
python -B -m isc112_v3.guarded_v2
python -B -m isc112_v3 review --mode guarded_v2
python -B -m isc112_v3 analyze --mode guarded_v2
python -B -m isc112_v3 check --mode guarded_v2
python -B -m isc112_v3 report
```

run隐藏输入密钥。已成功请求不会重发。语义审核与推理代码分开；推理不读取B、参考或审核标签。协议见ISC112_V3_PROTOCOL.md。结果results/isc112_v3/，两个模式分目录，共享相同一次修订运行与真实成本。

V2.2为失败的独立尝试（81/138），记录results/isc112_v22/。不覆盖或隐藏失败实验。V3使用112个逻辑新增请求；原三阶段成本和本次开发累计成本分别列明。

当前最终结果为guarded_v2（保守修订），102/138，原双路100/138。新增命中仅来自一段的两项关系补全，bootstrap区间包含零，不能称稳定超越。该规则是在112段开发结果上修正的，不是封存确认。依据不足原始行比例下降不代表独立事实精确率提高，绝对不足断言数166对156；实际流程tokens约为原1.47倍。完整结果及负模式均在报告中。
