# RealPersonaChat：单边对话隐藏身份关联

主体错归属过滤复验：[四个固定匿名者的运行说明](FILTERED_PORTRAIT_REPEAT.md)。IA、HW、HS、HU 沿用各自全部 A 侧原文，使用 `elara_subject_v2 → 一次主体错归属过滤 → Summary`，重新抽取并重新生成两路画像；自述档案不进入模型输入。交付见 `runs/portrait_subject_filter_20261108`。

此前实验：[固定209属性的字符串去重与画像汇总对照](PORTRAIT_SUMMARY.md)。本轮复用209条提取结果，精确去重为206条，Qwen thinking分别重新生成汇总画像与direct画像，两路生成均不看档案，冻结后由独立Sol high子代理双向评分。

主体与稳定性约束改进版已独立实现，设计及运行方式见 [PROFILE_SUBJECT_V2.md](PROFILE_SUBJECT_V2.md)：显式 `A says:`、保守主体/稳定性准入、合并后二次核验、全量冲突配对，以及原生 Sol high 子代理原子评分；原版算法与首轮结果保留。

新增独立实验：单个 B 的全部 A-only 对话 → ELARA v1 → 稳定特征 → 与 B 自述档案语义一致性评分，并设置 direct+thinking 对照。设计与复现命令见 [PROFILE_CONSISTENCY.md](PROFILE_CONSISTENCY.md)，新结果保存在 `runs/single_b_profile_20261106`。

首轮四个条件已完整运行，40/40 个组×方法结果、200/200 份原版 v1 属性清单均已保存。结果与局限见 [REPORT.md](runs/pilot_final/REPORT.md) 和 [ANALYSIS.md](runs/pilot_final/ANALYSIS.md)。输入隔离及引用审计通过；10 项测试通过；完整缓存回放新增 API 请求为零。首轮整体关联效果较弱，不能支持高准确率身份关联结论。

2026-11-06 主体归属专项审计见 [主体审计报告](audits/subject_attribution_20261106/REPORT.md)：固定随机抽取每组一段，共 20 段、349 条，由主助手逐条复核，保守确认 65 条主体/说话行为误归，其中 60 条为 A→B 信息转移；不是人工金标。全量 3,195 条另有独立提示词的 Qwen 筛查，标签与确认数分开保存。此前“引用审计通过”只验证原文子串和输入隔离，不能当成语义支持或主体正确性保证。原预测和评分没有改写。

四个实验条件：Same-A × ELARA v1 + Qwen 关联、Different-A × ELARA v1 + Qwen 关联、Same-A × 纯 Qwen thinking、Different-A × 纯 Qwen thinking。两种方法在每个设置内严格共用输入。每组十段对话，真实 K 从 1 到 10，预测时未知。

ELARA 路线完整调用原始 `../new_algorithm.py` 的 `pipeline`：explicit → implicit → gap_scan → 每八项独立 audit → 保留原模块产生的所有最终 claims 和审核状态。原算法文件及提示词没有修改。独立私有 Python 包只替换输入校验器，允许真实 RealPersonaChat A-only 数据和本地连续 turn_id；不会伪装成 DailyDialog，也不会修改原模块的全局校验函数。每段产生一个属性清单，因此十段得到十份清单，每份可有零到多条属性，并非强制每段一个属性。

关联模块只接收这十份清单，包含原始证据、置信度、审核等级与分歧。Qwen 联合输出一个完整聚类和 K，并为每个合并组提供连通的证据引用；引用必须确实存在。提示词区分稳定的区分性证据、常见特征、情境变化、属性缺失与矛盾，但不按答案调参，不设置固定相似度阈值，不强制 K。

纯 LLM 路线只接收十段 A-only 文本，一次调用直接联合聚类，提示词完全不提属性提取、persona、画像或中间清单。两路线的关联/直接聚类调用均为 `qwen3.8-flash`、temperature=0、enable_thinking=true、thinking_budget=2048、max_tokens=8192；ELARA 抽取保留 v1 原始 512/4096 预算。无法从外部验证 LLM 的内部思考一定不使用类似属性的概念，因此该对照的准确名称是“无显式属性提取流程的直接提示词基线”。两个方法总调用量不同，不声称计算成本相同。

## 数据与隔离

