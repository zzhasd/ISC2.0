"""Evaluation-only reference access; no full A+B dialogue is sent to Qwen."""
import argparse
import csv
from concurrent.futures import ThreadPoolExecutor,as_completed
import os
import sys
from .common import BASE,read,save,jsonlines,digest,filehash,require_dataset,require_direction,run_folder
from .client import Client
from .inference import payload
from .prompts import MATCH
from .statistics import matching,metrics,four_metrics,cluster_bootstrap,paired_bootstrap

def validate_matches(obj,predictions,reference):
    ms=obj.get('matches') if isinstance(obj,dict) else None
    wanted={p['prediction_id'] for p in predictions};allowed={r['claim_id'] for r in reference}
    if not isinstance(ms,list) or len(ms)!=len(wanted) or {x.get('prediction_id') for x in ms}!=wanted:
        raise ValueError('Matcher omitted/duplicated a prediction')
    for m in ms:
        if not isinstance(m.get('reference_ids'),list) or not set(m['reference_ids'])<=allowed:raise ValueError('Invented reference ID')
        if m.get('relation') not in ['equivalent','narrower','broader','none']:raise ValueError('Bad relation')
    return ms

def reference_path(dataset):
    require_dataset(dataset)
    return BASE/'references/dailydialog_human_adjudicated_588.json'

def _reference_records(path):
    records={}
    for x in read(path):
        require_direction(x['direction'])
        key=(x['dialogue_id'],x['direction'])
        if key in records:raise ValueError('Duplicate reference direction: '+str(key))
        ids=[r['claim_id'] for r in x['claims']]
        if len(ids)!=len(set(ids)):raise ValueError('Duplicate reference claim ID: '+str(key))
        records[key]=x['claims']
    return records

def reference_map(dataset,*,reference_file=None):
    require_dataset(dataset)
    if reference_file is not None and reference_file not in ['dailydialog.json','dailydialog_human_adjudicated_588.json']:
        raise ValueError('Unknown reference version')
    p=BASE/'references'/reference_file if reference_file is not None else reference_path(dataset)
    if not p.exists():
        if dataset=='dailydialog' or reference_file is not None:raise FileNotFoundError('Required reference missing: '+str(p))
        return {}
    records=_reference_records(p)
    if dataset=='dailydialog' and p.resolve()==reference_path(dataset).resolve():
        for (_,direction),claims in records.items():
            if direction!='A_to_B':raise ValueError('Human-adjudicated DailyDialog reference is A_to_B only')
            for r in claims:
                if r['truth']!='true' or r['evidence_level'] not in ['E1','E2','E3','E4']:
                    raise ValueError('Invalid human-adjudicated reference label: '+r['claim_id'])
                if r.get('review_status','reviewed')!='reviewed':
                    raise ValueError('Unreviewed human-adjudicated reference: '+r['claim_id'])
    return records

def is_supported_reference(r,dataset):
    # Final human labels override any retained legacy consensus flags.
    return r['evidence_level'] in ['E1','E2'] or (dataset!='dailydialog' and bool(r.get('support_consensus')))

def _reference_inventory(claims):
    return [{'claim_id':r['claim_id'],'claim':r['claim']} for r in claims]

def _prediction_inventory(arms):
    inventory={digest(c['claim']):c['claim'] for arm in arms for c in arm['claims']}
    return [{'prediction_id':h,'claim':s} for h,s in sorted(inventory.items())]

def _cached_matches(saved,pp,rr,direction,legacy=None):
    if saved.get('binding')==digest(matching_content(pp,rr,direction)):
        return validate_matches(saved,pp,rr)
    if legacy is None:return None
    # Reuse only a binding-verified old comparison whose retained ID/text pairs
    # are identical. Changed text, added references or changed predictions fail.
    old={r['claim_id']:r['claim'] for r in legacy}
    if any(old.get(r['claim_id'])!=r['claim'] for r in rr):return None
    if saved.get('binding')!=digest(matching_content(pp,legacy,direction)):return None
    original=validate_matches(saved,pp,legacy);allowed={r['claim_id'] for r in rr}
    projected=[]
    for m in original:
        ids=[r for r in m['reference_ids'] if r in allowed]
        projected.append(dict(m,reference_ids=ids,relation=m['relation'] if ids else 'none'))
    return validate_matches({'matches':projected},pp,rr)

