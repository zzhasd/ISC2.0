# 主体、稳定性和语义关系约束改进

入口 `profile_subject_v2.py`；独立副本 `elara_subject_v2.py`；输出 `runs/single_b_profile_v2`。保持上一轮同一个 B=HS、同样20段对话、3个伙伴、300条A话语。原始 `isc113/new_algorithm.py` 和上一轮结果不变。本轮针对观察到的错误作事后改进，不是未见样本上的验证。

本轮已完成。先读 [结果与局限](runs/single_b_profile_v2/ANALYSIS.md)，数值与验证汇总见 [REPORT.md](runs/single_b_profile_v2/REPORT.md)；最终可用特征见 `validated_stable_traits.json`。

## 模块改动

1. **说话人边界**：每条发给模型的可见话语都具有 `speaker: A` 及 `A says: 原文`；本地证据和 turn_id 仍对应原文。没有构造虚假的 B 轮次：固定交替的 mask 序列可能暗示原始语料未保证的交替/数量。模型引文必须去掉合成前缀，不让前缀成为证据。
2. **抽取副本**：保留 v1 的 explicit、implicit、gap_scan、分批 audit 主体流程，但改进每个阶段的主体规则；审核后只保留 supported、E1/E2 且原文引用有效的项。原版“保留 disputed”机制在此副本中改为保守拒绝。
3. **独立候选准入**：逐条核验主体、实际话语依据、蕴含关系和稳定性。代码仅允许 `B AND direct_address/reflection/resolved_reference AND entailed AND enduring` 且原候选 asserted 的项进入下一层；A/第三人/一般性/不确定主体、问句、第一人称自述、暂时状态/行程、推测均拒绝。原文完整提供，原审核标签不是第二份证据。所有拒绝与原因保存到 gates/。
4. **顶层合并后再审**：仅合并准入项，引用只能来自准入 claim；独立调用再次对合并后的精确命题核验主体、蕴含和稳定性，防止合并生成新细节或把局限文字当作准入理由。
5. **全量配对兼容性**：对所有最终准入提案的两两组合检查等价、可共存、真正矛盾或未解决。真正矛盾要求同主体、时间和适用范围内不可同时为真；不把范围宽窄或缺失证据当矛盾。对 conflict/unresolved 双侧隔离，不按频次投票选一个；等价项去重。完整配对覆盖由代码核验。
6. **原子评分**：独立 Sol high 子代理在不看对话或输出的情况下，把10条档案拆成18个最小命题，保留频率、时间、否定、实体等限定。对每个原子判 supported/contradicted/mixed/insufficient，并分开记录支持与反证引用。合取档案整体支持要求全部原子得到支持；没有证据不等于矛盾，部分支持不算整句支持。
7. **评分证据准入**：Sol评分代理独立复核全部Qwen特征，发现主体/稳定性/蕴含问题则记录并不用于评分。代码禁止已知问题特征贡献任何非“不足”标签，并导出 `validated_stable_traits.json`；Qwen原始输出仍保留在 `stable_traits.json`。问题复合特征整条隔离，不借评分临时修补成较弱命题来增加分数。该Sol复核也是模型判断，不等于人工确认。

## 模型分工和对照

- Qwen `qwen3.8-flash`、thinking=true：抽取、候选主体/稳定性核验、合并、合并后核验和内部冲突检查；没有任何Qwen请求接收档案或输出档案评分。副本沿用512 thinking预算，新增模块2048；temperature=0。
- Codex 原生 `gpt-6.1-sol` / `high` 子代理：档案拆分、ELARA结果与档案语义评分、direct直接原文分析与档案评分；不经外部Qwen/API调用。
- Direct 代理只接收相同的全部 A-only 原文和原子档案，直接判断，不设置属性提取、画像、稳定特征表等中间流程。ELARA评分代理只使用冻结特征，原始上下文只用于核验其证据，不得绕过特征另从原文挖掘事实补分。
- 两个评分代理分开运行，不看另一条件或上一轮输出；本轮提示词与设计已受上一轮错误启发，不声称整体实验盲测。评分协议见 [SOL_JUDGE_V2.md](SOL_JUDGE_V2.md)。

direct的直接分析属于评分步骤，因此按用户要求使用Sol high；它不再是上一轮Qwen direct。两路完整计算量不等，旧的55/30不可直接用来证明新模块提升。

## 复现与审计

```powershell
python -B -m isc113.identity_linkage.profile_subject_v2 prepare
python -B -m unittest isc113.identity_linkage.test_subject_v2 -v
# 通过进程环境变量提供QWEN_API_KEY
python -B -m isc113.identity_linkage.profile_subject_v2 extract --workers 8
# archive_atoms.json 由原生Sol high子代理独立生成；不是Qwen调用
python -B -m isc113.identity_linkage.profile_subject_v2 packets
# 分别以Sol high子代理按SOL_JUDGE_V2.md对两个packet评分，写judgment_*_sol.json
python -B -m isc113.identity_linkage.score_subject_v2
```

子代理配置和评分任务由本次Codex会话显式分派，评分文件记录模型和推理级别。Python脚本不伪装成调用Sol API；脱离Codex执行时需要重新安排相同评分子代理。请求完整记录在 attempts.jsonl；输入和代码冻结于 manifest.json；代码验证包括原算法与上一轮快照字节相同、全部A标记、Qwen无档案泄漏、候选准入、合并引用和完整冲突配对。原始引用正确仍不保证语义正确，结果必须结合Sol的特征质量审计和逐原子理由阅读。

分数以全条目为分母，`100 × (supported + 0.5×mixed)/N`，同时提供有证据条件分数和覆盖率；完整档案、原子两个粒度分别报告。不是身份准确率或人工金标准，也不是样本外泛化结论。
