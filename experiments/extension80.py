"""Fixed 80-dialogue extension; reuse frozen inference code, isolate all outputs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
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
import isc4_open as old4
import isc7_run as old7
from isc4_open import ROOT,read,save,freeze,sha,visible

DATA=ROOT/'data/extension80'
OUT=ROOT/'results/extension80'

def normalized(turns):
    return re.sub(r'[^\w]+',' ', ' '.join(turns).casefold()).strip()

def prepare():
    source=[json.loads(s) for s in (ROOT/'data/dailydialog.jsonl').read_text(encoding='utf-8').splitlines()]
    used=set(); texts=set(); files={}
    paths=list((ROOT/'data').rglob('dialogues.json'))+[ROOT/'data/natural_pilot.json',ROOT/'data/stage2/screening_v0_dialogues.json']
    for p in paths:
        if 'extension80' in str(p) or 'merged112' in str(p) or not p.exists():continue
        rows=read(p);files[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
        for r in rows:
            if 'id' in r:used.add(r['id'])
            if 'dialogue_id' in r:used.add(r['dialogue_id'])
            if 'turns' in r:texts.add(normalized(r['turns']))
    for p in (ROOT/'results').rglob('requests.json'):
        if 'extension80' in str(p) or 'merged112' in str(p):continue
        for r in read(p):
            if r.get('dialogue_id'):used.add(r['dialogue_id'])
    pool=[r for r in source if r['split']=='test' and r['id'] not in used and normalized(r['turns']) not in texts]
    random.Random(20261102).shuffle(pool)
    selected=[];seen=set();duplicates=[]
    for r in pool:
        norm=normalized(r['turns'])
        if norm in seen:duplicates.append(r['id']);continue
        seen.add(norm);selected.append({**r,'arm':'new_random'})
        if len(selected)==80:break
    assert len(selected)==80
    freeze(DATA/'dialogues.json',selected)
    prefix=[old4.task(d,k) for d in selected for k in range(1,len(visible(d))+1)]
    random.Random(20261101).shuffle(prefix)
    initial=[]
    for d in selected:
        for arm in old7.ARMS:
            for stage,system in ([('direct',old7.DIRECT)] if arm.startswith('direct') else [('global',old7.GLOBAL),('local',old7.LOCAL)]):
                initial.append(old7.task(d['id'],arm,stage,system,{'visible_A':visible(d)}))
    random.Random(2026110107).shuffle(initial)
    freeze(OUT/'isc4/baseline/requests.json',prefix)
    freeze(OUT/'isc7/initial/requests.json',initial)
    preserve={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for base in ['data/isc4','data/isc7','results/isc4','results/isc7'] for p in (ROOT/base).rglob('*') if p.is_file()}
    freeze(DATA/'manifest.json',{'seed':20261102,'new_dialogues':80,'old_dialogues':32,'merged_unique_dialogues':112,
        'candidate_pool_ids':[r['id'] for r in pool],'excluded_used_ids':sorted(used),'selection_skipped_duplicates':duplicates,
        'source_sha256':hashlib.sha256((ROOT/'data/dailydialog.jsonl').read_bytes()).hexdigest(),
        'dialogues_sha256':sha(selected),'prefix_calls':len(prefix),'factorial_max_calls':640,
        'prefix_requests_sha256':sha(prefix),'factorial_initial_sha256':sha(initial),
        'selection_source_files':files,'original_artifact_hashes':preserve,
        'frozen_code_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['ISC4_PROTOCOL.md','ISC7_PROTOCOL.md','EXTENSION_PROTOCOL.md','experiments/isc4_open.py','experiments/isc7_module.py','experiments/isc7_run.py','experiments/extension80.py']}})
    print({'selected':80,'prefix_calls':len(prefix),'factorial_max_calls':640,'pool':len(pool)})

def configure():
    old4.OUT=OUT/'isc4';old4.DATA=DATA
    old7.OUT=OUT/'isc7';old7.DATA=DATA

def run_phase(directory,key,cap,timeout):
    plan=read(directory/'requests.json');rp=directory/'api_raw.jsonl';ap=directory/'attempts.jsonl'
    rows=[json.loads(s) for s in rp.read_text(encoding='utf-8').splitlines()] if rp.exists() else []
    attempts=[json.loads(s) for s in ap.read_text(encoding='utf-8').splitlines()] if ap.exists() else []
    recorded={r['task_id'] for r in rows}
    if any(a['task_id'] not in recorded for a in attempts):raise RuntimeError('Unrecorded attempt requires audit')
    audit_path=OUT/'http_failure_audit.json'
    audited={r['task_id'] for r in read(audit_path)} if audit_path.exists() else set()
    if any(r.get('http_status')!=200 and r['task_id'] not in audited for r in rows):raise RuntimeError('Prior HTTP failure requires audit; no retry')
    pending=[t for t in plan if t['task_id'] not in recorded]
    assert len(plan)<=cap and len(attempts)+len(pending)<=cap
    lock=threading.Lock();pace=threading.Lock();next_start=[0.0];stop=threading.Event();local=threading.local()
    def call(t):
        if stop.is_set():return
        # Operational pacing only: <=24 starts/minute, with at most four in flight.
        with pace:
            delay=next_start[0]-time.monotonic()
            if delay>0:time.sleep(delay)
            if stop.is_set():return
            next_start[0]=time.monotonic()+2.5
        now=datetime.now(timezone.utc).isoformat();start=time.monotonic()
        with lock:
            with ap.open('a',encoding='utf-8') as f:f.write(json.dumps({'task_id':t['task_id'],'utc':now})+'\n');f.flush()
        r={k:v for k,v in t.items() if k!='payload'};r.update(endpoint=old4.URL,started_utc=now)
        try:
            if not hasattr(local,'session'):local.session=requests.Session()
            response=local.session.post(old4.URL,headers={'Authorization':'Bearer '+key},json=t['payload'],timeout=(15,timeout),allow_redirects=False)
            r['http_status']=response.status_code
            try:r['body']=response.json()
            except ValueError:r['error_type']='non_json_response'
            if response.status_code!=200:stop.set()
        except requests.RequestException as exc:r['error_type']=type(exc).__name__;stop.set()
        r['elapsed_seconds']=round(time.monotonic()-start,3)
        with lock:
            with rp.open('a',encoding='utf-8') as f:f.write(json.dumps(r,ensure_ascii=False).replace(key,'[REDACTED]')+'\n');f.flush()
            print(json.dumps({k:r.get(k) for k in ['dialogue_id','k','arm','stage','http_status','error_type','elapsed_seconds']}),flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(call,pending))
    rows=[json.loads(s) for s in rp.read_text(encoding='utf-8').splitlines()] if rp.exists() else []
    ok=len(rows)==len(plan) and all(r.get('http_status')==200 or r['task_id'] in audited for r in rows)
    save(directory/'run_status.json',{'planned':len(plan),'recorded':len(rows),'http_success':sum(r.get('http_status')==200 for r in rows),'complete':ok,'audited_failures_are_missing_not_retried':True})
    return ok

def run():
    refs=read(DATA/'reference.json');manifest=read(DATA/'reference_manifest.json')
    assert sha(refs)==manifest['reference_sha256'] and len(refs)==80
    configure()
    key=os.getenv('DASHSCOPE_API_KEY') or getpass.getpass('API key (hidden): ')
    if not key:raise RuntimeError('Missing API key')
    m=read(DATA/'manifest.json')
    if not run_phase(OUT/'isc4/baseline',key,m['prefix_calls'],180):return 2
    old4.export()
    if not run_phase(OUT/'isc7/initial',key,480,300):return 2
    old7.dependent()
    if not run_phase(OUT/'isc7/dependent',key,160,300):return 2
    old7.export()
    return 0

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','export']);a=p.parse_args()
    if a.action=='prepare':prepare()
    elif a.action=='run':raise SystemExit(run())
    else:configure();old4.export();old7.export()