源：[nu-dialogue/real-persona-chat](https://github.com/nu-dialogue/real-persona-chat)，固定提交 `28d0b6b3865b29cabc26c230a2db37cdf315e937`，CC BY-SA 4.0。作者 Sanae Yamashita, Koji Inoue, Ao Guo, Shota Mochizuki, Tatsuya Kawahara, Ryuichiro Higashinaka；论文 [PACLIC 2023](https://aclanthology.org/2023.paclic-1.85/)。本实验不恢复真实世界身份，仅评估匿名语料标签的归属。原语料为日语，保留日语输入，不进行翻译。

公开版实测 13,583 段、233 人、1,572 对；131 人至少十个不同伙伴；582 对至少十段会话。记录内 `dialogue_id` 有两处重复值，采用归档中文件名作为唯一来源 ID；六份完全相同的转录文本在抽样前排除。统计细节见 `runs/pilot/census.json`。这些资格数量不等于最大可生成的不重叠组数。

原始公开版平均每对约 8.6406 段；去除六份重复文本后，抽样池为 13,577 段，census 的配对均值约 8.6368 来自这个去重池。原始计数、重复文件对应关系另见 `data/corpus_audit.json`。

抽样使用可复现的固定 seed，在所有 K 和两个设置之间禁止复用源对话，也禁止正反方向重复使用同一对话。Same-A 固定观察者；Different-A 十个 A ID 不同，且 A 集合与 B 集合互斥。通过随机 B 及随机容量分配选择精确 K，Different-A 使用二分图匹配确保十个 A 不重复；不是均匀抽取全部可行组，K 内的身份频次也不是固定均衡。

原 ID 占位符（包括第三方 ID）全部替换为同一个 `[PERSON]`。不传原对话 ID、身份 ID、时间戳、评分、persona 或 B 发言。A 侧发言连续本地编号，移除隐藏轮次数量信息。模型只见不含 K 的随机样式 group_id 及 D1..D10；真实 K 只在独立 gold 文件和评分报告中出现。

`inputs.json` 与 `gold.json` 分离；`run.py` 不读取 gold 或 sampling。`score.py` 在预测后单独读取答案、检查冻结哈希再评分。每个合并必须引用有效来源，但引用正确不保证语义判断正确；未增加额外模型裁判。语料中的人可以跨测试组出现，不能将组当成说话人独立样本。

## 运行

在项目根目录执行，Python 3.11+，依赖现有 `requests`。密钥仅用进程环境变量 `QWEN_API_KEY` 或 `DASHSCOPE_API_KEY`，不放入代码、配置和日志。

```powershell
python -B -m isc113.identity_linkage.prepare --out isc113/identity_linkage/runs/pilot_final
python -B -m unittest isc113.identity_linkage.test_identity_linkage -v
python -B -m isc113.identity_linkage.run --folder isc113/identity_linkage/runs/pilot_final --workers 8
python -B -m isc113.identity_linkage.score --folder isc113/identity_linkage/runs/pilot_final
python -B -m isc113.identity_linkage.verify --folder isc113/identity_linkage/runs/pilot_final
```

默认首轮为每设置每 K 一组：20 个组、200 段原始对话、40 个方法结果。该规模属于探索性试验，不能单凭十组均值下论文结论。扩大样本必须新目录，避免覆盖冻结输入，例如：

```powershell
python -B -m isc113.identity_linkage.prepare --groups-per-k 10 --out isc113/identity_linkage/runs/main_10
python -B -m isc113.identity_linkage.run --folder isc113/identity_linkage/runs/main_10 --workers 8
python -B -m isc113.identity_linkage.score --folder isc113/identity_linkage/runs/main_10
```

抽样失败会明确报错；有界随机搜索失败不等于数学上不存在样本，不会悄悄降低 K 或允许重用。`prepare` 生成的语料 SHA256、输入和答案 digest、推理代码及原 ELARA 源文件 SHA256 都冻结。修改推理代码或参数需要新运行目录。

续跑重复同一条命令，使用同一完整请求的首个有效响应缓存；请求完整记录在 `attempts.jsonl`，包括原始输出、usage、失败和格式重试。每请求最多六次尝试；不会因聚类结果差而重试。可从附有说明文字的响应中读取已完整存在且通过原校验的 JSON，不补括号、不补字段、不恢复截断内容。连接复用及有记录的有限 TLS 重试减少代理握手故障；TLS 失败和中断请求的费用可能无法从 usage 确定，不将未知费用记为零。其他网络计费不确定时暂停相关任务，未完成 start 也阻止自动补发。认证/模型访问错误打开停止开关。失败状态保留在各阶段 status 文件，缺失结果不会按零分或成功处理。

报告：`runs/pilot_final/REPORT.md`；逐组真实人数、预测人数、差值、绝对差值、完整聚类准确率、pair TP/FP/FN/TN、ARI、B³ 指标见 CSV/JSON。人数差=预测 K−真实 K。K=10 的未定义 pair 指标记 null，且给出有效分母。报告包含同输入配对差值与请求返回的 token 总数；不猜测费用。

`predictions_vs_gold.json` 并列保存每组真实聚类、预测聚类、人数差和模型给出的合并证据；真实聚类只用 D1..D10 表示，无须查看语料说话人 ID。`verification.json` 检查全部发出的请求、模型与 thinking 参数、ELARA 每份清单的字面证据、最终合并引用、代码哈希及输入隔离，另给出属性总量、空清单、证据审核等级与分阶段 token。

`runs/pilot` 是早期连接排查记录，含未用于最终对照的旧 direct 提示词，不作为实验结论；完整保留便于审计。最终 direct 在 `runs/pilot_final` 执行；完全相同输入与代码绑定的 ELARA 阶段在 `runs/pilot_elara` 开始，后提高并发至 16，在 `runs/pilot_elara_fast` 复用缓存继续执行，再由 `manage combine` 合并到 `pilot_final`。只复用排查阶段参数完全相同的 ELARA 原始响应，不复用旧 direct。中断和 TLS 失败的补发逐项记录在各阶段的 `transport_recovery.json` 和 ledger 中。恢复及提高并发不参考答案。`data/feasibility_g10` 是已实际成功生成的每格十组容量检查（200 组、2,000 段），尚未运行在线推理，不是模型结果。
