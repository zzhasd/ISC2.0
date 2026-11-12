"""Journal-sized matplotlib figures from recovered, audited experimental scores."""
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import PercentFormatter
from isc4_open import ROOT,read,save

BASE=ROOT/'results/recovery112'
OUT=BASE/'paper_figures'
COHORTS=[('旧32段',BASE/'old32','#0072B2','o','-'),('新80段',BASE/'new80','#D55E00','s','--'),('合并112段',BASE,'#009E73','^','-.')]
ARMS=['direct_off','direct_on','dual_off','dual_on']
ARM_LABELS=['直接／关','直接／开','双路／关','双路／开']

def setup():
    for name in ['simsun.ttc','times.ttf']:
        font_manager.fontManager.addfont('C:/Windows/Fonts/'+name)
    plt.rcParams.update({'font.family':['Times New Roman','SimSun'],'font.size':8,'axes.labelsize':8,
        'axes.titlesize':9,'axes.titleweight':'normal','axes.linewidth':.6,'lines.linewidth':1.1,
        'xtick.labelsize':7.5,'ytick.labelsize':7.5,'legend.fontsize':7,'legend.frameon':False,
        'xtick.direction':'in','ytick.direction':'in','xtick.major.width':.5,'ytick.major.width':.5,
        'axes.unicode_minus':False,'figure.facecolor':'white','axes.facecolor':'white','savefig.facecolor':'white',
        'svg.fonttype':'path','hatch.linewidth':.4})

def clean(ax):
    ax.spines['top'].set_visible(False);ax.spines['right'].set_visible(False)
    ax.grid(axis='y',lw=.35,color='0.88');ax.set_axisbelow(True)

def export(fig,name):
    fig.savefig(OUT/(name+'.svg'),bbox_inches='tight',pad_inches=.035)
    fig.savefig(OUT/(name+'.png'),dpi=600,bbox_inches='tight',pad_inches=.035)
    fig.savefig(OUT/(name+'.tiff'),dpi=600,bbox_inches='tight',pad_inches=.035,pil_kwargs={'compression':'tiff_lzw'})
    plt.close(fig)

def load():
    return [{'name':n,'base':p,'color':c,'marker':m,'ls':ls,'s4':read(p/'isc4/summary.json'),
        's7':read(p/'isc7/summary.json'),'prefix':read(p/'isc4/prefix_analysis.json')} for n,p,c,m,ls in COHORTS]

def aligned(d):
    a={r['dialogue_id']:r for r in csv.DictReader((d['base']/'isc4/full_dialogue_scores.csv').open(encoding='utf-8-sig')) if r['valid']=='True'}
    b={r['dialogue_id']:r for r in read(d['base']/'isc7/dialogue_scores.json') if r['arm']=='direct_off' and r['valid']}
    ids=sorted(set(a)&set(d['s7']['common_ids']));den=sum(int(a[i]['A_reference_available']) for i in ids)
    return {'cohort':d['name'],'n':len(ids),'denominator':den,
        'E1':sum(int(a[i]['grounded_exact_reference_matches']) for i in ids),
        'E3_direct_off':sum(b[i]['legacy_strict'] for i in ids)}

