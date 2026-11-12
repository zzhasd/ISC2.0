"""Paired comparison and accounting for the fixed v4 append experiment."""
import random
from collections import Counter
from .common import BASE,read,save,jsonlines
from .inference import decode

OUT=BASE/'results/evidence_adaptive_v5_append'

def analyze():
 tables=read(OUT/'four_metrics_both_policies.json');table=tables['equivalent_only'];new=table[-1];old=next(x for x in table if x['method']=='evidence_adaptive_v3')
 a={r['dialogue_id']:r for r in read(OUT/'equivalent_only/per_input.json')};b={r['dialogue_id']:r for r in read(BASE/'results/evidence_adaptive_v3_append/equivalent_only/per_input.json')};assert a.keys()==b.keys() and len(a)==298
 ids=sorted(a);keys=['correct_output_assertions','predictions','true_tp','true_reference','supported_tp','supported_reference'];av=[[a[i][k] for k in keys] for i in ids];bv=[[b[i][k] for k in keys] for i in ids];rng=random.Random(113);draws={k:[] for k in ('precision','recall','grounded_recall')}
 for _ in range(2000):
  sa=[0]*6;sb=[0]*6
  for _ in ids:
   i=rng.randrange(298)
   for j in range(6):sa[j]+=av[i][j];sb[j]+=bv[i][j]
  for j,k in enumerate(draws):
   if sa[j*2+1] and sb[j*2+1]:draws[k].append(sa[j*2]/sa[j*2+1]-sb[j*2]/sb[j*2+1])
 def q(xs,p):
  ys=sorted(xs);i=(len(ys)-1)*p;lo=int(i);return ys[lo]+(ys[min(lo+1,len(ys)-1)]-ys[lo])*(i-lo)
 stats={k:dict(delta=new[k]-old[k],ci95=[q(xs,.025),q(xs,.975)]) for k,xs in draws.items()};save(OUT/'paired_uncertainty.json',dict(comparison='v5 minus v3',clusters=298,resamples=2000,seed=113,metrics=stats,adaptive_benchmark=True))
 usage=read(OUT/'transport_usage_audit.json');prior=read(BASE/'results/evidence_adaptive_v3_append/transport_usage_audit.json');goals={k:new[k]>old[k] for k in draws};goals['all_three_accuracy_improved']=all(goals.values());goals['precision_leads_frozen_prior_table']=new['precision']>max(x['precision'] for x in table[:-1]);goals['observed_token_lower_bound_decreased']=usage['mean_observed_tokens']<prior['mean_observed_tokens'];goals['strict_mean_token_improvement_proven']=new['mean_tokens'] is not None and old['mean_tokens'] is not None and new['mean_tokens']<old['mean_tokens'];goals['generalization_guaranteed']=False;save(OUT/'upgrade_goal_check.json',goals)
 ps=read(BASE/'runs/evidence_adaptive_v5_append/exports/dailydialog.json');relations=Counter();mechanisms={};empty=sum(not p['claims'] for p in ps)
 from .common import digest
 for p in ps:
  ms=read(OUT/'matches'/(p['dialogue_id']+'__A_to_B.json'))['matches'];by={m['prediction_id']:m for m in ms}
  for c in p['claims']:
   r=by[digest(c['claim'])]['relation'];relations[r]+=1;mechanisms.setdefault(c['mechanism'],Counter())[r]+=1
 save(OUT/'output_audit.json',dict(outputs=sum(len(p['claims']) for p in ps),empty_inputs=empty,relations=dict(relations),mechanisms={k:dict(v) for k,v in mechanisms.items()}))
 source=[r for r in jsonlines(BASE/'runs/evidence_adaptive_v2_corrected/attempts.jsonl') if r['logical_name'].endswith('/adaptive_v2_coverage')]+[r for r in jsonlines(BASE/'runs/evidence_adaptive_v4_append/attempts.jsonl') if r['logical_name'].endswith('/adaptive_v4_reconstruct')];current=jsonlines(BASE/'runs/evidence_adaptive_v5_append/attempts.jsonl');used={t for p in ps for t in p['task_ids']}
 expected=sum(r.get('body',{}).get('usage',{}).get('total_tokens',0) for r in source+current if r['event']=='complete' and r['task_id'] in used);assert expected==usage['observed_inference_tokens']
 own=sum(r.get('body',{}).get('usage',{}).get('total_tokens',0) for r in current if r['event']=='complete');coverage=expected-own
 save(OUT/'cost_provenance_audit.json',dict(used_task_ids=len(used),reused_coverage_and_reconstruction_observed_tokens=coverage,new_pragmatic_verifier_observed_tokens=own,full_algorithm_observed_tokens=expected,unused_v2_review_tokens_charged=False,reused_coverage_rebilled=False,unknown_usage_imputed=False))
 changes={k:dict(improved=sum(a[i][k]>b[i][k] for i in ids),worse=sum(a[i][k]<b[i][k] for i in ids),unchanged=sum(a[i][k]==b[i][k] for i in ids)) for k in ('true_tp','supported_tp')};save(OUT/'per_dialogue_gain_loss.json',changes)
 lines=['# v5 完整比较与研究结论','','固定 298 段适应性追加实验。无独立留出集；区间条件于已记录响应，不校正选择或模型采样。','', '| 指标 | v3 | v5 | 差值（百分点） | 配对 95% 区间（百分点） |','|---|---:|---:|---:|---:|']
 for k,s in stats.items():lines.append(f"| {k} | {old[k]:.4%} | {new[k]:.4%} | {100*s['delta']:+.4f} | [{100*s['ci95'][0]:+.4f}, {100*s['ci95'][1]:+.4f}] |")
 lines+=['',f"目标检查：{goals}",'',f"已知 token/段：v3 {prior['mean_observed_tokens']:.6f}，v5 {usage['mean_observed_tokens']:.6f}。v5 mean_tokens={new['mean_tokens']}；存在未知 usage 时不能宣称严格第四指标已改善。完整流程已知 {expected:,} token，其中复用覆盖与重构 {coverage:,}，新隐式审查 {own:,}。排除了未使用的 v2 review。",'',f"输出关系：{dict(relations)}；空输出 {empty}；逐对话增减 {changes}。",'',f"严格计数：正确输出 {new['correct_output_assertions']}/{new['output_assertions']}，恢复 {new['recovered_reference_attributes']}/588，有据恢复 {new['recovered_grounded_reference_attributes']}/262。",'', '研究依据及预设方案见 ../evidence_adaptive_v4_research/RESEARCH.md；完整十三算法严格/宽松四指标见 REPORT.md。', '', '原十算法行没有改动。EFCR v2 仅追加自身已有行，未用其联合重新评价替换原六算法行。未改写任何匹配判断。']
 (OUT/'UPGRADE_ANALYSIS.md').write_text('\n'.join(lines),encoding='utf-8');print(goals);print(stats);print(new);print({'known_mean_tokens':usage['mean_observed_tokens']})

if __name__=='__main__':analyze()
