"""Offline read-only replay of v4/v5 predictions, matcher bindings and scores."""
import importlib
from .common import BASE,read,jsonlines,digest,filehash,save
from .inference import decode,payload
from .client import URL
from .evaluate_prompts_v2 import load_prompt,validate_v2
from .evaluation import reference_map,_prediction_inventory,_reference_inventory,score_item,cost_map
from .statistics import four_metrics

def verify():
 cache={};costs={}
 for folder in ('evidence_adaptive_v2_corrected','evidence_adaptive_v4_append','evidence_adaptive_v5_append'):
  costs.update(cost_map(folder))
  for r in jsonlines(BASE/'runs'/folder/'attempts.jsonl'):
   if r['event']=='complete' and r.get('valid'):cache.setdefault(r['task_id'],r)
 class Recorded:
  def call(self,name,request,validate):
   tid=digest({'logical_name':name,'payload':request});return validate(decode(cache[tid]['body'])),tid
 refs=reference_map('dailydialog');prompt=load_prompt();items=read(BASE/'inputs/dailydialog.json')
 for version in (4,5):
  folder=BASE/'runs'/f'evidence_adaptive_v{version}_append';out=BASE/'results'/folder.name;module=importlib.import_module(f'isc113.Evidence-Adaptive v{version}');ps=read(folder/'exports/dailydialog.json');assert len(ps)==298
  scores={k:[] for k in ('equivalent_only','broader_counted_as_hit')}
  for item,p in zip(items,ps):
   assert module.pipeline(Recorded(),item)==[p]
   pp=_prediction_inventory([p]);rr=_reference_inventory(refs[(p['dialogue_id'],p['direction'])]);content=dict(predictions=pp,reference=rr,subject_mapping={'hidden partner / target':'original B','visible speaker / observer':'original A'},persona_reference_rule='In persona references I/my refer to the hidden target, never the observer.',matcher_prompt_sha256=digest(prompt));req=payload(prompt,content,4096);obj=read(out/'matches'/(p['dialogue_id']+'__A_to_B.json'))
   assert obj['binding']==digest(dict(request=req,endpoint=URL,adapter_version=1));ms=validate_v2(obj,pp,rr)
   if version==5:
    parent=read(BASE/'results/evidence_adaptive_v4_append/matches'/(p['dialogue_id']+'__A_to_B.json'));ids={x['prediction_id'] for x in pp};assert ms==[m for m in parent['matches'] if m['prediction_id'] in ids]
   for policy,accepted in [('equivalent_only',('equivalent',)),('broader_counted_as_hit',('equivalent','broader'))]:scores[policy].append(score_item(p,refs[(p['dialogue_id'],p['direction'])],ms,costs,accepted_relations=accepted))
  result=read(out/'four_metrics_both_policies.json')
  for policy,rows in scores.items():assert dict(method=f'evidence_adaptive_v{version}',**four_metrics(rows))==result[policy][-1]
  protect=read(folder/'historical_hashes.json');changed=[p for p,h in protect.items() if filehash(BASE/p)!=h];assert not changed,changed
  save(out/'offline_reproduction_audit.json',dict(inputs=298,predictions_identical=True,all_matcher_bindings_valid=True,both_policy_scores_identical=True,source_selection_unchanged=True,new_api_calls=0,protected_files_checked=len(protect),changed=changed))
 original=read(BASE/'runs/evidence_adaptive_v1_append/historical_hashes.json');assert all(filehash(BASE/p)==h for p,h in original.items())
 print('V4/V5 offline predictions, bindings, both-policy scores and original 1623 files verified.')
if __name__=='__main__':verify()
