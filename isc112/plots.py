"""Publication figures for one 112-dialogue cohort, without acquisition-batch panels."""
import collections
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import PercentFormatter, MaxNLocator, FuncFormatter

from .io import OUT, read, save
from .analysis import ARM_LABELS

FIG = OUT / 'figures'
COLORS = ['#0072B2', '#56B4E9', '#D55E00', '#009E73']
SHORT = ['直接／关', '直接／开', '双路／关', '双路／开']
EFFECT_NAMES = ['直接中：开−关', '双路中：开−关', '关时：双路−直接', '开时：双路−直接', '交互效应']

def style():
    from pathlib import Path
    for name in ['simsun.ttc', 'times.ttf']:
        p = Path('C:/Windows/Fonts') / name
        if p.exists():
            font_manager.fontManager.addfont(str(p))
    plt.rcParams.update({'font.family': ['Times New Roman', 'SimSun', 'DejaVu Sans'],
        'font.size': 8, 'axes.titlesize': 9, 'axes.labelsize': 8, 'axes.linewidth': .6,
        'xtick.labelsize': 7.5, 'ytick.labelsize': 7.5, 'legend.fontsize': 7, 'legend.frameon': False,
        'xtick.direction': 'in', 'ytick.direction': 'in', 'xtick.major.width': .5, 'ytick.major.width': .5,
        'axes.unicode_minus': False, 'figure.facecolor': 'white', 'axes.facecolor': 'white',
        'savefig.facecolor': 'white', 'svg.fonttype': 'path', 'hatch.linewidth': .4})

def clean(ax, grid='y'):
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.grid(axis=grid, color='0.88', lw=.35); ax.set_axisbelow(True)

def percentage(ax):
    ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))

def export(fig, stem):
    for ext in ['svg', 'png', 'tiff']:
        kw = {'dpi': 600} if ext != 'svg' else {}
        if ext == 'tiff':
            kw['pil_kwargs'] = {'compression': 'tiff_lzw'}
        fig.savefig(FIG / f'{stem}.{ext}', bbox_inches='tight', pad_inches=.035, **kw)
    plt.close(fig)

def rate_bars(ax, stats, labels, colors, max_y=.9, counts=False):
    x = np.arange(len(stats)); values = [s['estimate'] for s in stats]
    ax.bar(x, values, .57, color=colors, edgecolor='black', lw=.4)
    ax.errorbar(x, values, yerr=[[s['estimate'] - s['low'] for s in stats],
                               [s['high'] - s['estimate'] for s in stats]], fmt='none', ecolor='black', lw=.75, capsize=2)
    for xx, s in zip(x, stats):
        text = f'{s["estimate"]:.1%}' + (f'\n{s["numerator"]}/{s["denominator"]}' if counts else '')
        ax.text(xx, s['high'] + .018, text, ha='center', va='bottom', fontsize=7)
    ax.set_xticks(x, labels); ax.set_ylim(0, max_y); percentage(ax); clean(ax)

def figure1(s12, alignment):
    fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.85), layout='constrained')
    stats = [s12['full_reference_coverage'], s12['grounded_full_reference_coverage'], s12['A_supported_recovery']]
    rate_bars(ax[0], stats, ['完整参考\n严格匹配', '完整参考\n有据匹配', 'A支持子集\n有据匹配'], ['0.72', '0.5', '0.25'], max_y=.8, counts=True)
    ax[0].set_title('(a) 实验一：覆盖指标及其分母', loc='left'); ax[0].set_ylabel('严格覆盖／恢复率')
    rate_bars(ax[1], [alignment['e1'], alignment['e3_direct_off']], ['前缀实验完整A\n直接提取', '2×2实验\n直接＋关'], ['0.4', COLORS[0]], max_y=.85, counts=True)
    ax[1].set_title('(b) 相同A支持参考下的基线对照', loc='left'); ax[1].set_ylabel('A支持子集严格恢复率')
    export(fig, '图1_完整A恢复与指标对齐')

