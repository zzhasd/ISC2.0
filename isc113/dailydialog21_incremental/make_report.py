"""Write the final Chinese report only after full scoring and offline replay pass."""
import csv
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def table(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def fmt(v):return 'NA' if v in (None,'') else f'{float(v):.3f}'

def main():
    from prepare_evaluation import scoring_input_fingerprint
    assert not(HERE/'results/evaluation_revision_required.json').exists(), 'Run full scoring and verification after review revisions'
    assert read(HERE/'results/scoring_status.json')['input_fingerprint']==scoring_input_fingerprint(), 'Report inputs changed after scoring; rerun analysis and verification'
    verify=read(HERE/'results/verification.json');assert verify['complete'] and verify['offline_replayed_predictions']==682
    effects=read(HERE/'results/effect_summary.json');summary=table(HERE/'results/prefix_summary.csv')
    metrics=table(HERE/'results/prefix_metrics.csv');rows={(r['algorithm'],int(r['prefix_k'])):r for r in summary}
    names={'direct_thinking':'Direct Thinking','elara_v1':'ELARA v1'}
    final_effect=next(e for e in effects if e['statistic']=='final_unique_difference')
    pool_losses=read(HERE/'results/nonmonotonic_pool_review.json')
    loss_transitions=len({(r['dialogue_id'],r['prefix_k']) for r in pool_losses})
    lines=['# DailyDialog 21 条发言对话的逐轮属性发现实验',
           '', '本实验使用全部 31 段完整长度恰好为 21 的对话，以 A 的 11 个累积前缀独立预测 B 属性。推理模型为用户更正后的 `qwen3.8-flash`，外部评价由指定的 **GPT-6.1 Sol（高推理）子代理**完成。未使用 Qwen Max 评价器。',
           '', f"最终前缀（k=11）的平均有效唯一属性数：Direct Thinking {fmt(rows[('direct_thinking',11)]['mean_unique_count'])}，ELARA v1 {fmt(rows[('elara_v1',11)]['mean_unique_count'])}。配对差值（ELARA−Direct）为 {fmt(final_effect['estimate'])}，95% CI [{fmt(final_effect['ci95_low'])}, {fmt(final_effect['ci95_high'])}]。这是自动评价下的样本内结果。",
           '', '## 实验与审计', '',
           '- 数据：13,118 段中按长度筛出 31 段（train 27、validation 2、test 2），不按预测数量或评价结果排除样本。',
           '- 682 个独立算法预测全部完成；341 个前缀各有独立 Sweep、盲化 Support 和共享 Pool；31 个跨前缀身份索引完成。',
           '- 原始 ELARA v1 的三次生成及内部 Flash 候选审核属于预测算法，予以保留。Direct 原始上限为 10；ELARA 每次生成提示词上限 16、解析校验上限 18，未设置独立的最终截取上限。',
           '- E1/E2 有效，其他标签保留；原子化不删除未支持细节。所有实际成立的字段均 required，核心权重 2，其他权重 1。不存在旧 Gold，故不报告相对旧 Gold 的新颖性。',
           '- 离线重放了全部 682 个预测，确认结果与冻结算法及原始 API 响应一致；逐请求检查仅含对应当前 A-only 前缀。',
           '- 推理传输层采用冻结客户端：每逻辑阶段最多 6 次格式/服务失败尝试，保留首次有效响应和所有失败记录；可恢复 stop 响应中的完整 JSON 对象，拒绝通过补括号修复截断。原始算法提示词、内部阶段及生成参数保留，传输实现另有源码哈希。',
           '', f"原始 API 记录包含 {verify['api_attempts']} 次已完成请求，{verify['api_failure_count']} 次失败尝试（包括格式及网络失败），报告 token 总量 {verify['charged_tokens_reported']:,}。网络异常无 provider usage 时，无法把该数解释为精确账单。Sol 子代理不提供逐前缀 token 账单，相关 CSV 字段保持缺失。",
           '', '## 观察到的数量增长', '',
           '| 算法 | k=1 原始数 | k=11 原始数 | k=1 有效唯一数 | k=11 有效唯一数 | k=11 P_raw（微平均） | k=11 R_core（微平均） |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for alg in names:
        first=rows[(alg,1)];last=rows[(alg,11)]
        lines.append('| '+' | '.join([names[alg],fmt(first['mean_raw_count']),fmt(last['mean_raw_count']),fmt(first['mean_unique_count']),fmt(last['mean_unique_count']),fmt(last['p_raw_micro']),fmt(last['r_core_micro'])])+' |')
    lines.extend(['', '以下计数曲线按 31 段对话取均值；置信区间按整段对话配对重采样 2,000 次（seed=20261106）。逐前缀区间为描述性区间，不作为 11 次独立显著性检验。',
                  '', '![原始数量增长](figures/figure1_raw_growth.png)',
                  '', '![有效唯一属性与共享事实池](figures/figure2_valid_unique_growth.png)',
                  '', '![首次新增有效属性](figures/figure3_new_discovery.png)',
                  '', '![配对差值](figures/figure4_paired_difference.png)',
                  '', '## 预先指定的效应', '',
                  '| 统计量 | 点估计 | 95% CI |', '|---|---:|---|'])
    labels={'final_unique_difference':'最终前缀有效唯一数：ELARA − Direct',
            'gap_growth_k11_minus_k1':'两算法差距扩大：D(11) − D(1)',
            'mean_first_new_difference_k2_to_k11':'k=2–11 平均首次新增差：ELARA − Direct',
            'within_algorithm_growth_k11_minus_k1':'自身有效唯一数增长：k=11 − k=1'}
    for e in effects:
        label=labels[e['statistic']]+('（'+names[e['algorithm']]+'）' if e['algorithm'] in names else '')
        lines.append(f"| {label} | {fmt(e['estimate'])} | [{fmt(e['ci95_low'])}, {fmt(e['ci95_high'])}] |")
    def effect(key):return next(e for e in effects if e['statistic']==key)
    h2=effect('gap_growth_k11_minus_k1');marginal=effect('mean_first_new_difference_k2_to_k11')
    h2_text='区间整体大于零，支持本样本内 ELARA−Direct 有符号差值从 k=1 到 k=11 增大' if h2['ci95_low']>0 else '区间整体小于零，ELARA−Direct 有符号差值从 k=1 到 k=11 减小' if h2['ci95_high']<0 else '区间包含零，不能据此认定 ELARA−Direct 有符号差值随前缀增长而增大'
    lines.extend(['', f"H2：{h2_text}。首次新增差的区间为 [{fmt(marginal['ci95_low'])}, {fmt(marginal['ci95_high'])}]；首次新增按统一事实 ID 计算，消失后重现不重复计数。",
                  '', 'H1：两算法自身 k=11−k=1 的增长区间均大于零，支持本样本内从早期到最终前缀的有效唯一属性增长；端点增长不等同于每一轮均单调增加。',
                  '', '## 机制与敏感性诊断', '',
                  '| 算法 | k=11 E1 唯一核心均值 | k=11 E2 唯一核心均值 | k=2–11 首次新增 E1 均值 | k=2–11 首次新增 E2 均值 | k=11 Sweep 支持子集核心召回 |',
                  '|---|---:|---:|---:|---:|---:|'])
    for alg in names:
        final=[r for r in metrics if r['algorithm']==alg and int(r['prefix_k'])==11]
        later=[r for r in metrics if r['algorithm']==alg and int(r['prefix_k'])>=2]
        mean=lambda rs,k:sum(float(r[k]) for r in rs)/len(rs)
        lines.append('| '+' | '.join([names[alg],fmt(mean(final,'e1_core_count')),fmt(mean(final,'e2_core_count')),fmt(mean(later,'first_new_e1_count')),fmt(mean(later,'first_new_e2_count')),fmt(rows[(alg,11)]['sweep_r_core_micro'])])+' |')
    lines.extend(['', 'E1/E2 分层沿用当前完整规范事实的等级。核心命中不要求恢复该事实全部细节，因此 E2 核心数量本身不能证明算法已恢复其中全部隐式限定，需结合 R_full 和字段覆盖率解释；不据此单独作内部推理机制的因果判断。',
                  '', f"Direct 在 k=11 触达 10 条上限的比例为 {float(rows[('direct_thinking',11)]['cap_hit_rate']):.1%}。该主实验保留原算法；按用户决定，未补跑放宽至 20 条的敏感性版本（见 `user_decisions.json`）。输出限制仍是解释两算法数量差异的因素。",
                  '', '独立 Sweep 敏感性分母是共享规范池中、Sweep 审核原子已覆盖全部核心字段的事实子集。它减少候选来源影响，但并不意味着 Sweep 构成绝对完整真值。',
                  '', '## 解释边界与人工复核', '',
                  '研究只覆盖这 31 段固定长度对话的信息累积，不直接证明长对话优于短对话。假设均按观察结果报告，不能把原始输出增多直接解释为有效发现能力提升。',
                  '', '所有评价是自动模型判断，尚未完成人工校准。`results/human_audit.csv` 提供固定六段、66 个前缀的待人工复核样本；不得把其空白标注列视为审核完成。`results/nonmonotonic_pool_review.json` 列出共同事实池的非单调变化，需区分证据修正和评价器不一致。',
                  '', f'诊断共发现 {len(pool_losses)} 次局部池事实在下一前缀缺席，分布于 {loss_transitions} 个相邻前缀转换（全体共 310 个转换）。该计数是事实缺席次数，不是判错次数；候选遗漏、规范化或判定波动、证据修正均可能造成缺席。尚未进行人工裁决，因此首次发现和重现指标也应结合这一参考池限制解释。',
                  '', '`supported_at_k=false` 表示该事实未进入当前前缀池，不能解释为关于现实 B 的否定事实。跨前缀对齐只改变身份索引，不回填未来证据、字段或支持标签。',
                  '', '可复核的完整结果见 `results/prefix_metrics.csv`（682 行）、`results/fact_trajectory.csv`、`results/bootstrap_ci.csv`、`results/per_prediction.csv`、`results/per_fact.csv` 和 `results/verification.json`。源文件、源码快照及哈希均保留在此目录。', ''])
    (HERE/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print('Wrote REPORT.md from complete, verified results.')

if __name__=='__main__':main()
