# Evidence-Adaptive v3：保守主干＋直接描述补充

算法、全部提示词、过滤及独立追加实验入口在 `Evidence-Adaptive v3.py`。通过 `importlib.import_module('isc113.Evidence-Adaptive v3')` 加载；`pipeline(client,item)` 沿用 A-only 五字段输入、`Client.call` 以及标准预测列表输出结构，只输出 evidence_adaptive_v3。

三阶段：原样执行 v1 的单次生成/过滤（256 thinking、1536 输出）；执行 v2 覆盖生成和独立复核（各 512 thinking、3072 输出）；保留 v1 全部结果，只追加 v2 精确引用有效且模型复核标为 E1 的直接描述。新增候选只做确定性精确文本去重。E1 是模型在可见 A 文本上的判断，不是读取金标的标签。

本轮 v2 全量扩张没有达到精度目标，结果保留。其 E1/E2 分层显示 E2 是主要精度瓶颈，v3 因此不接入扩张版 E2，而保留 v1 较保守的隐式预测能力。本轮属于根据同一 298 段诊断后的再次适应性修订，不是独立留出集验证。

```powershell
python -B -m 'isc113.Evidence-Adaptive v3' --workers 8
python -B -m 'isc113.Evidence-Adaptive v3' --replay
python -B -m isc113.analyze_evidence_adaptive_v3
python -B -m unittest isc113.test_evidence_adaptive_v3
```

此次入口对三个推断阶段复用已经完成的 v1/v2 原始请求响应，严格校验 logical_name、payload 和 task_id。源日志哈希写入 source_calls.json；不存在改写、重采样或使用参考参与推断。298 段融合预测新写入 runs/evidence_adaptive_v3_append，prompts-v2.py 对融合输出进行新的在线语义评价，结果写入 results/evidence_adaptive_v3_append。

评价沿用原 validate_matches、score_item、four_metrics、588/262 参考分母和最大一对一匹配；空结果保留。主表 equivalent-only，另列宽松对照。十算法表保留原八算法及失败的 v2 扩张版行。原算法、评价 prompt 和评分函数不修改。

成本按完整三阶段归因：v1 和 v2 的所有推断尝试均计入 v3，复用响应不意味着部署成本为零。新一轮实际新增推断 API 用量、源调用复用以及中止的 JSON 示例适配轮成本分别记录；有未知 usage 时平均 token 仍为 null。评价成本不计入算法平均 token。

项目中另一个活跃 EFCR v2 追加实验的独立代码/日志不纳入本轮历史保护；原八算法、输入、参考、prompt、原结果仍严格核验。没有修改另一实验文件。v2 首批 JSON 示例接口问题的中止记录和完整 v2 扩张实验均保留，没有隐藏失败结果。
