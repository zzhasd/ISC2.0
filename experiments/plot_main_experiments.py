"""Cohort-aligned Chinese figures from recorded scores; no new model calls."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/merged112/figures'
COHORTS = [
    ('旧32段', ROOT / 'results', '#4777A6'),
    ('新80段', ROOT / 'results/extension80', '#DB8741'),
    ('合并112段', ROOT / 'results/merged112', '#27867D'),
]


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def style():
    font = Path('C:/Windows/Fonts/msyh.ttc')
    if font.exists():
        font_manager.fontManager.addfont(str(font))
        plt.rcParams['font.family'] = font_manager.FontProperties(fname=font).get_name()
    plt.rcParams.update({
        'font.size': 11, 'axes.titlesize': 14, 'axes.titleweight': 'bold',
        'axes.labelsize': 11, 'axes.unicode_minus': False,
        'figure.facecolor': '#F7F9FC', 'axes.facecolor': '#FFFFFF',
        'text.color': '#243349', 'axes.labelcolor': '#526174',
        'xtick.color': '#526174', 'ytick.color': '#243349',
        'svg.fonttype': 'none', 'savefig.facecolor': '#F7F9FC',
    })


def clean(ax, axis='x'):
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(axis='both', length=0, pad=8)
    ax.grid(axis=axis, color='#E7ECF2', linewidth=.8)
    ax.set_axisbelow(True)


def legend(fig, y):
    handles = [Line2D([0], [0], color=c, marker='o', lw=3, markersize=6, label=n)
               for n, _, c in COHORTS]
    fig.legend(handles=handles, loc='upper center', bbox_to_anchor=(.5, y),
               ncol=3, frameon=False, columnspacing=3.0)


def save(fig, stem):
    for suffix in ['png', 'svg']:
        fig.savefig(OUT / f'{stem}.{suffix}', dpi=240)
    plt.close(fig)


def overview(data):
    fig, axes = plt.subplots(1, 3, figsize=(15.2, 6.8))
    fig.subplots_adjust(left=.075, right=.976, top=.65, bottom=.28, wspace=.31)
    fig.text(.055, .932, '三个主实验｜扩样前后与合并结果', fontsize=23, weight='bold')
    fig.text(.055, .875, '同一套推理配置；112段 = 旧32段 + 新80段完整自然对话', fontsize=12, color='#637286')
    legend(fig, .837)
    y = np.array([2, 1, 0])
    names = [n for n, _, _ in COHORTS]
    titles = ['实验一｜完整A的信息恢复', '实验二｜首个A到完整A的增长', '实验三｜双路＋thinking覆盖']
    subtitles = ['严格匹配 ÷ 有效队列的完整A+B参考', '每段有依据属性增量；误差线为95%区间', '严格原子覆盖 ÷ 暂定A可支持参考']
    for ax, title, subtitle in zip(axes, titles, subtitles):
        ax.set_title(title, loc='left', pad=39)
        ax.text(0, 1.055, subtitle, transform=ax.transAxes, fontsize=9.5, color='#6D7A8C')
        ax.set_yticks(y, names)
        ax.set_ylim(-.6, 2.65)
        clean(ax)
    for i, ((name, _, color), d) in enumerate(zip(COHORTS, data)):
        s4 = d['isc4']; m = next(m for m in d['isc7']['methods'] if m['arm'] == 'dual_on')
        a = s4['exact_reference_matches']; b = s4['valid_cohort_full_reference_facts']
        axes[0].barh(y[i], a / b, height=.27, color=color, alpha=.94)
        axes[0].text(a / b + .012, y[i] + .04, f'{a / b:.1%}', fontsize=14, weight='bold', va='center', color=color)
        axes[0].text(.008, y[i] - .24, f'{a}/{b} 条参考  ·  有效 n={s4["valid_full_dialogues"]}', fontsize=9.5, color='#6D7A8C', va='top')
        v = s4['first_to_full_grounded_attribute_delta']
        axes[1].errorbar(v['mean'], y[i], xerr=[[v['mean'] - v['low']], [v['high'] - v['mean']]],
                         fmt='o', color=color, lw=2.5, markersize=8, capsize=4)
        axes[1].text(v['mean'], y[i] + .22, f'+{v["mean"]:.3f}', ha='center', fontsize=14, weight='bold', color=color)
        axes[1].text(.025, y[i] - .24,
                     f'[{v["low"]:.3f}, {v["high"]:.3f}]  ·  完整路径 n={v["dialogues"]}',
                     fontsize=9.5, color='#6D7A8C', va='top')
        a = m['atomic_coverage']; b = m['A_reference_count']
        axes[2].barh(y[i], a / b, height=.27, color=color, alpha=.94)
        axes[2].text(a / b + .012, y[i] + .04, f'{a / b:.1%}', fontsize=14, weight='bold', va='center', color=color)
        axes[2].text(.008, y[i] - .24, f'{a}/{b} 条参考  ·  共同有效 n={m["common"]}', fontsize=9.5, color='#6D7A8C', va='top')
    axes[0].set(xlim=(0, .38), xlabel='完整参考严格覆盖率')
    axes[0].set_xticks([0, .1, .2, .3]); axes[0].xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    axes[1].set(xlim=(0, 1.04), xlabel='平均增加的属性数 / 段')
    axes[1].set_xticks([0, .25, .5, .75, 1])
    axes[1].axvline(0, color='#A2AFBE', lw=1.3)
    axes[2].set(xlim=(0, 1.13), xlabel='A可支持参考严格覆盖率')
    axes[2].set_xticks([0, .25, .5, .75, 1]); axes[2].xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    for i, text in enumerate(['完整画像仍只能恢复一部分', '平均增长得到复现，非逐段单调', '95.3%的绝对覆盖未在新样本复现']):
        pos = axes[i].get_position()
        fig.text(pos.x0, .17, text, fontsize=11, color='#243349', weight='bold')
    fig.text(.055, .095, '阅读说明：三个面板使用不同单位和分母，不能直接比较实验一与实验三的百分比。', fontsize=10, color='#6D7A8C')
    fig.text(.055, .058, '合并112包含前两组，与它们不是独立样本；参考为AI暂定标注，尚非独立人工金标准。', fontsize=10, color='#6D7A8C')
    save(fig, '三个主实验_合并总览')


def details(data):
    fig, axes = plt.subplots(1, 2, figsize=(14.6, 7.1))
    fig.subplots_adjust(left=.075, right=.975, top=.70, bottom=.24, wspace=.27)
    fig.text(.055, .935, '展开看｜前缀累积曲线与四组配置', fontsize=23, weight='bold')
    fig.text(.055, .875, '曲线表示“当下有依据属性”，不使用天然单调的历史并集', fontsize=12, color='#637286')
    legend(fig, .832)
    for (name, _, color), d in zip(COHORTS, data):
        rows = [r for r in d['prefix']['normalized'] if r['measure'] == 'grounded_attribute_count_including_partial']
        x = np.array([r['fraction'] for r in rows]); mean = np.array([r['mean'] for r in rows])
        axes[0].plot(x, mean, marker='o', lw=2.5, markersize=6, color=color)
        axes[0].fill_between(x, [r['low'] for r in rows], [r['high'] for r in rows], color=color, alpha=.07)
    axes[0].set_title('实验二｜同一有效路径队列的平均曲线', loc='left', pad=30)
    axes[0].text(0, 1.04, '旧 / 新 / 合并：完整路径 n=30 / 76 / 106', transform=axes[0].transAxes, fontsize=10, color='#6D7A8C')
    axes[0].set(xlabel='已观察A发言的归一化进度', ylabel='当下有依据属性数 / 段', xlim=(-.025, 1.025), ylim=(0, None))
    axes[0].set_xticks([0, .25, .5, .75, 1]); axes[0].xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    clean(axes[0], 'y')
    xs = np.arange(4); width = .23
    for j, ((name, _, color), d) in enumerate(zip(COHORTS, data)):
        methods = d['isc7']['methods']; ys = [m['atomic_coverage'] / m['A_reference_count'] for m in methods]
        positions = xs + (j - 1) * width
        axes[1].bar(positions, ys, width=width * .9, color=color, alpha=.94)
        for x, val in zip(positions, ys):
            axes[1].text(x, val + .023, f'{val:.1%}', ha='center', fontsize=9, color=color, weight='bold')
    axes[1].set_title('实验三｜四组配置的严格原子覆盖', loc='left', pad=30)
    axes[1].text(0, 1.04, '各队列内使用同一分母；共同有效 n=31 / 73 / 104', transform=axes[1].transAxes, fontsize=10, color='#6D7A8C')
    axes[1].set_xticks(xs, ['直接\nthinking关', '直接\nthinking开', '双路\nthinking关', '双路\nthinking开'])
    axes[1].set(ylabel='A可支持参考严格覆盖率', ylim=(0, 1.10))
    axes[1].set_yticks([0, .25, .5, .75, 1]); axes[1].yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    clean(axes[1], 'y')
    fig.text(.075, .135, '曲线阴影：对话聚类bootstrap 95%区间。进度 p 对应 k=ceil(p×A总数)，0%为共用空输入。', fontsize=10, color='#6D7A8C')
    fig.text(.075, .09, '不同长度对话均保留完整边界。平均曲线上升不表示每段单调；更高覆盖率也不等于更高事实准确率。', fontsize=10, color='#6D7A8C')
    save(fig, '前缀曲线与四组配置_合并对照')


def main():
    style(); OUT.mkdir(parents=True, exist_ok=True)
    data = [{'isc4': read(p / 'isc4/summary.json'), 'isc7': read(p / 'isc7/summary.json'),
             'prefix': read(p / 'isc4/prefix_analysis.json')} for _, p, _ in COHORTS]
    overview(data); details(data)
    export = [{'cohort': name, 'source': str(p), **d} for (name, p, _), d in zip(COHORTS, data)]
    (OUT / 'plot_source_data.json').write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Saved overview and detail figures as PNG/SVG with source data:', OUT)


if __name__ == '__main__':
    main()
