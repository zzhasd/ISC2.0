# 保守修订的观察谓词形态修正

2026-11-03，Asia/Shanghai。上一guarded结果101/138，保留记录。检查发现观察主体保护仅识别you look等简单现在式，遗漏同义的you are looking/you're looking现在进行式，属于既定观察谓词规则的实现漏项。

本修正仅在本地规则匹配时，将you are/you're/you ’ re looking|seeming|sounding规范为you look|seem|sound；原始A、模型请求、命题、语义标签和最终引文不修改。原规则的最后一次观察、防疑问/假设、原命题不变、评价者和被评价者区分保持。全部112段统一执行，无对话ID或参考标签判断，无新增API。

代码isc112_v3/guarded_v2.py；输出results/isc112_v3/guarded_v2/；输入/规则哈希data/isc112_v3/guarded_v2_manifest.json。沿用同冻结138条参考、已有逐条审核及成本，完整保留前模式结果。这是已检查开发样本上的实现修正，不是预注册确认性结果。
