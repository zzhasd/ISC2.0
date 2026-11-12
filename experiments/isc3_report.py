"""Generate the Chinese report from evaluated, saved outputs only."""
import collections
import csv
import json
from isc3_common import *
from isc3_analyze import write_csv

def fmt(value,digits=1):
    return '—' if value is None else f'{value:.{digits}f}'

def pct(value):return '—' if value is None else f'{100*value:.1f}%'

def ci(value,scale=1):
    if not value:return '—'
    return f"{value['estimate']*scale:.2f} [{value['ci95'][0]*scale:.2f}, {value['ci95'][1]*scale:.2f}]"

def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(str(v) for v in row)+' |' for row in rows])

def review_packet():
    records=[];blind_truth=[];blind_support=[];key={}
    dialogues={d['id']:d for d in read(ROOT/'data/stage2/dialogues.json')}
    for c in read(DATA/'cases.json'):
        opaque=digest('human_review|'+c['case_id'])[:16];key[opaque]=c['case_id']
        if c['dataset']=='natural':
            full=[{'turn':j+1,'speaker':f'S{j%2}','text':t} for j,t in enumerate(dialogues[c['group']]['turns'])]
            truth_target=f"S{c['hidden']}"
        else:
            full={'world':c['full_world'],'visible_A':c['visible_A'],
                  'constraint':'B and Casey each have exactly one of the two catalogue assignment properties; neither has the other.'}
            truth_target='B'
        for f in c['facts']:
            claim=next(a['claim'] for a in c['catalogue'] if a['id']==f['id'])
            records.append({'case_id':c['case_id'],'dataset':c['dataset'],'split':c['split'],'claim_id':f['id'],
                'claim':claim,
                'A_transcript':c['visible_A'],'provisional_truth':f['truth'],'provisional_support':f['a_support'],
                'support_turns':f['support_turns'],'reviewer_1_truth':'','reviewer_1_support':'','reviewer_2_truth':'',
                'reviewer_2_support':'','adjudicated_truth':'','adjudicated_support':'','reviewer_notes':''})
            blind_truth.append({'review_id':opaque,'claim_id':f['id'],'claim_about_target':claim,
                'target':truth_target,'full_context':full,'reviewer_1_truth':'','reviewer_2_truth':'',
                'reviewer_1_evidence':'','reviewer_2_evidence':'','adjudicated_truth':''})
            blind_support.append({'review_id':opaque,'claim_id':f['id'],'claim_about_target':claim,
                'target':'B','visible_A':c['visible_A'],'reviewer_1_support':'','reviewer_2_support':'',
                'reviewer_1_evidence_turns':'','reviewer_2_evidence_turns':'','adjudicated_support':''})
    write_csv(OUT/'human_review/annotations.csv',records)
    save(OUT/'human_review/cases.json',read(DATA/'cases.json'))
    write_csv(OUT/'human_review/blind_truth.csv',blind_truth);write_csv(OUT/'human_review/blind_A_support.csv',blind_support)
    save(OUT/'human_review/review_key.json',key);save(OUT/'human_review/natural_full_dialogues.json',list(dialogues.values()))
    (OUT/'human_review/README.md').write_text('人工审核尚未完成，所有人工栏为空。先让两位审核者独立完成 blind_A_support.csv（只看 A、不得先读完整对话和 AI 标签），再独立完成 blind_truth.csv，最后才展示 annotations.csv 的 AI 暂定标签并裁决。盲表使用不含世界真假编码的不透明 review_id；review_key.json 为后续匹配键，不在首轮展示。自然真值仅为对话设定，不是现实人物核验；受控真值来自虚构世界。区分 truth、A 支持、持有者和证据充分性，unknown 不是 false。natural_reconstructions.json 是未经语义评分的自然重建文本，可另做断言审核。\n',encoding='utf-8')

