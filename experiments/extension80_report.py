"""Transparent cohort-separated replication report and exported statistical figure."""
import csv
import json
import statistics
from pathlib import Path
from isc4_open import ROOT,read,save
from isc4_analyze import bootstrap
from extension80 import DATA,OUT

LABELS={'direct_off':'直接＋关','direct_on':'直接＋开','dual_off':'两路＋关','dual_on':'两路＋开'}
EFFECTS={'thinking_in_direct':'直接：开−关','thinking_in_dual':'两路：开−关','pipeline_without_thinking':'关：两路−直接','pipeline_with_thinking':'开：两路−直接','interaction':'交互效应'}

def percent(n,d):return f'{n}/{d}（{n/d:.1%}）' if d else f'{n}/0（无分母）'
def ci(v):return f"{v['mean']:+.3f} [{v['low']:+.3f}, {v['high']:+.3f}]" if v else '无有效样本'

def main():
    bases={'旧32':ROOT/'results','新80':OUT,'合并112':ROOT/'results/merged112'}
    summaries={c:{k:read(p/k/'summary.json') for k in ['isc4','isc7']} for c,p in bases.items()}
    lines=['# 固定配置扩样：三个主实验的新增与合并结果','',
        '2026-11-02，Asia/Shanghai。新增80段未参加既有实验的DailyDialog完整自然对话，三个主实验复用同一批数据。合并后去重为112段，不是336段。实验一的完整A是实验二的最后前缀，不额外调用。','',
        '## 哪些结论得到复现','',
        '- **逐前缀的平均增长得到复现，但不是逐段单调。** 新样本首次A到完整A增加0.487个有依据属性/段，95%区间[0.250,0.816]；合并增加0.491个，[0.283,0.745]。新样本9段、合并11段有当下集合下降。',
        '- **双路＋thinking仍覆盖最高，但95.3%的绝对覆盖没有复现。** 新样本四组共同有效73段，直接关/直接开/双路关/双路开分别覆盖29/72、37/72、33/72、43/72，即40.3%、51.4%、45.8%、59.7%。合并104段为49.6%、60.9%、57.4%、73.0%。不能将旧95.3%推广到新自然对话。',
        '- **两个局部收益在新样本和合并结果中方向一致且区间排除零：** 双路中开启thinking，以及开启thinking时增加双路。排除新样本各自影响最大的一段后，区间仍排除零。直接流程单独开thinking、关闭thinking时单独增加双路，区间仍触及或跨零。',
        '- **更高覆盖仍伴随可靠性和成本代价。** 新样本直接关与双路开分别输出88/230条断言，无充分A依据或未决25/91条（28.4%/39.6%），平均tokens约相差8.0倍。两因素交互的新样本及合并区间仍跨零，没有稳定超加性的证据。',
        '- **实验一仍是有限恢复，绝对比例下降。** 新样本严格完整参考覆盖18.1%，合并20.4%，旧样本26.1%。因可见信息不对称及抽样构成不同，不能把这个差额解释成模型能力下降。','',
        '## 数据、参考与执行','',
        '新增样本从排除既有样本后的804段test候选中，以固定种子20261102随机抽取80段。不按长度或隐私密度筛选，不按结果追加样本。保留自然起止；原文标准化重复及近重复诊断均保存。新增80段每段2～18条双方发言、1～9条A发言，A均值3.825条。旧32段A均值4.75条。新增样本为随机样本，旧32段包含random/enriched抽样，因此合并平均值不能直接代表全部DailyDialog。另一个48段方法实验没有计入本报告的样本数和调用总数，其新增16段同样被排除在此次新样本之外。','',
        '新增参考由当前对话模型直接逐段阅读A+B、推理B信息，在查看新增Qwen输出之前冻结：229条B信息、94条暂定A可支持信息。加上旧参考，112段共329条、其中138条暂定A可支持。参考与复核仍为同一助手作出的AI暂定标注，尚无独立人工金标准；没有额外GPT API调用，也没有虚构GPT调用tokens。','',
        '所有新Qwen请求逐字复用旧提示和参数：qwen3.8-flash、temperature=0、max_tokens=4096、最多4并发。实验一二关闭thinking；实验三on组每次thinking_budget=2048。双路提取互不见对方答案，判别仅见A与合并候选。隐藏B和参考信息不进入任何Qwen请求。','']
    audits=read(OUT/'isc7/execution_audit.json');raw4=[json.loads(s) for s in (OUT/'isc4/baseline/api_raw.jsonl').read_text(encoding='utf-8').splitlines()]
    actualnew=len(raw4)+len(audits);oldcalls=408
    lines += [f'新增实验一二计划306个非空前缀、实际尝试{len(raw4)}次；复用旧共用空输入，不额外请求。实验三计划最多640次、实际{len(audits)}次。新增实际调用共{actualnew}次，连同旧408次累计{oldcalls+actualnew}次。', '',
        '出现的HTTP错误、截断和结构失败均留档为缺失，不修复后静默重跑，不把失败当成零事实。一次429限流后仅恢复从未尝试的请求，并将新请求间隔设为2.5秒；这改变调度速度，不改变推理配置。', '',
        '## 实验一：完整A恢复B信息','',
        '| 队列 | 完整A有效 | 完整参考严格覆盖 | 严格且有A依据 | A支持子集严格恢复 | 无A依据/未决断言 |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for c,s in summaries.items():
        x=s['isc4'];nr=x['valid_cohort_full_reference_facts'];na=x['valid_cohort_A_supported_reference_facts']
        lines.append(f"| {c} | {x['valid_full_dialogues']}/{x['planned_dialogues']} | {percent(x['exact_reference_matches'],nr)} | {percent(x['grounded_exact_reference_matches'],nr)} | {percent(x['grounded_exact_reference_matches'],na)} | {x['raw_A_ungrounded_or_uncertain_claims']}/{x['full_raw_claims']} |")
    lines += ['', '采用旧实验一的一对一严格语义匹配；较粗部分匹配、参考外新发现、范围外、未核验和明确矛盾分别保存。参考按既有属性/事件粒度记录，多值属性与限定条件保持合并；粗细粒度及拆行方式会影响严格匹配。A支持子集按冻结的暂定标注定义，未据Qwen输出扩充主分母。未匹配不能一律叫错误。GPT看A+B而Qwen只看A，所以差额混合了信息可见性和推理能力，不是纯模型能力差距。', '',
        '## 实验二：逐前缀累积','', '| 队列 | 全路径有效 | 首个A→完整A：有依据属性/段差值及95%区间 | 出现当下集合下降的路径 |', '| --- | ---: | --- | ---: |']
    for c,s in summaries.items():
        x=s['isc4'];lines.append(f"| {c} | {x['complete_prefix_paths']}/{x['planned_dialogues']} | {ci(x['first_to_full_grounded_attribute_delta'])} | {x['paths_with_declines']} |")
    lines += ['', '每个整数前缀独立提取，不继承前一次输出。主曲线只用全部前缀有效的完整路径；另外输出按相同A总轮数K的固定群组曲线。历史并集天然单调，只有当下集合用于检查撤回和下降。属性曲线包含有依据的部分恢复，因此不等同实验一的严格具体事实覆盖。', '',
        '## 实验三：四组配对比较','',
        '| 队列 | 组别 | 各组有效/计划 | 共同有效 | 严格原子覆盖A支持参考 | 原始断言 | 无A依据/未决 | 范围外 | 源文冲突 |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for c,s in summaries.items():
        for m in s['isc7']['methods']:
            lines.append(f"| {c} | {LABELS[m['arm']]} | {m['valid']}/{m['planned']} | {m['common']} | {percent(m['atomic_coverage'],m['A_reference_count'])} | {m['raw_claims']} | {m['A_unsupported_or_uncertain']} | {m['out_of_scope']} | {m['source_contradicted']} |")
    lines += ['', '每个队列内四组分母完全相同，使用四组共同有效对话。原子覆盖对有依据的独立子原子去重，同时保留旧一对一口径。不同问题列可能重叠，不能相加。无A依据不等于隐藏源文必假；复合句有正确子原子也可能包含额外无依据断言。', '',
        '| 对比 | 旧32：均值与95%区间 | 新80：均值与95%区间 | 合并112：均值与95%区间 |', '| --- | --- | --- | --- |']
    for idx,name in enumerate(EFFECTS):
        lines.append('| '+EFFECTS[name]+' | '+' | '.join(ci(s['isc7']['effects'][idx]['per_dialogue']) for s in summaries.values())+' |')
    lines += ['', '单位为每段净增加的严格参考原子。按对话聚类bootstrap，3000次固定种子；不把前缀或断言当独立样本，没有确认性多重检验。交互区间跨零不能解释为稳定超加性。', '',
        '## 全体计划队列的缺失影响范围','',
        '共同有效分析可能排除高信息密度对话，因此另报全体计划队列的参考覆盖界限：下界只累计已返回有效结果中的严格覆盖，上界再加上缺失对话全部暂定A支持参考。它是未知缺失结果的数学范围，不是把失败当零事实，也不是置信区间。','',
        '| 队列 | 组别 | 已观察覆盖～缺失可能上界 | 全体A支持参考分母 | 缺失对话 |',
        '| --- | --- | ---: | ---: | --- |']
    bounds={}
    for c,base in bases.items():
        scores=read(base/'isc7/dialogue_scores.json');bounds[c]=[]
        for arm in LABELS:
            rr=[r for r in scores if r['arm']==arm];obs=sum(r['atomic_coverage'] for r in rr if r['valid']);missing=[r for r in rr if not r['valid']]
            upper=obs+sum(r['A_reference_count'] for r in missing);den=sum(r['A_reference_count'] for r in rr)
            bounds[c].append({'arm':arm,'observed':obs,'missing_upper':upper,'all_planned_A_reference_count':den,'missing_ids':[r['dialogue_id'] for r in missing]})
            lines.append(f"| {c} | {LABELS[arm]} | {obs}～{upper} | {den} | {', '.join(r['dialogue_id'] for r in missing) or '无'} |")
    lines += ['',
        '## 计算成本与可靠性','', '| 队列 | 组别 | 实际调用 | 实际total tokens | 平均tokens/共同有效段 | 平均思考tokens |', '| --- | --- | ---: | ---: | ---: | ---: |']
    for c,s in summaries.items():
        for m in s['isc7']['methods']:
            lines.append(f"| {c} | {LABELS[m['arm']]} | {m['actual_calls_all_planned']} | {m['total_tokens_all_planned']} | {m['mean_total_tokens']:.1f} | {m['mean_reasoning_tokens']:.1f} |")
    lines += ['', '思考tokens包含在completion和total tokens内，不二次相加。流程和thinking都增加计算预算，因此不是等token的纯结构比较。返回模型名、思考文本与usage、阶段耗时和关键路径估算均保留；新旧不同日期的同名云模型可能存在后端变化。', '',
        '## 稳定性判断','', '结论应优先依据新80段的独立方向和区间，再参考合并112段；不能用合并后的显著性掩盖新样本不支持的效应。正式判断及单个高影响对话敏感性见stability.json。', '',
        '当前规模比32段更充分，但新样本仍来自同一脚本会话语料，参考与复核并非独立人工标注，且一次确定性运行不能估计模型采样或云端版本变化。固定参考中的A支持标注可能漏掉合理的语用支持；新增正确发现单列，未事后扩充主分母。审核中另有6个断言组合涉及3条冻结参考（test_392_resume_view、test_40_call、test_621_car），复核认为有合理A侧支持而原标注未列入A支持子集，留档reference_support_disagreements.json，供独立人工审核；主分析分母保持冻结值。', '',
        '语义质检曾纠正“无A证据＝被源文否定”的混淆，全部修改留档于semantic_source_status_QA.json；严格覆盖和A支持判断未因此改变。另在计算实验三统计前，修正一条明确present-ending时间标签的匹配，留档于semantic_temporal_QA.json。独立人工复核用的不带模型输出的A+B源文、A-only空白材料另存human_review，尚未获得人工标注。','',
        '所有旧data/isc4、data/isc7、results/isc4、results/isc7文件均按原哈希核对保留。新增原始请求、响应、逐项审核、失败和分析位于results/extension80；合并视图位于results/merged112。协议见EXTENSION_PROTOCOL.md。']
    output=ROOT/'results/merged112/扩样实验报告.md';output.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    neweff=summaries['新80']['isc7']['effects'];mergeeff=summaries['合并112']['isc7']['effects']
    stability={'new_prefix_delta':summaries['新80']['isc4']['first_to_full_grounded_attribute_delta'],
        'factorial_effects':[],'all_planned_missing_bounds':bounds,'actual_new_calls':actualnew,'actual_total_calls':oldcalls+actualnew}
    for olde,ne,me in zip(summaries['旧32']['isc7']['effects'],neweff,mergeeff):
        vals=ne['dialogue_differences'];ordered=sorted(vals,key=lambda d:abs(vals[d]),reverse=True)
        lo=[v for d,v in vals.items() if d!=ordered[0]] if ordered else []
        stability['factorial_effects'].append({'name':ne['name'],'old':olde['per_dialogue'],'new':ne['per_dialogue'],'merged':me['per_dialogue'],
            'same_mean_direction_as_old':ne['per_dialogue']['mean']*olde['per_dialogue']['mean']>0,
            'new_CI_excludes_zero':ne['per_dialogue']['low']>0 or ne['per_dialogue']['high']<0,
            'highest_absolute_influence_new_dialogue':ordered[0] if ordered else None,'without_that_dialogue':bootstrap(lo)})
    save(ROOT/'results/merged112/stability.json',stability)
    p4=summaries['新80']['isc4']
    prefix_text=f'''# 新80段：完整A与逐前缀结果

2026-11-02，当前对话模型先读A+B并冻结参考，Qwen仅看A。

- 新增80段完整自然对话，共306个非空A前缀；302次校验有效，完整A有效79段，完整前缀路径76段。
- 有效完整A队列：完整参考221条、A可支持参考91条。严格匹配40条，均暂定有A支持；完整覆盖18.1%，A支持子集恢复44.0%。
- 原始确定断言93条，其中21条缺乏充分A依据或未决。完整源文明确冲突{p4['raw_known_contradicted_claims']}条；这不等于全部无A依据的断言都是假的。
- 首次A到完整A平均增加0.487个有依据属性，95%区间[0.250,0.816]；9段路径出现当下集合下降。

完整参考共229条、94条暂定有A支持。完整A无效的test_40对应8条完整参考、3条A支持参考，因此有效分母为221/91。全部旧结果保留。AI暂定参考尚非独立人工gold，输入不对称不是纯模型能力比较。完整合并报告见results/merged112/扩样实验报告.md。
'''
    (OUT/'isc4/实验报告.md').write_text(prefix_text,encoding='utf-8')
    # Compact standalone scientific plot, not a product UI.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(1,2,figsize=(12,4.6),layout='constrained')
    for j,(c,s) in enumerate(summaries.items()):
        color=['#2979b9','#ed7d18','#2d9e3a'][j]
        ms=s['isc7']['methods'];axs[0].plot(range(4),[m['atomic_coverage']/m['A_reference_count'] for m in ms],marker='o',label=c,color=color)
        for i,e in enumerate(s['isc7']['effects']):
            v=e['per_dialogue'];y=i+(j-1)*.2
            axs[1].errorbar(v['mean'],y,xerr=[[v['mean']-v['low']],[v['high']-v['mean']]],fmt='o',capsize=2,label=c if i==0 else None,color=color)
    axs[0].set_xticks(range(4),['Direct off','Direct on','Dual off','Dual on']);axs[0].set(ylabel='Grounded atomic reference coverage',ylim=(0,1.05),title='Same settings, separate cohorts')
    axs[1].set_yticks(range(5),['Thinking / direct','Thinking / dual','Pipeline / off','Pipeline / on','Interaction']);axs[1].axvline(0,color='gray',ls='--');axs[1].set(xlabel='Reference atoms per dialogue; bootstrap 95% CI')
    # ASCII labels avoid assuming Chinese fonts are installed.
    for ax in axs:
        handles,_=ax.get_legend_handles_labels()
        if ax is axs[1]:ax.legend(handles,['Old 32','New 80','Merged 112'],loc='lower center',bbox_to_anchor=(.5,1.01),ncol=3,fontsize=8)
        else:ax.legend(handles,['Old 32','New 80','Merged 112'])
        ax.grid(alpha=.2)
    fig.savefig(ROOT/'results/merged112/replication.png',dpi=180);plt.close(fig)
    print(stability)

if __name__=='__main__':main()
