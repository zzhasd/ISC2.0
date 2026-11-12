# RealPersonaChat 十对话身份关联实验

完整运行：True；已评分 40/40 个组×方法。

| 设置 | 方法 | 组数 | 人数 MAE ↓ | 人数准确率 ↑ | 完整聚类准确率 ↑ | ARI ↑ | B³ F1 ↑ |
|---|---|---:|---:|---:|---:|---:|---:|
| same_a | elara | 10 | 2.400 | 0.200 | 0.000 | -0.030 | 0.637 |
| same_a | direct | 10 | 2.500 | 0.200 | 0.000 | -0.025 | 0.639 |
| different_a | elara | 10 | 3.400 | 0.200 | 0.100 | 0.081 | 0.651 |
| different_a | direct | 10 | 3.700 | 0.100 | 0.000 | 0.002 | 0.642 |

人数差定义为预测人数减真实人数；逐组真实 K、预测 K、差值和聚类指标见 group_metrics.csv。
K=10 没有真实同人对；未定义的 pair precision/recall/F1 记 null，ARI 和 B³ 仍可计算。

## 每个 K 的结果

| 设置 | K | ELARA 预测人数 | Direct 预测人数 | ELARA 绝对误差 | Direct 绝对误差 |
|---|---:|---|---|---|---|
| same_a | 1 | 7 | 5 | 6 | 4 |
| same_a | 2 | 8 | 7 | 6 | 5 |
| same_a | 3 | 6 | 7 | 3 | 4 |
| same_a | 4 | 9 | 9 | 5 | 5 |
| same_a | 5 | 6 | 6 | 1 | 1 |
| same_a | 6 | 7 | 10 | 1 | 4 |
| same_a | 7 | 7 | 7 | 0 | 0 |
| same_a | 8 | 9 | 7 | 1 | 1 |
| same_a | 9 | 9 | 9 | 0 | 0 |
| same_a | 10 | 9 | 9 | 1 | 1 |
| different_a | 1 | 10 | 9 | 9 | 8 |
| different_a | 2 | 7 | 7 | 5 | 5 |
| different_a | 3 | 10 | 10 | 7 | 7 |
| different_a | 4 | 9 | 8 | 5 | 4 |
| different_a | 5 | 7 | 10 | 2 | 5 |
| different_a | 6 | 9 | 8 | 3 | 2 |
| different_a | 7 | 8 | 7 | 1 | 0 |
| different_a | 8 | 10 | 10 | 2 | 2 |
| different_a | 9 | 9 | 10 | 0 | 1 |
| different_a | 10 | 10 | 7 | 0 | 3 |

## 解释边界

- Exploratory pilot: one group per K per setting by default; no population-level claim.
- Dialogue-disjoint groups may reuse speakers; groups are not speaker-independent.
- Direct prompt has no attribute-extraction scaffolding; internal reasoning strategy cannot be verified.
- K is not disclosed; exact-K stratification and multiplicities are design choices.
- No learned calibration, prompt tuning against gold, or real-world identity resolution.
- One logical linkage/direct prediction per group, with logged format/transport retries; ELARA uses additional extraction calls.

## 请求统计

```json
{
  "prompt_tokens": 1847225,
  "completion_tokens": 1327580,
  "total_tokens": 3174805,
  "completed_attempts": 1241,
  "valid_attempts": 1146,
  "rejected_or_failed_attempts": 95,
  "unresolved_starts": 0,
  "billing_unknown_attempts": 58,
  "usage_missing_attempts": 58,
  "wrapper_recovered_attempts": 0,
  "note": "Returned token totals include invalid/schema-retry responses. Missing usage/unknown billing is NOT zero cost; no monetary estimate."
}
```

结果为封闭语料库中匿名标签的聚类，不恢复任何真实姓名或外部身份。