def matching_content(pp,rr,direction):
    require_direction(direction)
    return {'predictions':pp,'reference':rr,
            'subject_mapping':{'hidden partner / target':'original B',
                               'visible speaker / observer':'original A'},
            'persona_reference_rule':'In persona references I/my refer to the hidden target, never the observer.',
            'matcher_prompt_sha256':digest(MATCH)}

def predictions(dataset,run_id=None):
    require_dataset(dataset)
    export=run_folder(run_id)/'exports/dailydialog.json' if run_id is not None else BASE/f'runs/main/exports/{dataset}.json'
    if run_id is not None and not export.exists():raise FileNotFoundError('Export this run before evaluation: '+str(export))
    out=read(export) if export.exists() else [x for p in sorted((BASE/'runs/main/predictions'/dataset).glob('*.json')) for x in read(p)]
    for p in out:require_direction(p['direction'])
    return out

def match_folder(dataset,run_id=None):
    require_dataset(dataset)
    return run_folder(run_id)/'evaluation/matches' if run_id is not None else BASE/'evaluation/matches'/dataset

def current_matches(dataset,ps,refs,run_id=None):
    groups={};out={}
    for p in ps:groups.setdefault((p['dialogue_id'],p['direction']),[]).append(p)
    legacy_path=BASE/'references/dailydialog.json'
    legacy=_reference_records(legacy_path) if run_id is None and legacy_path.exists() else {}
    for key,arms in groups.items():
        path=match_folder(dataset,run_id)/(key[0]+'__'+key[1]+'.json')
        if key not in refs or not path.exists():continue
        pp=_prediction_inventory(arms);rr=_reference_inventory(refs[key])
        saved=read(path)
        previous=_reference_inventory(legacy[key]) if key in legacy else None
        ms=_cached_matches(saved,pp,rr,key[1],previous)
        if ms is not None:out[key]=ms
    return out

def match_dataset(dataset,key=None,workers=12,run_id=None):
    refs=reference_map(dataset);ps=predictions(dataset,run_id) if run_id is not None else predictions(dataset);groups={}
    for p in ps:
        k=(p['dialogue_id'],p['direction'])
        if k in refs:groups.setdefault(k,[]).append(p)
    cached=current_matches(dataset,ps,refs,run_id)
    requires_api=any(k not in cached and refs[k] and any(p['claims'] for p in arms) for k,arms in groups.items())
    client=Client(key or os.environ.get('QWEN_API_KEY') or os.environ.get('DASHSCOPE_API_KEY'),run_id=run_id+'/evaluation' if run_id is not None else 'evaluation_'+dataset) if requires_api else None
    out=match_folder(dataset,run_id)
    def work(item):
        (did,direction),arms=item
        if (did,direction) in cached:return 'cached'
        target=out/(did+'__'+direction+'.json')
        inventory={digest(c['claim']):c['claim'] for arm in arms for c in arm['claims']}
        pp=[{'prediction_id':h,'claim':s} for h,s in sorted(inventory.items())]
        rr=[{'claim_id':r['claim_id'],'claim':r['claim']} for r in refs[(did,direction)]]
        content=matching_content(pp,rr,direction);binding=digest(content)
        if target.exists() and read(target).get('binding')==binding:return 'cached'
        name=dataset+'/'+did+'/'+direction+'/'+binding
        if client is not None and any(r.get('event')=='complete' and r.get('logical_name')==name and r.get('http_status')==400 for r in client.rows):
            return 'provider_blocked_retained_for_manual_review'
        if not pp:ms=[];tid=None
        elif not rr:ms=[{'prediction_id':p['prediction_id'],'reference_ids':[],'relation':'none'} for p in pp];tid=None
        else:
            ms,tid=client.call(name,payload(MATCH,content,4096),
                               lambda x:validate_matches(x,pp,rr))
        save(target,{'binding':binding,'matches':ms,'task_id':tid,'evaluation_model':'qwen3.8-flash',
                     'independent_human_correctness_review':False})
        return 'complete'
    errors=[];counts={}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fs={pool.submit(work,x):x[0] for x in groups.items()}
        for f in as_completed(fs):
            try:s=f.result();counts[s]=counts.get(s,0)+1
            except Exception as e:errors.append({'item':fs[f],'error':str(e)})
    status_folder=run_folder(run_id)/'evaluation' if run_id is not None else BASE/'evaluation'
    save(status_folder/f'{dataset}_match_status.json',{'counts':counts,'errors':errors})
    if errors:raise RuntimeError('Semantic matching failed; see evaluation/'+dataset+'_match_status.json')
    return counts

