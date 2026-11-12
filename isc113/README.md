# ISC113：DailyDialog A→B 单向属性预测

2026-11-04 使用 `prompts-v2.py` 的重新评价见 [results/prompts_v2/REPORT.md](results/prompts_v2/REPORT.md)，包含 equivalent-only 和 broader_counted_as_hit 两套六算法四指标及分子分母。原预测、588 条参考和历史结果均保留。接口沿用 DashScope / qwen3.8-flash；从原始响应按旧 `validate_matches` 规则选择首个有效完整响应，提示词格式偏离单独审计，不改写模型判断。可执行 `python -B -m isc113.evaluate_prompts_v2 --replay-recorded` 无密钥重算。配置哈希、逐输入计数、原始响应及验证记录分别位于该结果目录和 `runs/prompts_v2_evaluation/attempts.jsonl`。

仅保留指定的一轮六算法实验。A 是可见说话者，B 是隐藏预测目标。所有运行、输入校验和评价入口均拒绝 B→A。

## 一键检查与复现

在 D:\\桌面\\ISC2.0 执行：

```powershell
python -B -m isc113 check
python -B -m isc113 reproduce
python -B -m isc113 export
python -B -m isc113 match
python -B -m isc113 analyze
```

check 执行测试并复现；reproduce 从原始 API 响应重新经过六算法流程，逐条比较预测、任务 ID、原始数量及四指标。它同时核验消歧参考可由原 GPT 参考和 63 条人工裁决重建。export 从响应日志重建 1,788 条对话级结果并校验冻结文件。match 在当前缓存完整时无需密钥、无需请求。analyze 重算主表和统计。任何预测变化会使匹配绑定失效。

默认主表采用 equivalent 命中。另保留同一轮的 equivalent+broader 宽松计分对照，位于 results/broader_counted_as_hit；reproduce 同时核验该对照，二者不混用。

## 数据位置

| 用途 | 文件 |
|---|---|
| 原始冻结 300 段完整 A+B 对话 | data/confirmatory_dailydialog300.json |
| 298 段主分析 A-only 输入 | inputs/dailydialog.json |
| 冻结 300 段 A-only 输入 | inputs/dailydialog300.json |
| 最终 588 条消歧参考 | references/dailydialog_human_adjudicated_588.json |
| 消歧前 GPT 参考，A→B 的 300 段 | references/dailydialog.json |
| 六算法对话级原始结果，含空输出 | runs/main/exports/dailydialog.json |
| 原始请求、响应、重试和实际 usage | runs/dailydialog/attempts.jsonl |
| 语义匹配和绑定 | evaluation/matches/dailydialog/ |
| 四指标结果 | results/dailydialog_four_metrics.csv |
| 原结果冻结基线 | audit/experiment_baseline.json |
| 复现、接口测试和清理报告 | results/reproduction_check.json、results/interface_test_report.json、CLEANUP_REPORT.md |

六算法结果存于一个规范文件，以 method 字段区分，未另存六份重复数据。每方法都有 298 条对话级记录；空 claims 保留，不改变分母。

| method | 原始预测属性数 |
|---|---:|
| direct_thinking | 952 |
| direct_multisample_verifier | 1,379 |
| route1_only | 651 |
| route2_only | 1,087 |
| dual_without_verifier | 1,695 |
| dual_with_verifier | 1,255 |

合计 7,019 条。两个角色质量异常对话 train_5847、train_9210 保留在原始 300 段中，但不进入主分析。588 条参考为 E1=136、E2=126、E3=295、E4=31，有据分母为 262；36 段空参考也保留。

## 新一轮在线运行

通过进程环境 QWEN_API_KEY 或 DASHSCOPE_API_KEY 提供密钥。新实验独立存于 runs/<run-id>，禁止以 main、dailydialog 或 evaluation 开头的名称覆盖历史。凭据不写入项目文件。

```powershell
python -B -m isc113.run --run-id new_round --workers 8
python -B -m isc113 export --run-id new_round
python -B -m isc113 match --run-id new_round
python -B -m isc113 analyze --run-id new_round
```

默认 298 段；可加 --scope all300 运行原始 300 段。--limit 可用于小规模调试；小样本分析会明确报告 missing_input_method_outcomes 和 complete_experiment，不能当成完整主实验。新实验评价仍只使用 298 段最终参考。续跑须使用相同输入清单、scope、limit 和代码版本。

历史 API 标识符和参数保持为 qwen3.8-flash、thinking_budget=512、生成上限=2048、验证上限=3072；提示词、六算法输出逻辑和匹配语义保持原设定。重新请求供应商模型存在采样或模型服务变化，精确复现依靠已冻结的原始响应。

## 保留代码

- inference.py + prompts.py：六算法、候选合并、验证器、隔离输入。
- client.py + run.py + export.py：请求、重试、脱敏、续跑、原始响应重建。
- annotation.py + reconcile.py：GPT 完整 A+B 属性审核、A-only E1–E4 分级、独立审核对齐及人工裁决重建；用法见 ANNOTATION_GUIDE.md。
- evaluation.py + recover_evaluations.py：参考读取、语义匹配、缓存绑定及完整终止 JSON 恢复。
- statistics.py：四指标、最大一对一匹配和对话聚类统计。
- reproduction.py + test_*.py：历史结果及接口测试。

annotations/ 保留 A→B 的原始 GPT 审核及裁决，evaluation/alignment/ 保留审核清单的语义对齐，results/human_disambiguation_63/ 保留人工消歧依据。没有自动重建或改写任何 GPT 语义判断。

仅依赖 Python 3.11+ 和 requirements.txt 中的 requests。无需其他 ISC 目录。完整 GPT 审核不等同于全库人工金标；人工处理范围是 63 条层级分歧。
