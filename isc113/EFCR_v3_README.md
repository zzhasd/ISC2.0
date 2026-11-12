# EFCR G0/G1/G2/G3 实际验证

主目标为 Precision、Recall 和 Grounded Recall；token 仍按原规则记录，不要求降低。旧六算法、EFCR v1/v2 与此前研究文件保持不变。

模块 `EFCR_v3.py` 接受严格 A-only 输入和从 v2 原始生成响应重建的候选包，返回八组对话级预测及诊断数据。候选固定 1276 条，来自 298 段。候选包仅含 candidates 和 generation_task_ids，推断阶段不加载参考或完整 B 对话。

- G0：同轮重新请求原裁决，保留生成器分数和来源，作为服务时间/采样变化的对照。
- G1：相同候选顺序和原裁决提示词，仅移除 confidence 与 proposal_sources。
- G2：先从原文独立生成带主体、谓词、对象、时间、数量、否定、模态和证据的完整属性表；再对固定原候选检查八项条件。独立属性表不看候选、旧裁决或生成器分数，且不是金标。
- G3：在 G2 基础上，额外核验独立发现且与原候选非同文的新属性，补充置信度至少 0.9 的通过项。

四组均保留最终门槛 0.7 与 0.9 两种结果，事前固定，不只报告获胜项。G2 与 G1 同时改变核验任务和额外证据表，不将其差异归因于单一因素。每个方法保留必要的旧生成 task_ids 和新任务，包括运输失败的重试任务，不能把缓存成本记为零。

```powershell
python -B -m unittest isc113.test_efcr_v3
# QWEN_API_KEY / DASHSCOPE_API_KEY 通过进程环境提供
python -B -m isc113.EFCR_v3 --workers 12
python -B -m isc113.EFCR_v3 --replay
```

所有运行产物位于 `runs/efcr_v3_validation`，结果位于 `results/efcr_v3_validation`。支持同配置续跑，replay 不允许 API 调用。模型 qwen3.8-flash，temperature=0、thinking_budget=512。G0/G1 输出上限 6144，独立抽取、条件核验及语义匹配上限 8192。

评价阶段使用原 `prompts-v2.py`、`validate_matches`、`score_item`、`four_metrics`；八个新方法、原八算法和 v2 的 0.9 阈值控制共 17 方法联合匹配。完整未筛选候选及独立有效引用属性也加入同一匹配库存，供诊断误杀和候选覆盖上限。相同文本共享判分。原有参考分母仍为 588、有据 262；空输出仍计入 298 段。

历史保护清单仅包含本任务固定的旧算法、旧运行和研究产物，不把其他并行实验的日志列为冻结历史。原始响应、错误和重试全部保留。已用于反复分析的 298 段仍属于开发集，不能把本轮当作未见数据测试。