def figure2(prefix):
    fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.9), layout='constrained')
    specs = [('current_attributes', '当下有依据属性', COLORS[0], 'o', '-'),
             ('available_reference_count', '参考中A证据已出现', '0.4', 's', '--'),
             ('cumulative_attributes', '历史发现并集（辅助）', COLORS[3], '^', ':')]
    for measure, label, color, marker, ls in specs:
        rr = [r for r in prefix['normalized'] if r['measure'] == measure]
        x = [r['fraction'] for r in rr]; y = [r['mean'] for r in rr]
        ax[0].plot(x, y, color=color, marker=marker, ms=3, ls=ls, lw=1.15, label=label)
        if measure == 'current_attributes':
            ax[0].fill_between(x, [r['low'] for r in rr], [r['high'] for r in rr], color=color, alpha=.13, lw=0)
    ax[0].set_title('(a) 逐前缀恢复与参考证据', loc='left'); ax[0].set_xlabel('已观察A发言的归一化进度')
    ax[0].set_ylabel('平均属性数／段'); ax[0].set_xticks([0, .25, .5, .75, 1])
    ax[0].xaxis.set_major_formatter(PercentFormatter(1, decimals=0)); ax[0].set_ylim(bottom=0); ax[0].legend(loc='upper left'); clean(ax[0])
    counts = collections.Counter(r['delta'] for r in prefix['first_final_deltas'])
    xs = list(range(min(0, min(counts)), max(counts) + 1))
    ax[1].bar(xs, [counts[x] for x in xs], .75, color=['0.55' if x == 0 else COLORS[0] for x in xs], edgecolor='black', lw=.4)
    for x in xs:
        if counts[x]:
            ax[1].text(x, counts[x] + 1, str(counts[x]), ha='center', fontsize=7)
    ax[1].set_title('(b) 首个A到完整A的逐段增量', loc='left'); ax[1].set_xlabel('当下有依据属性数之差')
    ax[1].set_ylabel('对话数'); ax[1].xaxis.set_major_locator(MaxNLocator(integer=True)); ax[1].set_ylim(0, max(counts.values()) * 1.14); clean(ax[1])
    export(fig, '图2_前缀累积与逐段差异')

def effects_forest(ax, effects, sensitivity=False):
    for i, e in enumerate(effects):
        cases = [('per_dialogue', -.12 if sensitivity else 0, 'black', '完整112段')]
        if sensitivity:
            cases.append(('without_high_density', .12, COLORS[2], '去除参考最多的1段'))
        for field, offset, color, label in cases:
            v = e[field]
            ax.errorbar(v['mean'], i + offset, xerr=[[v['mean'] - v['low']], [v['high'] - v['mean']]],
                fmt='o', ms=3.1, lw=.8, capsize=2, color=color, label=label if i == 0 else None)
    ax.set_yticks(range(5), EFFECT_NAMES); ax.invert_yaxis(); ax.axvline(0, color='0.5', lw=.7, ls='--')
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.set_xlabel('严格参考原子增量／段（95%区间）')
    if sensitivity:
        ax.legend(loc='lower right')

def figure3(s3):
    methods = s3['methods']; fig, ax = plt.subplots(2, 2, figsize=(7.2, 5.5), layout='constrained')
    rate_bars(ax[0, 0], [m['coverage'] for m in methods], SHORT, COLORS, max_y=1.02, counts=True)
    ax[0, 0].set_title('(a) 四组严格原子覆盖', loc='left'); ax[0, 0].set_ylabel('A支持参考严格覆盖率')
    rate_bars(ax[0, 1], [m['unsupported_fraction'] for m in methods], SHORT, COLORS, max_y=.63)
    ax[0, 1].set_title('(b) 无充分A依据／未决输出', loc='left'); ax[0, 1].set_ylabel('占确定断言的比例')
    x = np.arange(4); means = [m['tokens_per_dialogue']['mean'] for m in methods]
    ax[1, 0].bar(x, means, .57, color=COLORS, edgecolor='black', lw=.4)
    ax[1, 0].errorbar(x, means, yerr=[[m['tokens_per_dialogue']['mean'] - m['tokens_per_dialogue']['low'] for m in methods],
                                   [m['tokens_per_dialogue']['high'] - m['tokens_per_dialogue']['mean'] for m in methods]],
                      fmt='none', ecolor='black', lw=.75, capsize=2)
    for xx, m in zip(x, methods):
        ax[1, 0].text(xx, m['tokens_per_dialogue']['high'] + 100, f'{m["tokens_per_dialogue"]["mean"]:,.0f}', ha='center', fontsize=7)
    ax[1, 0].set_xticks(x, SHORT); ax[1, 0].set_ylim(0, max(m['tokens_per_dialogue']['high'] for m in methods) * 1.15)
    ax[1, 0].yaxis.set_major_formatter(FuncFormatter(lambda value, _: f'{value:,.0f}'))
    ax[1, 0].set_title('(c) 实际计算成本（含失败与重试）', loc='left'); ax[1, 0].set_ylabel('平均total tokens／段'); clean(ax[1, 0])
    effects_forest(ax[1, 1], s3['effects'])
    ax[1, 1].set_title('(d) 流程与thinking的配对效应', loc='left')
    export(fig, '图3_四组覆盖_依据_成本与配对效应')

