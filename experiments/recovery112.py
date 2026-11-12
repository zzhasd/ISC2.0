"""Audited first-valid recovery of failed calls; preserve all previous artifacts."""
import argparse
from datetime import datetime,timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import requests
import isc4_open as i4
import isc7_run as i7
from isc5_run import decode
from isc7_module import validate_candidates,union_candidates,render,JUDGE
from isc4_open import ROOT,read,save,freeze,sha,visible

OUT=ROOT/'results/recovery112'
DATA=ROOT/'data/merged112'

def lines(p):return [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines()] if p.exists() else []

def valid(t,r,kind):
    if kind=='isc4':return i4.decode(r,t)
    obj=decode(r);v=json.loads(t['payload']['messages'][1]['content'])
    return validate_candidates(obj,v['visible_A']) if t['stage'] in ['global','local'] else render(obj,v['visible_A'],v.get('candidates'))

def origins():
    result=[]
    for cohort,base in [('old32',ROOT/'results'),('new80',ROOT/'results/extension80')]:
        for kind,phases in [('isc4',['baseline']),('isc7',['initial','dependent'])]:
            for phase in phases:
                p=base/kind/phase;rs={r['task_id']:r for r in lines(p/'api_raw.jsonl')}
                for t in read(p/'requests.json'):
                    result.append({'cohort':cohort,'kind':kind,'phase':phase,'source_directory':str(p.relative_to(ROOT)),
                                   'task':t,'original_response':rs.get(t['task_id'])})
    return result

