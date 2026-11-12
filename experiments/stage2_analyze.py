"""Read-only analysis of fixed-catalogue, hidden-speaker recovery."""
from pathlib import Path
import collections
import csv
import hashlib
import json
import numpy as np
try:
 from .stage2_parse import normalize_targets,decode_response
except ImportError:
 from stage2_parse import normalize_targets,decode_response

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/stage2';OUT=ROOT/'results/stage2'
LABELS={'true','false','unknown'}

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

def parse_calls():
 gold=read(DATA/'gold.json'); indexed={(r['dialogue_id'],r['target_source_speaker'],r['attribute']):r for r in gold}
 requests={t['task_id']:t for t in read(OUT/'requests.json')}
 dialogues={r['id']:r for r in read(DATA/'dialogues.json')}
 inventory={r['id'] for r in read(DATA/'inventory.json')}
 calls=[json.loads(x) for x in (OUT/'api_raw.jsonl').read_text(encoding='utf-8').splitlines()]
 predictions=[]; errors=[]; prior=None; repeat_rows=[]; seen=set()
 for call in calls:
  try:
   assert call['task_id'] in requests, 'Unexpected task'
   assert call.get('http_status')==200,'HTTP failure'
   assert call['task_id'] not in seen,'Duplicate successful task result'
   seen.add(call['task_id'])
   assert call['body']['choices'][0]['finish_reason']=='stop','Incomplete generation'
   request=requests[call['task_id']]
   text=call['body']['choices'][0]['message']['content']
   expected={'S0','S1'} if call['condition']=='full' else {'B'}
   decoded,malformed_json=decode_response(text)
   output,normalized=normalize_targets(decoded,expected)
   normalized=normalized or malformed_json
   missing=sorted(expected-{x['target'] for x in output})
   call['parse_audit']={'structural_normalization':normalized,'missing_targets':missing,'malformed_json':malformed_json}
   if missing:errors.append({'task_id':call['task_id'],'condition':call['condition'],'error':'Missing target output; available target retained','missing_targets':missing})
   request_content=json.loads(request['payload']['messages'][1]['content'])
   turn_count=len(request_content['transcript'])
   parsed=[]
   for target in output:
    facts=target['facts']
    assert len(facts)==len(inventory) and {f['id'] for f in facts}==inventory,'Missing or duplicate catalogue ids'
    for fact in facts:
     assert fact['label'] in LABELS,'Invalid label'
     ev=fact.get('evidence_turns',[])
     assert isinstance(ev,list) and all(isinstance(i,int) and not isinstance(i,bool) and 1<=i<=turn_count for i in ev),'Invalid evidence turn'
     if call['condition']=='prior':
      parsed.append({'attribute':fact['id'],'prediction':fact['label'],'evidence_turns':ev});continue
     source=int(target['target'][1]) if call['condition']=='full' else call['target_source_speaker']
     g=indexed[(call['dialogue_id'],source,fact['id'])]
     row={**g,'condition':call['condition'],'prediction':fact['label'],
          'model_evidence_turns':ev,'request_id':call['task_id'],'normalized_response_structure':normalized}
     if call['condition']=='full':original_evidence=ev
     else:
      visible_original=[i+1 for i in range(len(dialogues[call['dialogue_id']]['turns'])) if i%2!=source]
      original_evidence=[visible_original[i-1] for i in ev]
     row['model_evidence_original_turns']=original_evidence
     row['evidence_intersects_prelabelled_support']=bool(set(original_evidence)&set(g['a_evidence_turns'])) if call['condition']!='full' else bool(set(original_evidence)&set(g['full_evidence_turns']))
     row['definite_without_evidence']=fact['label']!='unknown' and not ev
     parsed.append(row)
   if call['condition']=='prior':prior=parsed
   elif call['condition']=='repeat':repeat_rows.extend(parsed)
   else:predictions.extend(parsed)
  except (AssertionError,KeyError,ValueError,TypeError,IndexError) as exc:
   errors.append({'task_id':call.get('task_id'),'condition':call.get('condition'),'error':str(exc)})
 if prior is not None:
  for g in gold:
   f=next(x for x in prior if x['attribute']==g['attribute'])
   predictions.append({**g,'condition':'prior','prediction':f['prediction'],
                       'model_evidence_turns':f['evidence_turns'],'model_evidence_original_turns':[],
                       'evidence_intersects_prelabelled_support':False,'definite_without_evidence':f['prediction']!='unknown',
                       'request_id':'shared_empty_evidence_catalogue'})
 return predictions,repeat_rows,errors,calls

