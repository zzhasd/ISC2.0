"""Auditable, resumable Qwen3.8 revision runs. Secrets only in stdin/environment."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import threading
import time
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/qwen38'
URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'
MODEL = 'qwen3.8-flash'

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def save(p, obj):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

def freeze(path, tasks):
    if path.exists() and read(path) != tasks:
        raise ValueError(f'Refusing to change frozen plan: {path}')
    save(path, tasks)

def convert(tasks):
    output = []
    for task in tasks:
        t = json.loads(json.dumps(task))
        t['original_task_id'] = t.get('task_id')
        t['payload']['model'] = MODEL
        t['request_sha256'] = digest(t['payload'])
        t['task_id'] = t['request_sha256'][:16] + '_r' + str(t.get('trial', 0))
        output.append(t)
    return output

def prepare_reruns():
    # Reuse exact frozen prompts, inputs, grouping, caps and order; model alone changes.
    for name, source in [('stage1', ROOT/'results/requests.json'),
                         ('singletons', ROOT/'results/singletons_requests.json'),
                         ('stage2', ROOT/'results/stage2/requests.json')]:
        freeze(OUT/name/'requests.json', convert(read(source)))

def run(plan_path, key, workers=6, limit=1800):
    directory=Path(plan_path).parent
    # OS releases the lock on process exit; the harmless marker file can remain.
    with (directory/'runner.lock').open('a+b') as guard:
        if guard.tell()==0:guard.write(b'0');guard.flush()
        guard.seek(0)
        if os.name=='nt':
            import msvcrt
            try:msvcrt.locking(guard.fileno(),msvcrt.LK_NBLCK,1)
            except OSError:raise RuntimeError('This request plan already has an active runner')
        else:
            import fcntl
            fcntl.flock(guard.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        return _run(plan_path,key,workers,limit)

def _run(plan_path, key, workers=6, limit=1800):
    plan_path = Path(plan_path)
    plan = read(plan_path); directory = plan_path.parent
    output = directory/'api_raw.jsonl'; attempts_path = directory/'attempts.jsonl'
    raw = [json.loads(x) for x in output.read_text(encoding='utf-8').splitlines()] if output.exists() else []
    completed = {r['task_id'] for r in raw if r.get('http_status') == 200}
    attempted = [json.loads(x) for x in attempts_path.read_text(encoding='utf-8').splitlines()] if attempts_path.exists() else []
    # An interrupted request could have been billed. Do not silently send it again.
    logged_attempts = {r.get('attempt_id') for r in raw}
    unlogged = [r for r in attempted if r['attempt_id'] not in logged_attempts]
    if unlogged:
        save(directory/'unresolved_attempts.json', unlogged)
        raise RuntimeError('Unlogged attempts require explicit audit before resume')
    pending = [t for t in plan if t['task_id'] not in completed]
    previous_counts = {}
    for a in attempted: previous_counts[a['task_id']] = previous_counts.get(a['task_id'], 0) + 1
    if attempted and pending:
        with (directory/'resume_audit.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),
                'completed':len(completed),'pending':len(pending),'prior_recorded_attempts':len(attempted),
                'retried_task_ids':[t['task_id'] for t in pending if t['task_id'] in previous_counts]})+'\n')
    if len(attempted) + len(pending) > limit:
        raise RuntimeError('Hard request cap exceeded before submitting')
    lock = threading.Lock(); stop = threading.Event(); local = threading.local()
    def call(t):
        if stop.is_set(): return
        if previous_counts.get(t['task_id'],0)>=3:
            stop.set();return
        now = datetime.now(timezone.utc).isoformat()
        attempt_id = t['task_id'] + '_' + now
        r = {k:v for k,v in t.items() if k != 'payload'}
        r.update(started_utc=now, attempt_id=attempt_id, endpoint=URL,
                 attempt_number_for_task=previous_counts.get(t['task_id'],0)+1)
        with lock:
            with attempts_path.open('a', encoding='utf-8') as f:
                f.write(json.dumps({'task_id':t['task_id'], 'attempt_id':attempt_id, 'utc':now})+'\n'); f.flush()
        start = time.monotonic()
        try:
            if not hasattr(local,'session'): local.session=requests.Session()
            response = local.session.post(URL, headers={'Authorization':'Bearer '+key}, json=t['payload'],
                                     timeout=(15, 180), allow_redirects=False)
            r['http_status'] = response.status_code
            try: r['body'] = response.json()
            except ValueError: r['body'] = {'unparsed_body':response.text[:2000]}
            if response.status_code != 200: stop.set()
        except requests.RequestException as exc:
            r['error'] = str(exc); stop.set()
            if hasattr(local,'session'):local.session.close();del local.session
        r['elapsed_seconds'] = round(time.monotonic()-start, 3)
        with lock:
            with output.open('a', encoding='utf-8') as f:
                f.write(json.dumps(r, ensure_ascii=False).replace(key, '[REDACTED]')+'\n'); f.flush()
            print(json.dumps({'directory':directory.name, 'task':t['task_id'], 'condition':t.get('condition'),
                              'http':r.get('http_status'), 'seconds':r['elapsed_seconds'],
                              'tokens':r.get('body',{}).get('usage',{}).get('total_tokens')}), flush=True)
    print(json.dumps({'plan':str(plan_path), 'pending':len(pending), 'completed':len(completed)}), flush=True)
    # Reuse a separate HTTPS session in each persistent worker thread. This
    # reduces handshakes without sharing mutable Session state between threads.
    with ThreadPoolExecutor(max_workers=workers) as pool:
      for i in range(0, len(pending), workers):
        recorded_tokens=0
        for path in OUT.rglob('api_raw.jsonl'):
            for line in path.read_text(encoding='utf-8',errors='replace').splitlines():
                try:recorded_tokens+=json.loads(line).get('body',{}).get('usage',{}).get('total_tokens',0)
                except json.JSONDecodeError:pass # another process can be appending its last record
        if recorded_tokens>=8_000_000:
            raise RuntimeError('Revision recorded-token cap reached')
        if any(previous_counts.get(t['task_id'],0)>=3 for t in pending[i:i+workers]):
            stop.set();break
        if len(attempted)+i+len(pending[i:i+workers])>min(limit,len(plan)+50):
            raise RuntimeError('Plan transport-retry allowance exhausted')
        list(pool.map(call, pending[i:i+workers]))
        if stop.is_set(): break
    success = completed | {json.loads(x)['task_id'] for x in output.read_text(encoding='utf-8').splitlines()
                           if json.loads(x).get('http_status') == 200}
    status = {'planned':len(plan), 'successful_tasks':len(success), 'stopped_on_error':stop.is_set(),
              'complete':all(t['task_id'] in success for t in plan)}
    save(directory/'run_status.json', status)
    return status['complete']

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--prepare-reruns', action='store_true')
    p.add_argument('--plan', nargs='+')
    p.add_argument('--workers', type=int, default=6)
    p.add_argument('--transport-resumes', type=int, default=12)
    args = p.parse_args()
    if args.prepare_reruns: prepare_reruns()
    if not args.plan: return
    key = os.environ.get('DASHSCOPE_API_KEY') or sys.stdin.readline().strip()
    if not key: raise SystemExit('Missing API key')
    for path in args.plan:
        for resume in range(args.transport_resumes+1):
            if run(ROOT/path, key, args.workers): break
            raw_path=(ROOT/path).parent/'api_raw.jsonl'
            recent=[json.loads(x) for x in raw_path.read_text(encoding='utf-8').splitlines()][-args.workers:]
            failures=[r for r in recent if r.get('http_status')!=200]
            # Bounded, explicitly recorded transport-only resumes. Never retry HTTP failures.
            if not failures or any('error' not in r for r in failures) or resume==args.transport_resumes:
                raise SystemExit(2)
            time.sleep(2)
        else: raise SystemExit(2)

if __name__ == '__main__': main()
