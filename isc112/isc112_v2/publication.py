"""Paper-oriented comparison figure and result-derived Chinese report."""
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import PercentFormatter
import numpy as np

from .runner import OUT, ROOT, read, save


def build():
    s = read(OUT / 'summary.json'); old, new = s['methods']
    methods = read(ROOT / 'results/isc112/e3/summary.json')['methods']
    labels = ['直接／关', '直接／开', '双路／关', '原双路／开', '优化双路／开']
    methods = [{**m, 'mean_tokens': m['tokens_per_dialogue']['mean']} for m in methods] + [new]
    colors = ['0.8', '0.7', '0.6', '#0072B2', '#D55E00']
    for name in ['simsun.ttc', 'times.ttf']:
        p = Path('C:/Windows/Fonts') / name
        if p.exists(): font_manager.fontManager.addfont(str(p))
    plt.rcParams.update({'font.family': ['Times New Roman', 'SimSun', 'DejaVu Sans'], 'font.size': 8,
        'axes.titlesize': 9, 'axes.labelsize': 8, 'xtick.labelsize': 7, 'ytick.labelsize': 7,
        'legend.fontsize': 7, 'axes.linewidth': .6, 'axes.unicode_minus': False,
        'xtick.direction': 'in', 'ytick.direction': 'in', 'svg.fonttype': 'path', 'figure.facecolor': 'white'})
    fig, axes = plt.subplots(1, 3, figsize=(7.5, 2.65), layout='constrained')
    x = np.arange(5)
    for ax, key, title in zip(axes[:2], ['coverage', 'unsupported_fraction'], ['(a) A支持参考严格原子覆盖', '(b) A依据不足／未决断言占比']):
        vv = [m[key] for m in methods]
        ax.bar(x, [v['estimate'] for v in vv], color=colors, edgecolor='black', linewidth=.4, width=.6)
        ax.errorbar(x, [v['estimate'] for v in vv],
            yerr=[[v['estimate']-v['low'] for v in vv], [v['high']-v['estimate'] for v in vv]],
            fmt='none', color='black', linewidth=.6, capsize=2)
        for j, v in enumerate(vv): ax.text(j, v['high'] + .015, f'{v["estimate"]:.1%}', ha='center', fontsize=7)
        ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0)); ax.set_ylim(0, min(1.05, max(v['high'] for v in vv) + .12))
        ax.set_title(title, loc='left')
    vals = [m['mean_tokens'] / 1000 for m in methods]
    axes[2].bar(x, vals, color=colors, edgecolor='black', linewidth=.4, width=.6)
    for j, v in enumerate(vals): axes[2].text(j, v + max(vals)*.02, f'{v:.2f}', ha='center', fontsize=7)
    axes[2].set_ylim(0, max(vals)*1.18); axes[2].set_ylabel('千tokens／段（含失败与重试）'); axes[2].set_title('(c) 实际平均计算成本', loc='left')
    for ax in axes:
        ax.set_xticks(x, labels, rotation=35, ha='right'); ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
        ax.grid(axis='y', color='0.88', lw=.35); ax.set_axisbelow(True)
    fg = OUT / 'figures'; fg.mkdir(parents=True, exist_ok=True)
    stem = '图1_优化双路与原四组的统一112段比较'
    for ext in ['svg', 'png', 'tiff']:
        kw = {'dpi': 600} if ext != 'svg' else {}
        if ext == 'tiff': kw['pil_kwargs'] = {'compression': 'tiff_lzw'}
        fig.savefig(fg / f'{stem}.{ext}', bbox_inches='tight', pad_inches=.035, **kw)
    plt.close(fig); save(fg / 'figure_data.json', {'methods': methods, 'dialogues': 112, 'reference_denominator': 138})
    paired = s['paired_gain']; sens = s['without_high_density']
    met = '达到' if s['joint_target_met'] else '未达到'
    ci = '区间下界大于零' if paired['low'] > 0 else '区间包含零，不能据此称稳定超越'
    def table(m):
        return f"| {m['method']} | {m['atomic_coverage']}/138（{m['coverage']['estimate']:.1%}） | {m['one_to_one_coverage']}/138 | {m['unsupported_or_uncertain']}/{m['raw_claims']}（{m['unsupported_fraction']['estimate']:.1%}） | {m['source_contradicted']} | {m['mean_tokens']:,.1f} |"
    version = globals().get('VERSION', '2')
    repair = ('当前V2.2对所有响应统一执行引文排版绑定，并允许两条均不接纳的候选保留重复关系；不改写命题、标签、checks或重复链接，不将被排除项提升为事实。原V2严格校验完整结果102/112，V2.1仅引文绑定110/112，V2.2结构修正112/112。各版本保留，修正属于故障后的开发调整。' if version == '2.2' else '')
    text = f'''# 证据约束双路V{version}：同112段开发对照

新算法{met}预设的“严格原子覆盖超过100/138，且A依据不足/未决比例不高于156/403”联合目标。本结论由实际API输出及逐条审核得到，不是预先保证。原算法、参考、112段主结果均保留。

{repair}

## 方法

两路独立读取完整A：全局关系/状态与逐句细节候选，候选明确保存时间、数量、程度、条件和模态。统一审核按主体、内容和限定逐项核对原文锚点，修复为A支持的命题；去重区分等价、强弱与冲突；允许依据A新增遗漏信息。引用字面合法和模型自报checks通过不等于语义正确，最终事实另由当前对话助手实际审核。

模型qwen3.8-flash，temperature=0，三个阶段均thinking开启、每次预算2048，max_tokens=4096，最多4并发，计划336个逻辑请求。初始失败预算为每请求最多4次；在任何最终语义评分前，因连续空/null时间字段故障另行冻结恢复增补，允许失败请求最多12次总尝试。采用原payload和原验证器的首个结构有效返回，不修补字段，不根据语义得分重跑或择优。原协议与增补分别保留，不能将恢复预算称为初始预注册。新旧仍是相同112段，不能相加为224段。新方法整体包比较包含提示、表示、审核和补漏变化，尚不能归因到单个组件。

## 同口径主结果

共同112段，冻结329条完整参考中的138条暂定A支持参考，沿用原实验三严格原子覆盖、一对一敏感性及支持性审核口径。

| 方法 | 严格原子覆盖 | 一对一覆盖 | A依据不足/未决 | 源文明确冲突 | 平均tokens/段 |
| --- | ---: | ---: | ---: | ---: | ---: |
{table(old)}
{table(new)}

覆盖净增{s['net_reference_gain']:+d}条，按完整对话配对的平均增量{paired['mean']:+.3f}，聚类bootstrap 95%区间[{paired['low']:+.3f}, {paired['high']:+.3f}]，{ci}。逐段改善{s['improved_dialogues']}、持平{s['tied_dialogues']}、退步{s['worsened_dialogues']}。去除冻结A支持参考最多的{s['excluded_dialogue']}后，平均增量{sens['mean']:+.3f}，区间[{sens['low']:+.3f}, {sens['high']:+.3f}]。

原双路实际{old['actual_calls']}次调用、{old['total_tokens']:,} total tokens；新双路实际{new['actual_calls']}次调用、{new['total_tokens']:,} total tokens。费用包含全部失败和重试，不再次叠加reasoning_tokens。新旧实际tokens比为{new['total_tokens']/old['total_tokens']:.2f}。不是等tokens的纯架构因果比较。

原V2严格校验下，336个逻辑请求中首次尝试结构有效{s['execution']['first_attempt_valid']}个；全部尝试中无效{s['execution']['invalid_attempts']}次。HTTP状态分布{s['execution']['http_status_counts']}，结构失败原因{s['execution']['validation_errors']}。离线修正后的完整率不代表原单次请求成功率，字段与锚点格式可靠性也是新方法需要报告的代价。

新增严格覆盖：{', '.join(s['added_reference_ids']) or '无'}。

丢失原严格覆盖：{', '.join(s['lost_reference_ids']) or '无'}。

## 评价边界

参考及审核均为当前同源助手的暂定标注，尚非独立人工gold。新输出逐条审核，新旧相同断言/时间且证据已覆盖的记录才复用旧审核。A依据不足不等于隐藏源文必假；原始有据行和部分匹配也不能当去重画像精确率。输出更细可能改变复合参考匹配，故保留一对一结果，不改参考以配合新算法。

这112段已参与错误分析与方法设计，属于开发诊断，不能声称封存测试泛化。bootstrap以完整对话为单位，3000次、种子20261101；不覆盖AI标注误差。单次固定版本整体包对照未验证组件消融、等token对照或不同thinking预算。

## 文件

代码isc112_v2/；协议ISC112_V2_PROTOCOL.md；原始请求initial/与dependent/；全部返回api_raw.jsonl；首个有效返回绑定selection_bindings.json；独立候选candidates.json；最终预测predictions.json；实际成本cost_ledger.json；逐包审核review_packets/；评分summary.json及dialogue_scores.csv；检查final_checks.json。

图1比较原四组和优化双路，统一112段，覆盖分母138；误差线为按对话聚类的95%bootstrap区间。可靠性分母为各配置原始确定断言数，成本包含失败与重试。SVG为矢量文件，PNG/TIFF为600dpi。
'''
    (OUT / '实验报告.md').write_text(text, encoding='utf-8')
    (fg / '图注.md').write_text('图1　同112段完整自然对话上，原四组方法与优化双路的严格原子覆盖、A依据不足/未决断言占比和实际平均token成本。覆盖分母138；支持性占比分母为各方法确定断言数；误差线为完整对话聚类bootstrap 95%区间。参考和审核为同源助手暂定标注，开发比较不构成独立封存确认。', encoding='utf-8')
    return {'report': str(OUT / '实验报告.md'), 'figure': str(fg / f'{stem}.svg'), 'joint_target_met': s['joint_target_met']}
