"""Version comparisons with explicit failed trial, real costs, and shared-cohort inference."""
from pathlib import Path
import statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import PercentFormatter
import numpy as np

from isc112_v2.runner import ROOT, read, save
from .run import OUT


def build():
    refined=read(OUT/'refined/summary.json');retained=read(OUT/'retain_union/summary.json')
    failed=read(ROOT/'results/isc112_v22/summary.json')
    guarded=read(OUT/'guarded/summary.json');final=read(OUT/'guarded_v2/summary.json')
    base=refined['methods'][0];v2=failed['methods'][1];r=refined['methods'][1];u=retained['methods'][1];g=final['methods'][1]
    methods=[base,v2,r,u,g];labels=['原双路','证据约束双路','证据修订','全部保留','保守修订'];colors=['#0072B2','0.7','#D55E00','#56B4E9','#009E73']
    for name in ['simsun.ttc','times.ttf']:
        p=Path('C:/Windows/Fonts')/name
        if p.exists():font_manager.fontManager.addfont(str(p))
    plt.rcParams.update({'font.family':['Times New Roman','SimSun','DejaVu Sans'],'font.size':8,'axes.titlesize':9,
        'axes.labelsize':8,'xtick.labelsize':7,'ytick.labelsize':7,'axes.linewidth':.6,'axes.unicode_minus':False,
        'xtick.direction':'in','ytick.direction':'in','svg.fonttype':'path','figure.facecolor':'white'})
    fig,axes=plt.subplots(1,3,figsize=(7.7,2.85),layout='constrained');xx=np.arange(5)
    for ax,key,title in zip(axes[:2],['coverage','unsupported_fraction'],['(a) A支持参考严格原子覆盖','(b) A依据不足／未决占比']):
        stats=[m[key] for m in methods]
        ax.bar(xx,[v['estimate'] for v in stats],color=colors,edgecolor='black',lw=.4,width=.57)
        ax.errorbar(xx,[v['estimate'] for v in stats],yerr=[[v['estimate']-v['low'] for v in stats],[v['high']-v['estimate'] for v in stats]],fmt='none',ecolor='black',lw=.65,capsize=2)
        for j,v in enumerate(stats):ax.text(j,v['high']+.015,f'{v["estimate"]:.1%}',ha='center',fontsize=7)
        ax.yaxis.set_major_formatter(PercentFormatter(1,decimals=0));ax.set_ylim(0,min(1.05,max(v['high'] for v in stats)+.12));ax.set_title(title,loc='left')
    vals=[m['mean_tokens']/1000 for m in methods]
    axes[2].bar(xx,vals,color=colors,edgecolor='black',lw=.4,width=.57)
    for j,v in enumerate(vals):axes[2].text(j,v+max(vals)*.02,f'{v:.2f}',ha='center',fontsize=7)
    axes[2].set_ylim(0,max(vals)*1.17);axes[2].set_title('(c) 实际流程计算成本',loc='left');axes[2].set_ylabel('千tokens／段，含失败重试')
    for ax in axes:
        ax.set_xticks(xx,labels,rotation=25,ha='right');ax.spines['top'].set_visible(False);ax.spines['right'].set_visible(False)
        ax.grid(axis='y',lw=.35,color='0.88');ax.set_axisbelow(True)
    fg=OUT/'figures';fg.mkdir(parents=True,exist_ok=True);stem='图1_原双路与独立优化方案的112段对照'
    for ext in ['svg','png','tiff']:
        kw={'dpi':600} if ext!='svg' else {}
        if ext=='tiff':kw['pil_kwargs']={'compression':'tiff_lzw'}
        fig.savefig(fg/f'{stem}.{ext}',bbox_inches='tight',pad_inches=.035,**kw)
    plt.close(fig);save(fg/'figure_data.json',{'dialogues':112,'reference_denominator':138,'methods':methods,'labels':labels})
    def row(label,m):return f"| {label} | {m['atomic_coverage']}/138（{m['coverage']['estimate']:.1%}） | {m['one_to_one_coverage']}/138 | {m['unsupported_or_uncertain']}/{m['raw_claims']}（{m['unsupported_fraction']['estimate']:.1%}） | {m['source_contradicted']} | {m['mean_tokens']:,.1f} |"
    def effect(label,s):
        e=s['paired_gain'];z=s['without_high_density']
        return f"{label}相对原双路覆盖净变化{s['net_reference_gain']:+d}条，每段配对增量{e['mean']:+.3f}，95%区间[{e['low']:+.3f}, {e['high']:+.3f}]；改善/持平/退步{s['improved_dialogues']}/{s['tied_dialogues']}/{s['worsened_dialogues']}段。去除冻结参考最多的一段后，均值{z['mean']:+.3f}，区间[{z['low']:+.3f}, {z['high']:+.3f}]。"
    newcost=read(OUT/'revision_cost_ledger.json');v2cost=read(ROOT/'results/isc112_v2/cost_ledger.json')
    fallbacks=sum(p['outcome']=='provider_blocked_baseline_fallback' for p in read(OUT/'refined/predictions.json'))
    devcalls=len(newcost)+len(v2cost);devtokens=sum(x.get('total_tokens') or 0 for x in newcost+v2cost)
    successful=[name for name,s in [('证据修订',refined),('全部保留',retained),('保守修订',final)] if s['joint_target_met']]
    conclusion=('保守修订模式在本开发队列上达到覆盖更高且依据不足原始行比例更低的数值目标；净增益集中于一段对话，区间包含零，尚未证明稳定超越。' if final['joint_target_met'] else '最终模式仍未达到联合目标，不能宣称已超越原双路。')
    text=f'''# 原双路算法优化：112段完整自然对话对照

{conclusion}联合目标为严格原子覆盖超过100/138，且A依据不足/未决原始行比例不高于156/403。这个目标不等于整体独立事实准确率、等成本效率或封存测试泛化。

## 实现与运行

原算法三阶段为全局提取、逐句提取、统一判别。V3保留原三阶段，复用其已完成的A-only dual_on返回，再新增一次证据修订/补漏。修订器只见完整A及原始候选断言/时间/证据位置，不见B、参考、审核或错误ID；候选是可错假设。逐项修订/拒绝并补充有依据的关系事件，保留参与者、数量、时间、条件、程度、状态和原因。本地按话轮位置取原文。

模型qwen3.8-flash，temperature=0，thinking开启、预算2048，max_tokens=4096，最多4并发。新增112个逻辑请求，每个最多4次总尝试，首个结构有效返回。原三阶段缓存是历史实际调用，未重新发送；模型后端与调用时间漂移未得到同步控制。没有权重训练。

refined模式只输出修订器最终接纳项；retain_union保留原事实并加入修订结果，只合并完全相同的规范化命题/时间。后者保证不主动丢弃原信息，但原错误也可能保留。

最终guarded_v2为保守修订：保留修订事实，仅为仍被修订器标为有效B画像的原bID保留原命题副本；纠正明确“B被A描述/评价”却被归成A画像的目标冲突，要求A的最后一次直接观察陈述，且支持普通现在式和现在进行式观察谓词。规则只读A、原命题和修订器自报决策，不读参考或语义审核，不设具体对话ID。规则在检查本队列前两模式后开发，因此是数据知情的开发修正，不是独立预注册确认。原guarded简单时态版本101/138也保留。

语义覆盖按参考去重，原始行比例会受重复/重叠表述影响，不能据其下降单独声称独立事实精度提高。最终模式依据不足绝对数为{g['unsupported_or_uncertain']}条，原方法{base['unsupported_or_uncertain']}条；源文明确冲突{g['source_contradicted']}对{base['source_contradicted']}条。应同时看绝对数、覆盖和成本。

## 共同112段、共同138条参考

| 方法 | 严格原子覆盖 | 一对一覆盖 | A依据不足/未决 | 源文明确冲突 | 平均流程tokens/段 |
| --- | ---: | ---: | ---: | ---: | ---: |
{row(labels[0],base)}
{row(labels[1],v2)}
{row(labels[2],r)}
{row(labels[3],u)}
{row('保守修订（简单时态中间版）',guarded['methods'][1])}
{row(labels[4],g)}

{effect('证据修订',refined)}

{effect('保留＋修订',retained)}

{effect('最终保守修订',final)}

最终净增益仅来自test_40的水管生锈＋更换建议、龙头故障＋维修建议两项完整表达；其余111段严格覆盖持平，没有原严格命中丢失。这主要是补全原先部分表达的关系/事件，不应写成广泛新增隐藏信息推理能力。

证据修订新增严格覆盖：{', '.join(refined['added_reference_ids']) or '无'}。

证据修订丢失原覆盖：{', '.join(refined['lost_reference_ids']) or '无'}。

保留＋修订新增严格覆盖：{', '.join(retained['added_reference_ids']) or '无'}。

最终保守修订新增严格覆盖：{', '.join(final['added_reference_ids']) or '无'}；丢失原覆盖：{', '.join(final['lost_reference_ids']) or '无'}。

## 成本、失败及负结果

V2.2是未达到目标的独立尝试：81/138，不能隐去。其551次调用及1,315,072 tokens保存在results/isc112_v2/；原文引用排版和排除项重复链接的结构问题分别保留V2、V2.1及V2.2版本记录。V2.2仅离线重放修复引文绑定/结构检查，没有新API或语义标签改写。

V3新增实际{len(newcost)}次调用，{sum(x.get('total_tokens') or 0 for x in newcost):,} total tokens；首次结构有效{refined['execution']['first_attempt_valid']}/112，失败尝试{refined['execution']['invalid_attempts']}次，HTTP分布{refined['execution']['http_status_counts']}。V3可部署流程成本含原三阶段336次/661,600 tokens，加全部新增尝试，共{r['actual_calls']}次/{r['total_tokens']:,} tokens。两个V3模式共享同一新增运行，不重复计费或增加对话样本。

其中新增修订有效{112-fallbacks}段；服务内容审核400拒绝后采用显式原基线降级{fallbacks}段。被拒请求未改写输入或重复发送，降级不是修订成功，仍计入同112段及真实成本；运行规则见ISC112_V3_OPERATIONAL_AMENDMENT.md。

本次优化工作累计新增API为{devcalls}次、{devtokens:,} total tokens（含失败的V2开发试验）；原历史基线调用另列，不冒充本次重跑。不二次叠加reasoning_tokens。相对原三阶段的V3流程tokens比为{r['total_tokens']/base['total_tokens']:.2f}，尚非等tokens架构比较。

## 审核与解释

冻结参考总329条，其中138条暂定A可支持。未修改参考以配合新算法。严格原子、一对一、部分匹配、参考外新发现、依据不足、源文冲突分别记录；粗略属性不补算成完整参考。当前对话助手实际读A+B审核未复用事实，只有断言/时间及证据变体相同才复用已有审核。这仍是方法作者同源助手暂定标注，无独立人工gold。

置信区间按完整对话聚类bootstrap，3000次、种子20261101。112段已参与错误分析及版本设计，属于开发优化；需要独立审核、封存对话和预算匹配对照才能支持稳定泛化结论。若区间包含零，不能称稳定显著超越。

## 复现与产物

协议ISC112_V3_PROTOCOL.md，保守模式ISC112_V3_GUARDED_PROTOCOL.md及形态修正ISC112_V3_GUARDED_V2_PROTOCOL.md；独立代码isc112_v3/；请求requests.json；全部返回api_raw.jsonl；各模式predictions.json、semantic_review.json、dialogue_scores.csv、summary.json、final_checks.json分目录保存。figures/含矢量SVG及600dpi PNG/TIFF。原算法和原112段主结果哈希保持不变。

图1：同112段、同138条A支持参考的覆盖、依据不足/未决占比和实际流程tokens。误差线为对话聚类95%bootstrap区间。保留模式的行级占比可能受语义冗余影响，结合绝对不足断言数及严格覆盖解释；它与证据修订共享计算。
'''
    (OUT/'实验报告.md').write_text(text,encoding='utf-8')
    (fg/'图注.md').write_text(text.split('图1：')[-1],encoding='utf-8')
    save(OUT/'development_accounting.json',{'new_calls_this_optimization':devcalls,'new_tokens_this_optimization':devtokens,
        'V3_incremental_calls':len(newcost),'V3_incremental_tokens':sum(x.get('total_tokens') or 0 for x in newcost),
        'V3_pipeline_calls_including_cached_baseline':r['actual_calls'],'V3_pipeline_tokens_including_cached_baseline':r['total_tokens']})
    return {'joint_target_met_modes':successful,'report':str(OUT/'实验报告.md'),'figure':str(fg/f'{stem}.svg')}
