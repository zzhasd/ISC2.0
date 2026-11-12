# Evidence-Adaptive v4

完整算法与追加实验入口：`Evidence-Adaptive v4.py`，可用 `importlib.import_module('isc113.Evidence-Adaptive v4')` 加载。接口仍为 `pipeline(client,item)`，只接收严格 A-only 输入，返回 `evidence_adaptive_v4` 的标准结果列表。

算法两阶段：原 v2 coverage（512 thinking / 3072 输出）＋新的独立归因、蕴含与去语境化重构（256 / 2048）。后者隐藏候选 confidence 和证据自评级，允许丢弃、合并、忠实改写、从 A 补充明确遗漏。最终最多 10 条；精确引用必须有效，空白修复仅限唯一相同 token 序列，保留词边界、大小写和标点。没有固定置信度阈值，不读取参考、完整 B 或匹配结果。

```powershell
python -B -m 'isc113.Evidence-Adaptive v4' --workers 8
python -B -m 'isc113.Evidence-Adaptive v4' --replay
python -B -m isc113.analyze_evidence_adaptive_v4
python -B -m unittest isc113.test_evidence_adaptive_v4
```

本轮为同一 298 段适应性追加实验，第一阶段按请求/task 哈希复用原 coverage，在线请求新的重构与评价。部署时仍需两阶段。成本计完整两阶段的所有尝试，排除未使用的旧 v2 review；复用不表示算法零成本。缺失 usage 时严格 mean_tokens=null，已知 token/298 仅为下界。

评价保持 prompts-v2.py 和原 validate_matches/score_item/four_metrics、588/262 参考分母及最大一对一召回。旧十算法行保持原值，另列已完成 EFCR v2 的自身行，其联合重评的六算法行不替换原基线。新产物只在 runs/evidence_adaptive_v4_append 和 results/evidence_adaptive_v4_append。

研究原始论文、诊断、预设目标及局限见 results/evidence_adaptive_v4_research/RESEARCH.md；本实现借鉴约束生成、独立验证和意义保持，并非原论文训练方法或完整 CoVe 的复现。没有改变评价标准以追求分数。精度、召回和成本是否改善由完整结果决定。

如有纯网络失败，仅当三次均未收到 HTTP/模型响应时可使用 recover_evidence_adaptive_v4，追加最多全局第 4–6 次通信；评价阶段加 --evaluation。保留全部失败日志与未知 usage，不对语义质量重采样。原 client.py 保持不变。
