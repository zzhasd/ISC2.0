"""Audited continuation for transport-only exhausted append-run tasks.

Does not change inference, prompts, metrics, or existing log rows. At most three
additional attempts (global 4-6), only if no HTTP/model response was received.
Unknown usage remains unknown. Refuses semantic/HTTP errors and in-flight tasks.
"""
import argparse
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import importlib
import requests
from .client import Client, URL
from .common import BASE, digest, jsonlines, save
from .inference import decode
from .evaluate_prompts_v2 import validate_v2


def recover(evaluation=False, workers=2):
    module=importlib.import_module('isc113.Evidence-Adaptive v3')
    run_id='evidence_adaptive_v3_append'+('/evaluation' if evaluation else '')
    client=Client(os.environ.get('QWEN_API_KEY') or os.environ.get('DASHSCOPE_API_KEY'),run_id)
    starts={}
    for row in client.rows:
        if row['event']=='start':starts[row['task_id']]=row
    tasks=[]
    for tid, start in starts.items():
        done=[r for r in client.rows if r['event']=='complete' and r['task_id']==tid]
        if any(r.get('valid') for r in done):continue
        begun={r['attempt_id'] for r in client.rows if r['event']=='start' and r['task_id']==tid}
        if begun != {r['attempt_id'] for r in done}:raise RuntimeError('Unresolved in-flight attempt')
        if len(done)<3:continue
        if len(done)>=6:raise RuntimeError('Recovery attempt budget exhausted: '+start['logical_name'])
        if any(r.get('http_status') is not None or r.get('body') is not None for r in done):
            raise RuntimeError('Recovery refuses tasks with HTTP/model responses: '+start['logical_name'])
        tasks.append((start,done))
    audit=BASE/'results/evidence_adaptive_v3_append'/('evaluation_transport_recovery.json' if evaluation else 'inference_transport_recovery.json')
    save(audit,dict(reason='Explicit transport-only continuation after exhausted initial three attempts',
                    tasks=[s['task_id'] for s,d in tasks],max_global_attempt=6,
                    prompts_changed=False,unknown_usage_imputed=False,original_rows_preserved=True))
    def work(task):
        start,done=task
        request=start['request']; name=start['logical_name'];tid=start['task_id']
        content=__import__('json').loads(request['messages'][1]['content'])
        validator=(lambda obj:validate_v2(obj,content['predictions'],content['reference'])) if evaluation else (lambda obj:(module.validate_review(obj,content['visible_turns']) if name.endswith('/adaptive_v2_review') else module.validate_claims(obj,content['visible_turns'])))
        for attempt in range(len(done)+1,7):
            base=dict(task_id=tid,attempt_id=digest({'task':tid,'attempt':attempt}),logical_name=name,attempt=attempt,utc=datetime.now(timezone.utc).isoformat(),transport_recovery=True)
            client.append(dict(base,event='start',request=request))
            row=dict(base,event='complete',valid=False)
            began=time.monotonic()
            try:
                response=requests.post(URL,json=request,headers={'Authorization':'Bearer '+client.key},timeout=(15,180),allow_redirects=False)
                row['http_status']=response.status_code;row['body']=response.json()
                if response.status_code==200:
                    validator(decode(row['body']));row['valid']=True
                else:row['error']='provider_error'
            except Exception as exc:
                row['error']=type(exc).__name__+': '+str(exc)[:250]
            row['elapsed_seconds']=round(time.monotonic()-began,3);client.append(row)
            if row['valid']:return name
            if row.get('http_status') is not None or row.get('body') is not None:
                raise RuntimeError('Recovery received unsuccessful HTTP/model response; inspect log')
            time.sleep(2)
        raise RuntimeError('Transport recovery exhausted: '+name)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for name in pool.map(work,tasks):print('Transport recovery succeeded: '+name,flush=True)
    print('Recovered tasks: '+str(len(tasks)),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('--evaluation',action='store_true');args=parser.parse_args();recover(args.evaluation)
