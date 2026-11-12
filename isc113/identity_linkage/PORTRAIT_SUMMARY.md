# 固定209属性的保全式画像汇总实验

实现：`portrait_summary.py`；输出：`runs/portrait_summary_20261107`。同一匿名B=HS，20段对话、300条A发言。本轮严格按用户要求复用改进抽取模块已有209条输出，不重新推理提取，不使用上一轮43条准入项、4条验证特征或旧评分。

本轮已完成：[结果与局限](runs/portrait_summary_20261107/ANALYSIS.md)、[评分报告](runs/portrait_summary_20261107/REPORT.md)。209条原细节保全通过，但完整输入的独立检查认为18/22条自然语言总结有偏差，不能把附件保全称为严格语义无损总结。

## 两路生成

**属性汇总路线**：读取上轮20个 attributes/*.json 的全部209条prediction.claims，保留每项claim、attribute、certainty、confidence、evidence、审核状态与来源。对claim字符串做精确相等去重，不strip、不改大小写、不做Unicode规范化、不模糊去重。结果206条不同字符串，3条完全重复记录；重复项的全部字段和来源仍在members中。83条qualified原记录均保留。

Qwen收到完整206项和全部209个原members，不接触档案、原子命题、旧评分或经过筛选的画像。它将语义相近项合并成逐条画像，保留所有独立细节、频率、时间、实体、否定、条件和不确定性。候选存在冲突/主体疑问时明确说明，不删除原属性或暗中择边。模型须将每个unique_id分配到恰好一条画像，代码校验全覆盖与不重复。代码再将该组所有原记录完整附到source_details，原样保留细节；这保证结构和原文字段保全，但不等同于自然语言总结已经无损。Sol另评估总结文字的忠实性。

**direct+thinking**：重新调用Qwen，只读相同全部A-only原文（speaker=A、A says标记）和局部伙伴编号，直接输出一条条B画像及原文引用。不提供209条属性、任何属性提取中间清单或提示、档案、原子命题、旧画像、旧评分。不强制画像数，也不按结果追加推理。它不是上一轮Sol直接评分，而是本轮Qwen直接生成。

两路本次生成均 `qwen3.8-flash`、temperature=0、enable_thinking=true、thinking_budget=2048、max_tokens=20000。两次调用独立并行，使用新的请求名与新的缓存目录，不复用旧生成响应。原属性抽取调用为0。

## 独立评分

画像生成冻结后，分别开启原生 `gpt-6.1-sol` / `high` 子代理，仅提供本条件画像与B的10条原始自述，不提供旧原子命题、另一条件或旧结果。评分不调用Qwen或外部API。

按 [PORTRAIT_SUMMARY_JUDGE.md](PORTRAIT_SUMMARY_JUDGE.md) 双向逐项判定：画像→自述、自述→画像，使用supported、partial、contradicted、mixed、not_covered。自述不完整，未覆盖不等于错误；复合陈述只有全部细节被蕴含才能supported；兼容性不当作支持，宽窄或不同时间不自动当作矛盾。子代理只给标签、引用和简明理由，代码按预先固定的1/0.5/0.5/0量表计算分数。

报告有覆盖条件一致性分、全条目对齐分、覆盖率和全部关系数量，两个方向分别列出。画像数量和粒度不等，画像均分可能受此影响，必须结合共同10条自述侧指标。原始属性中不准确内容不会因为被汇总或被档案遗漏就自动被验证。画像与自述语义对应也不等于原A文本确实支持画像；本轮不是重新做主体真值审核。

辅助忠实性检查另用完整输入补查：首次主评分包仅含claim/attribute/certainty，没有原证据，因此其fidelity_checks上下文有限。补查由第三个独立Sol high子代理只看实际生成指令与完整source_details（包括A原文证据），不看档案、另一条件或旧判断，核验总结是否遵从真实指令。主一致性标签、画像和Qwen调用完全不变；原评分及有限上下文fidelity记录保留，最终报告采用完整输入补查结果。

## 复现与文件

```powershell
python -B -m isc113.identity_linkage.portrait_summary prepare
python -B -m unittest isc113.identity_linkage.test_portrait_summary -v
# QWEN_API_KEY通过进程环境变量注入，不写文件
python -B -m isc113.identity_linkage.portrait_summary generate
python -B -m isc113.identity_linkage.portrait_summary packets
# 在Codex分别分派两个gpt-6.1-sol/high子代理按协议评分
python -B -m isc113.identity_linkage.score_portrait_summary
```

- `attributes_209.json`、`deduplicated.json`：冻结原属性和字符串去重映射。
- `summary_portraits.json/.md`：总结性画像及全部原始细节；JSON额外保留证据和审核元数据。
- `direct_portraits.json/.md`：本次直接分析画像与A原文引用。
- `judge_*_packet.json`：冻结后才创建的评分输入。
- `judgment_*_sol.json`：独立Sol双向判断和摘要忠实性检查。
- `fidelity_full_source_sol.json`：无档案的完整输入忠实性补查；原有限上下文记录不覆盖。
- `per_item_scores.json`：每条画像及每条自述的标签、理由、引用和固定量表分数；未覆盖为null。
- `generation_manifest.json`、`preparation.json`：来源/代码哈希、隔离条件。
- `attempts.jsonl`：仅本次Qwen生成请求、输出、usage和失败记录，不含key。
- `REPORT.md`、`results.json`、`verification.json`：数值、限定与审计。

审计直接对照实际发出的完整payload与预期输入，核验两路都没有档案/原子命题泄漏，direct没有属性输入，原209条与上轮文件完全一致且全部206组/209记录最终保全。结果只有一个B，不能支持身份识别准确率、统计显著性或泛化优劣结论。
