# direct 新旧流程审核

结论：四组 direct 的算法未修改。已逐条核对旧、本轮实际发出的所有 direct 请求；完整请求体完全一致，共用代码也逐字节一致。

| 匿名者 | 旧 direct 条目数 | 新 direct 条目数 | 输入、提示词、参数 |
|---|---:|---:|---|
| IA | 10 | 30 | 完全一致 |
| HW | 36 | 30 | 完全一致 |
| HS | 15 | 40 | 完全一致 |
| HU | 20 | 26 | 完全一致 |

具体核验：

- 原始 inputs.json 完全相同；direct 用户消息均为同一组全部 A 侧原文，并带相同的 A says 标记。
- 系统提示词完全相同，均明确要求不要强制画像条目数；没有新增属性抽取、主体过滤或 Summary 输入。
- 模型均为 qwen3.8-flash；temperature=0、enable_thinking=true、thinking_budget=2048、max_tokens=20000。
- portrait_summary.py、api.py、core.py 与四组旧 source_snapshot 分别逐字节一致。
- 所有新旧 direct 请求的 task_id 均可用同一个 API endpoint 与实际请求体重建，确认 endpoint 没变。
- 两轮交付的 direct JSON 都等于各自保存的原始预测对象，没有画像后处理改写；引用校验均通过。
- 实际请求体完全相同，因此新增过滤器和 B 的个人自述档案都未进入本轮 direct 输入。

变化发生在运行组织：本轮使用新目录和请求任务名，以便独立重跑；旧 direct 与 Summary 并行，本轮 direct 与抽取并行。两路调用彼此不传递结果。HW 本轮记录了一次代理连接失败恢复和一次 JSON 格式重试。

条目数变化是两次服务调用返回了不同的有效输出；没有通过修改 direct 提示词、输入、参数或人工改写来增加条目。仅凭这些日志，无法进一步确定服务端输出差异的具体原因，也不能按条目多少判断画像质量。

逐项请求摘要、参数、重试和代码核验结果见 direct_comparison_audit.json。