def cost_map(run_id=None):
    by={}
    for p in [run_folder(run_id)/'attempts.jsonl' if run_id is not None else BASE/'runs/dailydialog/attempts.jsonl']:
        for x in jsonlines(p):
            if x['event']!='complete':continue
            u=x.get('body',{}).get('usage',{}).get('total_tokens')
            old=by.setdefault(x['task_id'],{'tokens':0,'attempts':0,'missing_usage':0})
            old['attempts']+=1
            if u is None:old['missing_usage']+=1
            else:old['tokens']+=u
    return by

def score_item(p,refs,ms,costs,threshold=0,accepted_relations=('equivalent',)):
    require_direction(p['direction'])
    if not set(accepted_relations)<= {'equivalent','broader'}:raise ValueError('Unsupported scoring policy')
    cs=[c for c in p['claims'] if c['confidence']>=threshold]
    ref={r['claim_id']:r for r in refs if r.get('review_status','reviewed')=='reviewed'}
    eligible={k:r for k,r in ref.items() if r['truth']=='true' and is_supported_reference(r,p['dataset'])}
    mapby={x['prediction_id']:x for x in ms};trueedges={};supportededges={};unresolved=0;correct_outputs=0
    for i,c in enumerate(cs):
        m=mapby.get(digest(c['claim']),{'relation':'none','reference_ids':[]})
        ids=m['reference_ids'] if m['relation'] in accepted_relations else []
        tr={k for k in ids if k in ref and ref[k]['truth']=='true'}
        correct_outputs+=bool(tr)
        trueedges[str(i)]=tr
        supportededges[str(i)]={k for k in tr if k in eligible}
        # Reference absence, broad/narrow overlap and uncertain truth all need additional correctness review.
        if not ids or any(k not in ref or ref[k]['truth']=='uncertain' for k in ids):unresolved+=1
    tm=matching(trueedges);sm=matching(supportededges)
    # Duplicates are additional assertions: recall matching prevents inflated counts.
    scores={'dialogue_id':p['dialogue_id'],'direction':p['direction'],'dataset':p['dataset'],'method':p['method'],
            'predictions':len(cs),'supported_tp':len(sm),'true_tp':len(tm),'unresolved':unresolved,
            'correct_output_assertions':correct_outputs,'true_reference':sum(r['truth']=='true' for r in ref.values()),
            'supported_reference':len(eligible),'e1_reference':sum(r['evidence_level']=='E1' for r in eligible.values()),
            'e2_reference':sum(r['evidence_level']=='E2' for r in eligible.values()),
            'e1_hits':sum(eligible[k]['evidence_level']=='E1' for k in sm.values()),
            'e2_hits':sum(eligible[k]['evidence_level']=='E2' for k in sm.values()),
            'e12_disputed_reference':sum(r['evidence_level']=='E1_E2_disputed' for r in eligible.values()),
            'e12_disputed_hits':sum(eligible[k]['evidence_level']=='E1_E2_disputed' for k in sm.values()),
            'unsupported_correct':max(0,len(tm)-len(sm)),
            'valid_citations':sum(bool(c.get('evidence_span_valid')) or 'verifier' in c for c in cs),
            'tokens':sum(costs[t]['tokens'] for t in p['task_ids'] if t in costs),
            'missing_usage_attempts':sum(costs[t]['missing_usage'] if t in costs else 1 for t in p['task_ids']),
            'correctness_scope':('fixed human-adjudicated reference; unmatched outputs receive no credit under the completeness assumption'
                                 if p['dataset']=='dailydialog' else 'AI reference-matched lower bound; unmatched claims unresolved, not automatically false'),
            'unsupported_correct_definition':'additional full-truth matches beyond maximum grounded matches; disjoint count, no double-credit for equivalent references',
            'citation_entailment_human_verified':False}
    scores['failed_abstention']=p.get('outcome')=='failed_abstention'
    return scores

