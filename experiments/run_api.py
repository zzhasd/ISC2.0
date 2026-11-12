"""Bounded Qwen pilot; API key via process stdin or environment, never disk."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import os
import random
import sys
import threading
import time
import requests

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'
SYSTEM = '''You are evaluating evidence about a fictional dialogue participant, B.
A addresses hidden B as "you"; any other named person, including Casey, is a third party.
Each input item is independent. Never borrow evidence across items.
For each candidate proposition, assign probabilities to:
true: the available text supports that the proposition about B is true;
false: the available text supports its negation;
unknown: the available text does not establish either answer.
Unknown is not false. Questions alone need not confirm their content, but possessive
presuppositions, corrections, reference order and confirmations may supply evidence.
Use only the provided text. Do not infer a diagnosis from a nonspecific symptom,
or transfer A's or a third person's attributes to B. An unordered word list has lost
all holder, polarity and order relations not explicitly recoverable from the list.
Return a JSON object {"answers": [{"id": "...", "p_true": 0.0,
"p_false": 0.0, "p_unknown": 1.0, "label": "unknown", "evidence": "brief exact quote or empty"}]}.
Probabilities must sum to 1. Return every requested id exactly once. No other prose.'''

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def tasks():
    result=[]
    rng=random.Random(20261031)
    for dataset,file in [('dailydialog','natural_pilot.json'),('controlled','controlled_pilot.json')]:
        rows=json.loads((ROOT/'data'/file).read_text(encoding='utf-8'))
        conditions=list(rows[0]['conditions'])
        for condition in conditions:
            blocks=[]
            if dataset=='controlled':
                groups={}
                for r in rows: groups.setdefault(r['group'],[]).append(r)
                halves=[[],[]]
                for group in groups.values():
                    rng.shuffle(group)
                    for i,r in enumerate(group): halves[i].append(r)
                blocks=halves
            else:
                blocks=[rows.copy()]
            for block in blocks:
                rng.shuffle(block)
                for start in range(0,len(block),6):
                    part=block[start:start+6]
                    assert len(set(r['group'] for r in part))==len(part)
                    payload_items=[]; mapping={}
                    for r in part:
                        opaque=hashlib.sha256(f'{r["id"]}|{condition}|20261031'.encode()).hexdigest()[:12]
                        mapping[opaque]={'item_id':r['id'],'group':r['group']}
                        payload_items.append({'id':opaque,'proposition':r['claim'],'text':r['conditions'][condition]})
                    payload={'model':'qwen-plus','temperature':0,'enable_thinking':False,'max_tokens':4000,
                             'response_format':{'type':'json_object'},
                             'messages':[{'role':'system','content':SYSTEM},
                                         {'role':'user','content':json.dumps({'items':payload_items},ensure_ascii=False)}]}
                    digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
                    result.append({'task_id':digest[:16],'request_sha256':digest,'dataset':dataset,
                                   'condition':condition,'mapping':mapping,'payload':payload})
    rng.shuffle(result)
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',default='results/api_raw.jsonl')
    parser.add_argument('--max-attempts',type=int,default=99)
    args=parser.parse_args()
    key=os.environ.get('DASHSCOPE_API_KEY') or sys.stdin.readline().strip()
    if not key: raise SystemExit('No API key provided in stdin or DASHSCOPE_API_KEY.')
    out=ROOT/args.out; out.parent.mkdir(exist_ok=True)
    planned=tasks()
    # Frozen public requests contain no key. Safe to review and reproduce.
    (ROOT/'results'/'requests.json').write_text(json.dumps(planned,ensure_ascii=False,indent=2),encoding='utf-8')
    completed=set()
    attempts=1 # successful initial 14-token connection probe
    if out.exists():
        for line in out.read_text(encoding='utf-8').splitlines():
            r=json.loads(line); attempts+=1
            if r.get('http_status')==200: completed.add(r['task_id'])
    pending=[t for t in planned if t['task_id'] not in completed]
    if attempts+len(pending)>args.max_attempts+1:
        raise SystemExit('Planned requests exceed hard cap; no requests sent.')
    lock=threading.Lock(); stop=threading.Event()

    def call(task):
        if stop.is_set(): return None
        start=time.monotonic()
        record={k:v for k,v in task.items() if k!='payload'}
        record.update(started_utc=utcnow())
        try:
            response=requests.post(URL,headers={'Authorization':'Bearer '+key},
                                   json=task['payload'],timeout=100,allow_redirects=False)
            record['http_status']=response.status_code
            try: body=response.json()
            except ValueError: body={'unparsed_body':response.text[:2000].replace(key,'[REDACTED]')}
            record['body']=body
            if response.status_code in [401,403,429] or response.status_code>=500:
                stop.set()
        except requests.RequestException as e:
            record['error']=str(e).replace(key,'[REDACTED]'); stop.set()
        record['elapsed_seconds']=round(time.monotonic()-start,3)
        # Defensive redaction also covers service error text.
        serial=json.dumps(record,ensure_ascii=False).replace(key,'[REDACTED]')
        with lock:
            with out.open('a',encoding='utf-8') as f: f.write(serial+'\n')
            print(json.dumps({'task_id':task['task_id'],'dataset':task['dataset'],
                              'condition':task['condition'],'http_status':record.get('http_status'),
                              'usage':record.get('body',{}).get('usage'),
                              'elapsed_seconds':record['elapsed_seconds']},ensure_ascii=False),flush=True)
        return record

    print(json.dumps({'planned_requests':len(planned),'pending':len(pending),'probe_requests':1}),flush=True)
    # Submit in bounded waves: stop after first rate-limit/auth error, no blind retries.
    for i in range(0,len(pending),3):
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(call,pending[i:i+3]))
        if stop.is_set(): break
    print(json.dumps({'finished_utc':utcnow(),'stopped_on_error':stop.is_set()}),flush=True)

if __name__=='__main__': main()
