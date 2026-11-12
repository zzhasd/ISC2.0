# EFCR 独立模块及追加实验

`EFCR.py` 包含完整 EFCR 提示词、候选生成、引用过滤、反事实裁决、修复和去重逻辑，以及独立实验入口。算法逻辑移植自用户提供的 `prompts-EFCR.py` / `inferenceEFCR.py`；未使用其中的 MATCH 替换现有评价 prompt。

接口为 `isc113.EFCR.pipeline(client, item)`，与原 `inference.pipeline` 一样返回对话级结果列表，但只包含 `evidence_counterfactual_repair` 一个方法。`client.call(name, payload, validator)`、输入、claims、task_ids 的结构沿用现有接口。原六算法 METHODS、推断入口和评价代码均未改动。

算法只接收校验后的 A-only 输入。先生成至多 10 条附原文引用的候选；无效引用直接丢弃，不通过重采样补救。第二阶段逐候选 keep/repair/reject，仅接收 E1/E2 且原文引用有效、修复引用与原候选来源有交集的结果。空输出完整保留。

在项目根目录运行：

```powershell
# 先通过进程环境提供 QWEN_API_KEY 或 DASHSCOPE_API_KEY
python -B -m isc113.EFCR --workers 12
python -B -m isc113.EFCR --replay
python -B -m unittest isc113.test_efcr
```

首个命令只追加 EFCR，不重跑六算法；支持同配置续跑。`--replay` 不创建 API 请求，从已有预测、匹配和日志重新计算四指标；缺失缓存则报错。

输入固定为 `inputs/dailydialog.json` 的 298 段 A→B；参考固定为 588 条最终消歧参考，其中 E1/E2 为 262 条。评价使用 `prompts-v2.py` 和现有 `validate_matches`、`score_item`、`four_metrics`，主表 equivalent-only，同时保留 equivalent+broader 对照。Precision 计原始输出，Recall 与 Grounded Recall 使用最大一对一匹配。平均 token 为全部 EFCR 推断尝试的实际模型 token / 298，排除评价成本。

所有新产物位于 `runs/efcr_append_v1/` 和 `results/efcr_append_v1/`。七算法表中前六行直接读取 `results/prompts_v2/four_metrics_both_policies.json`，保持已有结果。原文件哈希保存在新运行目录，完成时生成 `historical_integrity.json`。

失败请求缺失 usage 时，严格按原评价体系返回 `mean_tokens=null`，不擅自计为零。`transport_usage_audit.json` 单列缺失尝试与已知 token/298 下界。最初运行源文件归档为 `runs/efcr_append_v1/EFCR_initial.py`，后续仅运行器记账审计修订由 `runner_revision.json` 记录，并验证提示词和全部推断函数 AST 完全相同。

原始参考的人工裁决范围仍为 63 条层级分歧，预测与参考的语义匹配仍由模型完成。该追加实验没有扩大人工审核范围。
