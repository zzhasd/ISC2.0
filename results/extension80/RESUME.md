# 扩样运行与恢复

状态：本轮已完成。新增940次实际请求（306个前缀＋634次2×2流程），670条实验三语义审核、220条实验一二语义审核均已覆盖最终队列；22项完整性检查通过。最终报告为`results/merged112/扩样实验报告.md`，合并112段，旧文件不变。以下为复现/审计说明，不代表仍有未执行步骤。

固定80段、参考与请求已经冻结。详见根目录EXTENSION_PROTOCOL.md。

`python experiments/extension80.py run` 通过隐藏输入读取凭证，跳过所有已记录尝试；不会重试成功、格式失败或经审计的429。若存在未落盘尝试或未经审核的HTTP失败，会停止而非擅自重发。最大4并发，当前请求启动间隔2.5秒。

运行顺序：306个新非空A前缀 → 480个2×2初始请求 → 最多160个依赖判别。空输入复用旧共享先验。所有产物在新目录，旧实验不可覆盖。

参考在首个新增请求之前完成。`experiments/extension80_reference.py` 是当前对话助手逐段读A+B所写的参考，不是调用外部GPT自动标注。语义审核的显式决定写在extension80_adjudicate.py；增量审核快照保留，最终队列需完整对齐，不可将早期快照冒充全量审核。

最终步骤：导出、创建完整队列、补齐语义审核、运行extension80_analysis.py的new与merged，再运行extension80_report.py。必须核对所有预期响应和全部确定断言已纳入，而不能仅看到部分文件存在就认定完成。统计使用有效匹配队列，HTTP/结构错误为缺失。

复现检查：`python -m unittest discover -s experiments -p test_extension80.py -v`。旧test_isc4.py与test_isc7.py同样需通过。
