"""Bounded resumable execution. Key read once from stdin/environment, never saved."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import collections
import json
import os
import sys
import threading
import time
import requests
from isc3_common import *

URL='https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'
ATTEMPT_CAP=6500
TOKEN_CAP=8_000_000

def run_plan(name, key):
    directory=OUT/name;plan=read(directory/'requests.json')
    # Refuse a second live runner; the OS releases the file lock on termination.
    with (directory/'runner.lock').open('a+b') as guard:
        if guard.tell()==0:guard.write(b'0');guard.flush()
        guard.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(guard.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return execute(name,plan,key)

def execute(name,plan,key):
    directory=OUT/name;raw_path=directory/'api_raw.jsonl';attempt_path=directory/'attempts.jsonl'
    existing=raw_index(directory);counts=collections.Counter();total_attempts=0;tokens=0
    transport_errors=0
    for path in OUT.glob('*/api_raw.jsonl'):
        for line in path.read_text(encoding='utf-8').splitlines():
            row=json.loads(line);tokens+=row.get('body',{}).get('usage',{}).get('total_tokens',0)
            if row.get('error'):transport_errors+=1
    for path in OUT.glob('*/attempts.jsonl'):
        attempts=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        total_attempts+=len(attempts)
        returns={json.loads(line)['attempt_id'] for line in (path.parent/'api_raw.jsonl').read_text(encoding='utf-8').splitlines()} if (path.parent/'api_raw.jsonl').exists() else set()
        unresolved=[a for a in attempts if a['attempt_id'] not in returns]
        if unresolved:
            save(path.parent/'unresolved_attempts.json',unresolved)
            raise RuntimeError('Unresolved potentially billed attempts: inspect before resubmission')
        if path==attempt_path:counts.update(a['task_id'] for a in attempts)
    pending=[t for t in plan if t['task_id'] not in existing]
    if total_attempts+len(pending)>ATTEMPT_CAP:raise RuntimeError('Attempt cap would be exceeded')
    lock=threading.Lock();stop=threading.Event();local=threading.local();finished=0;failures=[]
    started=time.monotonic()
    def status():
        return {'stage':name,'planned':len(plan),'successful_tasks':len(existing)+finished,
                'pending_at_start':len(pending),'recorded_suite_tokens':tokens,'suite_attempts':total_attempts,
                'complete':len(existing)+finished==len(plan),'failures':failures,
                'elapsed_seconds':round(time.monotonic()-started,1)}
    print(json.dumps(status()),flush=True)
    def work(t):
        nonlocal total_attempts,tokens,transport_errors,finished
        for retry in range(3):
            with lock:
                if stop.is_set():return
                if tokens>=TOKEN_CAP or total_attempts>=ATTEMPT_CAP or counts[t['task_id']]>=3:
                    failures.append({'task_id':t['task_id'],'error':'Budget/task attempt cap'});stop.set();return
                now=datetime.now(timezone.utc).isoformat();aid=t['task_id']+'_'+now
                attempt={'task_id':t['task_id'],'attempt_id':aid,'utc':now,'attempt_number':counts[t['task_id']]+1}
                with attempt_path.open('a',encoding='utf-8') as f:f.write(json.dumps(attempt)+'\n');f.flush()
                counts[t['task_id']]+=1;total_attempts+=1
            record={k:v for k,v in t.items() if k!='payload'}
            record.update(attempt_id=aid,started_utc=now,endpoint=URL,attempt_number=attempt['attempt_number'])
            start=time.monotonic()
            try:
                if not hasattr(local,'session'):local.session=requests.Session()
                response=local.session.post(URL,headers={'Authorization':'Bearer '+key},json=t['payload'],timeout=(15,180),allow_redirects=False)
                record['http_status']=response.status_code
                try:record['body']=response.json()
                except ValueError:record['body']={'unparsed_body':response.text[:2000]}
            except requests.RequestException as exc:
                record['error']=str(exc).replace(key,'[REDACTED]')
                if hasattr(local,'session'):local.session.close();del local.session
            record['elapsed_seconds']=round(time.monotonic()-start,3)
            with lock:
                with raw_path.open('a',encoding='utf-8') as f:
                    f.write(json.dumps(record,ensure_ascii=False).replace(key,'[REDACTED]')+'\n');f.flush()
                tokens+=record.get('body',{}).get('usage',{}).get('total_tokens',0)
                if record.get('http_status')==200:
                    finished+=1
                    if finished%25==0:
                        save(directory/'run_status.json',status());print(json.dumps(status()),flush=True)
                    return
                if 'error' not in record:
                    failures.append({'task_id':t['task_id'],'http_status':record.get('http_status')});stop.set();return
                transport_errors+=1
                if transport_errors>=50 or counts[t['task_id']]>=3:
                    failures.append({'task_id':t['task_id'],'error':'Transport retry cap'});stop.set();return
            time.sleep(2)
    with ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(work,pending))
    result=status();save(directory/'run_status.json',result);print(json.dumps(result),flush=True)
    return result['complete']

def main():
    import isc3_prepare
    key=os.environ.get('DASHSCOPE_API_KEY') or sys.stdin.readline().strip()
    if not key:raise SystemExit('Missing API key')
    if not run_plan('initial',key):raise SystemExit(2)
    isc3_prepare.dependent()
    if not run_plan('dependent',key):raise SystemExit(2)
    print('All planned ISC3 calls returned; semantic/schema validation is separate.',flush=True)

if __name__=='__main__':main()
