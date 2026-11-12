# Evidence-Adaptive v1 独立模块

完整算法及追加实验入口位于 `Evidence-Adaptive v1.py`。使用 `importlib.import_module('isc113.Evidence-Adaptive v1')` 加载；接口为 `pipeline(client, item)`，也保留原名 `pipeline_evidence_adaptive(client, item)`。返回只含 `evidence_adaptive_v1` 的标准预测记录列表，沿用 `Client.call`、claims、task_ids 结构。

原提供文件中的提示词、`valid_evidence`、`validate_claims`、`payload`、`_adaptive_filter`、`pipeline_evidence_adaptive` 原样移植；测试比较函数 AST 与提示词原文。未将原提供文件中的六算法副本移入新模块。推断只接收严格校验后的 A-only 数据，无完整对话或参考访问。

新算法单次生成：qwen3.8-flash、temperature=0、enable_thinking=true、thinking_budget=256、max_tokens=1536。先按原结构校验至多 10 条输出，再依次过滤引用错误、全部为问句结尾的证据和规范化重复，按 confidence 降序保留至多 8 条；不改变原过滤规则，不以引用错误触发重采样。

在项目根目录执行（密钥通过进程环境 QWEN_API_KEY 或 DASHSCOPE_API_KEY 提供）：

```powershell
python -B -m 'isc113.Evidence-Adaptive v1' --workers 12
python -B -m 'isc113.Evidence-Adaptive v1' --replay
python -B -m unittest isc113.test_evidence_adaptive_v1
```

只追加 298 段 A→B 新算法预测及其语义匹配；不重新请求原六算法或 EFCR。评价固定使用 `prompts-v2.py` 和既有 `validate_matches`、`score_item`、`four_metrics`，评价请求沿用 thinking_budget=512、max_tokens=4096。参考为 588 条，E1/E2 有据分母为 262 条，空输出和空参考保留。

四指标沿用原始口径：Precision 按全部原始输出计数；Recall、Grounded Recall 使用最大一对一匹配；平均 token 为本算法全部推断尝试实际 usage/298，含重试、排除评价，未知 usage 时为 null。主表 equivalent-only，另保留 equivalent+broader 对照。八算法表前七行直接读取已有 prompts-v2 六算法和 EFCR 结果。

新产物仅位于 `runs/evidence_adaptive_v1_append/` 和 `results/evidence_adaptive_v1_append/`。运行绑定输入、源代码、客户端、评价 prompt 与参考哈希。历史文件哈希在运行前后校验；预测还会从原始响应逐条重放核验。报告为结果目录 `REPORT.md`，CSV/JSON 包含四指标及全部分子分母。

断点续跑必须使用相同代码与配置；`--replay` 禁止发起 API 请求，缺失预测/匹配即报错。原始请求响应与失败尝试留存于独立目录，凭据不保存。


网络异常恢复：`recover_evidence_adaptive_v1.py` 仅处理初始三次均未获得 HTTP/模型响应的任务，先审计日志，最多追加全局第 4–6 次通信尝试；请求、算法与校验器不变。它拒绝有 HTTP/模型返回、未知在途状态或已耗尽六次尝试的任务，保留全部旧日志与未知 usage，不对模型输出质量进行重采样。完成恢复后用主入口续跑。评价阶段可加 `--evaluation`。该恢复是本轮明确记录的额外通信预算，与原六算法客户端默认三次重试区分，原 `client.py` 不变。
