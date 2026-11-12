"""Full 298-input / 588-reference runner. Python 3.10+, standard library only.

python run_COVER.py                         # securely enter key; 12 + 12 workers
python run_COVER.py --preflight             # no key, no requests
python run_COVER.py --run-id cover_smoke --limit 3
python run_COVER.py --evaluate-only         # resume evaluation
python run_COVER.py --joint-baselines       # same judgments for all 17 methods

Requires COVER.py, inputs/dailydialog.json, references/
dailydialog_human_adjudicated_588.json and prompts-v2.py (existing project files).
All generated artifacts are confined to runs/<run-id>; historical files unchanged.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import getpass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import threading
import time
import urllib.error
import urllib.request

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('cover_algorithm',HERE/'COVER.py')
algorithm=importlib.util.module_from_spec(spec);spec.loader.exec_module(algorithm)
URL='https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'
HISTORY=('main','efcr_append_v1','evidence_adaptive_v1_append','evidence_adaptive_v2_corrected',
         'evidence_adaptive_v3_append','efcr_append_v2','evidence_adaptive_v4_append',
         'evidence_adaptive_v5_append','elara_append_v1','elara_v2_append','elara_v3_append')

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def digest(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def filehash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    temp.replace(path)
def freeze(path,obj):
    if path.exists():
        if read(path)!=obj:raise ValueError('Frozen configuration/content changed; choose a NEW --run-id: '+str(path))
    else:save(path,obj)
def ratio(a,b):return a/b if b else None

def load_prompt(matcher):
    # Read a string literal, without executing historical modules.
    path=HERE/('prompts-v2.py' if matcher=='v2' else 'prompts.py')
    tree=ast.parse(path.read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MATCH' for t in node.targets):
            value=ast.literal_eval(node.value)
            if isinstance(value,str) and value.strip():return value
    raise ValueError('No literal MATCH prompt in '+str(path))

def read_inputs(limit=None):
    records=read(HERE/'inputs/dailydialog.json')
    if len(records)!=298 or len({r['item_id'] for r in records})!=298:raise ValueError('Expected frozen 298 unique inputs')
    for r in records:algorithm.validate_input(r)
    return records if limit is None else records[:limit]

def read_refs():
    records=read(HERE/'references/dailydialog_human_adjudicated_588.json');refs={}
    for r in records:
        if r['direction']!='A_to_B' or r['dialogue_id'] in refs:raise ValueError('Invalid reference scope')
        refs[r['dialogue_id']]=r['claims']
        if len({c['claim_id'] for c in r['claims']})!=len(r['claims']):raise ValueError('Duplicate reference IDs')
        if any(c['truth']!='true' or c['evidence_level'] not in ('E1','E2','E3','E4') or c.get('review_status','reviewed')!='reviewed' for c in r['claims']):
            raise ValueError('Unreviewed/invalid reference')
    labels=Counter(c['evidence_level'] for rr in refs.values() for c in rr)
    if len(refs)!=298 or labels!=Counter(E1=136,E2=126,E3=295,E4=31):raise ValueError('Expected frozen 588 references, including 262 E1/E2')
    if set(refs)!={r['dialogue_id'] for r in read_inputs()}:raise ValueError('Reference/input IDs differ')
    return refs

def decode(body):
    choice=body['choices'][0]
    if choice.get('finish_reason')!='stop':raise ValueError('Truncated/incomplete completion')
    content=choice['message']['content']
    if not isinstance(content,str):raise ValueError('No text content')
    s=content.strip()
    if s.startswith('```') and s.endswith('```'):s=s.split('\n',1)[1].rsplit('```',1)[0].strip()
    try:return json.loads(s)
    except json.JSONDecodeError:
        # First complete JSON object, not favorable-decision selection.
        start=s.find('{')
        if start<0:raise
        obj,_=json.JSONDecoder().raw_decode(s,start)
        return obj

class APIClient:
    """Per-request durable journals; first valid result, retries fully charged."""
    def __init__(self,key,root,endpoint=URL,max_attempts=4,timeout=180,retry_interrupted=False):
        self.key=key;self.root=Path(root);self.endpoint=endpoint;self.max_attempts=max_attempts
        self.timeout=timeout;self.retry_interrupted=retry_interrupted;self.stop=threading.Event()
        self.locks={};self.guard=threading.Lock()
    def _lock(self,tid):
        with self.guard:return self.locks.setdefault(tid,threading.Lock())
    def _save(self,path,obj):
        # Keys are never included in payloads, logs or command-line arguments.
        if self.key:obj=json.loads(json.dumps(obj,ensure_ascii=False).replace(self.key,'[REDACTED]'))
        save(path,obj)
    def call(self,name,payload,validator):
        tid=digest({'name':name,'endpoint':self.endpoint,'payload':payload})
        with self._lock(tid):
            path=self.root/'calls'/(tid+'.json')
            state=read(path) if path.exists() else dict(task_id=tid,name=name,endpoint=self.endpoint,request=payload,attempts=[])
            for a in state['attempts']:
                if a.get('valid'):return validator(decode(a['body'])),tid
            for a in state['attempts']:
                if a.get('status')=='started':
                    if not self.retry_interrupted:raise RuntimeError('Interrupted request with unknown billing. Inspect '+str(path)+'; use --retry-interrupted to resend.')
                    a.update(status='interrupted_unknown_usage',valid=False)
            while len(state['attempts'])<self.max_attempts:
                if self.stop.is_set():raise RuntimeError('Provider circuit open after authentication/request rejection')
                if not self.key:raise RuntimeError('API key required for uncached requests')
                a=dict(index=len(state['attempts'])+1,status='started',valid=False,utc=datetime.now(timezone.utc).isoformat())
                state['attempts'].append(a);self._save(path,state)
                started=time.monotonic();status=None
                try:
                    req=urllib.request.Request(self.endpoint,json.dumps(payload,ensure_ascii=False).encode('utf-8'),
                        {'Content-Type':'application/json','Authorization':'Bearer '+self.key},method='POST')
                    # Never forward credentials through a provider redirect.
                    class NoRedirect(urllib.request.HTTPRedirectHandler):
                        def redirect_request(self,*args,**kwargs):return None
                    opener=urllib.request.build_opener(NoRedirect)
                    try:
                        with opener.open(req,timeout=self.timeout) as response:
                            status=response.status;body=response.read().decode('utf-8')
                    except urllib.error.HTTPError as exc:
                        status=exc.code;body=exc.read().decode('utf-8',errors='replace')
                    a['http_status']=status
                    try:a['body']=json.loads(body)
                    except ValueError:a['response_excerpt']=body[:500]
                    if status==200:
                        result=validator(decode(a['body']));a['valid']=True
                    else:a['error']='provider_http_'+str(status)
                except Exception as exc:a['error']=type(exc).__name__+': '+str(exc)[:300]
                a.update(status='complete',elapsed_seconds=round(time.monotonic()-started,3));self._save(path,state)
                if a['valid']:return result,tid
                if status and (300<=status<400 or 400<=status<500 and status not in (408,429)):
                    self.stop.set();raise RuntimeError('Provider rejected request (HTTP '+str(status)+'); inspect redacted call journal')
                if len(state['attempts'])<self.max_attempts:time.sleep(min(8,2**len(state['attempts'])))
            raise RuntimeError('Request attempt limit reached. Resume with larger --max-attempts after inspecting '+str(path))

def run_jobs(jobs,workers,label,fn,error_path):
    errors=[];completed=0
    print(f'[{label}] pending={len(jobs)}, concurrency={workers}',flush=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(fn,j):j for j in jobs}
        for future in as_completed(futures):
            completed+=1
            try:future.result()
            except Exception as exc:errors.append({'item':futures[future]['dialogue_id'],'error':str(exc)})
            print(f'[{label}] {completed}/{len(jobs)}; failed={len(errors)}',flush=True)
    save(error_path,errors)
    if errors:raise RuntimeError(f'{label}: {len(errors)} failures; successful requests saved. See {error_path}')

def prediction_path(root,item):return root/'predictions'/(item['dialogue_id']+'__A_to_B.json')

def valid_prediction(path,item):
    if not path.exists():return False
    rows=read(path)
    if not isinstance(rows,list) or len(rows)!=1:raise ValueError('Invalid prediction file '+str(path))
    p=rows[0]
    if any(p.get(k)!=item[k] for k in ('item_id','dialogue_id','direction','dataset')) or p.get('method')!=algorithm.METHOD:
        raise ValueError('Prediction identity mismatch')
    if not isinstance(p.get('claims'),list) or not isinstance(p.get('task_ids'),list):raise ValueError('Invalid prediction schema')
    for c in p['claims']:
        if not algorithm.claim_object(c,item['visible_turns'])['evidence_span_valid']:raise ValueError('Prediction lost supporting citations')
    return True

def infer(records,root,api,workers,completion,repair):
    todo=[r for r in records if not valid_prediction(prediction_path(root,r),r)]
    def job(item):
        p,trace=algorithm.pipeline(api,item,completion=completion,repair=repair)
        save(root/'diagnostics'/(item['dialogue_id']+'__A_to_B.json'),trace)
        save(prediction_path(root,item),[p])
    run_jobs(todo,workers,'inference',job,root/'inference_errors.json')

def export(records,root):
    out=[]
    for item in records:
        path=prediction_path(root,item)
        if not valid_prediction(path,item):raise RuntimeError('Missing prediction: '+item['item_id'])
        out.extend(read(path))
    freeze(root/'exports/dailydialog.json',out)
    return out

def validate_matches(obj,pp,rr):
    ms=obj.get('matches') if isinstance(obj,dict) else None
    wanted={p['prediction_id'] for p in pp};allowed={r['claim_id'] for r in rr}
    if not isinstance(ms,list) or len(ms)!=len(wanted) or any(not isinstance(m,dict) for m in ms) or {m.get('prediction_id') for m in ms}!=wanted:
        raise ValueError('Matcher omitted/duplicated prediction')
    for m in ms:
        if not isinstance(m.get('reference_ids'),list) or any(not isinstance(k,str) for k in m['reference_ids']) or not set(m['reference_ids'])<=allowed:
            raise ValueError('Invented reference ID')
        if m.get('relation') not in ('equivalent','narrower','broader','none'):raise ValueError('Invalid relation')
    return ms

def maximum_matching(edges):
    owner={}
    def visit(p,seen):
        for r in sorted(edges[p]):
            if r in seen:continue
            seen.add(r)
            if r not in owner or visit(owner[r],seen):owner[r]=p;return True
        return False
    for p in sorted(edges):visit(p,set())
    return {p:r for r,p in owner.items()}

def score(p,refs,matches,accepted):
    rr={r['claim_id']:r for r in refs if r['truth']=='true'};mm={m['prediction_id']:m for m in matches}
    edges={};ground={};correct=0
    for i,c in enumerate(p['claims']):
        m=mm[digest(c['claim'])]
        ids=set(m['reference_ids']) & rr.keys() if m['relation'] in accepted else set()
        correct+=bool(ids);edges[str(i)]=ids
        ground[str(i)]={k for k in ids if rr[k]['evidence_level'] in ('E1','E2')}
    hits=maximum_matching(edges);ghits=maximum_matching(ground)
    row=dict(dialogue_id=p['dialogue_id'],method=p['method'],outputs=len(p['claims']),correct=correct,
             hits=len(hits),references=len(rr),grounded_hits=len(ghits),
             grounded_references=sum(r['evidence_level'] in ('E1','E2') for r in rr.values()),
             e1_hits=sum(rr[k]['evidence_level']=='E1' for k in ghits.values()),
             e2_hits=sum(rr[k]['evidence_level']=='E2' for k in ghits.values()),
             e1_total=sum(r['evidence_level']=='E1' for r in rr.values()),
             e2_total=sum(r['evidence_level']=='E2' for r in rr.values()),empty_output=not p['claims'])
    missed=[]
    for k,r in rr.items():
        if r['evidence_level'] not in ('E1','E2') or k in ghits.values():continue
        related=[{'claim':c['claim'],**mm[digest(c['claim'])]} for c in p['claims'] if k in mm[digest(c['claim'])]['reference_ids']]
        rel={m['relation'] for m in related}
        reason=('empty_output' if not p['claims'] else 'matching_competition' if rel & set(accepted) else
                'broader_only' if 'broader' in rel else 'narrower_only' if 'narrower' in rel else 'no_semantic_edge')
        missed.append(dict(dialogue_id=p['dialogue_id'],method=p['method'],claim_id=k,claim=r['claim'],
                           level=r['evidence_level'],reason=reason,related=related))
    return row,missed

def cost_ledger(folder):
    tokens=0;missing=0;attempts=0;states=[]
    for path in sorted((folder/'calls').glob('*.json')):
        s=read(path);states.append(s)
        for a in s['attempts']:
            attempts+=1;u=a.get('body',{}).get('usage',{}).get('total_tokens')
            if type(u) is int and u>=0:tokens+=u
            else:missing+=1
    return dict(known_tokens=tokens,missing_usage_attempts=missing,attempts=attempts,
                task_ids=[s['task_id'] for s in states])

def summarize(rows,cost=None):
    total={k:sum(r[k] for r in rows) for k in ('outputs','correct','hits','references','grounded_hits','grounded_references','e1_hits','e2_hits','e1_total','e2_total','empty_output')}
    return dict(precision=ratio(total['correct'],total['outputs']),recall=ratio(total['hits'],total['references']),
                grounded_recall=ratio(total['grounded_hits'],total['grounded_references']),
                mean_tokens=ratio(cost['known_tokens'],len(rows)) if cost and not cost['missing_usage_attempts'] else None,
                e1_recall=ratio(total['e1_hits'],total['e1_total']),e2_recall=ratio(total['e2_hits'],total['e2_total']),
                e1_missed=total['e1_total']-total['e1_hits'],e2_missed=total['e2_total']-total['e2_hits'],
                single_sided_inputs=len(rows),**total)

def evaluate(records,predictions,root,api,workers,matcher,joint):
    # The algorithm has already finished and its export is frozen. References
    # and old methods enter ONLY this function and NEVER generation prompts.
    refs=read_refs();prompt=load_prompt(matcher);ps=list(predictions)
    ids={r['dialogue_id'] for r in records};history_hashes={}
    if joint:
        for run in HISTORY:
            path=HERE/'runs'/run/'exports/dailydialog.json';old=read(path)
            history_hashes[run]=filehash(path)
            ps.extend(p for p in old if p['dialogue_id'] in ids)
    freeze(root/'evaluation/manifest.json',dict(matcher=matcher,prompt_sha256=digest(prompt),
           reference_sha256=filehash(HERE/'references/dailydialog_human_adjudicated_588.json'),
           predictions_sha256=digest(ps),joint_baselines=history_hashes,scope=sorted(ids)))
    groups=defaultdict(list)
    for p in ps:groups[p['dialogue_id']].append(p)
    jobs=[];cached={}
    for did,arms in sorted(groups.items()):
        inv={digest(c['claim']):c['claim'] for p in arms for c in p['claims']}
        pp=[dict(prediction_id=k,claim=v) for k,v in sorted(inv.items())]
        rr=[{k:r[k] for k in ('claim_id','claim')} for r in refs[did]]
        content=dict(predictions=pp,reference=rr,subject_mapping={'hidden partner / target':'original B','visible speaker / observer':'original A'},
                     persona_reference_rule='In persona references I/my refer to the hidden target, never the observer.',matcher_prompt_sha256=digest(prompt))
        # One per-dialogue inventory ensures identical text shares ONE judgment.
        request=algorithm.payload(prompt,content,max(4096,min(32768,160*len(pp)+1024)))
        binding=digest({'request':request,'endpoint':api.endpoint})
        path=root/'evaluation/matches'/(did+'__A_to_B.json')
        task=dict(dialogue_id=did,pp=pp,rr=rr,request=request,binding=binding,path=path)
        if path.exists():
            old=read(path)
            if old.get('binding')!=binding:raise ValueError('Stale evaluation binding; use a new run ID')
            cached[did]=validate_matches(old,pp,rr)
        else:jobs.append(task)
    def job(t):
        pp,rr=t['pp'],t['rr'];tid=None
        if not pp:ms=[]
        elif not rr:ms=[dict(prediction_id=p['prediction_id'],reference_ids=[],relation='none') for p in pp]
        else:ms,tid=api.call(t['dialogue_id']+'/match',t['request'],lambda obj:validate_matches(obj,pp,rr))
        save(t['path'],dict(binding=t['binding'],matches=ms,task_id=tid,evaluation_model=algorithm.MODEL,independent_human_correctness_review=False))
    run_jobs(jobs,workers,'evaluation',job,root/'evaluation/errors.json')
    msby={did:read(root/'evaluation/matches'/(did+'__A_to_B.json'))['matches'] for did in groups}
    inference_cost=cost_ledger(root/'inference');evaluation_cost=cost_ledger(root/'evaluation')
    # Every successful pipeline task must be represented, including all retries.
    required={tid for p in predictions for tid in p['task_ids']}
    if not required<=set(inference_cost['task_ids']):raise ValueError('Missing inference request journal')
    result=dict(method=algorithm.METHOD,model=algorithm.MODEL,matcher=matcher,full_benchmark=len(records)==298,
                reference_count=sum(len(refs[r['dialogue_id']]) for r in records),costs=dict(inference=inference_cost,evaluation=evaluation_cost),policies={})
    table=[];misses=[]
    for policy,accepted in [('strict',('equivalent',)),('lenient',('equivalent','broader'))]:
        rows=[]
        for p in ps:
            row,missing=score(p,refs[p['dialogue_id']],msby[p['dialogue_id']],accepted)
            rows.append(row);misses.extend(dict(m,policy=policy) for m in missing)
        per_method={}
        for method in dict.fromkeys(p['method'] for p in ps):
            rr=[r for r in rows if r['method']==method]
            if len(rr)!=len(records) or len({r['dialogue_id'] for r in rr})!=len(records):raise ValueError('Incomplete method scope')
            metric=summarize(rr,inference_cost if method==algorithm.METHOD else None)
            if method!=algorithm.METHOD:metric['token_note']='Historical costs not re-estimated in joint matching; see frozen historical ledgers.'
            per_method[method]=metric;table.append(dict(policy=policy,method=method,**metric))
        result['policies'][policy]=per_method
        save(root/'results'/policy/'per_input.json',rows)
    save(root/'results/four_metrics.json',result);save(root/'results/missed_grounded_attributes.json',misses)
    fields=list(dict.fromkeys(k for r in table for k in r))
    with (root/'results/four_metrics.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(table)
    for policy in ('strict','lenient'):
        m=result['policies'][policy][algorithm.METHOD]
        print(policy, json.dumps({k:m[k] for k in ('precision','recall','grounded_recall','mean_tokens','e1_missed','e2_missed','empty_output')},ensure_ascii=False),flush=True)
    print('Results:',root/'results/four_metrics.json',flush=True)
    return result

def get_key():
    key=os.getenv('QWEN_API_KEY') or os.getenv('DASHSCOPE_API_KEY')
    if not key and sys.stdin.isatty():key=getpass.getpass('Qwen DashScope API Key (hidden): ').strip()
    if not key:raise RuntimeError('Set QWEN_API_KEY / DASHSCOPE_API_KEY or run in an interactive terminal')
    return key

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--run-id',default='cover_v1')
    p.add_argument('--workers',type=int,default=12);p.add_argument('--eval-workers',type=int,default=12)
    p.add_argument('--limit',type=int);p.add_argument('--max-attempts',type=int,default=4)
    p.add_argument('--timeout',type=int,default=180);p.add_argument('--retry-interrupted',action='store_true')
    p.add_argument('--model',default=algorithm.MODEL);p.add_argument('--endpoint',default=URL)
    p.add_argument('--matcher',choices=('v2','original'),default='v2')
    p.add_argument('--joint-baselines',action='store_true')
    p.add_argument('--no-completion',action='store_true');p.add_argument('--no-repair',action='store_true')
    phase=p.add_mutually_exclusive_group()
    phase.add_argument('--infer-only',action='store_true');phase.add_argument('--evaluate-only',action='store_true')
    phase.add_argument('--preflight',action='store_true');phase.add_argument('--offline',action='store_true',help='Replay cached inference and matches; never request a key or make network calls')
    a=p.parse_args(argv)
    if not re.fullmatch(r'[A-Za-z0-9_-]+',a.run_id) or a.run_id in HISTORY or a.run_id in ('dailydialog','evaluation'):
        p.error('Choose a new safe run ID; historical run IDs are protected')
    if min(a.workers,a.eval_workers,a.max_attempts,a.timeout)<1 or (a.limit is not None and not 1<=a.limit<=298):p.error('Invalid count/limit')
    if not a.endpoint.startswith('https://'):p.error('HTTPS endpoint required')
    algorithm.MODEL=a.model;records=read_inputs(a.limit);prompt=load_prompt(a.matcher)
    if a.preflight:
        refs=read_refs()
        print(json.dumps(dict(inputs=len(records),full_inputs=298,full_reference_attributes=sum(map(len,refs.values())),
              full_grounded_attributes=262,workers=a.workers,eval_workers=a.eval_workers,model=a.model,matcher=a.matcher,
              source_sha256=filehash(HERE/'COVER.py'),network_calls=0),indent=2));return
    root=HERE/'runs'/a.run_id
    manifest=dict(method=algorithm.METHOD,version=algorithm.VERSION,model=a.model,endpoint=a.endpoint,
          algorithm_sha256=filehash(HERE/'COVER.py'),runner_sha256=filehash(Path(__file__)),inputs_sha256=digest(records),
          scope_count=len(records),completion=not a.no_completion,repair=not a.no_repair,
          matcher_sha256=digest(prompt),joint_baselines=a.joint_baselines,reference_access_during_inference=False)
    freeze(root/'manifest.json',manifest);freeze(root/'inputs.json',records)
    # Key remains process-local and is never written. Offline path proves replay.
    key=None if a.offline else get_key()
    opts=dict(endpoint=a.endpoint,max_attempts=a.max_attempts,timeout=a.timeout,retry_interrupted=a.retry_interrupted)
    if not a.evaluate_only:
        infer(records,root,APIClient(key,root/'inference',**opts),a.workers,not a.no_completion,not a.no_repair)
    predictions=export(records,root)
    if not a.infer_only:evaluate(records,predictions,root,APIClient(key,root/'evaluation',**opts),a.eval_workers,a.matcher,a.joint_baselines)

if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError,OSError,KeyError) as exc:
        print('ERROR:',exc,file=sys.stderr);sys.exit(1)