def prepare():
    entries=origins();bad=[]
    for e in entries:
        try:valid(e['task'],e['original_response'] or {},e['kind'])
        except (ValueError,KeyError,IndexError,TypeError) as exc:
            r=e['original_response'] or {};bad.append({**{k:e[k] for k in ['cohort','kind','phase','source_directory']},
                'task':e['task'],'original_error':str(exc),'original_http_status':r.get('http_status'),
                'failure_type':'transport' if r.get('http_status')!=200 else 'structure_or_evidence'})
    freeze(OUT/'repair_plan.json',bad)
    freeze(OUT/'original_tasks.json',entries)
    hashes={}
    for base in [ROOT/'results/isc4',ROOT/'results/isc7',ROOT/'results/extension80',ROOT/'results/merged112',ROOT/'data/isc4',ROOT/'data/isc7',ROOT/'data/extension80',DATA]:
        for p in base.rglob('*'):
            if p.is_file():hashes[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    freeze(OUT/'preservation_hashes.json',hashes)
    freeze(OUT/'protocol_manifest.json',{'protocol_sha256':hashlib.sha256((ROOT/'RECOVERY112_PROTOCOL.md').read_bytes()).hexdigest(),
        'original_actual_calls':1348,'failed_logical_requests':len(bad),'max_additional_attempts_per_logical_request':3,
        'selection':'first valid by original validators, never by semantic score','dialogues':112})
    print([{'kind':r['kind'],'dialogue':r['task']['dialogue_id'],'stage':r['task'].get('stage'),'k':r['task'].get('k'),'error':r['original_error']} for r in bad])

def attempts():return lines(OUT/'attempt_results.jsonl')

def chosen(t,kind,original=None):
    if original:
        try:valid(t,original,kind);return original
        except (ValueError,KeyError,IndexError,TypeError):pass
    for r in attempts():
        if r['task_id']==t['task_id'] and r['kind']==kind:
            try:valid(t,r,kind);return r
            except (ValueError,KeyError,IndexError,TypeError):pass
    return None

def execute(t,kind,key):
    old=chosen(t,kind)
    if old:return old
    prior=[r for r in attempts() if r['task_id']==t['task_id'] and r['kind']==kind]
    ap=OUT/'attempt_starts.jsonl'
    starts=lines(ap);done={r['attempt_id'] for r in attempts()}
    if any(r['attempt_id'] not in done for r in starts):raise RuntimeError('Unrecorded attempt requires audit')
    for number in range(len(prior)+1,4):
        attempt_id=sha({'kind':kind,'task_id':t['task_id'],'additional_attempt':number})[:24]
        utc=datetime.now(timezone.utc).isoformat()
        with ap.open('a',encoding='utf-8') as f:f.write(json.dumps({'attempt_id':attempt_id,'task_id':t['task_id'],'kind':kind,'utc':utc})+'\n');f.flush()
        row={k:v for k,v in t.items() if k!='payload'}
        row.update(attempt_id=attempt_id,kind=kind,additional_attempt=number,started_utc=utc,endpoint=i4.URL)
        start=time.monotonic()
        try:
            response=requests.post(i4.URL,headers={'Authorization':'Bearer '+key},json=t['payload'],timeout=(15,180 if kind=='isc4' else 300),allow_redirects=False)
            row['http_status']=response.status_code
            try:row['body']=response.json()
            except ValueError:row['error_type']='non_json_response'
        except requests.RequestException as exc:row['error_type']=type(exc).__name__
        row['elapsed_seconds']=round(time.monotonic()-start,3)
        try:valid(t,row,kind);row['valid']=True
        except (ValueError,KeyError,IndexError,TypeError) as exc:row.update(valid=False,validation_error=str(exc))
        with (OUT/'attempt_results.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False).replace(key,'[REDACTED]')+'\n');f.flush()
        print({k:row.get(k) for k in ['dialogue_id','k','arm','stage','additional_attempt','http_status','valid','validation_error']},flush=True)
        if row['valid']:return row
        time.sleep(8 if row.get('http_status')==429 else 3)
    return None

def dependent_tasks():
    original=read(OUT/'original_tasks.json');by={e['task']['task_id']:e for e in original}
    initial={(e['task']['dialogue_id'],e['task']['arm'],e['task']['stage']):e for e in original if e['kind']=='isc7' and e['phase']=='initial'}
    existing={(e['task']['dialogue_id'],e['task']['arm']) for e in original if e['kind']=='isc7' and e['phase']=='dependent'}
    ds=read(DATA/'dialogues.json');tasks=[];missing=[]
    for d in ds:
        for arm in ['dual_off','dual_on']:
            if (d['id'],arm) in existing:continue
            sources=[initial[d['id'],arm,s] for s in ['global','local']]
            try:
                rs=[chosen(e['task'],'isc7',e['original_response']) for e in sources]
                cs=[valid(e['task'],r or {},'isc7') for e,r in zip(sources,rs)]
                merged=union_candidates(*cs)
                tasks.append(i7.task(d['id'],arm,'judge',JUDGE,{'visible_A':visible(d),'candidates':merged},[e['task']['task_id'] for e in sources]))
            except (ValueError,KeyError,IndexError,TypeError) as exc:missing.append({'dialogue_id':d['id'],'arm':arm,'error':str(exc)})
    freeze(OUT/'new_dependent_requests.json',tasks);save(OUT/'remaining_source_errors.json',missing)
    return tasks

def run():
    key=os.getenv('DASHSCOPE_API_KEY') or getpass.getpass('API key (hidden): ')
    if not key:raise RuntimeError('Missing API key')
    for e in read(OUT/'repair_plan.json'):
        execute(e['task'],e['kind'],key);time.sleep(3)
    for t in dependent_tasks():execute(t,'isc7',key);time.sleep(3)
    export()

def export():
    entries=read(OUT/'original_tasks.json');newp=OUT/'new_dependent_requests.json'
    if newp.exists():entries += [{'kind':'isc7','phase':'dependent','task':t,'original_response':None,'cohort':'old32' if t['dialogue_id'] in {d['id'] for d in read(ROOT/'data/isc4/dialogues.json')} else 'new80'} for t in read(newp)]
    p4=[];p7=[];audit7=[];missing=[];bindings=[]
    for e in entries:
        t=e['task'];kind=e['kind'];r=chosen(t,kind,e['original_response'])
        if not r:
            missing.append({'kind':kind,'dialogue_id':t['dialogue_id'],'k':t.get('k'),'arm':t.get('arm'),'stage':t.get('stage'),'task_id':t['task_id']});continue
        obj=valid(t,r,kind)
        bindings.append({'kind':kind,'task_id':t['task_id'],'selection':'original_valid' if r is e['original_response'] else 'first_valid_additional','attempt_id':r.get('attempt_id')})
        if kind=='isc4':p4.append({k:t[k] for k in ['task_id','dialogue_id','k','K']}|obj)
        else:
            body=r.get('body',{});u=body.get('usage',{});msg=body['choices'][0]['message']
            audit7.append({'task_id':t['task_id'],'dialogue_id':t['dialogue_id'],'arm':t['arm'],'stage':t['stage'],'http_status':r.get('http_status'),
                'returned_model':body.get('model'),'finish_reason':body['choices'][0].get('finish_reason'),
                'prompt_tokens':u.get('prompt_tokens'),'completion_tokens':u.get('completion_tokens'),'reasoning_tokens':u.get('completion_tokens_details',{}).get('reasoning_tokens'),
                'total_tokens':u.get('total_tokens'),'reasoning_chars':len(msg.get('reasoning_content') or ''),'elapsed_seconds':r['elapsed_seconds']})
            if t['stage'] in ['direct','judge']:p7.append({k:t[k] for k in ['task_id','dialogue_id','arm','stage']}|obj)
    save(OUT/'isc4/predictions.json',p4);save(OUT/'isc4/full_predictions.json',[p for p in p4 if p['k']==p['K'] and p['K']>0])
    save(OUT/'isc7/predictions.json',p7);save(OUT/'isc7/selected_execution_audit.json',audit7)
    actual=[]
    lookup={e['task']['task_id']:e['task'] for e in entries if e['kind']=='isc7'}
    allrows=[e['original_response'] for e in entries if e['kind']=='isc7' and e['original_response']]+[r for r in attempts() if r['kind']=='isc7']
    for r in allrows:
        t=lookup[r['task_id']];body=r.get('body',{});u=body.get('usage',{});ch=body.get('choices',[{}])[0];msg=ch.get('message',{})
        actual.append({'task_id':t['task_id'],'attempt_id':r.get('attempt_id'),'dialogue_id':t['dialogue_id'],'arm':t['arm'],'stage':t['stage'],
            'http_status':r.get('http_status'),'returned_model':body.get('model'),'finish_reason':ch.get('finish_reason'),
            'prompt_tokens':u.get('prompt_tokens'),'completion_tokens':u.get('completion_tokens'),'reasoning_tokens':u.get('completion_tokens_details',{}).get('reasoning_tokens'),
            'total_tokens':u.get('total_tokens'),'reasoning_chars':len(msg.get('reasoning_content') or ''),'elapsed_seconds':r['elapsed_seconds']})
    save(OUT/'isc7/execution_audit.json',actual)
    save(OUT/'selection_bindings.json',bindings);save(OUT/'remaining_missing.json',missing)
    save(OUT/'execution_status.json',{'additional_actual_calls':len(attempts()),'total_actual_calls':1348+len(attempts()),
        'selected_prefix_results':len(p4),'selected_factorial_final_results':len(p7),'remaining_missing':len(missing),
        'note':'execution_audit includes every original and supplementary attempt for actual cost; selected_execution_audit contains only selected valid responses.'})
    print(read(OUT/'execution_status.json'))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','export']);a=p.parse_args()
    if a.action=='prepare':prepare()
    elif a.action=='run':run()
    else:export()
