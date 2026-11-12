"""Auditable 2x2 API experiment; credentials stay in stdin/process memory."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import getpass
import hashlib
import json
import os
import random
import sys
import threading
import time
import requests
from isc4_open import ROOT,read,save,freeze,sha,visible
from isc5_run import decode
from isc7_module import DIRECT,GLOBAL,LOCAL,JUDGE,validate_candidates,union_candidates,render

OUT=ROOT/'results/isc7';DATA=ROOT/'data/isc7'
URL='https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'
ARMS=['direct_off','direct_on','dual_off','dual_on']


def task(did,arm,stage,system,content,sources=None):
    thinking=arm.endswith('_on')
    payload={'model':'qwen3.8-flash','temperature':0,'enable_thinking':thinking,
        'max_tokens':4096,'response_format':{'type':'json_object'},
        'messages':[{'role':'system','content':system},{'role':'user','content':json.dumps(content,ensure_ascii=False)}]}
    if thinking:payload['thinking_budget']=2048
    h=sha(payload)
    return {'task_id':h[:24],'request_sha256':h,'dialogue_id':did,'arm':arm,'stage':stage,
            'source_task_ids':sources or [],'payload':payload}


def records(phase):
    p=OUT/phase/'api_raw.jsonl'
    return [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines()] if p.exists() else []


def prepare():
    ds=read(ROOT/'data/isc4/dialogues.json');freeze(DATA/'dialogues.json',ds)
    refs=[r for r in read(ROOT/'data/isc5/full_AB_reference.json') if r['dialogue_id'] in {d['id'] for d in ds}]
    freeze(DATA/'reference.json',refs)
    tasks=[]
    for d in ds:
        for arm in ARMS:
            for stage,system in ([('direct',DIRECT)] if arm.startswith('direct') else [('global',GLOBAL),('local',LOCAL)]):
                tasks.append(task(d['id'],arm,stage,system,{'visible_A':visible(d)}))
    random.Random(2026110107).shuffle(tasks)
    freeze(OUT/'initial/requests.json',tasks)
    originals={}
    for p in [ROOT/'data/isc5/full_AB_reference.json',ROOT/'results/isc5/summary.json',ROOT/'results/isc6/summary.json']:
        originals[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    freeze(DATA/'manifest.json',{'planned_dialogues':32,'planned_final_outputs':128,'planned_calls':256,
        'initial_requests_sha256':sha(tasks),'dialogues_sha256':sha(ds),'reference_sha256':sha(refs),
        'protocol_sha256':hashlib.sha256((ROOT/'ISC7_PROTOCOL.md').read_bytes()).hexdigest(),
        'module_sha256':hashlib.sha256((ROOT/'experiments/isc7_module.py').read_bytes()).hexdigest(),
        'runner_sha256':hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest(),
        'old_source_hashes':originals,'thinking_budget':2048,'answer_cap':4096,'seed':2026110107,
        'setting':'same 32 previously inspected development dialogues; no held-out confirmation'})
    print({'initial_requests':len(tasks),'planned_calls':256},flush=True)


def dependent():
    plan={t['task_id']:t for t in read(OUT/'initial/requests.json')}
    results={r['task_id']:r for r in records('initial')}
    by={(t['dialogue_id'],t['arm'],t['stage']):t for t in plan.values()}
    tasks=[];errors=[];candidates=[]
    for d in read(DATA/'dialogues.json'):
        for arm in ['dual_off','dual_on']:
            sources=[by[d['id'],arm,s] for s in ['global','local']]
            try:
                cs=[validate_candidates(decode(results[t['task_id']]),visible(d)) for t in sources]
                merged=union_candidates(*cs)
                candidates.append({'dialogue_id':d['id'],'arm':arm,'global':cs[0],'local':cs[1],'merged':merged})
                tasks.append(task(d['id'],arm,'judge',JUDGE,{'visible_A':visible(d),'candidates':merged},[t['task_id'] for t in sources]))
            except (ValueError,KeyError,TypeError,IndexError) as exc:
                errors.append({'dialogue_id':d['id'],'arm':arm,'error':str(exc)})
    random.Random(2026110108).shuffle(tasks)
    freeze(OUT/'dependent/requests.json',tasks);save(OUT/'dependent/source_errors.json',errors)
    save(OUT/'candidates.json',candidates)
    print({'dependent_requests':len(tasks),'invalid_sources':len(errors)},flush=True)


def run_phase(phase,key):
    directory=OUT/phase;plan=read(directory/'requests.json');raw=records(phase)
    previous={r['task_id'] for r in raw};ap=directory/'attempts.jsonl'
    attempted=[json.loads(s) for s in ap.read_text(encoding='utf-8').splitlines()] if ap.exists() else []
    if any(a['task_id'] not in previous for a in attempted):raise RuntimeError('Unrecorded attempt requires audit before resume')
    if any(r.get('http_status')!=200 for r in raw):raise RuntimeError('Previous HTTP failure requires audit')
    pending=[t for t in plan if t['task_id'] not in previous]
    prior=sum(len((OUT/p/'attempts.jsonl').read_text(encoding='utf-8').splitlines()) for p in ['initial','dependent'] if (OUT/p/'attempts.jsonl').exists())
    if prior+len(pending)>256:raise RuntimeError('256-request hard cap exceeded')
    lock=threading.Lock();stop=threading.Event();local=threading.local()
    def call(t):
        if stop.is_set():return
        utc=datetime.now(timezone.utc).isoformat();start=time.monotonic()
        with lock:
            with ap.open('a',encoding='utf-8') as f:f.write(json.dumps({'task_id':t['task_id'],'utc':utc})+'\n');f.flush()
        row={k:v for k,v in t.items() if k!='payload'};row.update(endpoint=URL,started_utc=utc)
        try:
            if not hasattr(local,'session'):local.session=requests.Session()
            response=local.session.post(URL,headers={'Authorization':'Bearer '+key},json=t['payload'],timeout=(15,300),allow_redirects=False)
            row['http_status']=response.status_code
            try:row['body']=response.json()
            except ValueError:row['error_type']='non_json_response'
            if response.status_code!=200:stop.set()
        except requests.RequestException as exc:row['error_type']=type(exc).__name__;stop.set()
        row['elapsed_seconds']=round(time.monotonic()-start,3)
        with lock:
            with (directory/'api_raw.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False).replace(key,'[REDACTED]')+'\n');f.flush()
            print(json.dumps({k:row.get(k) for k in ['dialogue_id','arm','stage','http_status','error_type','elapsed_seconds']}),flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(call,pending))
    raw=records(phase);ok=len(raw)==len(plan) and all(r.get('http_status')==200 for r in raw)
    save(directory/'run_status.json',{'planned':len(plan),'recorded':len(raw),'complete':ok})
    return ok


def export():
    predictions=[];audit=[];errors=[]
    for phase in ['initial','dependent']:
        pp=OUT/phase/'requests.json'
        if not pp.exists():continue
        plan={t['task_id']:t for t in read(pp)}
        for r in records(phase):
            t=plan[r['task_id']];body=r.get('body',{});usage=body.get('usage',{});choice=body.get('choices',[{}])[0]
            msg=choice.get('message',{});detail=usage.get('completion_tokens_details',{})
            audit.append({'task_id':t['task_id'],'dialogue_id':t['dialogue_id'],'arm':t['arm'],'stage':t['stage'],
                'http_status':r.get('http_status'),'returned_model':body.get('model'),'finish_reason':choice.get('finish_reason'),
                'prompt_tokens':usage.get('prompt_tokens'),'completion_tokens':usage.get('completion_tokens'),
                'reasoning_tokens':detail.get('reasoning_tokens'),'total_tokens':usage.get('total_tokens'),
                'reasoning_chars':len(msg.get('reasoning_content') or ''),'elapsed_seconds':r['elapsed_seconds']})
            content=json.loads(t['payload']['messages'][1]['content'])
            try:
                obj=decode(r)
                if t['stage'] in ['global','local']:validate_candidates(obj,content['visible_A'])
                else:
                    final=render(obj,content['visible_A'],content.get('candidates'))
                    predictions.append({k:t[k] for k in ['task_id','dialogue_id','arm','stage']}|final)
            except (ValueError,KeyError,TypeError,IndexError) as exc:
                errors.append({'dialogue_id':t['dialogue_id'],'arm':t['arm'],'stage':t['stage'],'error':str(exc)})
    save(OUT/'predictions.json',predictions);save(OUT/'execution_audit.json',audit);save(OUT/'validation_errors.json',errors)
    print({'valid_final_outputs':len(predictions),'validation_errors':len(errors),'records':len(audit)},flush=True)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','export','dependent']);args=p.parse_args()
    if args.action=='prepare':prepare()
    elif args.action=='export':export()
    elif args.action=='dependent':dependent()
    else:
        key=os.getenv('DASHSCOPE_API_KEY') or (getpass.getpass('API key (hidden): ') if sys.stdin.isatty() else sys.stdin.readline().strip())
        if not key:raise SystemExit('No API key')
        if not run_phase('initial',key):export();raise SystemExit(2)
        dependent()
        if not run_phase('dependent',key):export();raise SystemExit(2)
        export()