def main():
    a=read(OUT/'audit.json');manifest=read(DATA/'manifest_initial.json')
    required=['initial','dependent']
    if (OUT/'reconstruction_v2_generate/requests.json').exists():required+=['reconstruction_v2_generate','reconstruction_v2_extract']
    if not all(stage in a['stages'] and a['stages'][stage]['missing_http_tasks']==0 for stage in required):
        raise SystemExit('Refusing to publish a final report before both frozen request stages return')
    one=read(OUT/'E1.json');two=read(OUT/'E2.json');three=read(OUT/'E3.json')
    four=read(OUT/'E4.json');five=read(OUT/'E5.json');growth=read(OUT/'turn_accumulation.json')
    normalized=list(csv.DictReader((OUT/'turn_accumulation_normalized.csv').open(encoding='utf-8-sig')))
    key_findings=[]
    for ds in ['controlled','natural']:
        for method in ['direct','recover']:
            g=growth[ds][method]
            key_findings.append(f"{ds}／{method}：完整相对空输入的正确正事实增量为 {ci(g['full_minus_empty']['positive_delta_per_100_views'])} 项/百视图；{g['complete_prefix_paths']} 条完整路径中 {g['paths_with_declines']} 条出现过下降。")
    d10=one['controlled']['direct']['operating_points']['0.1']['test']
    r10=one['controlled']['recover']['operating_points']['0.1']['test']
    nd10=one['natural']['direct']['operating_points']['0.1']['test']
    nr10=one['natural']['recover']['operating_points']['0.1']['test']
    natural_cases=[c for c in read(DATA/'cases.json') if c['dataset']=='natural' and c['split']=='test']
    supported_natural=sum(f['truth']=='true' and f['a_support']=='true' for c in natural_cases for f in c['facts'])
    raw_natural=one['natural']['direct']['unthresholded_test']
    risk_finding=f"**E1 的主要结果：** 在预定 10% nonverified 选择规则下，受控测试 Direct 恢复 {d10['grounded_true_recoveries']} 个有支持正事实，RECOVER-B 恢复 {r10['grounded_true_recoveries']} 个；自然测试两者分别输出 {nd10['assertions']}、{nr10['assertions']} 个断言。当前提示原型与校准规则未证明同风险下超过 Direct。nonverified 包含未核验属性，不能当作已知幻觉率或真实世界 FDR。"
    lines=['# ISC 3.0：E1–E5 与信息随话轮累积的实验报告','',
           '日期：2026 年 10 月 31 日（Asia/Shanghai）。本报告对应实际保存的百炼北京端点 `qwen3.8-flash` 返回；temperature=0，thinking 关闭。旧 ISC 2.0 文件保留。', '',
           '**这是探索性先导实验。E1–E4、单模型范围的 E5 和 4.1 均按下述协议运行；E5 的独立模型家族对照未运行，不能称为完整的 ACL Main 级验证。RECOVER-B 是两阶段提示原型，尚无可训练 SGCI 模块。**','',
           risk_finding,'',
           '**4.1 的直接回答（估计值 [聚类 95% CI]）：**','',
           *['- '+v for v in key_findings],'',
           f"受控集 {manifest['by_dataset']['controlled']} 个目标视图、60 对相反归属场景；自然集 {manifest['by_dataset']['natural']} 个视图、32 段对话。受控校准／测试为 30／90 视图，自然校准／测试为 18／46 视图。校准按场景／对话分组，两个隐藏目标或相反世界不会跨校准和测试。",'',
           '自然对话 truth 和 A-support 是沿用的 AI 暂定标注，并非真实人物的独立核验私人经历。结构化真值来自作者指定的虚构世界；支持集合是作者编码的充分证据代理，未经双人独立审核。','',
           '计量单位是固定目录中的属性项，不是信息熵或彼此独立的事实。例如 has_son 与 has_children 相关；本文不把属性项个数换算成 bit 或真实条件互信息。开放式发现只在可对应既有目录的范围内严格计数。','',
           '自然集由 16 段随机组和 16 段富集组组成，两个目标各形成一个视图；1,280 项中暂定 true 26、false 1、unknown 1,253。8 个 true 项带政策敏感标记。`natural_sensitivity.json` 单列随机／富集组，并在不改标签和不重选阈值的前提下排除这些争议项复算；混合组结果不是总体隐私发生率。','',
           '## 执行状态与可复算材料','',
           table(['阶段','计划唯一请求','HTTP 成功任务','HTTP 缺失','记录尝试','记录 tokens'],
                 [[s,v['planned'],v['successful_http_tasks'],v['missing_http_tasks'],v['attempts'],v['tokens']] for s,v in a['stages'].items()]),'',
           f"共记录 {a['recorded_attempts']:,} 次尝试、{a['recorded_tokens']:,} tokens；HTTP 返回的模型标识为 `{a['returned_models']}`。事实预测验证失败的绑定为 {a['validation_error_bindings']} 条，详见 `validation_errors.json`。同一去重请求可能被多个世界／相同子集引用，绑定数不是付费调用数。缺失、截断和格式错误不填为 unknown。",'',
           f"另有 {a['dependent_source_error_bindings']} 个前序源输出未通过检查，故未创建其依赖请求；完整性修正版源输出失败为 {a['v2_reconstruction_source_errors']}。详情分别在 dependent/source_errors.json、reconstruction_v2_extract/source_errors.json。所有 HTTP 计划已返回不等于每个方法在每个视图都产生有效事实输出。",'',
           '方案见仓库根目录 `ISC3_PROTOCOL.md`；补充和限制见 `DEVIATIONS.md`；原请求及返回位于 `initial/`、`dependent/`，E2 完整性修正版在 `reconstruction_v2_generate/`、`reconstruction_v2_extract/`；逐属性结果位于 `predictions.csv`，补充的本地重建断言检查位于 `E2_reconstruction_assertions.csv`。所有统计都由保存的返回离线计算，密钥不进入产物。','',
           f"输入边界核验覆盖原依赖阶段 {a['dependent_payload_boundary']['checked']} 个请求及 E2 v2 的 {a['reconstruction_v2_payload_boundary']['checked']} 个抽取请求：草稿／假想 B／开放发现均与原始输出一致，未加入 gold 或隐藏 B；开放规范化不接触 A。数据、调用脚本、协议和冻结案例标签的哈希核验见 audit.json。",'',
           '## E1：固定风险下的可信恢复','',
           '主要比较为 Direct 固定属性分类、开放式发现后规范化、提示式证据图、RECOVER-B 图候选＋竞争验证，以及两次调用的普通自检控制。图基线不是 GraphProfiler 官方复现；重建基线也不是 1SC 官方复现。', '',
           '下表阈值仅由各数据集校准部分选择，目标 nonverified fraction 为 10%。选择最大化正确且有支持的明确断言数。测试指标没有回头参与选阈值。nonverified=已知真值错误＋真值 unknown 的断言，后者不是已知错误；known error fraction 单列。无输出时风险未定义。小样本 bootstrap 上界只用于探索性选择，不保证总体 FDR≤10%。零错误时 bootstrap 可退化，另导出 cluster-any-error 的单侧上界作敏感性检查。','']
    lines += ['阈值作用于模型自报的“所选标签获得文本支持”的置信度，不是 token likelihood，也不是天然校准的真实人物属性概率。实际风险由独立校准／测试标签估计，不能用模型自报值证明。','']
    rows=[]
    for ds in ['controlled','natural']:
        for method,m in one[ds].items():
            op=m['operating_points']['0.1'];t=op['test'];s=op['selection']['selected_calibration']
            rows.append([ds,method,fmt(s['threshold'],2),f"{t['views']}/{t['planned_test_views']}",t['assertions'],t['true_positive_recoveries'],t['grounded_true_recoveries'],pct(t['known_error_fraction']),pct(t['nonverified_fraction']),pct(t['unsupported_fraction'])])
    lines += [table(['数据','方法','阈值','有效/计划测试视图','断言','正确正事实','有支持正事实','已知错误/断言','nonverified/断言','无支持/断言'],rows),'',
              '无效输出不伪造为 unknown。CSV 同时给出有效视图比例、以全部计划检查项为分母的 coverage，以及以全部计划正属性为分母的恢复率，避免通过丢弃格式失败样本抬高总体覆盖率。配对区间使用双方有效的共同视图；各方法有效样本数不同须一并考虑。','',
              '完整 5%／10%／20% 目标及阈值网格见 `E1_operating_points.csv`、`E1.json`。恢复数—风险曲线是测试集描述，不用于测试后择优。它表示这些候选方法的经验边界，不是信息论意义的最大可恢复上限。','',
              'grounded 计数要求真值正确、当前可见上下文包含预标支持、且输出提供有效话轮引用；这不保证模型引用本身已经组成完整证明。另导出 `grounded_true_with_complete_prelabelled_citations`，要求预标整组证据均被引用；替代模板／中文的完整引用集合不与原英文布局直接等同，需独立人工审核。','',
              f"![E1 recovery-risk]({(OUT/'E1_recovery_risk.png').as_posix()})",'',
              '结构化目录含两项明确排他的属性、一项 A 不提及但隐藏世界指定真假的鬣蜥属性，以及一项完整世界也未指定的帆船属性。猜中鬣蜥真值只计 factual，不计 grounded；不能把全部真属性都作为 A-only 可恢复属性。自然集只在既有固定目录内评分；开放式目录外发现见 `unmatched_open_facts.csv`，其真实性与召回率没有独立 gold。','',
              '**Open 的风险只覆盖映射到既有目录的输出子集，无法约束全部自由发现事实的错误率，因此不能据该列声称开放式整体 FDR 与闭世界方法等价。** 所有未用于明确目录断言的源发现均被导出，不依赖规范化模型是否完整列出 unmatched。','',
              f"自然测试集 {raw_natural['known_positive_truths']} 个暂定真属性中，只有 {supported_natural} 个预标为 A 可充分支持；Direct 的未加阈值输出已命中其中 {raw_natural['grounded_true_recoveries']} 个，同时仍输出 {raw_natural['unsupported_assertions']} 个无预标支持的断言。当前固定目录中，优先问题是可靠性和真值／支持标注，不能仅追求生成更多画像。预标支持集不完整，不能据此证明其他信息不可恢复。",'',
              '## E2：先重建 B 是否有用','',
              '每个视图分别生成一个、三个假想 B，再在新上下文中抽取。抽取明确知道 B 是生成假设，不能把它当成新增观察。下表使用未加阈值的明确输出，不能与 E1 风险约束操作点混为一谈。','']
    lines += ['`recon_one`／`recon_multi` 是原冻结 v1；`recon_one_v2`／`recon_multi_v2` 是发现单假设经常只返回片段后，对全部 184 视图补跑的完整位置控制版本。两种 v2 生成均提供空输出骨架并严格验证所有回复位置，抽取提示和真值保持不变。修订协议见 `ISC3_RECONSTRUCTION_V2_PROTOCOL.md`，属于看到 v1 后的探索性修正，所有 v1 均保留。','']
    rows=[]
    for ds,v in two.items():
        for method,m in v['methods'].items():rows.append([ds,method,m['views'],m['true_positive_recoveries'],m['grounded_true_recoveries'],m['unsupported_assertions'],m['known_truth_errors'],m['unverified_assertions']])
    lines += [table(['数据','方法','测试视图','正确正事实','有支持正事实','无支持断言','已知真值错误','未核验断言'],rows),'']
    cm=two['controlled']['methods'];nm=two['natural']['methods']
    lines += [f"完整性修正后的 v2：受控测试 Direct、单假设、三假设分别恢复 {cm['direct']['grounded_true_recoveries']}、{cm['recon_one_v2']['grounded_true_recoveries']}、{cm['recon_multi_v2']['grounded_true_recoveries']} 个有支持正事实，两阶段普通自检为 {cm['direct_review']['grounded_true_recoveries']} 个。自然测试三者有支持恢复均为 {nm['direct']['grounded_true_recoveries']} 个，但单／三假设无支持断言为 {nm['recon_one_v2']['unsupported_assertions']}／{nm['recon_multi_v2']['unsupported_assertions']} 个，Direct 为 {nm['direct']['unsupported_assertions']} 个。在本数据和提示下，完整重建没有增加有支持的恢复量；配对区间如下，不能从点估计外推所有模型与语料。",'']
    rows=[]
    for ds,v in two.items():
        for name,p in v['comparisons'].items():rows.append([ds,name,p['paired_views'],ci(p['positive_delta_per_100_views']),ci(p['grounded_delta_per_100_views']),ci(p['unsupported_delta_per_100_views'])])
    lines += [table(['数据','配对差（参照见名称）','共同视图','正确正事实差/百视图 [95% CI]','有支持正事实差/百视图','无支持断言差/百视图'],rows),'',
              '同一场景生成的多个假设不能当作独立样本，置信区间按模板或原始对话聚类；三假设方案调用和 tokens 更高。原始假想 B 保存在 `initial/api_raw.jsonl`，最终恢复与生成文本自身的断言分别评估。','']
    lines += ['各方法含前序生成／验证在内的独立运行调用与输入／输出 tokens 见 `method_costs.csv`。两阶段普通自检用于控制调用次数；不同方法实际 token 预算仍不完全相等。源码中共享的图／重建输出只付费一次，按方法核算的成本可能重叠，不能把方法成本列相加当作总账。','']
    ap=OUT/'E2_reconstruction_assertions.json'
    if ap.exists():
        au=read(ap);rows=[]
        for ds,methods in au['methods'].items():
            for method,m in methods.items():rows.append([ds,method,m['views'],m['hypotheses'],m['explicit_assertions'],m['unsupported'],fmt(m['unsupported_per_100_hypotheses']),m['known_truth_errors']])
        lines += [table(['数据','生成方式','测试视图','假设条数','明确断言','无 A 支持断言','无支持断言/百假设','已知真值错误'],rows),'',
                  f"生成文本本地规则审计另有 {len(au['validation_errors'])} 条解析错误，精确摘录逐项保存于 `E2_reconstruction_assertions.csv`。只检测受控虚构文本中句首、第一人称的规范属性表达，是匹配到的明确断言下界，不能覆盖改写、隐含 yes/no 或全部语义。自然重建文本只导出至 `human_review/natural_reconstructions.json` 待人工审核。额外的外部模型断言审计因自动审批拒绝而没有执行，未通过其他路径重试。",'']
        cr=[]
        for ds,methods in au.get('reply_coverage',{}).items():
            for method,m in methods.items():cr.append([ds,method,m['hypotheses'],m['fully_covered_hypotheses'],pct(m['mean_turn_coverage']),m['empty_hypotheses']])
        lines += [table(['数据','重建方式','测试假设','覆盖全部 A 位置的假设','平均回复位置覆盖率','空假设'],cr),'',
                  'v1 源生成校验要求假设数量和有效回复引用，未强制每个 A 位置都有回复；其片段输出保留原流程结果，不补写或择优重跑。v2 对全部视图统一补跑，并严格要求每个 A 位置都有非空回复，未通过的生成单独列为缺失。覆盖率用于暴露方法执行偏差，不能把片段重建叫作完整 B 重建。','',
                  'v1 案例 `correction_11_1_1`：A 先说把“有兄弟”记在 Casey 名下，再要求改为“你”。冻结世界中 B 有兄弟、没有姐妹。单假设和三假设生成均出现原文 “I don\'t have a brother.”；最终单假设抽取返回正确的有兄弟，三假设抽取却返回没有兄弟／有姐妹，虽引用全部 A 话轮仍与世界真值冲突。该案例说明生成的多种解释可能干扰证据使用，不能据一个案例断言平均效果。','']
    lines += ['## E3：跨话轮组合','',
              '对预先选定的 20 对／40 个受控世界运行每一单轮、每一删一话轮子集和等话轮数随机子集。单轮联合的参照是“任意单轮曾正确恢复该正事实”，不把多个单轮结论相加重复计数。','']
    rows=[]
    for method,m in three.items():rows.append([method,m['views_with_singleton_controls'],m['joint_only_correct_positive_facts'],ci(m['joint_only_per_100_views']),ci(m['full_minus_union_singletons_per_100_views'])])
    lines += [table(['方法','视图','仅联合恢复的正确正事实','仅联合/百视图 [95% CI]','完整−单轮并集/百视图 [95% CI]'],rows),'',
              '完整删证据明细和等长度随机对照见 `E3.json`，联合专有事实见 `E3_joint_only_facts.csv`。联合正确、单轮错误并不单独证明新算法机制；模板、指代、排他前提和额外文本都可能影响结果。证据量与 token 数仍非严格相等。','',
              '## 4.1：信息是否随可见话轮增加而增长','',
              '每个测试视图实际运行从 0 到全部 A 话轮的每个整数前缀；相同输入去重。下表在固定测试人群上按 ceil(n×可见比例) 汇总，避免“长对话留下来、短对话被排除”造成伪增长。未加阈值曲线保留模型本身的所有升降，风险阈值曲线另存 CSV。','']
    lines += ['主曲线只使用 Direct 和 RECOVER-B 的每个整数前缀都返回有效结果的共同完整路径人群；缺失视图统一从整条主曲线排除，不让不同横坐标换人。灰线是预标 A 支持参考，黑线是完整世界已知真属性参考，均不是已证明的信息恢复上限；自然真值仍为 AI 暂定。','',
              '校准版本把完整上下文校准得到的阈值固定迁移到所有前缀，不重新逐前缀择优。阈值相同不代表各前缀实际风险相同；每个横坐标的 known error、nonverified 和 unsupported 比例均保存在 CSV。','']
    nr=[]
    for r in normalized:
        if r['operating_point']=='nominal':nr.append([r['dataset'],r['method'],pct(float(r['fraction'])),r['views'],r['missing_views'],fmt(float(r['true_facts_per_100_views'])) if r['true_facts_per_100_views'] else '—',fmt(float(r['grounded_facts_per_100_views'])) if r['grounded_facts_per_100_views'] else '—'])
    lines += [table(['数据','方法','可见比例','有效测试视图','缺失视图','正确正事实/百视图','有支持正事实/百视图'],nr),'',
              f"![Turn accumulation]({(OUT/'turn_accumulation.png').as_posix()})",'']
    for ds,methods in growth.items():
        for method,m in methods.items():
            lines += [f"- {ds}／{method}：完整前缀路径 {m['complete_prefix_paths']}/{m['expected_paths']}；出现至少一次恢复数下降的路径 {m['paths_with_declines']} 条；正向话轮增量累计 {m['positive_step_fact_gains']} 项，负向累计 {m['negative_step_fact_losses']} 项；完整减空输入的正确正事实差/百视图为 {ci(m['full_minus_empty']['positive_delta_per_100_views'])}。"]
    lines += ['', '应区分“完整上下文相对空输入的平均增益”和“每个新增话轮都单调改善”。前者为正不证明后者，也不能据此宣称稳定非线性组合机制。逐路径升降和绝对话轮数曲线在 `turn_accumulation_paths.csv`、`turn_accumulation_absolute.csv`。绝对 k 曲线的 eligible cohort 随 k 变化，不能当作同一人群增长曲线。另有 `turn_accumulation_fixed_k_cohorts.csv`：分别固定至少有 2／4／8 个 A 话轮的人群，在同一批视图上比较整数 k=0…K，避免人群变化及归一化取整的影响。自然集前缀支持只依据既有一组充分证据作保守代理，需人工复核。','',
              '完整对话参考：原 Qwen3.8 stage-2 完整控制与相同 64 个自然视图配对，结果来自既有独立请求；其提示与本轮不同，因此只能作参考，不能把差异全部归于可见话轮。本轮结构化 full-world 是作者指定的真值参照，不是另一次完整对话模型预测。','',
              '## E4：反事实可信性','']
    rows=[]
    for method,m in four.items():
        h=m['hidden_true_or_false_iguana'];u=m['unspecified_sailboat']
        rows.append([method,m['opposite_holder_pairs'],m['both_correct_pairs'],f"{h['unknown']}/{h['views']}",h['unsupported_definite_guesses'],f"{u['unknown']}/{u['views']}"])
    lines += [table(['方法','相反归属对','一对两侧均正确','不可识别鬣蜥：unknown','鬣蜥无依据猜测','未设定帆船：unknown'],rows),'',
              '属性交换通过相反归属对检验；第三方 Casey→A 的持有者交换通过同事实反事实检验；证据删除在 E3 中逐项运行。只发生预测翻转而两侧均错不算成功。鬣蜥的两个隐藏真值世界使用完全相同 A 和请求，因此复用同一输出；不会把重复发送相同输入当作额外独立证据。详见 `E4.json`。','',
              '## E5：领域、表面形式和语言稳健性','',
              '将受控校准阈值冻结后迁移到替代模板、作者编写的中文语义对应版本和自然对话。下表使用共同的受控测试世界，名义指标不加阈值；完整阈值迁移、领域分层和配对区间见 `E5.json`。','']
    rows=[]
    for method,m in five['methods'].items():
        for cond,z in m['conditions'].items():
            p=z['nominal'];rows.append([method,cond,p['views'],p['true_positive_recoveries'],p['grounded_true_recoveries'],p['unsupported_assertions'],pct(z['transferred_threshold']['nonverified_fraction'])])
    lines += [table(['方法','输入条件','测试视图','正确正事实','有支持正事实','无支持断言','迁移阈值 nonverified'],rows),'',
              '**未完成独立模型家族复验。** 新增调用使用指定的 `qwen3.8-flash`；历史 `qwen-plus` 也属于同一家族。中文与英文表面改写有混杂，未做独立翻译一致性／自然度审核；无任务训练，因此“未见模板”指阈值未在该变体上选择，不代表模型预训练未见过。','']
    lines += [f"原有手写英文模板／持有者代换中检测到 {five['surface_quality']['flagged_turns']} 处保守语法标记（例如 me would、you … is），保留在 `surface_quality_flags.csv`。E5.json 同时报告按整对场景排除这些表面形式问题的敏感性分析；主数据和主结果未改写，语法标记不是完整人工自然度评价。",'']
    hist=five['historical_model_comparison'];hr=[]
    for scope,z in hist['cohorts'].items():
        for model,m in z['models'].items():hr.append([scope,model,m['views'],m['true_positive_recoveries'],m['grounded_true_recoveries'],m['unsupported_assertions']])
    lines += [f"保存的历史 stage-2 A-only 对照有 {hist['exact_payload_pairs_ignoring_model']}/{hist['available_prompt_pairs']} 对请求在去掉 model 字段后完全相同。它检验旧固定目录提示下的模型版本变化，不检验新 RECOVER-B 的跨模型迁移；原始响应没有置信度，故不虚构其风险曲线。",'',
              table(['历史对照人群','模型','视图','正确正事实','有支持正事实','无支持断言'],hr),'',
              '## 结论的范围与剩余研究工作','',
              '本轮可以检验：这些固定场景上哪些事实被实际恢复，重建后多了哪些无支持断言，联合话轮比单轮多恢复了什么，以及前缀增加时输出何时上升或下降。不能把经验风险曲线叫作理论信息恢复上限，也不能把自然对话设定当作真实私人信息泄露率。','',
              '逐项方法分歧见 `case_studies_method_disagreements.csv`；每次正确正事实获得／失去对应的新增 A 发言、预测和证据见 `case_studies_prefix_transitions.csv`。这些是可检查的案例导出，不会据此回改真值或挑选重跑。','',
              '下一阶段仍需独立人工 gold／证据裁决、目录外事实核验与漏检测量、不同模型家族、强基线官方复现、严格预算匹配和可训练 SGCI／归属对比模块。`human_review/` 提供空白双人审核栏；这些工作没有伪造为已完成。','',
              'DailyDialog 可能进入模型预训练，按对话划分校准／测试并不能排除预训练污染；未获得供应商训练集审计。模型使用服务别名，未来更新也可能影响逐字复现；原始返回、请求参数和哈希均保留。','',
              '## 复现','',
              '无需 API：','',
              '```powershell\npython -m unittest discover -s experiments -p test_isc3.py -v\npython experiments/isc3_local_reconstruction_audit.py\npython experiments/isc3_analyze.py\npython experiments/isc3_report.py\n```','',
              '新增调用从环境变量 `DASHSCOPE_API_KEY` 或 stdin 读取凭据；`isc3_run.py` 可跳过已成功请求。存在未返回的已记录尝试时先停止并审计，不能悄悄重发潜在已计费请求。','']
    (OUT/'实验报告.md').write_text('\n'.join(lines),encoding='utf-8')
    review_packet()
    print('Wrote results/isc3/实验报告.md and human_review packet')

if __name__=='__main__':main()