def figure4(intersections):
    patterns = intersections['patterns']; x = np.arange(len(patterns))
    fig = plt.figure(figsize=(7.2, 3.45), layout='constrained'); grid = fig.add_gridspec(2, 1, height_ratios=[2.0, 1.15], hspace=.04)
    upper = fig.add_subplot(grid[0]); lower = fig.add_subplot(grid[1], sharex=upper)
    counts = [r['count'] for r in patterns]
    upper.bar(x, counts, .65, color=['0.75' if r['pattern'] == '0000' else COLORS[0] for r in patterns], edgecolor='black', lw=.4)
    for xx, count in zip(x, counts):
        upper.text(xx, count + .65, str(count), ha='center', fontsize=7)
    upper.set_ylim(0, max(counts) * 1.15); upper.set_ylabel('互斥交集中的参考信息数')
    upper.tick_params(axis='x', which='both', bottom=False, labelbottom=False); clean(upper)
    lower.set_yticks(range(4), [ARM_LABELS[a] for a in intersections['method_order']]); lower.invert_yaxis()
    for xx, r in enumerate(patterns):
        active = [i for i, bit in enumerate(r['pattern']) if bit == '1']
        lower.scatter([xx] * 4, range(4), s=12, color='0.84')
        if active:
            lower.plot([xx, xx], [min(active), max(active)], color='black', lw=.8)
            lower.scatter([xx] * len(active), active, s=16, color='black', zorder=3)
        else:
            lower.text(xx, 1.5, '均未\n覆盖', ha='center', va='center', fontsize=7, color='0.35', bbox={'facecolor': 'white', 'edgecolor': 'none', 'pad': .5})
    lower.set_xticks([]); lower.set_xlim(-.6, len(patterns) - .4)
    lower.set_xlabel('黑点表示该配置覆盖；每列是一种互斥的覆盖组合')
    for s in lower.spines.values():
        s.set_visible(False)
    lower.tick_params(axis='y', length=0)
    export(fig, '图4_四组参考信息覆盖交集')

def supplements(prefix, s3):
    rows = prefix['fixed_K']; groups = sorted({r['K'] for r in rows if r['dialogues'] >= 8})
    cols = 3; nr = math.ceil(len(groups) / cols)
    fig, axs = plt.subplots(nr, cols, figsize=(7.2, 1.95 * nr), layout='constrained', squeeze=False)
    for ax, K in zip(axs.flat, groups):
        rr = [r for r in rows if r['K'] == K]; x = [r['k'] for r in rr]
        ax.plot(x, [r['mean'] for r in rr], marker='o', ms=3, color=COLORS[0])
        ax.fill_between(x, [r['low'] for r in rr], [r['high'] for r in rr], color=COLORS[0], alpha=.13, lw=0)
        ax.set_title(f'K={K}，n={rr[0]["dialogues"]}', loc='left'); ax.set_xlabel('已观察A发言数 k'); ax.set_ylabel('平均当下有据属性数')
        ax.xaxis.set_major_locator(MaxNLocator(integer=True)); ax.set_ylim(bottom=0); clean(ax)
    for ax in list(axs.flat)[len(groups):]:
        ax.set_visible(False)
    export(fig, '图S1_相同A总轮数的前缀曲线')
    fig, ax = plt.subplots(figsize=(5.1, 3.15), layout='constrained')
    effects_forest(ax, s3['effects'], sensitivity=True)
    export(fig, '图S2_去除参考最多对话的敏感性')

def plot():
    style(); FIG.mkdir(parents=True, exist_ok=True)
    s12 = read(OUT / 'e1_e2/summary.json'); prefix = read(OUT / 'e1_e2/prefix_analysis.json')
    s3 = read(OUT / 'e3/summary.json'); alignment = read(OUT / 'baseline_alignment.json')
    intersections = read(OUT / 'e3/reference_intersections.json')
    figure1(s12, alignment); figure2(prefix); figure3(s3); figure4(intersections); supplements(prefix, s3)
    save(FIG / 'figure_data.json', {'cohort': 'all112', 'dialogues': 112, 'e1_e2': s12,
        'prefix': prefix, 'e3': s3, 'baseline_alignment': alignment, 'reference_intersections': intersections,
        'rendering': {'dpi': 600, 'formats': ['svg', 'png', 'tiff'], 'width_inches': 7.2}})
    return {'main_figures': 4, 'supplementary_figures': 2, 'cohort': 'all112'}
