"""Single-cohort manuscript tables, narrative and figure captions."""
from .io import DATA, OUT, read, write_csv
from .analysis import ARM_LABELS

def ratio(s):
    return f"{s['numerator']}/{s['denominator']}（{s['estimate']:.1%}）"

def ci(s):
    return f"{s['mean']:+.3f} [{s['low']:+.3f}, {s['high']:+.3f}]"

def report():
    s12 = read(OUT / 'e1_e2/summary.json'); prefix = read(OUT / 'e1_e2/prefix_analysis.json')
    s3 = read(OUT / 'e3/summary.json'); alignment = read(OUT / 'baseline_alignment.json')
    inter = read(OUT / 'e3/reference_intersections.json'); account = read(OUT / 'accounting.json')
    ds = read(DATA / 'dialogues.json'); lengths = [len(d['turns']) for d in ds]
    main = ['# 112段完整自然对话：三个主实验的统一结果', '',
        '本报告全部统计及主图统一使用同一批112段完整自然对话。完整A结果112份、完整逐前缀路径112条、2×2最终结果448份，均有效。本次代码整理与绘图未调用模型API。', '',
        '## 数据、实验与统计口径', '',
        f'数据为DailyDialog test的112段完整原始对话，双方发言数{min(lengths)}～{max(lengths)}，保留自然起止，不拼接、不截断。A为原先发言者；模型仅看A，隐藏B及参考不进入请求。参考由当前对话助手读取A+B整理，共329条完整B信息，其中138条暂定有A依据；尚无独立人工金标准。样本曾用于探索与方法设计，不宣称是全语料的无偏随机代表或独立确认性测试。', '',
        '实验一是逐前缀基线的最后一个前缀，实验二复用同一轮请求，不重复计数。实验三是四组重新独立调用。虽然两种直接关闭配置都看完整A，但其冻结提示、输出结构和接纳规则不同，保留为两个配置，只在同队列同分母下比较，不把重复观察混成新的独立样本。', '',
        '模型为qwen3.8-flash、temperature=0、max_tokens=4096。实验一二关闭thinking；实验三开启组预算2048。双路候选互不看对方答案，再按原判别流程接纳。全部失败补跑采用原结构规则下的首个有效结果，实际成本包含失败与重试；成功率属于恢复后结果，不是原单次成功率。', '',
        '主指标沿用冻结参考与已有语义审核：实验一用一对一严格匹配；实验三用独立原子覆盖，并保留一对一口径作对照。完整参考覆盖的分母329，A支持子集恢复的分母138。部分匹配、新发现、未决、范围外与源文冲突单列；未匹配不能一律称为错误，无A依据不等于源文必假。', '',
        '所有区间均按完整对话聚类bootstrap（3000次、固定种子20261101），不把多前缀或多断言当独立样本。比例指标对重采样对话的分子、分母分别求和后相除；配对效应在同一重采样中保留方法间对应关系。区间为探索性，未作确认性多重检验校正，也不覆盖AI参考本身的标注误差。', '',
        '## 实验一：完整A的信息恢复', '',
        '| 指标 | 结果 | 对话聚类95%区间 |', '| --- | ---: | --- |']
    for label, field in [('完整B参考严格覆盖', 'full_reference_coverage'), ('严格匹配且有A依据／完整B参考', 'grounded_full_reference_coverage'), ('A支持子集严格恢复', 'A_supported_recovery')]:
        r = s12[field]; main.append(f"| {label} | {ratio(r)} | [{r['low']:.1%}, {r['high']:.1%}] |")
    d = alignment['paired_difference']
    main += ['', f"原始确定断言{s12['raw_claims']}条，其中{s12['unsupported_or_uncertain']}条A依据不足或未决；相对参考一致性P/F1不应解释为真实世界事实准确率。", '',
        f"同112段、同138条A支持参考、同样有依据的一对一严格匹配下，前缀基线完整A为{ratio(alignment['e1'])}，2×2直接关闭为{ratio(alignment['e3_direct_off'])}。配对差为{d['estimate']*100:+.2f}个百分点，95%区间[{d['low']*100:+.2f}, {d['high']*100:+.2f}]跨零。不能把该差额当作已证实的能力提升。", '',
        '## 实验二：信息累积与逐段差异', '',
        f"首次A到完整A平均增加{ci(s12['first_to_full_delta'])}个有依据属性／段。112段中，{s12['positive_delta_paths']}段增加、{s12['zero_delta_paths']}段首尾持平、{s12['negative_delta_paths']}段首尾减少。另有{s12['paths_with_declines']}段在中间前缀出现过下降，共{s12['declining_transitions']}个下降转移；首尾不减少不等于全程单调。", '',
        '主曲线用全部112条完整路径，进度p对应k=ceil(pK)，0表示共用空输入。当下有据属性允许语义部分恢复及经审核的新属性，不能与实验一的具体事实严格覆盖混为一个指标。历史发现并集仅为辅助描述，天然单调。参考中A证据出现曲线不是GPT独立前缀实验，也不是已经证明的信息可恢复上界。', '',
        '补充图S1按相同A总轮数K固定队列显示每个整数前缀，仅展示各组n≥8的长度组，不改变主结果的112段队列。', '',
        '## 实验三：覆盖、可靠性与计算代价', '',
        '| 配置 | A支持参考严格原子覆盖 | 原一对一覆盖 | 原始断言 | A依据不足/未决 | 平均total tokens/段 |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    table = []
    for m in s3['methods']:
        main.append(f"| {m['label']} | {ratio(m['coverage'])} | {m['one_to_one_coverage']}/138 | {m['raw_claims']} | {ratio(m['unsupported_fraction'])} | {m['tokens_per_dialogue']['mean']:,.1f} |")
        table.append({'configuration': m['label'], 'dialogues': 112, 'covered_reference_atoms': m['atomic_coverage'], 'A_supported_reference_count': 138,
            'strict_coverage': m['coverage']['estimate'], 'coverage_low': m['coverage']['low'], 'coverage_high': m['coverage']['high'],
            'raw_claims': m['raw_claims'], 'unsupported_or_uncertain': m['unsupported_or_uncertain'],
            'unsupported_fraction': m['unsupported_fraction']['estimate'], 'mean_total_tokens': m['tokens_per_dialogue']['mean']})
    high = s3['methods'][-1]; low = s3['methods'][0]
    main += ['', f"双路开启相对直接关闭净增{high['atomic_coverage']-low['atomic_coverage']}条严格覆盖，但断言从{low['raw_claims']}条增至{high['raw_claims']}条，A依据不足/未决比例从{low['unsupported_fraction']['estimate']:.1%}升至{high['unsupported_fraction']['estimate']:.1%}，平均token约为{high['tokens_per_dialogue']['mean']/low['tokens_per_dialogue']['mean']:.1f}倍。较高召回不等于整体准确率最高。", '',
        '| 配对效应 | 净增加参考原子 | 平均增量及95%区间 | 去除A支持参考最多的1段 |', '| --- | ---: | --- | --- |']
    names = ['直接中开−关', '双路中开−关', '关时双路−直接', '开时双路−直接', '交互']
    for name, e in zip(names, s3['effects']):
        main.append(f"| {name} | {e['net_reference_count']:+d} | {ci(e['per_dialogue'])} | {ci(e['without_high_density'])} |")
    main += ['', f"敏感性排除规则按冻结参考密度选择：{s3['high_density_dialogue']}有最多11条A支持参考，排除后为111段。单独直接开启thinking在完整队列中的区间接近零，去除该段后跨零；交互区间跨零。双路内开启thinking及开启thinking时增加双路的正向效应更稳健，但仍是本语料与本预算下的探索结果。", '',
        '## 方法发现的信息重叠', '',
        f"138条A支持参考中，{inter['covered_by_all']}条四组都覆盖，{inter['covered_by_any']}条至少一组覆盖，{inter['uncovered_by_all']}条四组均未覆盖。双路开启独有{inter['exclusive_to']['dual_on']}条，直接开启独有{inter['exclusive_to']['direct_on']}条；覆盖最高的配置仍漏掉{inter['covered_by_any']-high['atomic_coverage']}条其他配置能覆盖的信息。", '',
        '图4每列是一个互斥覆盖模式，全部柱数之和为138，不重复累加同一参考。至少一组覆盖的104条是离线审核后得到的命中并集，不是已运行的新集成模型成绩，不能据此声称集成精度或新流程收益。', '',
        '## 调用与复现', '',
        f"共458个非空前缀＋1个共用空输入、896个逻辑2×2阶段请求。含原始失败与补跑的实际调用为{account['actual_total_calls']}次，其中前缀相关{account['actual_prefix_calls_including_failed_attempts']}次、2×2相关{account['actual_factorial_calls_including_failed_attempts']}次；累计记录{account['actual_total_tokens']:,} total tokens，不二次叠加reasoning tokens。", '',
        '统一代码位于isc112/，输入快照data/isc112/，结果及论文图results/isc112/。主分析不按采集批次分组；历史请求、重试、原始报告和来源哈希仅作为审计保留。提示文本见data/isc112/prompts.json，首次有效返回选择绑定及全部实际成本账本同时保留。', '',
        '```powershell', 'python -m isc112 all', 'python -m unittest discover -s tests -p test_isc112.py -v', '```', '',
        '结果JSON和逐段CSV分别在e1_e2/与e3/；论文图见[图注与文件索引](figures/论文图注.md)，数值源见figures/figure_data.json。验证结果见validation.json。', '',
        'DailyDialog是公开编写的脚本会话材料，事实仅指对话设定中的人物信息，不是已验证的真实个人经历。数据来源及CC BY-NC-SA 4.0许可沿用data/source.json与项目来源说明。模型条件不对称、同源助手标注、参考属性粒度及重复限定会影响解释。统一为112段并不消除这些限制。']
    (OUT / '实验报告.md').write_text('\n'.join(main) + '\n', encoding='utf-8')
    write_csv(OUT / '论文主表.csv', table)
    captions = f'''# 112段对话的论文图注与文件索引

以下全部主图使用同一批112段完整自然对话。每图均提供SVG矢量、600dpi PNG和LZW压缩TIFF；位图可预览，投稿排版优先使用SVG或TIFF。代码为isc112/plots.py，数据为figure_data.json。所有区间以对话为聚类单位、bootstrap 3000次；比例按重采样后分子与分母之和的比值计算。区间是探索性的抽样不确定性，不包含参考标注误差。

## 图1 完整A恢复与指标对齐

[PNG](图1_完整A恢复与指标对齐.png) · [SVG](图1_完整A恢复与指标对齐.svg) · [TIFF](图1_完整A恢复与指标对齐.tiff)

(a) 实验一的一对一严格完整参考覆盖、有A依据的完整参考覆盖、A支持子集恢复。柱上分别标明分子和分母，前两者分母329，后者分母138，不能互换。(b) 前缀实验最后一次完整A结果与2×2实验直接关闭组，在同112段、同138条冻结A支持参考、同有依据的一对一匹配下比较；其提示与输出规则不同，差异不能直接归因于模型能力。误差线为对话聚类95%区间。配对差4.35个百分点，95%区间[-1.63,11.21]。

## 图2 前缀累积与逐段差异

[PNG](图2_前缀累积与逐段差异.png) · [SVG](图2_前缀累积与逐段差异.svg) · [TIFF](图2_前缀累积与逐段差异.tiff)

(a) 全部112条完整路径上的当下有据属性、参考A证据已出现数量及辅助历史并集。归一化进度p取k=ceil(pK)，0为共用空输入；阴影仅显示当下有据属性的95%区间。参考曲线不是GPT的独立前缀推理，也不是可靠信息上界；并集天然单调，不用于证明模型表现单调。(b) 每段首个A到完整A的属性数差分布；80段持平、32段增加，主均值+0.598。12段在中间前缀有过下降，首尾差不减少不等于全程单调。

## 图3 四组覆盖、依据、成本与配对效应

[PNG](图3_四组覆盖_依据_成本与配对效应.png) · [SVG](图3_四组覆盖_依据_成本与配对效应.svg) · [TIFF](图3_四组覆盖_依据_成本与配对效应.tiff)

四组均使用同112段，直接或双路流程与thinking关/开形成2×2。(a) 对同138条冻结A支持参考的严格原子覆盖。(b) 无充分A依据/未决断言在原始确定断言中的比例，分母为各组输出行数；该指标不是源文假事实率。(c) 每段实际total tokens，包括原始失败和授权重试；reasoning tokens不重复加总。(d) 配对严格参考原子增量／段。交互=(双路开−双路关)−(直接开−直接关)。各项误差线为对话聚类95%区间，未经多重比较校正。

## 图4 四组参考信息覆盖交集

[PNG](图4_四组参考信息覆盖交集.png) · [SVG](图4_四组参考信息覆盖交集.svg) · [TIFF](图4_四组参考信息覆盖交集.tiff)

对138条A支持参考作互斥覆盖模式统计。下方黑点表示该配置严格覆盖，灰点表示未覆盖；每列模式对应上方条数，所有柱数之和138。四组共同命中61条、至少一组命中104条、均未命中34条。双路开独有7条、直接开独有2条；方法并集是离线审核描述，不是新集成系统的成绩。

## 补充图S1 相同A总轮数的前缀曲线

[PNG](图S1_相同A总轮数的前缀曲线.png) · [SVG](图S1_相同A总轮数的前缀曲线.svg) · [TIFF](图S1_相同A总轮数的前缀曲线.tiff)

按固定A总数K分组，横轴为真实已观察A发言数k，每组路径保持不变。仅展示各组n≥8的K=2～7组，共97段；其余15段保留在全部112段主分析内，并未删样。阴影为各固定组的对话聚类95%区间，短路径和小组的估计需谨慎解释。

## 补充图S2 高密度对话敏感性

[PNG](图S2_去除参考最多对话的敏感性.png) · [SVG](图S2_去除参考最多对话的敏感性.svg) · [TIFF](图S2_去除参考最多对话的敏感性.tiff)

比较完整112段与去除冻结A支持参考最多的test_526后111段的五项配对效应。排除规则基于参考信息密度，不据效应方向逐项选择样本；误差线为对话聚类95%区间。这是敏感性分析，主结果仍为112段。

参考和语义审核来自同一助手的AI暂定判断，尚非独立人工金标准。样本曾用于探索与方法设计，不能仅凭统计区间认定总体泛化已证实。
'''
    (OUT / 'figures/论文图注.md').write_text(captions, encoding='utf-8')
    return {'report': str(OUT / '实验报告.md'), 'dialogues': 112, 'main_figures': 4, 'supplementary_figures': 2}
