"""Frozen 48-dialogue, equal-two-call controlled pilot. Secrets are never persisted."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import argparse
import collections
import getpass
import hashlib
import json
import os
from pathlib import Path
import random
import re
import sys
import threading
import time
import requests
from isc4_open import ROOT, read, save, freeze, sha, visible
from isc5_module import DIRECT, SELFCHECK, LEDGER, VERIFY, compile_cues, guard_ledger, index_provenance, render_extraction

DATA=ROOT/'data/isc5';OUT=ROOT/'results/isc5'
URL='https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'

def make_task(did,split,stage,system,content,source_id=None):
    payload={'model':'qwen3.8-flash','temperature':0,'enable_thinking':False,'max_tokens':4096,
        'response_format':{'type':'json_object'},'messages':[{'role':'system','content':system},
        {'role':'user','content':json.dumps(content,ensure_ascii=False)}]}
    h=sha(payload)
    return {'task_id':h[:24],'request_sha256':h,'dialogue_id':did,'split':split,
            'stage':stage,'source_task_id':source_id,'payload':payload}

def prepare():
    rows=[json.loads(x) for x in (ROOT/'data/dailydialog.jsonl').read_text(encoding='utf-8').splitlines()]
    old=set()
    for name in ['data/natural_pilot.json','data/stage2/dialogues.json','data/revision/dialogues.json']:
        old.update(r['id'] for r in read(ROOT/name))
    norm=lambda r:re.sub(r'\W+','',' '.join(r['turns']).lower())
    excluded={norm(r) for r in rows if r['split']!='test' or r['id'] in old}
    unique={}
    for r in rows:
        if r['split']=='test' and norm(r) not in excluded:unique.setdefault(norm(r),r)
    new=random.Random(2026110105).sample(list(unique.values()),16)
    dialogues=[{**r,'evaluation_split':'development'} for r in read(ROOT/'data/isc4/dialogues.json')]
    dialogues += [{**r,'arm':'new_random','evaluation_split':'new_evaluation'} for r in new]
    freeze(DATA/'dialogues.json',dialogues)
    plan=[]
    for d in dialogues:
        turns=visible(d)
        plan.append(make_task(d['id'],d['evaluation_split'],'direct',DIRECT,{'visible_A':turns}))
        plan.append(make_task(d['id'],d['evaluation_split'],'ledger',LEDGER,{'visible_A':turns,'lexical_cues':compile_cues(turns)}))
    random.Random(2026110105).shuffle(plan);freeze(OUT/'initial/requests.json',plan)
    manifest={'dialogues':len(dialogues),'development':32,'new_evaluation':16,'length_filter':None,
        'new_selection_seed':2026110105,'new_pool':len(unique),'historical_excluded_ids':len(old),
        'source_sha256':hashlib.sha256((ROOT/'data/dailydialog.jsonl').read_bytes()).hexdigest(),
        'dialogues_sha256':sha(dialogues),'initial_requests_sha256':sha(plan),
        'protocol_sha256':hashlib.sha256((ROOT/'ISC5_PROTOCOL.md').read_bytes()).hexdigest(),
        'module_sha256':hashlib.sha256((ROOT/'experiments/isc5_module.py').read_bytes()).hexdigest(),
        'maximum_planned_calls':192,'attempt_cap':240,'max_workers':4}
    freeze(DATA/'manifest.json',manifest);print(json.dumps(manifest))

def decode(r):
    if r.get('http_status')!=200:raise ValueError('HTTP failure')
    c=r['body']['choices'][0]
    if c.get('finish_reason')!='stop':raise ValueError('Incomplete generation')
    obj=json.loads(c['message']['content'])
    if not isinstance(obj,dict):raise ValueError('Output must be object')
    return obj

def records(stage):
    path=OUT/stage/'api_raw.jsonl'
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []

def dependent():
    plan={t['task_id']:t for t in read(OUT/'initial/requests.json')};tasks=[];errors=[]
    for r in records('initial'):
        t=plan[r['task_id']];content=json.loads(t['payload']['messages'][1]['content']);turns=content['visible_A']
        try:
            obj=decode(r)
            if t['stage']=='direct':
                render_extraction(obj,turns);name='selfcheck';system=SELFCHECK
                content={'visible_A':turns,'draft':obj}
            else:
                guard_ledger(obj,turns);name='ledger_verify';system=VERIFY
                content={**content,'ledger':index_provenance(obj)}
            tasks.append(make_task(t['dialogue_id'],t['split'],name,system,content,t['task_id']))
        except (ValueError,KeyError,TypeError,IndexError) as exc:errors.append({'task_id':t['task_id'],'dialogue_id':t['dialogue_id'],'stage':t['stage'],'error':str(exc)})
    freeze(OUT/'dependent/requests.json',tasks);save(OUT/'dependent/source_errors.json',errors)
    print({'dependent':len(tasks),'invalid_sources':len(errors)})

def run_stage(stage,key):
    directory=OUT/stage;plan=read(directory/'requests.json');raw=records(stage)
    previous={r['task_id'] for r in raw};attempt_path=directory/'attempts.jsonl'
    attempts=[json.loads(x) for x in attempt_path.read_text(encoding='utf-8').splitlines()] if attempt_path.exists() else []
    if any(a['task_id'] not in previous for a in attempts):raise RuntimeError('Unrecorded interrupted request needs audit')
    if any(r.get('http_status')!=200 for r in raw):raise RuntimeError('Previous HTTP failure: inspect before retry')
    pending=[t for t in plan if t['task_id'] not in previous]
    existing=sum(len((OUT/s/'attempts.jsonl').read_text(encoding='utf-8').splitlines()) for s in ['initial','dependent'] if (OUT/s/'attempts.jsonl').exists())
    if existing+len(pending)>240:raise RuntimeError('Attempt cap')
    lock=threading.Lock();stop=threading.Event()
    def call(t):
        if stop.is_set():return
        utc=datetime.now(timezone.utc).isoformat();start=time.monotonic()
        with lock:
            with attempt_path.open('a',encoding='utf-8') as f:f.write(json.dumps({'task_id':t['task_id'],'utc':utc})+'\n')
        row={k:v for k,v in t.items() if k!='payload'};row.update(endpoint=URL,started_utc=utc)
        try:
            response=requests.post(URL,headers={'Authorization':'Bearer '+key},json=t['payload'],timeout=(15,180),allow_redirects=False)
            row['http_status']=response.status_code
            try:row['body']=response.json()
            except ValueError:row['error_type']='non_json_response'
            if response.status_code!=200:stop.set()
        except requests.RequestException as exc:row['error_type']=type(exc).__name__;stop.set()
        row['elapsed_seconds']=round(time.monotonic()-start,3)
        with lock:
            with (directory/'api_raw.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False).replace(key,'[REDACTED]')+'\n')
            print(json.dumps({k:row.get(k) for k in ['dialogue_id','stage','http_status','error_type','elapsed_seconds']}),flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i in range(0,len(pending),4):
            list(pool.map(call,pending[i:i+4]))
            if stop.is_set():break
    raw=records(stage);ok=len(raw)==len(plan) and all(r.get('http_status')==200 for r in raw)
    save(directory/'run_status.json',{'planned':len(plan),'recorded':len(raw),'complete':ok})
    return ok

def export():
    result=[];errors=[];audit=[]
    for phase in ['initial','dependent']:
        pp=OUT/phase/'requests.json'
        if not pp.exists():continue
        plan={t['task_id']:t for t in read(pp)}
        for r in records(phase):
            t=plan[r['task_id']];content=json.loads(t['payload']['messages'][1]['content'])
            audit.append({'task_id':t['task_id'],'dialogue_id':t['dialogue_id'],'stage':t['stage'],
                'tokens':r.get('body',{}).get('usage',{}).get('total_tokens'),
                'elapsed_seconds':r['elapsed_seconds'],'http_status':r.get('http_status')})
            if t['stage']=='ledger':continue
            try:
                obj=render_extraction(decode(r),content['visible_A'])
                result.append({k:t[k] for k in ['task_id','dialogue_id','stage','split']}|obj)
            except (ValueError,TypeError,KeyError,IndexError) as exc:errors.append({'dialogue_id':t['dialogue_id'],'stage':t['stage'],'error':str(exc)})
    save(OUT/'predictions.json',result);save(OUT/'validation_errors.json',errors);save(OUT/'execution_audit.json',audit)
    print({'valid_predictions':len(result),'invalid_predictions':len(errors),'http_records':len(audit)})

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','dependent','run','export']);args=p.parse_args()
    if args.action=='prepare':prepare()
    elif args.action=='dependent':dependent()
    elif args.action=='export':export()
    else:
        key=os.getenv('DASHSCOPE_API_KEY') or (getpass.getpass('API key (hidden): ') if sys.stdin.isatty() else sys.stdin.readline().strip())
        if not key:raise SystemExit('No API key')
        if not run_stage('initial',key):raise SystemExit(2)
        dependent()
        if not run_stage('dependent',key):raise SystemExit(2)
        export()
