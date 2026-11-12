#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Paper-ready grouped bars + per-reviewer dots + SD error bars + growth-rate line.
Updated version: HW sample removed; legends for raw reviewer points and ±SD removed.

Input is hard-coded as a 4 x 5 x 2 NumPy matrix; no Excel/CSV is read.
Rows: reviewer 01..04; columns: IA, HU, HS, IB, IF;
last dimension: [Summary, Direct].
"""

from pathlib import Path
import csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from matplotlib.font_manager import fontManager

# -------------------------------------------
# 1) Original observations with HW removed
#    Shape: 4 reviewers x 5 samples x 2 methods
# -------------------------------------------
SAMPLES = ['IA', 'HU', 'HS', 'IB', 'IF']
METHODS = ['Summary', 'Direct']
DATA = np.array([
    # Reviewer 01:          IA           HU           HS           IB           IF
    [[21.0,  5.8], [23.6, 19.6], [45.6, 37.4], [36.6, 27.0], [ 8.0,  5.0]],
    # Reviewer 02
    [[18.8,  5.2], [14.0, 11.6], [38.6, 37.8], [37.8, 31.6], [16.0, 11.0]],
    # Reviewer 03
    [[23.0, 11.4], [22.2, 20.4], [46.0, 39.0], [40.8, 31.2], [18.0, 13.0]],
    # Reviewer 04
    [[22.6,  7.6], [17.6, 16.4], [47.6, 36.0], [34.0, 27.0], [10.0,  5.0]],
], dtype=float)

OUTPUT_DIR = Path(__file__).resolve().parent


def compute_stats(data):
    assert data.shape == (4, 5, 2), f'Unexpected data shape: {data.shape}'
    avg = data.mean(axis=0)
    sd = data.std(axis=0, ddof=1)  # sample SD
    growth = (avg[:, 0] - avg[:, 1]) / avg[:, 1] * 100.0
    return avg, sd, growth


def export_table(avg, sd, growth, out_dir):
    filename = out_dir / 'reviewer_scores_noHW_summary.csv'
    with filename.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['样本', 'Summary均值', 'Direct均值', 'Summary标准差', 'Direct标准差', '增长率(%)'])
        for i, sample in enumerate(SAMPLES):
            writer.writerow([sample, f'{avg[i,0]:.2f}', f'{avg[i,1]:.2f}',
                             f'{sd[i,0]:.2f}', f'{sd[i,1]:.2f}', f'{growth[i]:.2f}'])
    return filename


def choose_chinese_font():
    available = {f.name for f in fontManager.ttflist}
    for name in ('Noto Sans CJK SC', 'Microsoft YaHei', 'PingFang SC',
                 'SimHei', 'Source Han Sans SC', 'Noto Sans CJK JP',
                 'WenQuanYi Micro Hei', 'Arial Unicode MS'):
        if name in available:
            return name
    return 'DejaVu Sans'


def draw_figure(data, avg, sd, growth, lang='zh', out_dir=OUTPUT_DIR):
    assert lang in ('zh', 'en')
    zh = lang == 'zh'

    plt.rcParams.update({
        'font.family': choose_chinese_font() if zh else 'DejaVu Sans',
        'axes.unicode_minus': False,
        'font.size': 10,
        'axes.labelsize': 11,
        'axes.linewidth': 0.85,
        'xtick.labelsize': 10.5,
        'ytick.labelsize': 10,
        'svg.fonttype': 'path',
        'pdf.fonttype': 42,
        'savefig.facecolor': 'white',
    })

    color_summary = '#3D70A1'
    color_direct = '#D49358'
    color_growth = '#79518F'
    color_text = '#243143'
    color_dot = '#26313A'

    fig, ax = plt.subplots(figsize=(8.8, 5.25), facecolor='white')
    fig.subplots_adjust(left=0.085, right=0.86, bottom=0.17, top=0.855)

    centers = np.arange(len(SAMPLES), dtype=float)
    width = 0.32
    offset = 0.185
    positions = [centers - offset, centers + offset]

    for m, (xs, color) in enumerate(zip(positions, (color_summary, color_direct))):
        ax.bar(xs, avg[:, m], width=width,
               color=color, edgecolor='white', linewidth=0.9,
               alpha=0.96, zorder=2)

        # T-shaped SD error bars
        ax.errorbar(xs, avg[:, m], yerr=sd[:, m],
                    fmt='none', ecolor=color_text,
                    elinewidth=1.25, capsize=4.5, capthick=1.25,
                    zorder=5)

        # individual reviewer points
        jitter = np.array([-0.087, -0.029, 0.029, 0.087])
        for j in range(len(SAMPLES)):
            ax.scatter(xs[j] + jitter, data[:, j, m],
                       s=24, facecolor=color_dot, edgecolor='white', linewidth=0.65,
                       zorder=7)
            annotation_y = max(avg[j, m] + sd[j, m], data[:, j, m].max()) + 1.6
            ax.text(xs[j], annotation_y, f'{avg[j, m]:.2f}',
                    ha='center', va='bottom', fontsize=9.3,
                    fontweight='medium', color=color_text, zorder=8)

    # put 0% growth baseline above all bars
    peak = max(float(data.max()), float((avg + sd).max()))
    right_axis_zero_at_left_score = np.ceil(peak + 5.0)
    growth_to_left_scale = 0.19
    left_ylim_max = 97.0

    assert np.min(right_axis_zero_at_left_score + growth * growth_to_left_scale) > peak

    ax.set_ylim(0, left_ylim_max)
    ax.set_xlim(-0.54, len(SAMPLES) - 0.46)
    ax.set_xticks(centers, SAMPLES)
    ax.set_yticks(np.arange(0, 100, 10))
    ax.set_ylabel('分值' if zh else 'Score', color=color_text, labelpad=10)
    ax.set_xlabel('样本编号' if zh else 'Sample', color=color_text, labelpad=9)
    ax.tick_params(axis='both', colors=color_text, length=0, pad=7)
    ax.grid(axis='y', color='#E8ECF0', linewidth=0.8, alpha=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#B7BEC5')
    ax.spines['bottom'].set_color('#B7BEC5')

    ax.axhline(right_axis_zero_at_left_score, color='#B6A6C1',
               linewidth=1.05, linestyle=(0, (4, 4)), zorder=1)

    right_ax = ax.twinx()
    right_ax.set_ylim(
        (0 - right_axis_zero_at_left_score) / growth_to_left_scale,
        (left_ylim_max - right_axis_zero_at_left_score) / growth_to_left_scale,
    )
    right_ax.set_yticks([0, 50, 100, 150, 200])
    right_ax.set_ylabel('Summary 相对 Direct 增长率（%）' if zh else 'Summary vs Direct growth (%)',
                        color=color_growth, labelpad=10)
    right_ax.tick_params(axis='y', colors=color_growth, length=0, pad=8)
    right_ax.spines['top'].set_visible(False)
    right_ax.spines['left'].set_visible(False)
    right_ax.spines['right'].set_color('#B7BEC5')
    right_ax.spines['bottom'].set_visible(False)

    right_ax.plot(centers, growth, color=color_growth, linewidth=2.2,
                  marker='D', markersize=6.5, markerfacecolor=color_growth,
                  markeredgecolor='white', markeredgewidth=1.0,
                  solid_capstyle='round', zorder=10)
    for j, pct in enumerate(growth):
        label = f'{pct:+.1f}%'
        right_ax.annotate(label, xy=(centers[j], pct), xytext=(0, 10),
                          textcoords='offset points', ha='center', va='bottom',
                          fontsize=9.5, fontweight='bold', color=color_growth,
                          zorder=11)

    # legend only keeps bars and growth line
    handles = [
        Patch(facecolor=color_summary, edgecolor='white', label='Summary'),
        Patch(facecolor=color_direct, edgecolor='white', label='Direct'),
        Line2D([0], [0], color=color_growth, linewidth=2.2,
               marker='D', markersize=5.5, label='相对增长率' if zh else 'Relative growth'),
    ]
    fig.legend(handles=handles, loc='upper center', bbox_to_anchor=(0.47, 0.965),
               ncol=3, frameon=False, fontsize=9.2, handletextpad=0.55,
               columnspacing=1.5)

    suffix = 'cn' if zh else 'en'
    png_path = out_dir / f'reviewer_scores_noHW_{suffix}.png'
    svg_path = out_dir / f'reviewer_scores_noHW_{suffix}.svg'
    fig.savefig(png_path, dpi=600, facecolor='white', bbox_inches='tight', pad_inches=0.14)
    fig.savefig(svg_path, facecolor='white', bbox_inches='tight', pad_inches=0.14)
    plt.close(fig)
    return png_path, svg_path


def main():
    avg, sd, growth = compute_stats(DATA)
    csv_path = export_table(avg, sd, growth, OUTPUT_DIR)
    for lang in ('zh', 'en'):
        png_path, svg_path = draw_figure(DATA, avg, sd, growth, lang=lang)
        print(f'Saved: {png_path.name}, {svg_path.name}')
    print(f'Saved: {csv_path.name}')
    print('\nSample  SummaryMean  DirectMean  SummarySD  DirectSD  Growth(%)')
    for i, sample in enumerate(SAMPLES):
        print(f'{sample:<6s} {avg[i,0]:11.2f} {avg[i,1]:11.2f} '
              f'{sd[i,0]:10.2f} {sd[i,1]:9.2f} {growth[i]:10.2f}')


if __name__ == '__main__':
    main()
