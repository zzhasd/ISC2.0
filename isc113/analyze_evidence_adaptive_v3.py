"""Read-only experiment analysis; writes only new v2 diagnostic artifacts."""
import importlib
import random
from collections import Counter
from .common import BASE, read, save, jsonlines
from .inference import decode

OUT=BASE/'results/evidence_adaptive_v3_append'

def analyze():
    result=read(OUT/'four_metrics_both_policies.json')
    table=result['equivalent_only'];new=table[-1];old=next(r for r in table if r['method']=='evidence_adaptive_v1')
    assert new['method']=='evidence_adaptive_v3' and old['method']=='evidence_adaptive_v1'
    a={r['dialogue_id']:r for r in read(OUT/'equivalent_only/per_input.json')}
    b={r['dialogue_id']:r for r in read(BASE/'results/evidence_adaptive_v1_append/equivalent_only/per_input.json')}
    assert a.keys()==b.keys() and len(a)==298
    ids=sorted(a);rng=random.Random(113)
    keys=['correct_output_assertions','predictions','true_tp','true_reference','supported_tp','supported_reference']
    av=[[a[i][k] for k in keys] for i in ids];bv=[[b[i][k] for k in keys] for i in ids]
    draws={k:[] for k in ('precision','recall','grounded_recall')}
    for _ in range(2000):
        sa=[0]*6;sb=[0]*6
        for _ in ids:
            index=rng.randrange(len(ids))
            for j in range(6):sa[j]+=av[index][j];sb[j]+=bv[index][j]
        for j,name in enumerate(draws):
            if sa[2*j+1] and sb[2*j+1]:draws[name].append(sa[2*j]/sa[2*j+1]-sb[2*j]/sb[2*j+1])
    def quantile(xs,p):
        ys=sorted(xs);i=(len(ys)-1)*p;lo=int(i);return ys[lo]+(ys[min(lo+1,len(ys)-1)]-ys[lo])*(i-lo)
    uncertainty={k:dict(delta=new[k]-old[k],ci95=[quantile(v,.025),quantile(v,.975)],resamples=len(v)) for k,v in draws.items()}
    save(OUT/'paired_uncertainty.json',dict(comparison='v3 minus v1',seed=113,clusters=298,metrics=uncertainty,adaptive_benchmark=True))
    goal=dict(precision_leads_all_previous=new['precision']>max(r['precision'] for r in table[:-1]),recall_improved=new['recall']>old['recall'],grounded_recall_improved=new['grounded_recall']>old['grounded_recall'])
    goal['all_point_estimate_targets_met']=all(goal.values())
    goal['out_of_sample_precision_guaranteed']=False
    save(OUT/'upgrade_goal_check.json',goal)
    changes={key:dict(improved=sum(a[i][key]>b[i][key] for i in ids),unchanged=sum(a[i][key]==b[i][key] for i in ids),worse=sum(a[i][key]<b[i][key] for i in ids)) for key in ('true_tp','supported_tp')}
    save(OUT/'per_dialogue_gain_loss.json',changes)
    v=importlib.import_module('isc113.Evidence-Adaptive v3')
    items={x['item_id']:x for x in read(BASE/'inputs/dailydialog.json')}
    counts=Counter();levels=Counter();seen=set()
    source_raw=[r for folder in ('evidence_adaptive_v1_append','evidence_adaptive_v2_corrected') for r in jsonlines(BASE/'runs'/folder/'attempts.jsonl')]
    for row in source_raw:
        if row['event']!='complete' or not row.get('valid') or row['task_id'] in seen:continue
        seen.add(row['task_id']);stage='anchor' if row['logical_name'].endswith('/evidence_adaptive') else ('review' if row['logical_name'].endswith('/adaptive_v2_review') else 'coverage')
        item_id=row['logical_name'].rsplit('/',1)[0];turns=items[item_id]['visible_turns']
        claims=decode(row['body'])['claims']
        if stage=='anchor':
            hypothetical=v.align_evidence(claims,turns)
            counts['anchor_hypothetical_whitespace_recoverable']+=sum(not v.valid_evidence(c['evidence'],turns) and q['evidence_span_valid'] for c,q in zip(claims,hypothetical))
            aligned=[dict(c,evidence_span_valid=v.valid_evidence(c['evidence'],turns)) for c in claims]
        else:
            aligned=v.align_evidence(claims,turns)
        counts[stage+'_raw']+=len(claims)
        counts[stage+'_invalid_before_alignment']+=sum(not v.valid_evidence(c['evidence'],turns) for c in claims)
        counts[stage+'_whitespace_repaired']+=sum(bool(c.get('whitespace_alignment')) for c in aligned)
        counts[stage+'_invalid_after_alignment']+=sum(not c['evidence_span_valid'] for c in aligned)
        if stage=='review':levels.update(c['evidence_level'] for c in claims)
    save(OUT/'stage_audit.json',dict(counts=dict(counts),review_levels=dict(levels)))
    pilot=read(BASE/'results/evidence_adaptive_v2_append/status.json')
    known=read(OUT/'transport_usage_audit.json')
    actual_v2=read(BASE/'results/evidence_adaptive_v2_corrected/transport_usage_audit.json')
    save(OUT/'development_cost_audit.json',dict(v3_modeled_full_pipeline_observed_tokens=known['observed_inference_tokens'],v3_new_inference_api_calls=0,v2_new_observed_inference_tokens=actual_v2['observed_inference_tokens'],schema_trial_observed_tokens=pilot['observed_tokens'],schema_trial_unresolved_attempts=len(pilot['unresolved_attempt_ids']),schema_trial_in_final_metric=False,turn_new_observed_inference_tokens_excluding_evaluation=actual_v2['observed_inference_tokens']+pilot['observed_tokens'],reused_tokens_not_rebilled=True,unknown_usage_imputed=False))
    lines=['# Evidence-Adaptive v3 升级分析','',
           '依据同一 298 段旧记录诊断后升级，是适应性追加实验。没有独立留出验证，点估计领先不构成样本外精度保证。区间条件于已记录输出，不校正适应性开发或模型采样不确定性。','',
           '| 指标 | v1 | v3 | 差值（百分点） | 配对对话 bootstrap 95% 区间（百分点） |',
           '|---|---:|---:|---:|---:|']
    for name,d in uncertainty.items():
        lines.append(f"| {name} | {old[name]:.4%} | {new[name]:.4%} | {100*d['delta']:+.4f} | [{100*d['ci95'][0]:+.4f}, {100*d['ci95'][1]:+.4f}] |")
    lines+=['',f"点估计目标检查：{goal}",'',
            f"v1 输出 {old['output_assertions']} 条，严格正确 {old['correct_output_assertions']} 条，恢复 {old['recovered_reference_attributes']}/588、有据恢复 {old['recovered_grounded_reference_attributes']}/262；v3 输出 {new['output_assertions']} 条，严格正确 {new['correct_output_assertions']} 条，恢复 {new['recovered_reference_attributes']}/588、有据恢复 {new['recovered_grounded_reference_attributes']}/262。",'',
            f"阶段审计：{dict(counts)}；复核等级：{dict(levels)}。",'',
            f"逐对话召回计数变化：{changes}。",'',
            '配置：v1 主干（256/1536）＋v2 覆盖生成及独立复核（每阶段 512/3072）；仅追加 E1，temperature=0。不读取参考或完整 B。v1 主干保持原引用和问号过滤；只有 v2 覆盖分支使用唯一空白定位与语义问句复核。anchor_hypothetical_whitespace_recoverable 仅为诊断潜力，不是 v1 实际修复。没有按本轮结果挑选置信度阈值。','',
            f"完整新轮已知推断 token {known['observed_inference_tokens']:,}，已知用量下界 {known['mean_observed_tokens']:.6f}/段。严格平均按原缺失 usage 规则，详见 transport_usage_audit.json。完整三阶段计入成本，推断复用已有同请求响应但本轮独立重评融合输出；这增加部署时的调用成本，不能把 token 下界直接当成精确节省。",'',
            f"首批 JSON 示例接口错误的中止轮另有已知推断 token {pilot['observed_tokens']:,}、{len(pilot['unresolved_attempt_ids'])} 个未知在途状态，完整保留，不纳入最终模型性能行；开发用量单列于 development_cost_audit.json。",'',
            'E1/E2 分层属于本轮完成后诊断，v3 是再次适应性修订；不能据此声称独立泛化保证。', '',
            '主报告 REPORT.md 包含十算法严格及宽松四指标。原八算法及失败的 v2 覆盖扩张版均保留；历史哈希和离线重放单独核验。']
    (OUT/'UPGRADE_ANALYSIS.md').write_text('\n'.join(lines),encoding='utf-8')
    print(goal)
    print(uncertainty)

if __name__=='__main__':analyze()
