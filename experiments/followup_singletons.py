"""Exploratory batch-sensitivity probes; never replace main-run predictions."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import sys
import time
import requests
from run_api import ROOT, URL, tasks, utcnow

# Selected after inspecting main-run failures. These are not random or held-out.
SELECTED=[('dailydialog','test_838'),('dailydialog','test_189'),
          ('dailydialog','test_303'),('dailydialog','test_671'),
          ('controlled','cross_turn_0_1'),('controlled','cross_turn_5_1'),
          ('controlled','confirmation_3_0'),('controlled','confirmation_0_0')]

def main():
    key=sys.stdin.readline().strip()
    if not key:raise SystemExit('No key')
    output=ROOT/'results/singletons_raw.jsonl'
    if output.exists():raise SystemExit('Follow-up already exists; refusing accidental paid rerun')
    main_calls=len((ROOT/'results/api_raw.jsonl').read_text(encoding='utf-8').splitlines())
    assert main_calls+1+len(SELECTED)<=100
    planned=[]
    for dataset,item_id in SELECTED:
        task=next(t for t in tasks() if t['dataset']==dataset and t['condition']=='a_only' and any(x['item_id']==item_id for x in t['mapping'].values()))
        opaque=next(k for k,v in task['mapping'].items() if v['item_id']==item_id)
        payload=json.loads(json.dumps(task['payload']))
        items=json.loads(payload['messages'][1]['content'])['items']
        item=next(x for x in items if x['id']==opaque)
        payload['messages'][1]['content']=json.dumps({'items':[item]},ensure_ascii=False)
        payload['max_tokens']=1000
        planned.append({'dataset':dataset,'item_id':item_id,'condition':'a_only',
                        'original_task_id':task['task_id'],'payload':payload,
                        'request_sha256':hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()})
    (ROOT/'results/singletons_requests.json').write_text(json.dumps(planned,ensure_ascii=False,indent=2),encoding='utf-8')
    def call(task):
        start=time.monotonic()
        r=requests.post(URL,headers={'Authorization':'Bearer '+key},json=task['payload'],timeout=90,allow_redirects=False)
        rec={k:v for k,v in task.items() if k!='payload'}
        rec.update(http_status=r.status_code,body=r.json(),utc=utcnow(),elapsed_seconds=time.monotonic()-start)
        return rec
    for i in range(0,len(planned),3):
        with ThreadPoolExecutor(max_workers=3) as pool:
            records=list(pool.map(call,planned[i:i+3]))
        with output.open('a',encoding='utf-8') as f:
            for rec in records:f.write(json.dumps(rec,ensure_ascii=False).replace(key,'[REDACTED]')+'\n')
        print(json.dumps({'completed':min(i+3,len(planned)),'total':len(planned)}),flush=True)
        if any(r['http_status']!=200 for r in records):break

if __name__=='__main__':main()
