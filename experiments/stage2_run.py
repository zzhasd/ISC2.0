"""One conversation per request, no hidden-target utterances in A-only calls."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import argparse
import copy
import hashlib
import json
import os
import random
import sys
import threading
import time
import requests

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/stage2'
OUT=ROOT/'results/stage2'
URL='https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'
SYSTEM='''Evaluate a fixed catalogue of propositions about the indicated dialogue target(s).
Use only the supplied transcript. Each request is independent. In a one-sided transcript,
A is the visible speaker addressing hidden B. Every utterance by B has been removed;
you must assess B, not A. In a complete transcript, S0 and S1 are the two speakers.
Assign true only when the text supports the proposition for that target; false only
when it supports its negation; otherwise unknown. Unknown is not false. A fact about
the visible speaker, their spouse/child/friend, or a news subject is not automatically
a fact about the target. Do not infer pregnancy from someone else's pregnancy, unemployment
from general unemployment discussion, or marriage from a girlfriend breakup.
Possessives, shared-relationship statements, confirmations and references may supply
evidence about the hidden target. Generic responses such as 'good' do not identify
the hidden disclosure. A question's specific content need not be true, but an unrebutted
possessive such as 'your wife' can support the relationship presupposition.
Employment includes an unambiguous present professional service role; hypothetical or
future work does not establish a current job. Personal financial hardship is not the
same as shopping for a cheaper item. Interpret medical facts only at supported specificity.
Return only JSON: {"targets":[{"target":"B", "facts":[{"id":"attribute_id",
"label":"true|false|unknown", "evidence_turns":[1]}]}]}.
Return all catalogue ids exactly once per requested target. Evidence turn numbers refer
only to the supplied transcript. Unknown can use an empty evidence list. Do not add
attributes, probabilities, summaries, missing dialogue reconstruction or prose.'''

def load(name):return json.loads((DATA/name).read_text(encoding='utf-8'))

def task(payload,condition,dialogue=None,target=None,trial=0):
 digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
 return {'task_id':f'{digest[:16]}_r{trial}','request_sha256':digest,'condition':condition,
         'dialogue_id':None if dialogue is None else dialogue['id'],
         'arm':None if dialogue is None else dialogue['arm'],'target_source_speaker':target,
         'trial':trial,'payload':payload}

def build_plan():
 inventory=load('inventory.json'); dialogues=load('dialogues.json')
 base={'model':'qwen-plus','temperature':0,'enable_thinking':False,'max_tokens':2200,
       'response_format':{'type':'json_object'}}
 def payload(content,cap=2200):
  return {**base,'max_tokens':cap,'messages':[{'role':'system','content':SYSTEM},
                                           {'role':'user','content':json.dumps(content,ensure_ascii=False)}]}
 tasks=[]
 for d in dialogues:
  full=[{'turn':i+1,'speaker':f'S{i%2}','text':text} for i,text in enumerate(d['turns'])]
  tasks.append(task(payload({'targets':['S0','S1'],'catalogue':inventory,'transcript':full},4000),'full',d))
  for hidden in [0,1]:
   visible=[text for i,text in enumerate(d['turns']) if i%2!=hidden]
   a_only=[{'turn':i+1,'speaker':'A','text':text} for i,text in enumerate(visible)]
   tasks.append(task(payload({'targets':['B'],'catalogue':inventory,'transcript':a_only}),'a_only',d,hidden))
 tasks.append(task(payload({'targets':['B'],'catalogue':inventory,'transcript':[]}),'prior'))
 rng=random.Random(20261033)
 repeats=rng.sample([t for t in tasks if t['condition']=='a_only'],3)
 rng.shuffle(tasks)
 for original in repeats:
  repeat=copy.deepcopy(original)
  repeat.update(task_id=original['request_sha256'][:16]+'_r1',condition='repeat',trial=1,
                original_task_id=original['task_id'])
  tasks.append(repeat)
 assert len(tasks)==100 and len({t['task_id'] for t in tasks})==100
 return tasks

def freeze_plan():
 OUT.mkdir(parents=True,exist_ok=True)
 planned=build_plan()
 text=json.dumps(planned,ensure_ascii=False,indent=2)
 p=OUT/'requests.json'
 if p.exists() and p.read_text(encoding='utf-8')!=text:raise RuntimeError('Frozen request plan changed')
 p.write_text(text,encoding='utf-8')
 return planned

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
 planned=freeze_plan()
 if args.prepare_only:
  print(json.dumps({'requests':len(planned),'a_only':64,'full':32,'prior':1,'exact_repeats':3}));return
 key=os.environ.get('DASHSCOPE_API_KEY') or sys.stdin.readline().strip()
 if not key:raise SystemExit('No key supplied')
 out=OUT/'api_raw.jsonl';completed=set();attempts=0
 if out.exists():
  for line in out.read_text(encoding='utf-8').splitlines():
   r=json.loads(line);attempts+=1
   if r.get('http_status')==200:completed.add(r['task_id'])
 pending=[t for t in planned if t['task_id'] not in completed]
 interruption_path=OUT/'interruption_audit.json'
 reserved_unlogged=0
 if interruption_path.exists():
  interruption=json.loads(interruption_path.read_text(encoding='utf-8'))
  reserved_unlogged=interruption['max_unlogged_requests']
  omitted={t['task_id'] for t in planned[-interruption['omit_last_repeat_requests']:]}
  assert all(t['condition']=='repeat' for t in planned if t['task_id'] in omitted)
  pending=[t for t in pending if t['task_id'] not in omitted]
 if attempts+reserved_unlogged+len(pending)>100:raise SystemExit('Stage 2 request cap reached; no more calls sent')
 stop=threading.Event(); lock=threading.Lock()
 def call(t):
  if stop.is_set():return
  record={k:v for k,v in t.items() if k!='payload'}
  record['started_utc']=datetime.now(timezone.utc).isoformat();start=time.monotonic()
  with lock:
   with (OUT/'attempts_after_resume.jsonl').open('a',encoding='utf-8') as f:
    f.write(json.dumps({'task_id':t['task_id'],'started_utc':record['started_utc']})+'\n')
  try:
   response=requests.post(URL,headers={'Authorization':'Bearer '+key},json=t['payload'],timeout=100,allow_redirects=False)
   record['http_status']=response.status_code
   try:record['body']=response.json()
   except ValueError:record['body']={'unparsed_body':response.text[:1000].replace(key,'[REDACTED]')}
   if response.status_code!=200:stop.set()
  except requests.RequestException as exc:
   record['error']=str(exc).replace(key,'[REDACTED]');stop.set()
  record['elapsed_seconds']=round(time.monotonic()-start,3)
  with lock:
   with out.open('a',encoding='utf-8') as f:f.write(json.dumps(record,ensure_ascii=False).replace(key,'[REDACTED]')+'\n')
   print(json.dumps({'task':t['task_id'],'condition':t['condition'],'http':record.get('http_status'),
                     'usage':record.get('body',{}).get('usage'),'seconds':record['elapsed_seconds']}),flush=True)
 for i in range(0,len(pending),3):
  with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(call,pending[i:i+3]))
  if stop.is_set():break
 print(json.dumps({'finished':True,'stopped_on_error':stop.is_set(),'utc':datetime.now(timezone.utc).isoformat()}),flush=True)

if __name__=='__main__':main()
