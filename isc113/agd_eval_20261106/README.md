# AGD-Eval 2026-11-06

本目录单独完成六算法预测的 A-only 自动评价。既有 runs、references、inputs、results 均不写入。

## 数据与配置

- frozen_inputs：从 ISC113 复制的原始输入、588 条参考和五份导出文件（含六种方法）。source_manifest.json 记录原文件 SHA256。
- agd_eval_kit_original.zip、agd_eval_kit：用户提供的工具包原样存档。
- work：首次默认思考模式的试运行，因长请求连接中断而停止，不参与正式计分。
- evaluation：统一预算的三段先导检查，保留但不计分。
- final_eval：先导检查后冻结提示词的正式评价，298 段对话，7,868 条预测，6,915 条去重文本。
- run_pipeline.py：审核阶段及断点缓存。所有模型请求均盲化来源 ID，不发送原算法证据、置信度、旧标签或隐藏 B 话语。
- agd_eval.py：工具包本地副本及确定性评分。修复了零输出对话跳过召回分母的问题；新发现按旧参考是否覆盖事实核心判断。
- verify_scoring.py：测试复合断言、字段联合覆盖、零输出对话与六算法统一分母。

固定模型 qwen3.8-max-0902。temperature=0。审核批量上限 12。sweep/pred/gold/sweep_support 思考预算 4096，pool 为 8192。输出上限分别 16000、12000、12000、12000、30000。流式接收仅改变传输。旧试运行未并入正式评价。

评价请求需要外部模型服务，密钥只从 DASHSCOPE_API_KEY 进程环境读取。密钥不保存在代码和数据文件中。

## 复现与续跑

在本目录执行，先通过环境提供密钥：

```powershell
python run_pipeline.py --workers 16
python audit_results.py
python prepare_scoring_view.py
python agd_eval.py score --work ./scored_eval --bootstraps 2000
python make_report.py
node build_workbook.mjs
```

已有完整批次从内容哈希缓存恢复，已有完整对话阶段跳过。缓存文件包含实际请求绑定与判定。attempts.jsonl 记录重试和可用的 token 用量，费用属于评价端。

试运行曾因 TLS、代理中断而失败，且两次进程中止时部分请求未收到最终回复。这些请求可能已计费，不能从缺失 usage 推断零费用。探测调用额外使用了 103 和 1460 token，均不计入算法生成成本。

## 产物与解释

最终指标为微平均：先累计分子分母，再相除。所有算法在全部 298 段对话和同一事实池上评价，零输出对话的召回分子为零，分母保留。原始预测准确率保留同算法重复预测的条数权重。

scored_eval/results 保存六算法主表、计数表、逐预测/事实/字段结果、对话配对 bootstrap 差值、参考标签迁移和人工复核队列。outputs/six_algorithm_evaluation 保存 Excel 交付表。

UNCERTAIN 不自动认定有据，并进入人工队列。真实人工复核尚未完成，自动表不能声称已完成人工校准。区间只涵盖对话抽样误差。共享池仍可能遗漏全部来源共同未发现的事实。P_raw ≥ 90% 用于报告冻结输出是否达标，不用测试标签筛选输出。

诊断按事实核心缺失、具体字段缺失及原子标签统计。E3 不等同于 E2 推断不足，CONTRADICTED 不等同于事件状态错误，脚本不强行制造这两类原因统计。

完整度统一规则：scored_eval 是 final_eval 原始判定的评分副本。所有规范事实字段统一为 required=true，核心字段权重 2，其余为 1。原模型 required/weight 保存为 judge_required/judge_weight，原判定文件完整保留。此规则在产生任何正式分数前确定，避免模型任选可选字段使完整召回率失去一致含义。

结构校验补强：仅对可唯一识别的 c/a 数字 ID 补齐前导零，原响应保留在 attempts.jsonl。无输入原子覆盖的 pool 字段会触发同提示词重审，原结果另存 quality_rejected。正式运行期间未修改模型提示词。
