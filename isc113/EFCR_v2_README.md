# EFCR v2

独立完整模块 `EFCR_v2.py` 保留 `pipeline(client, item)` 列表结果接口，方法名为 `evidence_counterfactual_repair_v2`。旧版 `EFCR.py` 与原六算法均保留。

固定三阶段：证据优先生成、独立直接事实扫描、统一反事实 keep/reject 裁决。两生成通道各至多 10 个候选，直接通道只接收 confidence >= 0.8，最终裁决要求 E1/E2、有效引用且 confidence >= 0.7。关闭 repair，不把候选修弱后重新输出。提示词要求以 B 为主体，保留有据的动作、对象、时间、数量、模态与否定，不输出泛泛的谈话参与描述。

仅在原文中出现唯一相同 token 序列时恢复引用的空白差异；不改变单词、大小写、标点、乱码或输入。最终引用附原文 start/end，切片可校验。确定性去重只折叠大小写、空白和句末句点差异；原始响应不改写。

```powershell
# 通过进程环境提供 QWEN_API_KEY / DASHSCOPE_API_KEY
python -B -m isc113.EFCR_v2 --workers 8
python -B -m isc113.EFCR_v2 --replay
python -B -m unittest isc113.test_efcr_v2
```

固定使用 298 段 A-only A→B 输入，模型 qwen3.8-flash，temperature=0、thinking_budget=512；生成输出上限 3072，裁决 6144。所有本轮算法参数在完整实验前固定。运行目录为 `runs/efcr_append_v2`，结果为 `results/efcr_append_v2`；同配置可续跑，`--replay` 不允许 API 请求。

只重新推断新版；旧版和六算法读取冻结预测。评价时按对话合并八算法全部预测并按原精确文本 digest 去重，使用不变的 `prompts-v2.py` 与 `validate_matches`，同文预测共享一个匹配判断。为容纳联合清单，匹配输出上限为 8192。八算法均用原 `score_item`、`four_metrics` 重新计算，主表 equivalent-only，另有 broader 宽松对照；平均 token 仅计各算法推断的全部尝试，不含联合评价。如 usage 缺失则仍为 null，并报告已知用量下界。

本轮联合表另存，不覆盖任何历史表、匹配或推断。参考仍为 588 条，其中有据 E1/E2 262 条。该 298 段已用于诊断和方案开发，因此本轮属于开发集追加实验，尚非未见数据上的泛化验证。改动包括多项组合，不能仅凭主表区分各项独立贡献。

初始源码归档于 `runs/efcr_append_v2/EFCR_v2_initial.py`。运行器允许不改变模块提示词、参数和推断函数 AST 的流程修订，并记录 `runner_revision.json`。本轮修订仅用于排除另一个并行实验 `evidence_adaptive_v1_append` 的可变日志/结果，以及补跑连续三次无 HTTP 响应的评价请求。原始全目录哈希快照保留，排除清单另存；原六算法和旧 EFCR 文件仍逐一核验。评价补跑使用单独的 transport_recovery 任务 ID，保留失败日志；存在 HTTP 或模型结构失败的请求不通过该机制额外重采样。