def main_figure(data):
    fig,axs=plt.subplots(2,2,figsize=(7.2,5.75),layout='constrained')
    x=np.arange(3);w=.30;ax=axs[0,0]
    full=[d['s4']['strict_full_reference_coverage'] for d in data]
    support=[d['s4']['A_supported_subset_exact_recovery'] for d in data]
    ax.bar(x-w/2,full,w,color='0.72',edgecolor='black',lw=.4,label='完整B参考覆盖')
    ax.bar(x+w/2,support,w,color='0.25',edgecolor='black',lw=.4,hatch='//',label='A支持子集恢复')
    for offset,ys in [(-w/2,full),(w/2,support)]:
        for xx,y in zip(x+offset,ys):ax.text(xx,y+.012,f'{y:.1%}',ha='center',fontsize=7)
    ax.set_xticks(x,[d['name'] for d in data]);ax.set_ylim(0,.72);ax.yaxis.set_major_formatter(PercentFormatter(1,decimals=0))
    ax.set_ylabel('严格覆盖／恢复率');ax.set_title('(a) 实验一：完整A恢复',loc='left');ax.legend(loc='upper left');clean(ax)
    ax=axs[0,1]
    for d in data:
        rr=[r for r in d['prefix']['normalized'] if r['measure']=='grounded_attribute_count_including_partial']
        ax.plot([r['fraction'] for r in rr],[r['mean'] for r in rr],marker=d['marker'],ls=d['ls'],color=d['color'],ms=3.3,label=d['name'])
        if d['name']=='合并112段':ax.fill_between([r['fraction'] for r in rr],[r['low'] for r in rr],[r['high'] for r in rr],color=d['color'],alpha=.12,lw=0)
    ax.set_title('(b) 实验二：逐前缀累积',loc='left');ax.set_xlabel('已观察A发言的归一化进度');ax.set_ylabel('当下有依据属性数／段')
    ax.set_xticks([0,.25,.5,.75,1]);ax.xaxis.set_major_formatter(PercentFormatter(1,decimals=0));ax.set_ylim(bottom=0);ax.legend(loc='upper left');clean(ax)
    ax=axs[1,0];x=np.arange(4);w=.23
    for j,d in enumerate(data):
        ms=d['s7']['methods'];ys=[m['atomic_coverage']/m['A_reference_count'] for m in ms]
        positions=x+(j-1)*w
        ax.bar(positions,ys,w*.94,color=d['color'],edgecolor='black',lw=.35,hatch=['//','..',''][j],label=d['name'])
        for xx,y in zip(positions,ys):ax.text(xx,y+.013,f'{100*y:.1f}',ha='center',fontsize=6.3)
    ax.set_xticks(x,ARM_LABELS);ax.set_ylim(0,1.15);ax.yaxis.set_major_formatter(PercentFormatter(1,decimals=0))
    ax.set_title('(c) 实验三：四组配对对照',loc='left');ax.set_ylabel('A支持参考严格原子覆盖率');ax.set_xlabel('流程／thinking状态');ax.legend(loc='upper left',ncol=3,columnspacing=.8,handlelength=1.2);clean(ax)
    ax=axs[1,1];effects=data[-1]['s7']['effects'];ys=np.arange(5)
    for i,e in enumerate(effects):
        v=e['per_dialogue'];ax.errorbar(v['mean'],i,xerr=[[v['mean']-v['low']],[v['high']-v['mean']]],fmt='o',ms=3.3,color='black',lw=.85,capsize=2)
    ax.set_yticks(ys,['直接中：开−关','双路中：开−关','关时：双路−直接','开时：双路−直接','交互效应']);ax.invert_yaxis();ax.axvline(0,color='0.5',lw=.7,ls='--')
    ax.set_title('(d) 实验三：合并队列的配对效应',loc='left');ax.set_xlabel('严格参考原子增量／段（95%区间）')
    ax.spines['top'].set_visible(False);ax.spines['right'].set_visible(False)
    export(fig,'图1_三个主实验_论文分面图')