def analyze(dataset,bootstrap=True,run_id=None):
    refs=reference_map(dataset);costs=cost_map(run_id);rows=[];missing=[];ps=predictions(dataset,run_id)
    matched=current_matches(dataset,ps,refs,run_id)
    results_folder=run_folder(run_id)/'results' if run_id is not None else BASE/'results'
    for p in ps:
        key=(p['dialogue_id'],p['direction'])
        if key not in refs:continue
        if key not in matched:missing.append({'item':key,'method':p['method'],'reason':'missing reference or missing/stale matching binding'});continue
        rows.append(score_item(p,refs[key],matched[key],costs))
    methods=sorted({r['method'] for r in rows});summary={}
    for method in methods:
        rs=[r for r in rows if r['method']==method]
        summary[method]=metrics(rs)
        if dataset=='dailydialog':summary[method].update(four_metrics(rs))
        if bootstrap:summary[method]['recall_cluster_bootstrap']=cluster_bootstrap(rs,metric='full_reference_recall' if dataset=='dailydialog' else 'recall')
    if 'dual_with_verifier' in methods and 'direct_multisample_verifier' in methods:
        paired=paired_bootstrap([r for r in rows if r['method']=='dual_with_verifier'],[r for r in rows if r['method']=='direct_multisample_verifier'],metric='full_reference_recall' if dataset=='dailydialog' else 'recall') if bootstrap else None
    else:paired=None
    result={'dataset':dataset,'methods':summary,'paired_primary':paired,'missing_evaluation_items':len(missing),
            'status':'provisional_AI_reference_evaluation','human_gold':False,'unmatched_precision_is_bound':True}
    result.update(reference_file=reference_path(dataset).relative_to(BASE).as_posix(),
                  reference_sha256=filehash(reference_path(dataset)),
                  predictions_sha256=digest(ps),
                  evaluated_reference_inputs=len(refs),evaluated_directions=sorted({d for _,d in refs}),
                  predictions_outside_reference_scope=sum((p['dialogue_id'],p['direction']) not in refs for p in ps))
    if dataset=='dailydialog':
        result.update(status='fixed_human_adjudicated_reference_evaluation',metric_policy='fixed_reference_four_metrics',
                      reference_completeness_assumed=True,unmatched_precision_is_bound=False,
                      human_adjudication_scope='63 evidence-level disputes; prediction-reference matching remains automated',
                      legacy_bound_fields='precision_lower/upper and f1_lower retain grounded diagnostic definitions')
        table=[dict(method=method,**four_metrics([r for r in rows if r['method']==method])) for method in methods]
        csv_path=results_folder/'dailydialog_four_metrics.csv';csv_path.parent.mkdir(parents=True,exist_ok=True)
        with csv_path.open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(table[0]) if table else ['method'])
            writer.writeheader();writer.writerows(table)
    from .inference import METHODS
    expected={(did,direction,method) for did,direction in refs for method in METHODS}
    actual={(r['dialogue_id'],r['direction'],r['method']) for r in rows}
    result['run_id']=run_id or 'historical'
    result['missing_input_method_outcomes']=len(expected-actual)
    result['complete_experiment']=actual==expected and len(rows)==len(expected)
    result['missing_usage_attempts']=sum(r['missing_usage_attempts'] for r in rows)
    save(results_folder/f'{dataset}_scores.json',rows);save(results_folder/f'{dataset}_summary.json',result)
    status_folder=run_folder(run_id)/'evaluation' if run_id is not None else BASE/'evaluation'
    save(status_folder/f'{dataset}_missing.json',missing)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['match','analyze']);p.add_argument('dataset',choices=['dailydialog'],nargs='?',default='dailydialog');p.add_argument('--workers',type=int,default=24);p.add_argument('--run-id');a=p.parse_args()
    if a.action=='match':print(match_dataset(a.dataset,os.environ.get('QWEN_API_KEY'),a.workers,a.run_id))
    else:print(analyze(a.dataset,run_id=a.run_id))
