# Evidence-Adaptive v2

完整算法及独立追加实验入口为 `Evidence-Adaptive v2.py`。通过 `importlib.import_module('isc113.Evidence-Adaptive v2')` 加载，`pipeline(client,item)` 返回只含 `evidence_adaptive_v2` 的标准预测记录列表。

v2 根据既有 v1 日志的引用空格损失、问号硬过滤和粒度问题升级：覆盖生成、空白字符唯一定位、独立反事实复核、跨轮遗漏扫描。最终只保留原文引用有效的 E1/E2 声明。最多 12 条；无固定输出配额，不设置按测试分数搜索的 confidence 阈值。生成和复核各 thinking_budget=512、max_tokens=3072、temperature=0。

推断只接收 A-only 五字段结构，不读取参考、完整对话、v1 预测或匹配结果。评价使用现有 prompts-v2.py、validate_matches、score_item、four_metrics。298 个 A→B 输入和 588/262 参考分母不变；空预测和空参考保留。平均 token 计全部两阶段推断尝试，排除评价；缺失 usage 仍为 null。

```powershell
# 密钥仅通过进程环境 QWEN_API_KEY / DASHSCOPE_API_KEY 提供
python -B -m 'isc113.Evidence-Adaptive v2' --workers 8
python -B -m 'isc113.Evidence-Adaptive v2' --replay
python -B -m unittest isc113.test_evidence_adaptive_v2
```

只追加 v2，本轮不重跑原六算法、EFCR 或 v1。产物位于 `runs/evidence_adaptive_v2_corrected/` 和 `results/evidence_adaptive_v2_corrected/`；九算法表前八行复制已有 v1 对比表，strict equivalent-only 为主表，equivalent+broader 为独立宽松对照。历史文件哈希、源代码/客户端/输入/prompt/参考绑定、逐响应重放和原始请求响应日志保留。

瓶颈报告见 `results/evidence_adaptive_v2_diagnostics/REPORT.md`。升级参考了同一批 298 段旧实验，因此本轮是适应性追加实验，不能当作独立留出集泛化验证。精度领先和召回提升以实际评测判定，不预先承诺。

网络异常恢复工具 `recover_evidence_adaptive_v2.py` 仅在初始三次都未获得 HTTP/模型响应时，经日志审计追加最多全局第 4–6 次通信，保留全部旧尝试和未知 usage，拒绝有模型返回的语义结果重采样。推断中断后执行该模块，再续跑主入口；评价阶段恢复加 `--evaluation`。这只增加有明确记录的通信预算，不改动原 `client.py`。

首批结构适配失败的运行原样保留于 runs/evidence_adaptive_v2_append 和 results/evidence_adaptive_v2_append；不进入最终性能对比，其成本和未决尝试独立审计。完整新轮使用修正后统一包含 evidence_level 的复核 JSON 示例，未改变评价器。
