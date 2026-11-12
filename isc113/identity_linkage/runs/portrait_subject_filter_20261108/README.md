# IA、HW、HS、HU 四组独立复验

Summary 流程：原版 elara_subject_v2 → 一次主体错归属过滤 → 精确字符串去重 → Summary。

四人沿用旧实验的全部对侧 A 发言，从头重新在线抽取、过滤并生成 Summary；direct 使用相同原文重新在线生成，提示词与参数沿用旧实验。未复用旧响应缓存。自述来自原始语料，仅在两路画像冻结后的交付阶段读取。

| 匿名者 | 对话数 | 原始属性 | 删除 | 保留 | 去重后 | 自述条目 | Summary条目 | direct条目 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| IA | 15 | 126 | 2 | 124 | 123 | 10 | 25 | 30 |
| HW | 19 | 257 | 17 | 240 | 240 | 10 | 21 | 30 |
| HS | 20 | 211 | 7 | 204 | 202 | 10 | 34 | 40 |
| HU | 20 | 184 | 9 | 175 | 175 | 10 | 23 | 26 |

## 交付文件

- [四组画像汇总](四组画像汇总.md)：12份画像的可读合并版。
- `IA/`、`HW/`、`HS/`、`HU/`：各含 self_portrait.md、summary_portrait.md、direct_portrait.md。
- `all_portraits.json`：全部画像；Summary JSON 保留逐条原始属性、证据及来源。
- 每组的 subject_decisions.json、filter_batches/ 与 attempts.jsonl：过滤判断、原始响应和请求审计。
- verification.json：全量输入、代码绑定、过滤约束、Summary覆盖、direct引用及请求隔离核验。

只删除有逐字原文锚点且明确被标为 A 自述错归属的候选；UNKNOWN、第三方、泛化和证据不足等其他情况保留。不改写候选，不在 Summary 后追加模型审核。格式失败的重试会单独记入请求日志。

引用匹配与流程核验通过不代表日语语义判断完全正确；本轮没有新增画像评分或错误率估计。自述保留日语原文。

复现：设置进程环境变量 QWEN_API_KEY 后，在项目根目录运行：

```powershell
python -B -m isc113.identity_linkage.filtered_portrait_repeat all --out <新目录> --workers 8
```

模型与参数：抽取为原 subject_v2 的 512/4096；过滤为 thinking_budget=2048、max_tokens=8192；Summary/direct 为 2048/20000。均 qwen3.8-flash、temperature=0、enable_thinking=true。

返回 usage 与未知计费请求数见 verification.json；不推算费用。
