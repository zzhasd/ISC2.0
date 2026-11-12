"""Render a Chinese report directly from the saved stage-2 summaries."""
from pathlib import Path
import collections
import json

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/stage2'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def pct(x):return '不可估计' if x is None else f'{100*x:.1f}%'
def interval(x):return '不可估计' if x is None else f'[{100*x[0]:.1f}%, {100*x[1]:.1f}%]'

def main():
 s=read(OUT/'summary.json');rows=read(OUT/'predictions.json');gold=read(ROOT/'data/stage2/gold.json')
 a=s['conditions']['all/a_only'];full=s['conditions'].get('all/full');prior=s['conditions'].get('all/prior')
 interrupted=read(OUT/'interruption_audit.json')
 lines=['# 第二阶段：完全隐藏 B 后，A 会暴露 B 的多少属性？','',
 '日期：2026 年 10 月 31 日。模型：百炼官方北京端点 `qwen-plus`，temperature=0，关闭 thinking。', '',
 f'**本轮观察到：仅看 A，恢复了 {a["true_recoveries"]}/{a["gold_true"]} 个暂定真实属性（{pct(a["recovery_rate"])}）。其中 {a["a_supported_true_recoveries"]} 个恢复项也有事先标注的 A 侧证据。这个结果支持“隐藏 B 的话语不能保证隐藏 B 的全部属性”，不要求证明独立于普通语义的机制。**','',
 '**这些是 AI 暂定标注下的探索性结果，不是人类核验的真实个人隐私测量。** “属性”限定为事前固定的 20 项目录，不代表 B 的全部私人信息，也不表示这些属性在所有场景中都具有相同敏感程度。','',
 '## 本阶段如何修正研究重点','',
 '攻击者的输入只有 A 的话轮，B 的全部话语被删除；完整对话只用于独立的标签审读和全信息模型对照。A 仍然可以提到 B 的配偶、孩子、症状或安排，这正是研究要测量的信息来源。普通叙述也能包含同样信息、简单短语也能帮助恢复，都不否定这种单侧暴露。','',
 '不再把“超出普通语义的独立交互机制”作为本阶段成功条件。本阶段不评测因果中介或重建防御。','',
 '## 样本、目录与标注','',
 '- 新增 32 段原始测试对话，16 段随机抽取、16 段线索富集；每段两位说话者轮流作为隐藏 B，共 64 个视图。',
 '- 在抽样前排除与训练集、验证集、上一轮样本的规范化精确重复；样本内也去除精确重复。近重复和模型预训练污染仍未知。',
 '- 每次提问都使用相同的 20 项目录，不把从隐藏话轮中挑出的属性清单交给攻击者。每个 A-only 请求只包含一段对话、一个目标。',
 '- 20 项覆盖健康、婚姻、家庭、就业、财务。年龄、投票、具体伤病等未纳入；例如本轮一个样本明确暴露年龄和投票，但不能事后加入目录增加成绩。',
 '- 由本次 Codex AI 助手在模型调用前审读并固定真值、A 侧支持和证据话轮；没有独立人类标注员复核，也没有人类一致性数据。Qwen 的完整对话输出不作为 gold。',
 '- 1,280 个检查项中，暂定 true 26、false 1、unknown 1,253。随机组只有 3 个真属性，富集组有 23 个；unknown 不是 false。',
 '- 同一人的“有孩子／有儿子／有女儿”相互嵌套，不当作独立信息位。就业中的明确服务职业角色、只有预设支撑的婚姻及带玩笑语气的财务表述另做保守敏感性分析。','',
 '## 主要结果：两类抽样分开报告','',
 '| 样本组 | 可见输入 | 可用视图 | 暂定真属性 | 恢复数 | 恢复率 | 对话聚类 bootstrap 95% 区间 |',
 '| --- | --- | ---: | ---: | ---: | ---: | --- |']
 labels={'random':'随机 16 段','enriched':'富集 16 段'}
 for arm in ['random','enriched']:
  for condition,name in [('prior','无对话证据'),('a_only','仅 A'),('full','完整对话')]:
   c=s['conditions'].get(arm+'/'+condition)
   if c:lines.append(f'| {labels[arm]} | {name} | {c["views"]} | {c["gold_true"]} | {c["true_recoveries"]} | {pct(c["recovery_rate"])} | {interval(c["recovery_cluster_bootstrap"]["ci95"])} |')
 lines += ['',
 f'两组混合的 A-only 恢复为 **{a["true_recoveries"]}/{a["gold_true"]} = {pct(a["recovery_rate"])}**，区间 {interval(a["recovery_cluster_bootstrap"]["ci95"])}；这是人为组成的诊断样本结果，**不能作为全库或真实世界泄露率**。无对话条件在同一证据约束提示下提供“空证据”基线，不是从真实人群中估计的属性先验。','',
 '随机组 0/3 的 bootstrap 区间在全零观察下退化为 [0,0]，不能作为总体风险为零的置信保证；三个真标签也仅涉及就业，本目录外的年龄、政治参与等并未计入。','',
 f'{a["views_with_gold_true"]} 个视图至少有一个目录内真属性；其中 {a["views_with_true_recovery"]} 个视图至少恢复了一项。按全部 {a["views"]} 个视图计算，每个视图平均恢复 {a["recoveries_per_view"]:.3f} 项。样本里没有可确认事实的视图，不等于现实中的参与者没有这些属性。','',
 '## 恢复了哪些类型？','',
 '| 属性 | 暂定真属性数 | 仅 A 恢复 | 完整对话恢复 |',
 '| --- | ---: | ---: | ---: |']
 name_map={'headache':'头痛','fever':'发热','cold':'感冒','stomach_problem':'胃肠问题','allergy':'过敏',
 'medical_treatment':'当前治疗／处方','pregnant':'怀孕','alcohol_use':'饮酒','smokes':'吸烟','married':'已婚',
 'marriage_planned':'筹备结婚','divorce_separation':'离婚／婚姻分居','has_children':'有孩子','has_son':'有儿子','has_daughter':'有女儿',
 'unemployed':'失业','employed':'当前有工作','job_seeking':'正在求职','financial_hardship':'财务困难','personal_debt':'个人债务'}
 for attr,v in s['attributes'].items():
  ac=v.get('a_only',{});fc=v.get('full',{})
  if ac.get('gold_true',0):lines.append(f'| {name_map.get(attr,attr)} | {ac["gold_true"]} | {ac["true_recoveries"]} | {fc.get("true_recoveries","缺失")} / {fc.get("gold_true","缺失")} |')
 lines += ['',
 '未出现在表中的属性，在本轮没有可确认的正事实，因而不能估计该属性的恢复能力。职业角色推断、亲属预设等都是可用文本线索；本阶段描述其风险，不要求它们属于一种独立新机制。','',
 '## 真实恢复与未确认断言','',
 '| 输入 | 肯定断言总数 | 与暂定真值一致 | 与已知 false 冲突 | 对 unknown 真值的未确认肯定 | 对 unknown 真值的未确认否定 |',
 '| --- | ---: | ---: | ---: | ---: | ---: |']
 for cond,name in [('prior','无对话证据'),('a_only','仅 A'),('full','完整对话')]:
  c=s['conditions'].get('all/'+cond)
  if c:lines.append(f'| {name} | {c["positive_assertions"]} | {c["true_recoveries"]} | {c["positive_assertions_known_false"]} | {c["positive_assertions_unverified_truth"]} | {c["false_assertions_on_unknown_truth"]} |')
 lines += ['',
 f'A-only 的 {a["true_recoveries"]} 个真恢复中，{a["a_supported_true_recoveries"]} 个有事先标注的 A 侧充分支持，另 {a["true_recoveries_without_prelabelled_A_support"]} 个没有。后者单列为“结果碰巧符合完整对话、但可见支持不足或有标注争议”，不能自动当作可靠的证据恢复。','',
 f'事先标注 A 侧有充分证据的真属性共有 {a["a_supported_true_gold"]} 项，本次恢复 {a["a_supported_true_recoveries"]} 项。这个条件性比例衡量模型对已标证据的利用，不能替代总体恢复率。','',
 f'A-only 对事先标为证据不足的项目，产生了 {a.get("positive_assertions_without_prelabelled_A_support",0)} 次肯定、{a.get("negative_assertions_without_prelabelled_A_support",0)} 次否定。这里“证据不足”也是 AI 暂定标签；未确认断言不等于经核验的虚假事实。','',
 '目录仅有 1 个已知 false，因此不能据此可靠估计一般假阳性率。把 1,253 个 unknown 都当作负例会混淆“缺乏证据”和“事实为假”，本报告不这样计算。总体准确率也不作为主要结论。','',
 '例如全部回答 unknown 就能得到 97.9% 的三类标签准确率，却没有恢复任何真实属性。这正是本阶段改用恢复计数、证据对齐和未确认断言作为主指标的原因。','',
 '## 保守标注敏感性与全信息对照','',
 '| 范围 | 条件 | 保守子集中的真属性 | 恢复数 | 恢复率 |',
 '| --- | --- | ---: | ---: | ---: |']
 for arm in ['all','random','enriched']:
  for cond in ['a_only','full']:
   c=s['strict_sensitivity'].get(arm,{}).get(cond)
   if c:lines.append(f'| {arm} | {cond} | {c["gold_true"]} | {c["true_recoveries"]} | {pct(c["recovery_rate"])} |')
 lines += ['',
 '保守子集剔除事前标记的职业服务角色推断、酒吧饮酒语境、婚姻仅预设支撑、玩笑财务表述，不根据模型答对与否筛样本。它不能替代独立人类审核。','',
 '全信息差异只比较两种条件都实际返回的项目，不填补缺失输出：','',
 '| 范围 | 配对检查项 | 配对真属性 | 完整减 A 的恢复率差 | 95% 区间 |',
 '| --- | ---: | ---: | ---: | --- |']
 for arm,p in s['paired_comparisons'].items():
  lines.append(f'| {arm} | {p["paired_decisions"]} | {p["gold_true_in_pairs"]} | {pct(p["full_minus_A_recovery_rate"])} | {interval(p["ci95"])} |')
 lines += ['',
 '区间通过 5,000 次按抽样组分层、以原始对话为单位的 bootstrap 计算；同一对话的两种方向和所有目录项始终成组。随机组只有 3 个真标签，一些重采样没有正例，这些无定义的比率不进入分位数，实际有效次数保存在 summary.json。区间仅是固定样本下的探索性不确定性，不代表跨模型、跨数据集或真实人群的泛化。','',
 '## 调用完整性和异常处理','',
 f'- 已记录 {s["calls"]} 个请求结果；记录返回中的 token 为 **{s["token_usage"]["total_tokens"]:,}**（输入 {s["token_usage"]["prompt_tokens"]:,}、输出 {s["token_usage"]["completion_tokens"]:,}）。此外有至多 {interrupted["max_unlogged_requests"]} 个中断时可能已发送但无返回的请求；其 token 和实际账单未知，记录量不等于最终计费总量。',
 '- 本轮按保守口径最多 100 次请求尝试。出现一次 TLS EOF 传输失败，原请求原样重试；三次计划中的重复测试全部取消以守住预算。因此本阶段没有完成重复稳定性实验，不能宣称已经解决上一轮的不稳定性。',
 f'- {s["structurally_normalized_calls"]} 个返回需要结构规范化；{s["missing_target_outputs"]} 个目标输出缺失。规范化仅恢复原返回中明确出现的目标／属性／标签／证据关系，不补猜缺失项。原始 JSON 原样保留，规则在 stage2_parse.py，差异记录在 DEVIATIONS.md。',
 '- 64 个 A-only 主请求全部通过原始结构校验，不需要上述规范化；格式恢复和缺失仅影响完整对话对照。单侧恢复的主结论不依赖完整对照的结构修复。',
 f'- 当前保留的格式或传输异常记录共 {len(s["validation_errors"])} 条；逐条见 validation_errors.json。传输失败不作为模型错误答案，缺失目标也不补成 unknown。',
 '- 主攻击一条对话、一个隐藏目标一次调用；完整对照一次评估同一完整对话中的两位目标，输出结构和长度不同，因此两条件差异不能被解释为纯粹的格式因果效应。',
 '- `qwen-plus` 是滚动模型别名，未获得固定权重版本。单模型、单提示、暂定标签和稀疏真值仍限制解释；证据约束提示测量一种攻击者的可实现恢复，不是最强攻击或最大泄露上限。',
 '- 密钥只通过进程内存和标准输入传递，没有写入项目文件。数据与请求文件保持冻结哈希；程序检查 A-only 输入没有 B 话语、隐藏话轮占位符或从 B 派生的候选清单。','',
 '## 可支持的论文表述','',
 f'> 在固定属性目录和完全移除目标说话者话语的条件下，我们观察到 Qwen 仍可从对话对象的话轮恢复部分对话内个人属性。本轮诊断样本中的恢复为 {a["true_recoveries"]}/{a["gold_true"]}，其中 {a["a_supported_true_recoveries"]} 项也有预先标注的可见证据。该比例依赖采样、目录、模型和暂定标注，不代表真实世界整体隐私泄露率。','',
 '不宜声称“B 的全部隐私有某一固定百分比被泄露”，也不宜将没有恢复的属性解释为受到保护。本轮的有效推进是把**完整真值、可见证据、真实恢复和未确认断言**分开，并移除按隐藏内容选择提问属性这一混杂。','',
 '下一步应优先由两名独立人类标注员审核事实和持有者，扩展去重自然对话，补足每类真事实与明确否定例，再在更充分的重复调用和另一模型上检验。当前 20 项目录漏掉年龄和政治参与等信息，目录扩展应在新的保留样本前确定。无需先追求“超出普通语义”的独立机制，才能继续这条风险测量路线。','',
 '## 文件与复现','',
 '- `summary.json`：分组计数、聚类区间、保守子集、配对比较及逐属性结果。',
 '- `predictions.csv` / `predictions.json`：逐目标、逐属性结果。',
 '- `requests.json` / `api_raw.jsonl`：固定公开请求和未改写的原始返回。',
 '- `annotation_review.md` / `annotation_review.csv`：AI 标签证据及留空的人类审核栏。',
 '- `data_audit.json` / `final_checks.json`：样本边界、去重、哈希和结果一致性检查。',
 '- `../../data/stage2/`：固定样本、目录、暂定 gold 和哈希。',
 '- `../../STAGE2_PROTOCOL.md` 与 `DEVIATIONS.md`：原方案和运行偏差。','',
 '无 API 的结果重算：','',
 '```powershell','python experiments/stage2_audit.py','python experiments/stage2_analyze.py','python experiments/stage2_plot.py','python experiments/stage2_report.py','```','',
 '数据来源：[DailyDialog 原论文](https://aclanthology.org/I17-1099/)与 [ACL 原始附件](https://aclanthology.org/attachments/I17-1099.Datasets.zip)。许可元数据见[维护版本数据卡](https://huggingface.co/datasets/ConvLab/dailydialog)：CC BY-NC-SA 4.0；保留署名、非商业和相同方式共享条件。','',
 '![第二阶段结果](D:/桌面/ISC2.0/results/stage2/stage2_results.png)','']
 (OUT/'第二阶段实验报告.md').write_text('\n'.join(lines),encoding='utf-8')
 print('Report written:',OUT/'第二阶段实验报告.md')

if __name__=='__main__':main()
