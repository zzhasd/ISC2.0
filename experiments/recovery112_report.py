"""Supplementary recovery report with explicit denominators and pre/post distinctions."""
from isc4_open import ROOT,read,save
from recovery112 import OUT,attempts

def pct(n,d):return f'{n}/{d}（{n/d:.1%}）'
def ci(v):return f"{v['mean']:+.3f} [{v['low']:+.3f}, {v['high']:+.3f}]"

def main():
    groups=[('旧32段',OUT/'old32'),('新80段',OUT/'new80'),('合并112段',OUT)]
    labels={'direct_off':'直接＋关','direct_on':'直接＋开','dual_off':'双路＋关','dual_on':'双路＋开'}
    effects=['直接中开−关','双路中开−关','关时双路−直接','开时双路−直接','交互']
    ss=[(n,read(p/'isc4/summary.json'),read(p/'isc7/summary.json')) for n,p in groups]
    status=read(OUT/'execution_status.json');rs=attempts();plan=read(OUT/'repair_plan.json')
    a=read(OUT/'metric_alignment.json')
    lines=['# 三个主实验：缺失补跑后的合并报告','',
        '2026-11-02，Asia/Shanghai。本报告是缺失补跑后的最新视图，旧结果及原始返回均保留，未覆盖此前文件。样本仍为同一批112段完整自然对话，无新增抽样或训练。','',
        '## 执行与选择规则','',
        f'原始失败逻辑请求{len(plan)}个：1个429限流、13个结构/引用校验失败。实验一二有6个无效前缀；实验三有7个无效全局候选和1个无效判别，另有7个判别因候选失败从未执行。', '',
        f'本次实际新增{len(rs)}次Qwen调用，其中21个响应通过原校验、5个仍因结构/支持标签无效而保留。所有新增请求HTTP 200。实际累计调用{status["total_actual_calls"]}次（原1348＋新增26），不是新增26段对话。', '',
        '对每个失败逻辑请求，最多增加3次相同payload的尝试，选取时间上首个通过原校验的响应。没有按命中数选择，没有修改JSON、修引用、放宽校验或重新运行原本有效的请求。原来有效的另一条候选源沿用。原始B、参考和思考文本不进入Qwen请求。', '',
        '模型、提示及参数保持原配置：qwen3.8-flash、temperature=0、max_tokens=4096；本次补跑的缺失均来自thinking关闭组。原on组thinking_budget仍为2048。新判别用原合并/判别函数构造。此次按顺序低速发起，未超过4并发上限。', '',
        '现有459个前缀结果（458个非空＋1个旧共用空输入）、448个实验三最终结果全部有效。实验一完整A为112/112，实验二全路径为112/112，实验三四组均112/112。补跑后成功率不能冒充原单次尝试的原生成功率。', '',
        '新增断言的14条实验一二审核、26条实验三审核由当前对话助手阅读A+B后完成；其他审核判断复用不改。冻结参考仍为329条完整B信息，其中138条暂定A可支持；没有修改参考内容或事后扩充分母，尚非独立人工gold。','',
        '## 实验一、二','',
        '| 队列 | 完整A有效 | 完整参考严格覆盖 | A支持子集严格恢复 | 完整前缀路径 | 首个A到完整A属性增量及95%区间 |',
        '| --- | ---: | ---: | ---: | ---: | --- |']
    for name,s4,s7 in ss:
        lines.append(f"| {name} | {s4['valid_full_dialogues']} | {pct(s4['exact_reference_matches'],s4['valid_cohort_full_reference_facts'])} | {pct(s4['grounded_exact_reference_matches'],s4['valid_cohort_A_supported_reference_facts'])} | {s4['complete_prefix_paths']} | {ci(s4['first_to_full_grounded_attribute_delta'])} |")
    lines += ['', '完整参考覆盖与A支持子集恢复的分母不同。属性曲线包含有依据的部分恢复，不能当成具体事实严格覆盖。历史并集不用于证明逐段单调；按同一完整路径队列归一化和按固定K分组的原始表均已重新生成。', '',
        '## 实验三','', '| 队列 | 配置 | 四组共同有效n | A支持参考严格原子覆盖 | 原始断言 | 无A依据/未决 | 平均total tokens/段（含失败重试） |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for name,s4,s7 in ss:
        for m in s7['methods']:
            lines.append(f"| {name} | {labels[m['arm']]} | {m['common']} | {pct(m['atomic_coverage'],m['A_reference_count'])} | {m['raw_claims']} | {pct(m['A_unsupported_or_uncertain'],m['raw_claims'])} | {m['mean_total_tokens']:.1f} |")
    lines += ['', '| 配对效应（严格原子/段） | 旧32段 | 新80段 | 合并112段 |', '| --- | --- | --- | --- |']
    for i,e in enumerate(effects):lines.append('| '+e+' | '+' | '.join(ci(s7['effects'][i]['per_dialogue']) for _,_,s7 in ss)+' |')
    lines += ['', '区间按对话聚类bootstrap 3000次，不把多前缀/多断言当作独立样本。区间为探索性，未进行确认性多重比较校正。额外流程、thinking及重试均增加算力，不能解释为等token纯架构比较。原无A依据、范围外、源文冲突列有重叠，不相加。', '',
        '## 实验一与实验三直接关的公平对照','',
        f'在共同有效的{a["dialogues"]}段、同一批{a["A_supported_reference_count"]}条暂定A支持参考、同样有依据的一对一严格匹配下，实验一为{pct(a["experiment1"]["matches"],a["A_supported_reference_count"])}，实验三直接关为{pct(a["experiment3_direct_off"]["matches"],a["A_supported_reference_count"])}，相差{a["difference_percentage_points"]:.2f}个百分点。两者的冻结提示、输出结构、接纳规则和独立调用不同。', '',
        '## 与补跑前结果的关系','',
        '补跑前实验一为64/313=20.4%，现在为69/329=21.0%；多出的分子、分母来自原本无效的两段完整A结果。补跑前实验二使用106条完整路径，现在为112条。新纳入路径的内容分布不同，因此均值与区间也会变化，不是同一已有效样本的能力提升。', '',
        '实验三直接关的112份原始有效输出一份都没有重跑，双路开同样未重跑。原来四组公共队列仅104段，分母115条A支持参考，现在恢复到112段、138条。直接关从57/115=49.6%变为72/138=52.2%，双路开从84/115=73.0%变为100/138=72.5%，均主要体现公共统计队列变化，不能归功于算法更新。双路关新增的8份有效结果同样单列来源。', '',
        '在原来110段完整A、106条全前缀路径以及104段四组公共有效样本上，已有有效输出未更换；此前报告可继续作为单次无重试/完整样本敏感性视图。补跑后的表格是另一个明确包含失败恢复策略的结果。', '',
        '## 论文图与复现','',
        '[图1：三个主实验论文分面图](paper_figures/图1_三个主实验_论文分面图.svg)；[图2：口径对齐与可靠性成本](paper_figures/图2_口径对齐与可靠性成本.svg)；[图注](paper_figures/论文图注.md)。另有600dpi PNG、LZW压缩TIFF和figure_data.json。图中没有PPT式大标题或结论卡，按双栏宽度绘制，使用标准坐标轴、线型、标记和误差区间。', '',
        'Python：experiments/recovery112.py、recovery112_review.py、recovery112_analysis.py、recovery112_report.py、paper_figures112.py。原始补跑请求计划repair_plan.json、新依赖请求new_dependent_requests.json、每次返回attempt_results.jsonl、首个有效选择selection_bindings.json和final_checks.json均保留。', '',
        '实际成本：isc7/execution_audit.json含所有原始及补充尝试，包括被替代的无效响应；selected_execution_audit.json仅列最终所选有效响应。延迟的原关键路径估算不代表跨日期补跑后的在线实测端到端耗时。协议为根目录RECOVERY112_PROTOCOL.md。']
    (OUT/'补跑合并实验报告.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Recovery report written.')

if __name__=='__main__':main()
