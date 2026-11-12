"""Resumable requests, first valid response, all attempts charged, secret redaction."""
from datetime import datetime, timezone
import json
import threading
import time
import requests
from .common import BASE, digest, jsonlines
from .inference import decode

URL='https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'

class Client:
    def __init__(self,key,run_id='main'):
        if not key: raise ValueError('Missing QWEN_API_KEY')
        self.key=key; self.lock=threading.Lock(); self.stop=threading.Event()
        self.path=BASE/'runs'/run_id/'attempts.jsonl'; self.path.parent.mkdir(parents=True,exist_ok=True)
        self.rows=jsonlines(self.path); self.local=threading.local()

    def append(self,row):
        # Redact error bodies too; never log headers or credential.
        safe=json.loads(json.dumps(row,ensure_ascii=False).replace(self.key,'[REDACTED]'))
        with self.lock:
            with self.path.open('a',encoding='utf-8') as f:
                f.write(json.dumps(safe,ensure_ascii=False)+'\n'); f.flush()
            self.rows.append(safe)

    def call(self,name,payload,validate):
        tid=digest({'logical_name':name,'payload':payload})
        old=[r for r in self.rows if r['task_id']==tid and r.get('event')=='complete']
        for r in old:
            if r.get('valid'): return validate(decode(r['body'])),tid
        # No automatic resend after an interrupted response: billing status is unknown.
        starts={r['attempt_id'] for r in self.rows if r['task_id']==tid and r.get('event')=='start'}
        done={r['attempt_id'] for r in old}
        if starts-done: raise RuntimeError('Unresolved in-flight request; audit before retry: '+name)
        for attempt in range(len(old)+1,4):
            if self.stop.is_set(): raise RuntimeError('Provider circuit is open')
            aid=digest({'task':tid,'attempt':attempt})
            base={'task_id':tid,'attempt_id':aid,'logical_name':name,'attempt':attempt,
                  'utc':datetime.now(timezone.utc).isoformat()}
            self.append(dict(base,event='start',request=payload))
            t=time.monotonic(); row=dict(base,event='complete',valid=False)
            try:
                if not hasattr(self.local,'session'): self.local.session=requests.Session()
                r=self.local.session.post(URL,json=payload,headers={'Authorization':'Bearer '+self.key},
                                          timeout=(15,180),allow_redirects=False)
                row['http_status']=r.status_code
                row['body']=r.json()
                if r.status_code==200:
                    result=validate(decode(row['body'])); row['valid']=True
                else: row['error']='provider_error'
            except Exception as e: row['error']=type(e).__name__+': '+str(e)[:250]
            row['elapsed_seconds']=round(time.monotonic()-t,3); self.append(row)
            if row['valid']: return result,tid
            status=row.get('http_status')
            if status in [401,403,404]: self.stop.set(); raise RuntimeError('Provider authentication/model access failure')
            if status and 400<=status<500 and status!=429: raise RuntimeError('Provider rejected request: '+name)
            time.sleep(min(8,2**attempt))
        raise RuntimeError('Attempt limit exceeded: '+name)
