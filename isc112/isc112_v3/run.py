"""One additional A-only revision call per original cached dual result."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import threading
import time
import requests

from isc112_v2.runner import ROOT, read, save, freeze, lines, sha, verify_frozen, URL
from isc112_v2.core import visible, decode
from .core import PROMPT, render

DATA = ROOT / 'data/isc112_v3'; OUT = ROOT / 'results/isc112_v3'


def prepare():
    verify_frozen()
    ds = read(ROOT / 'data/isc112/dialogues.json')
    old = {p['dialogue_id']: p for p in read(ROOT / 'data/isc112/e3/predictions.json') if p['arm'] == 'dual_on'}
    assert len(old) == 112
    aa = [{'id': d['id'], 'visible_A': visible(d)} for d in ds]
    freeze(DATA / 'visible_A.json', aa); freeze(DATA / 'baseline_predictions.json', list(old.values()))
    freeze(DATA / 'manifest.json', {'dialogues': 112, 'planned_new_logical_calls': 112, 'max_attempts': 4,
        'protocol_sha256': hashlib.sha256((ROOT / 'ISC112_V3_PROTOCOL.md').read_bytes()).hexdigest(),
        'core_sha256': hashlib.sha256((ROOT / 'isc112_v3/core.py').read_bytes()).hexdigest(),
        'baseline_sha256': sha(list(old.values())), 'A_sha256': sha(aa),
        'modes': ['refined', 'retain_union'], 'baseline_generation': 'Original cached A-only dual_on, all 336 original calls charged'})
    tasks = []
    for d in aa:
        prior = [{k: f[k] for k in ['claim', 'time', 'evidence_turns']} | {'id': f'b{i+1}'} for i, f in enumerate(old[d['id']]['facts'])]
        content = {'visible_A': d['visible_A'], 'prior_items': prior}
        payload = {'model': 'qwen3.8-flash', 'temperature': 0, 'enable_thinking': True, 'thinking_budget': 2048,
            'max_tokens': 4096, 'response_format': {'type': 'json_object'},
            'messages': [{'role': 'system', 'content': PROMPT}, {'role': 'user', 'content': json.dumps(content, ensure_ascii=False)}]}
        tasks.append({'task_id': sha(payload)[:24], 'request_sha256': sha(payload), 'dialogue_id': d['id'], 'stage': 'revision', 'payload': payload})
    random.Random(2026110301).shuffle(tasks); freeze(OUT / 'requests.json', tasks)
    return {'new_calls_planned': len(tasks), 'cached_baseline_calls': 336}


def valid(t, r):
    u = json.loads(t['payload']['messages'][1]['content'])
    return render(decode(r), u['visible_A'], u['prior_items'])


def chosen(t, rows):
    for r in rows:
        if r['task_id'] != t['task_id']: continue
        try: valid(t, r); return r
        except (ValueError, TypeError, KeyError, IndexError, AttributeError): pass
    return None


def verify():
    verify_frozen(); m = read(DATA / 'manifest.json')
    assert m['protocol_sha256'] == hashlib.sha256((ROOT / 'ISC112_V3_PROTOCOL.md').read_bytes()).hexdigest()
    assert m['core_sha256'] == hashlib.sha256((ROOT / 'isc112_v3/core.py').read_bytes()).hexdigest()
    assert m['baseline_sha256'] == sha(read(DATA / 'baseline_predictions.json'))
    assert m['A_sha256'] == sha(read(DATA / 'visible_A.json'))
    if (DATA/'operational_amendment.json').exists():
        assert read(DATA/'operational_amendment.json')['sha256'] == hashlib.sha256((ROOT/'ISC112_V3_OPERATIONAL_AMENDMENT.md').read_bytes()).hexdigest()


def blocked(t, rows):
    return any(r['task_id']==t['task_id'] and r.get('http_status')==400 and
               r.get('body',{}).get('error',{}).get('code')=='data_inspection_failed' for r in rows)


def run():
    verify(); rows = lines(OUT / 'api_raw.jsonl'); starts = lines(OUT / 'attempt_starts.jsonl')
    assert {r['attempt_id'] for r in rows} == {r['attempt_id'] for r in starts}, 'Unrecorded attempt requires audit'
    key = os.environ.get('DASHSCOPE_API_KEY') or (getpass.getpass('API key (hidden): ') if sys.stdin.isatty() else sys.stdin.readline().strip())
    if not key: raise RuntimeError('Missing API key')
    lock = threading.Lock(); stop = threading.Event(); local = threading.local()
    def append(path, x):
        with lock:
            with path.open('a', encoding='utf-8') as f: f.write(json.dumps(x, ensure_ascii=False).replace(key, '[REDACTED]') + '\n'); f.flush()
    def execute(t):
        prior = [r for r in rows if r['task_id'] == t['task_id']]
        for n in range(len(prior) + 1, 5):
            if stop.is_set(): return
            aid = sha({'task': t['task_id'], 'attempt': n})[:24]
            row = {k: t[k] for k in ['task_id', 'dialogue_id', 'stage']}
            row.update(attempt_id=aid, attempt=n, started_utc=datetime.now(timezone.utc).isoformat())
            append(OUT / 'attempt_starts.jsonl', row); start = time.monotonic()
            try:
                if not hasattr(local, 'session'): local.session = requests.Session()
                response = local.session.post(URL, json=t['payload'], headers={'Authorization': 'Bearer ' + key}, timeout=(15,300), allow_redirects=False)
                row['http_status'] = response.status_code
                try: row['body'] = response.json()
                except ValueError: row['error_type'] = 'non_json_response'
            except requests.RequestException as e: row['error_type'] = type(e).__name__
            row['elapsed_seconds'] = round(time.monotonic() - start, 3)
            try: valid(t,row); row['valid'] = True
            except (ValueError, TypeError, KeyError, IndexError, AttributeError) as e: row.update(valid=False, validation_error=str(e))
            append(OUT / 'api_raw.jsonl', row)
            print({k: row.get(k) for k in ['dialogue_id','attempt','http_status','valid','validation_error']}, flush=True)
            if row['valid']: return
            status = row.get('http_status')
            if status==400 and row.get('body',{}).get('error',{}).get('code')=='data_inspection_failed': return
            if status and 400 <= status < 500 and status != 429: stop.set(); return
            time.sleep(min(20, 2 ** n + (5 if status == 429 else 0)))
    try:
        pending = [t for t in read(OUT / 'requests.json') if not chosen(t, rows) and not blocked(t,rows)]
        with ThreadPoolExecutor(max_workers=4) as pool: list(pool.map(execute, pending))
    finally: print(export(), flush=True)


def export():
    tasks = read(OUT / 'requests.json'); raw = lines(OUT / 'api_raw.jsonl'); old = {p['dialogue_id']:p for p in read(DATA / 'baseline_predictions.json')}
    refined = []; union = []; selection = []; missing = []; costs = []
    for r in raw:
        body=r.get('body',{});u=body.get('usage',{});ch=body.get('choices',[{}])[0];msg=ch.get('message',{})
        costs.append({k:r.get(k) for k in ['task_id','attempt_id','dialogue_id','stage','valid','http_status','elapsed_seconds']} |
            {'total_tokens':u.get('total_tokens'),'reasoning_tokens':u.get('completion_tokens_details',{}).get('reasoning_tokens'),
             'returned_model':body.get('model'),'reasoning_chars':len(msg.get('reasoning_content') or ''),'finish_reason':ch.get('finish_reason')})
    norm=lambda s:' '.join(s.lower().split())
    for t in tasks:
        r=chosen(t,raw)
        if r is None and not blocked(t,raw):missing.append({'dialogue_id':t['dialogue_id'],'task_id':t['task_id']});continue
        if r is None:
            p={**old[t['dialogue_id']],'task_id':t['task_id'],'stage':'baseline_fallback','arm':'refined',
               'outcome':'provider_blocked_baseline_fallback','baseline_task_id':old[t['dialogue_id']]['task_id']}
            selection.append({'task_id':t['task_id'],'attempt_id':None,'selection':'explicit_provider_blocked_baseline_fallback'})
        else:
            p={k:t[k] for k in ['task_id','dialogue_id','stage']} | {'arm':'refined','outcome':'new_revision'} | valid(t,r)
            selection.append({'task_id':t['task_id'],'attempt_id':r['attempt_id'],'selection':'first_structurally_valid'})
        refined.append(p)
        found={}
        for f in old[t['dialogue_id']]['facts'] + p['facts']:
            k=(norm(f['claim']),norm(f['time']))
            if k not in found:found[k]=f
        union.append({**p,'arm':'retain_union','facts':list(found.values())})
    save(OUT/'refined/predictions.json',refined);save(OUT/'retain_union/predictions.json',union)
    save(OUT/'selection_bindings.json',selection);save(OUT/'revision_cost_ledger.json',costs);save(OUT/'remaining_missing.json',missing)
    baseline=[r for r in read(ROOT/'data/isc112/e3/cost_ledger.json') if r['arm']=='dual_on']
    pipeline=baseline+costs
    for mode in ['refined','retain_union']:save(OUT/mode/'cost_ledger.json',pipeline)
    return {'valid_dialogues':len(refined),'new_revision_valid':sum(p['outcome']=='new_revision' for p in refined),
        'baseline_fallback':sum(p['outcome']!='new_revision' for p in refined),'new_actual_calls':len(raw),
        'pipeline_actual_calls':len(pipeline),'missing':len(missing),'new_tokens':sum(r.get('total_tokens') or 0 for r in costs)}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','export','early','review','reuse','analyze','check','report']);p.add_argument('--mode',choices=['refined','retain_union','guarded','guarded_v2'],default='refined');a=p.parse_args()
    if a.action in ['prepare','run','export']:print(globals()[a.action]());return
    from . import evaluation
    print(getattr(evaluation,a.action)(a.mode))


if __name__=='__main__':main()