def counts(rows):
 pos=[r for r in rows if r['truth']=='true']
 known=[r for r in rows if r['truth']!='unknown']
 unknown=[r for r in rows if r['truth']=='unknown']
 assertions=[r for r in rows if r['prediction']=='true']
 tp=[r for r in assertions if r['truth']=='true']
 fp=[r for r in assertions if r['truth']=='false']
 up=[r for r in assertions if r['truth']=='unknown']
 view={r['view_id'] for r in rows};true_views={r['view_id'] for r in pos};hit_views={r['view_id'] for r in tp}
 out={'decisions':len(rows),'views':len(view),'dialogues':len({r['dialogue_id'] for r in rows}),
      'gold_true':len(pos),'gold_false':sum(r['truth']=='false' for r in rows),'gold_unknown':len(unknown),
      'true_recoveries':len(tp),'recovery_rate':len(tp)/len(pos) if pos else None,
      'positive_assertions':len(assertions),'positive_assertions_known_false':len(fp),
      'positive_assertions_unverified_truth':len(up),
      'confirmed_fraction_of_positive_assertions':len(tp)/len(assertions) if assertions else None,
      'known_truth_conditional_positive_precision':len(tp)/(len(tp)+len(fp)) if tp or fp else None,
      'definite_wrong_on_known_truth':sum(r['prediction']!='unknown' and r['prediction']!=r['truth'] for r in known),
      'false_assertions_on_unknown_truth':sum(r['prediction']=='false' for r in unknown),
      'a_supported_true_gold':sum(r['truth']=='true' and r['a_support']=='true' for r in rows),
      'a_supported_true_recoveries':sum(r['a_support']=='true' for r in tp),
      'true_recoveries_without_prelabelled_A_support':sum(r['a_support']!='true' for r in tp),
      'views_with_gold_true':len(true_views),'views_with_true_recovery':len(hit_views),
      'fraction_all_views_with_true_recovery':len(hit_views)/len(view) if view else None,
      'fraction_positive_views_with_recovery':len(hit_views)/len(true_views) if true_views else None,
      'recoveries_per_view':len(tp)/len(view) if view else None,
      'recoveries_per_dialogue':len(tp)/len({r['dialogue_id'] for r in rows}) if rows else None,
      'label_accuracy_secondary':sum(r['prediction']==r['truth'] for r in rows)/len(rows) if rows else None,
      'definite_without_evidence':sum(r['definite_without_evidence'] for r in rows)}
 if rows and rows[0]['condition']=='a_only':
  unsupported=[r for r in rows if r['a_support']=='unknown']
  out['positive_assertions_without_prelabelled_A_support']=sum(r['prediction']=='true' for r in unsupported)
  out['negative_assertions_without_prelabelled_A_support']=sum(r['prediction']=='false' for r in unsupported)
  out['A_support_alignment_secondary']=sum(r['prediction']==r['a_support'] for r in rows)/len(rows)
 return out

def recovery_bootstrap(rows,seed=20261033):
 rng=np.random.default_rng(seed)
 grouped=collections.defaultdict(list)
 for r in rows:grouped[r['dialogue_id']].append(r)
 strata=collections.defaultdict(list)
 for group in grouped.values():
  strata[group[0]['arm']].append([sum(r['truth']=='true' and r['prediction']=='true' for r in group),sum(r['truth']=='true' for r in group)])
 numerator=np.zeros(5000);denominator=np.zeros(5000)
 for groups in strata.values():
  a=np.array(groups);draw=rng.integers(0,len(a),size=(5000,len(a)))
  numerator+=a[draw,0].sum(1);denominator+=a[draw,1].sum(1)
 valid=denominator>0
 if not valid.any():return {'ci95':None,'valid_bootstrap_samples':0,'requested_samples':5000}
 rates=numerator[valid]/denominator[valid]
 return {'ci95':np.quantile(rates,[.025,.975]).tolist(),'valid_bootstrap_samples':int(valid.sum()),'requested_samples':5000,
         'sampling_unit':'dialogue; both target views and all attributes clustered; arm-stratified'}

