"""Append-only audit ledger, exact payload cache, bounded format retries."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
import time
import requests
from .core import ENDPOINT, digest


class Client:
    def __init__(self,key,folder,endpoint=ENDPOINT):
        if not key:
            raise ValueError('Missing QWEN_API_KEY / DASHSCOPE_API_KEY')
        if not endpoint.startswith('https://'):
            raise ValueError('HTTPS endpoint required')
        self.key=key
        self.endpoint=endpoint
        self.lock=threading.Lock()
        self.stop=threading.Event()
        self.local=threading.local()
        self.path=Path(folder)/'attempts.jsonl'
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.rows=[json.loads(s) for s in self.path.read_text(encoding='utf-8').splitlines()] if self.path.exists() else []

    def append(self,row):
        safe=json.loads(json.dumps(row,ensure_ascii=False).replace(self.key,'[REDACTED]'))
        with self.lock:
            with self.path.open('a',encoding='utf-8') as f:
                f.write(json.dumps(safe,ensure_ascii=False)+'\n')
                f.flush()
            self.rows.append(safe)

    @staticmethod
    def parse(body,validate):
        c=body['choices'][0]
        if c.get('finish_reason')!='stop':
            raise ValueError('Incomplete response')
        s=c['message']['content'].strip()
        if s.startswith('```'):
            s=s.split('\n',1)[1].rsplit('```',1)[0]
        try:
            return validate(json.loads(s))
        except (ValueError,TypeError,KeyError,AttributeError) as original:
            # Same complete-object recovery already used by ISC113 ELARA runners.
            # Never repair truncated JSON, synthesize a bracket, or infer decisions.
            dec=json.JSONDecoder()
            for match in re.finditer(r'\{',s):
                try:
                    obj,_=dec.raw_decode(s,match.start())
                    return validate(obj)
                except (ValueError,TypeError,KeyError,AttributeError):
                    pass
            raise original

    def call(self,name,payload,validate):
        task=digest(dict(name=name,endpoint=self.endpoint,payload=payload))
        with self.lock:
            rows=[r for r in self.rows if r['task_id']==task]
        for r in rows:
            if r['event']=='complete' and r.get('valid'):
                return self.parse(r['body'],validate),task
        # Recover a complete previously returned object before issuing another call.
        for r in rows:
            if r['event']=='complete' and r.get('http_status')==200:
                try:
                    result=self.parse(r['body'],validate)
                except (ValueError,TypeError,KeyError,AttributeError):
                    continue
                self.append(dict(event='wrapper_recovery',task_id=task,attempt_id=r['attempt_id'],logical_name=name))
                return result,task
        started={r['attempt_id'] for r in rows if r['event']=='start'}
        completed={r['attempt_id'] for r in rows if r['event']=='complete'}
        if started-completed:
            raise RuntimeError('Unresolved in-flight request; inspect ledger before retry: '+name)
        acknowledged={r['attempt_id'] for r in rows if r['event']=='network_retry_acknowledged'}
        if any(r.get('billing_unknown') and r['attempt_id'] not in acknowledged for r in rows):
            raise RuntimeError('Prior network failure has uncertain billing; inspect ledger before retry: '+name)
        for attempt in range(len(completed)+1,7):
            if self.stop.is_set():
                raise RuntimeError('Provider circuit open')
            aid=digest([task,attempt])
            base=dict(task_id=task,attempt_id=aid,logical_name=name,attempt=attempt,utc=datetime.now(timezone.utc).isoformat())
            self.append(dict(base,event='start',request=payload))
            row=dict(base,event='complete',valid=False)
            start=time.monotonic()
            try:
                if not hasattr(self.local,'session'):
                    self.local.session=requests.Session()
                r=self.local.session.post(self.endpoint,json=payload,headers={'Authorization':'Bearer '+self.key},timeout=(15,180),allow_redirects=False)
                row.update(http_status=r.status_code,body=r.json())
                if r.status_code==200:
                    result=self.parse(row['body'],validate)
                    row['valid']=True
                else:
                    row['error']='provider_error'
            except requests.exceptions.SSLError as e:
                row.update(error=type(e).__name__+': '+str(e)[:500],billing_unknown=True,tls_failure=True)
            except requests.RequestException as e:
                # A timeout may already have incurred billing; no automatic resend.
                row.update(error=type(e).__name__+': '+str(e)[:500],billing_unknown=True)
            except (ValueError,TypeError,KeyError,AttributeError) as e:
                row['error']=type(e).__name__+': '+str(e)[:250]
            row['elapsed_seconds']=round(time.monotonic()-start,3)
            self.append(row)
            if row['valid']:
                return result,task
            if row.get('billing_unknown'):
                if row.get('tls_failure') and attempt<6:
                    # Bounded retries of TLS failures are separately auditable.
                    # This does not assert the provider charged zero tokens.
                    self.append(dict(event='network_retry_acknowledged',task_id=task,attempt_id=aid,logical_name=name,
                                     reason='bounded retry of TLS transport failure; usage unavailable'))
                else:
                    raise RuntimeError('Network failure with uncertain billing: '+name)
            status=row.get('http_status')
            if status in (401,403,404) or (status and 400<=status<500 and status!=429):
                self.stop.set()
                raise RuntimeError(f'Provider rejected request HTTP {status}: {name}')
            if attempt<6:
                time.sleep(min(8,2**attempt))
        raise RuntimeError('Attempt limit reached: '+name)
