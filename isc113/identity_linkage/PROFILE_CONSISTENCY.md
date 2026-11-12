# 单 B 全量 A-only 与自述档案语义一致性

这是独立于原聚类实验的新实验。入口 `profile_consistency.py`；运行目录 `runs/single_b_profile_20261106`，不覆盖既有结果。

本轮已完整执行。**解读结果请先读 [质量复核](runs/single_b_profile_20261106/ANALYSIS.md)**：实际模型仍有主体转移、稳定性筛选与语义关系误判，不能把原始分数当作方法有效性的证明。数值汇总见 [原始报告](runs/single_b_profile_20261106/REPORT.md)。

## 抽样和输入

固定种子 2026110603，从原始公开语料中全部对话数为 10–20、不同伙伴不少于 2 的匿名说话人中等概率选择一个 B。资格不看档案内容或模型结果。实际选中 HS，20 段对话、3 个伙伴、300 条 A 话语。纳入原始语料中所有涉及 HS 的人际对话，不按话题、证据强弱筛选，不使用系统生成的模拟对话。所有 A 可能不同，所有 B 是同一匿名语料说话人；伙伴用 A1..A3 编号。只有 A 侧话语进入模型；原始身份占位符统一替换。完整选择规则、匿名原始 ID 和来源映射保存在 selection.json，模型不接触该文件。

档案使用 `interlocutors.json` 中 B 的全部 10 条 `persona` 自述文本，保留日语；不将缺乏可校准文本对应关系的数值性格问卷强行转换为语义命题。来源沿用 README.md 的固定提交与许可。B 的发言、其他人的档案、对话评价与时间戳均不进入推理。

## 方法

1. **ELARA v1 + 稳定特征顶层模块 + 一致性评分**：每段 A-only 原样调用 `new_algorithm.py` 完整 v1 pipeline（explicit、implicit、gap_scan、分批 audit）。只复用现有私有输入校验适配器，不修改 v1 算法和提示词。顶层接收全部 v1 结果、审核状态、原始 A 文本和伙伴局部标签，检查主体归属、稳定性、合并同义项、记录局限，并以 D/claim 引用输出稳定特征。顶层不接触档案。筛选稳定特征是新模块的设计，不是改变 v1 保留 disputed 候选的行为。冻结稳定特征后，独立调用将这些特征与完整档案逐项比较。
2. **direct+thinking**：单次调用直接读取相同的 20 段 A-only 文本和完整档案，按同一关系量表逐项分析。提示词不要求属性提取、稳定特征表、persona 抽取或其他中间产物；没有给它 ELARA 结果。无法从外部限制模型内部采用什么思考概念，因此该条件是“无显式抽取流程的直接分析”。

所有 LLM 均 `qwen3.8-flash`、`enable_thinking=true`、temperature=0。v1 保留原始 thinking_budget=512、max_tokens=4096；顶层、两路评分使用 thinking_budget=2048、max_tokens=12000。两组最终量表和预算一致，完整流程计算量不同。API key 只由环境变量注入进程，不保存到源码、配置或 ledger。请求日志包含原始模型输出、usage、缓存键和有限重试。只因格式/传输失败重试，不因结果重试；续跑严格匹配请求缓存。

## 评分

对每条档案输出 supported、contradicted、mixed、insufficient，引用必须存在。ELARA 路线引用冻结的 T 编号，再追溯到 v1 claim 和 A 原文；direct 引用 D/turn/原文子串。支持和矛盾必须具有语义蕴含，相关话题不算支持；缺失证据不算矛盾；mixed 只用于真正同时存在支持和反证。

- 全档案支持分 = 100 × (supported + 0.5 × mixed) / 全部档案条目数。
- 有证据条件一致性 = 100 × (supported + 0.5 × mixed) / (supported + contradicted + mixed)，分母为零记 null。
- 同时报告覆盖率、矛盾率和四类数量。全档案分受覆盖率影响，条件一致性也不能脱离覆盖率解释。

分数是固定量表的模型关系判断经代码汇总，不是已校准的人类语义相似度；一次 B 实验不能证明身份识别准确率、普遍优劣或统计显著性。档案是不完整自述；正确引用也不等于正确主体归属/蕴含。所有阶段由同一模型处理，存在共同偏差。未增加其他候选人/负例，不将一致性称作身份概率。

## 复现

在根目录运行，先通过进程环境变量提供 `QWEN_API_KEY` 或 `DASHSCOPE_API_KEY`：

```powershell
python -B -m isc113.identity_linkage.profile_consistency prepare
python -B -m unittest isc113.identity_linkage.test_profile_consistency isc113.identity_linkage.test_identity_linkage -v
python -B -m isc113.identity_linkage.profile_consistency run --workers 8
python -B -m isc113.identity_linkage.profile_consistency report
python -B -m isc113.identity_linkage.verify_profile_consistency
```

输入与源码 SHA256 在 manifest.json 冻结；代码/输入变化必须另开 `--folder`。相同命令可用已验证响应缓存完整回放。最终结果见运行目录 REPORT.md、results.json；逐项理由与证据见 direct.json、elara.json；稳定特征见 stable_traits.json；全部 v1 输出及诊断见 attributes/。