def paired_bootstrap(rows):
 by=collections.defaultdict(dict)
 for r in rows:by[(r['dialogue_id'],r['target_source_speaker'],r['attribute'])][r['condition']]=r
 pairs=[v for v in by.values() if 'a_only' in v and 'full' in v]
 grouped=collections.defaultdict(list)
 for p in pairs:grouped[p['a_only']['dialogue_id']].append(p)
 strata=collections.defaultdict(list)
 for group in grouped.values():
  den=sum(p['a_only']['truth']=='true' for p in group)
  a=sum(p['a_only']['truth']=='true' and p['a_only']['prediction']=='true' for p in group)
  f=sum(p['full']['truth']=='true' and p['full']['prediction']=='true' for p in group)
  strata[group[0]['a_only']['arm']].append([a,f,den])
 rng=np.random.default_rng(20261033);aa=np.zeros(5000);ff=np.zeros(5000);dd=np.zeros(5000)
 total=np.zeros(3)
 for groups in strata.values():
  a=np.array(groups);total+=a.sum(0);draw=rng.integers(0,len(a),size=(5000,len(a)))
  aa+=a[draw,0].sum(1);ff+=a[draw,1].sum(1);dd+=a[draw,2].sum(1)
 valid=dd>0
 return {'paired_decisions':len(pairs),'gold_true_in_pairs':int(total[2]),
         'full_minus_A_recovery_rate':float((total[1]-total[0])/total[2]) if total[2] else None,
         'ci95':np.quantile((ff[valid]-aa[valid])/dd[valid],[.025,.975]).tolist() if valid.any() else None,
         'valid_bootstrap_samples':int(valid.sum())}

def main():
 rows,repeats,errors,calls=parse_calls()
 save(OUT/'predictions.json',rows);save(OUT/'validation_errors.json',errors)
 fields=['dialogue_id','arm','target_source_speaker','view_id','attribute','domain','condition','truth','a_support','prediction','truth_basis','support_type','model_evidence_original_turns','a_evidence_turns','full_evidence_turns','sensitive_to_annotation_policy','request_id']
 with (OUT/'predictions.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
 summary={'calls':len(calls),'completed_main_decisions_by_condition':dict(collections.Counter(r['condition'] for r in rows)),
          'validation_errors':errors,'token_usage':{k:sum(c.get('body',{}).get('usage',{}).get(k,0) for c in calls) for k in ['prompt_tokens','completion_tokens','total_tokens']},
          'returned_models':sorted({c.get('body',{}).get('model','') for c in calls}),
          'structurally_normalized_calls':sum(c.get('parse_audit',{}).get('structural_normalization',False) for c in calls),
          'missing_target_outputs':sum(len(c.get('parse_audit',{}).get('missing_targets',[])) for c in calls),
          'malformed_json_with_complete_target_recovery':sum(c.get('parse_audit',{}).get('malformed_json',False) for c in calls),
          'finish_reasons':dict(collections.Counter(c.get('body',{}).get('choices',[{}])[0].get('finish_reason','missing') for c in calls)),
          'conditions':{},'attributes':{},'strict_sensitivity':{},'paired_comparisons':{}}
 for arm in ['all','random','enriched']:
  subset=[r for r in rows if arm=='all' or r['arm']==arm]
  for condition in ['prior','a_only','full']:
   current=[r for r in subset if r['condition']==condition]
   if current:summary['conditions'][arm+'/'+condition]={**counts(current),'recovery_cluster_bootstrap':recovery_bootstrap(current)}
  strict=[r for r in subset if not r['sensitive_to_annotation_policy']]
  summary['strict_sensitivity'][arm]={c:counts([r for r in strict if r['condition']==c]) for c in ['prior','a_only','full'] if any(r['condition']==c for r in strict)}
  summary['paired_comparisons'][arm]=paired_bootstrap(subset)
 for attr in sorted({r['attribute'] for r in rows}):
  summary['attributes'][attr]={c:counts([r for r in rows if r['condition']==c and r['attribute']==attr]) for c in ['a_only','full'] if any(r['condition']==c and r['attribute']==attr for r in rows)}
 repeat_comparisons=[]
 for repeat in repeats:
  match=next((r for r in rows if r['condition']=='a_only' and r['view_id']==repeat['view_id'] and r['attribute']==repeat['attribute']),None)
  if match:repeat_comparisons.append({'view_id':repeat['view_id'],'attribute':repeat['attribute'],'main':match['prediction'],'repeat':repeat['prediction'],'changed':match['prediction']!=repeat['prediction']})
 summary['exact_repeats']={'repeated_views':len({r['view_id'] for r in repeats}),'decisions_compared':len(repeat_comparisons),
                           'changed_labels':sum(x['changed'] for x in repeat_comparisons),'items':repeat_comparisons}
 save(OUT/'summary.json',summary)
 save(OUT/'repeat_predictions.json',repeats)
 print(json.dumps({'calls':len(calls),'validation_errors':errors,'token_usage':summary['token_usage'],
                   'primary':summary['conditions'],'repeats_changed':summary['exact_repeats']['changed_labels']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