def supplement(data):
    fig,axs=plt.subplots(1,2,figsize=(7.2,2.75),layout='constrained')
    ax=axs[0];alignment=[aligned(d) for d in data];x=np.arange(3);w=.31
    for offset,field,color,hatch,label in [(-w/2,'E1','0.72','','实验一'),(w/2,'E3_direct_off','0.25','//','实验三：直接＋关')]:
        vals=[a[field]/a['denominator'] for a in alignment];ax.bar(x+offset,vals,w,color=color,edgecolor='black',lw=.4,hatch=hatch,label=label)
        for xx,y in zip(x+offset,vals):ax.text(xx,y+.012,f'{y:.1%}',ha='center',fontsize=7)
    ax.set_xticks(x,[d['name'] for d in data]);ax.set_ylim(0,.87);ax.yaxis.set_major_formatter(PercentFormatter(1,decimals=0))
    ax.set_title('(a) 同队列、同分母、同匹配规则',loc='left');ax.set_ylabel('A支持子集严格恢复率');ax.legend(loc='upper left');clean(ax)
    ax=axs[1];methods=data[-1]['s7']['methods'];baseline=methods[0]['mean_total_tokens'];colors=['#0072B2','#56B4E9','#D55E00','#009E73'];markers=['o','s','D','^']
    for m,label,c,mk in zip(methods,ARM_LABELS,colors,markers):
        xx=m['A_unsupported_or_uncertain']/m['raw_claims'];yy=m['atomic_coverage']/m['A_reference_count']
        ax.scatter(xx,yy,s=28,marker=mk,color=c,edgecolor='black',lw=.4,label=label)
        ax.annotate(f'{m["mean_total_tokens"]/baseline:.1f}×',xy=(xx,yy),xytext=(5,3),textcoords='offset points',fontsize=7)
    ax.set_title('(b) 合并队列的覆盖、依据与成本',loc='left');ax.set_xlabel('无充分A依据／未决断言比例');ax.set_ylabel('A支持参考严格覆盖率')
    ax.set_xlim(.15,.65);ax.set_ylim(.35,.9);ax.xaxis.set_major_formatter(PercentFormatter(1,decimals=0));ax.yaxis.set_major_formatter(PercentFormatter(1,decimals=0));ax.legend(loc='lower right',ncol=2,columnspacing=.6,handletextpad=.3);clean(ax)
    export(fig,'图2_口径对齐与可靠性成本')
    return alignment

def main():
    setup();OUT.mkdir(parents=True,exist_ok=True);data=load();main_figure(data);alignment=supplement(data)
    serial=json.loads(json.dumps(data,default=str,ensure_ascii=False))
    save(OUT/'figure_data.json',{'cohorts':serial,'aligned_baselines':alignment,'source':'recovery112 first-valid merged results','dpi':600})
    n4=[d['s4']['valid_full_dialogues'] for d in data];nprefix=[d['s4']['complete_prefix_paths'] for d in data];n7=[len(d['s7']['common_ids']) for d in data]
    text=f'''# 论文图及图注

图1 三个主实验在旧32段、新80段及合并112段完整自然对话上的结果。所有图来自原配置缺失补跑后的合并视图。
(a) 实验一的完整B参考覆盖率与暂定A支持子集恢复率；两类柱分母不同，不应互换解释。有效完整A对话数依次为{n4}。
(b) 当下有依据属性数随A前缀进度的变化；完整有效路径数依次为{nprefix}。阴影仅表示合并队列按对话聚类bootstrap 3000次的95%区间。归一化进度p取k=ceil(pK)，0为共用空输入。属性曲线含有依据的部分恢复，不等于具体事实严格覆盖；平均上升不表示逐段单调。
(c) 实验三四配置在每个队列内使用相同的四组共同有效对话数，依次为{n7}；分母为这些对话的冻结A支持参考。柱上数字为百分比。
(d) 合并队列的配对严格原子覆盖增量及对话聚类bootstrap 95%区间。交互定义为(双路开−双路关)−(直接开−直接关)。区间为探索性，未作多重比较校正。

图2 (a) 实验一与实验三直接关在共同有效对话、同一A支持参考分母及有依据的一对一严格匹配下的比较。数据见figure_data.json的aligned_baselines。(b) 合并队列各配置的严格覆盖与无充分A依据/未决输出比例；点旁倍数表示含原失败及本轮补跑的平均total tokens相对于直接关的倍数。没有A依据不等于源文必假；更高覆盖不等于更高事实准确率。

合并队列包含旧、新两个队列，三者不相互独立。全部参考为当前助手作出的AI暂定标注，尚非独立人工金标准。补跑采用首个结构有效响应，图中有效率属于补跑后结果，不是单次原生成功率。推理提示、模型参数、冻结参考与原结构校验未改变。

文件：SVG为文字转路径的矢量图，避免跨机缺字体；PNG与LZW压缩TIFF为600 dpi。图1按7.2英寸双栏宽、图2同宽绘制。Python源码为experiments/paper_figures112.py。
'''
    (OUT/'论文图注.md').write_text(text,encoding='utf-8')
    print('Paper figures exported.')

if __name__=='__main__':main()
