"""Controlled v3/v4 joint matching; unchanged prompts-v2 and scoring functions."""
import os
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
from .common import BASE,read,save,freeze,digest,filehash
from .client import Client,URL
from .inference import payload
from .evaluate_prompts_v2 import load_prompt,validate_v2
from .evaluation import reference_map,_prediction_inventory,_reference_inventory,score_item,cost_map
from .statistics import four_metrics

RUN='evidence_adaptive_v4_joint_evaluation'
OUT=BASE/'results'/RUN

def run(workers=8,replay=False):
 methods=('evidence_adaptive_v3','evidence_adaptive_v4')
 files=('runs/evidence_adaptive_v3_append/exports/dailydialog.json','runs/evidence_adaptive_v4_append/exports/dailydialog.json')
 groups={}
 for path in files:
  ps=read(BASE/path);assert len(ps)==298
  for p in ps:groups.setdefault((p['dialogue_id'],p['direction']),[]).append(p)
 refs=reference_map('dailydialog');assert set(groups)==set(refs)
 prompt=load_prompt();jobs=[]
 for (did,direction),arms in sorted(groups.items()):
  assert tuple(p['method'] for p in arms)==methods
  pp=_prediction_inventory(arms);rr=_reference_inventory(refs[(did,direction)])
  content=dict(predictions=pp,reference=rr,subject_mapping={'hidden partner / target':'original B','visible speaker / observer':'original A'},persona_reference_rule='In persona references I/my refer to the hidden target, never the observer.',matcher_prompt_sha256=digest(prompt))
  request=payload(prompt,content,4096);binding=digest(dict(request=request,endpoint=URL,adapter_version=1))
  jobs.append(dict(dialogue_id=did,direction=direction,pp=pp,rr=rr,request=request,binding=binding))
 freeze(OUT/'manifest.json',dict(input_count=298,prediction_files={p:filehash(BASE/p) for p in files},reference_sha256=filehash(BASE/'references/dailydialog_human_adjudicated_588.json'),prompt_sha256=filehash(BASE/'prompts-v2.py'),jobs_digest=digest(jobs),model='qwen3.8-flash',thinking_budget=512,max_tokens=4096,original_results_modified=False,selection='predeclared single shared judgment per exact text; no consensus or prompt change'))
 def path(j):return OUT/'matches'/(j['dialogue_id']+'__A_to_B.json')
 def cached(j):
  if not path(j).exists():return None
  obj=read(path(j))
  if obj['binding']!=j['binding']:raise ValueError('Stale joint cache')
  return validate_v2(obj,j['pp'],j['rr'])
 pending=[j for j in jobs if cached(j) is None]
 if replay and pending:raise RuntimeError('Joint replay requires all cached matches')
 needs=any(j['pp'] and j['rr'] for j in pending)
 client=Client(os.environ.get('QWEN_API_KEY') or os.environ.get('DASHSCOPE_API_KEY'),run_id=RUN) if needs else None
 def work(j):
  tid=None
  if not j['pp']:ms=[]
  elif not j['rr']:ms=[dict(prediction_id=p['prediction_id'],reference_ids=[],relation='none') for p in j['pp']]
  else:ms,tid=client.call('v3_v4_joint/'+j['dialogue_id']+'/'+j['binding'],j['request'],lambda obj:validate_v2(obj,j['pp'],j['rr']))
  save(path(j),dict(binding=j['binding'],matches=ms,task_id=tid,shared_exact_text_judgment=True))
 errors=[]
 if pending:
  work(pending[0]);print('Joint first item complete',flush=True)
 with ThreadPoolExecutor(max_workers=workers) as pool:
  futures={pool.submit(work,j):j for j in pending[1:]}
  for n,f in enumerate(as_completed(futures),2):
   try:f.result()
   except Exception as exc:errors.append(dict(dialogue_id=futures[f]['dialogue_id'],error=str(exc)))
   if n%20==0 or n==len(pending):print(dict(joint_finished=n,total=len(pending),errors=len(errors)),flush=True)
 save(OUT/'status.json',dict(complete=not errors,errors=errors,matched_inputs=sum(cached(j) is not None for j in jobs)))
 if errors:raise RuntimeError('Joint incomplete: inspect status and resume')
 assert all(cached(j) is not None for j in jobs)
 costs={}
 for folder in ('evidence_adaptive_v1_append','evidence_adaptive_v2_corrected','evidence_adaptive_v4_append'):costs.update(cost_map(folder))
 result={}
 for policy,accepted in [('equivalent_only',('equivalent',)),('broader_counted_as_hit',('equivalent','broader'))]:
  rows=[score_item(p,refs[(j['dialogue_id'],j['direction'])],cached(j),costs,accepted_relations=accepted) for j in jobs for p in groups[(j['dialogue_id'],j['direction'])]]
  table=[dict(method=m,**four_metrics([r for r in rows if r['method']==m])) for m in methods]
  save(OUT/policy/'per_input.json',rows);save(OUT/policy/'four_metrics.json',table);result[policy]=table
 save(OUT/'four_metrics_both_policies.json',result)
 lines=['# v3/v4 同批联合匹配稳健性对照','','保持 prompts-v2.py、历史解析器和原四指标；相同预测文本在同一对话只获得一个语义判断。没有修改历史主表。','', '| 口径 | 算法 | Precision | Recall | Grounded Recall | 平均 token |','|---|---|---:|---:|---:|---:|']
 for policy,table in result.items():
  for r in table:
   tok='N/A' if r['mean_tokens'] is None else f"{r['mean_tokens']:.4f}"
   lines.append(f"| {policy} | {r['method']} | {r['precision']:.4%} | {r['recall']:.4%} | {r['grounded_recall']:.4%} | {tok} |")
 (OUT/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8');print(result['equivalent_only'],flush=True)
 return result

if __name__=='__main__':
 p=argparse.ArgumentParser(__doc__);p.add_argument('--workers',type=int,default=8);p.add_argument('--replay',action='store_true');a=p.parse_args();run(a.workers,a.replay)
