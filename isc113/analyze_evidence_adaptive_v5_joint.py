"""Reuse one binding-verified joint judgment for unchanged v5 subsets."""
from .common import BASE,read,save,digest,filehash
from .evaluation import reference_map,_prediction_inventory,_reference_inventory,score_item,cost_map
from .evaluate_prompts_v2 import load_prompt,validate_v2
from .inference import payload
from .client import URL
from .statistics import four_metrics

def analyze():
 out=BASE/'results/evidence_adaptive_v5_append/joint_control';joint=BASE/'results/evidence_adaptive_v4_joint_evaluation'
 versions={m:{p['item_id']:p for p in read(BASE/'runs'/folder/'exports/dailydialog.json')} for m,folder in [('evidence_adaptive_v3','evidence_adaptive_v3_append'),('evidence_adaptive_v4','evidence_adaptive_v4_append'),('evidence_adaptive_v5','evidence_adaptive_v5_append')]}
 refs=reference_map('dailydialog');prompt=load_prompt();costs={}
 for folder in ('evidence_adaptive_v1_append','evidence_adaptive_v2_corrected','evidence_adaptive_v4_append','evidence_adaptive_v5_append'):costs.update(cost_map(folder))
 all_rows={k:[] for k in ('equivalent_only','broader_counted_as_hit')}
 for item in read(BASE/'inputs/dailydialog.json'):
  did=item['dialogue_id'];key=(did,item['direction']);p3=versions['evidence_adaptive_v3'][item['item_id']];p4=versions['evidence_adaptive_v4'][item['item_id']];p5=versions['evidence_adaptive_v5'][item['item_id']]
  full=_prediction_inventory([p3,p4]);rr=_reference_inventory(refs[key]);content=dict(predictions=full,reference=rr,subject_mapping={'hidden partner / target':'original B','visible speaker / observer':'original A'},persona_reference_rule='In persona references I/my refer to the hidden target, never the observer.',matcher_prompt_sha256=digest(prompt));req=payload(prompt,content,4096)
  cache=read(joint/'matches'/(did+'__A_to_B.json'));assert cache['binding']==digest(dict(request=req,endpoint=URL,adapter_version=1));ms=validate_v2(cache,full,rr)
  assert all(c in p4['claims'] for c in p5['claims'])
  formal=dict(p5,method='v5_formal_linguistic_ablation',claims=[c for c in p5['claims'] if c['mechanism'] in ('explicit','presupposition')])
  for policy,accepted in [('equivalent_only',('equivalent',)),('broader_counted_as_hit',('equivalent','broader'))]:
   for p in (p3,p4,p5,formal):all_rows[policy].append(score_item(p,refs[key],ms,costs,accepted_relations=accepted))
 result={}
 methods=('evidence_adaptive_v3','evidence_adaptive_v4','evidence_adaptive_v5','v5_formal_linguistic_ablation')
 for policy,rows in all_rows.items():
  table=[dict(method=m,**four_metrics([r for r in rows if r['method']==m])) for m in methods];result[policy]=table;save(out/policy/'per_input.json',rows);save(out/policy/'four_metrics.json',table)
  assert table[:2]==read(joint/'four_metrics_both_policies.json')[policy]
 save(out/'four_metrics_both_policies.json',result);save(out/'provenance.json',dict(joint_manifest_sha256=filehash(joint/'manifest.json'),all_298_parent_bindings_verified=True,new_api_calls=0,labels_modified=False,subset_filter_used_reference=False,posthoc_formal_filter_is_diagnostic_only=True))
 lines=['# 同一判断下的稳健性对照','','完全复用已绑定的 v3/v4 联合评审；相同文本判定相同，v5 为 v4 不变子集。formal 筛选仅为事后消融，未作为正式升级。没有修改历史主表。','','| 算法 | Precision | Recall | Grounded Recall |','|---|---:|---:|---:|']
 for r in result['equivalent_only']:lines.append(f"| {r['method']} | {r['precision']:.4%} | {r['recall']:.4%} | {r['grounded_recall']:.4%} |")
 (out/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8');print(result['equivalent_only'])
if __name__=='__main__':analyze()
