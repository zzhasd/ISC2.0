"""Frozen, resumable API runner; secrets exist only in process memory."""
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

from . import core

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/isc112_v2'
OUT = ROOT / 'results/isc112_v2'
URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'
ARM = 'evidence_dual_on'


def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))


def save(p, x):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2), encoding='utf-8')


def sha(x): return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def freeze(p, x):
    if Path(p).exists():
        if read(p) != x: raise RuntimeError('Frozen file differs: ' + str(p))
    else: save(p, x)


def lines(p): return [json.loads(s) for s in Path(p).read_text(encoding='utf-8').splitlines()] if Path(p).exists() else []


def protected_files():
    files = [ROOT / 'ISC7_PROTOCOL.md', ROOT / 'README.md']
    for base in ['isc112', 'data/isc112', 'results/isc112']:
        files.extend(p for p in (ROOT / base).rglob('*') if p.is_file() and '__pycache__' not in str(p))
    files.extend((ROOT / 'experiments').glob('isc7*.py'))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def task(did, stage, system, content, sources=()):
    payload = {'model': 'qwen3.8-flash', 'temperature': 0, 'enable_thinking': True,
               'thinking_budget': 2048, 'max_tokens': 4096, 'response_format': {'type': 'json_object'},
               'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': json.dumps(content, ensure_ascii=False)}]}
    h = sha(payload)
    return {'task_id': h[:24], 'request_sha256': h, 'dialogue_id': did, 'arm': ARM,
            'stage': stage, 'source_task_ids': list(sources), 'payload': payload}


def prepare():
    ds = read(ROOT / 'data/isc112/dialogues.json')
    assert len(ds) == 112 and len({d['id'] for d in ds}) == 112
    # The runtime snapshot contains A ONLY, never the hidden B utterances.
    aa = [{'id': d['id'], 'visible_A': core.visible(d)} for d in ds]
    freeze(DATA / 'visible_A.json', aa)
    freeze(DATA / 'preservation_hashes.json', protected_files())
    prompts = {s: getattr(core, s.upper()) for s in ['global', 'local', 'judge']}
    freeze(DATA / 'prompts.json', prompts)
    freeze(DATA / 'manifest.json', {'dialogues': 112, 'logical_calls': 336, 'max_attempts_per_call': 4,
        'primary_reference_hits_to_exceed': 100, 'primary_unsupported_fraction_not_to_exceed': 156 / 403,
        'protocol_sha256': hashlib.sha256((ROOT / 'ISC112_V2_PROTOCOL.md').read_bytes()).hexdigest(),
        'core_sha256': hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest(),
        'prompts_sha256': sha(prompts), 'A_sha256': sha(aa), 'development_comparison': True})
    tasks = [task(d['id'], s, prompts[s], {'visible_A': d['visible_A']}) for d in aa for s in ['global', 'local']]
    random.Random(2026110208).shuffle(tasks)
    freeze(OUT / 'initial/requests.json', tasks)
    return {'dialogues': len(aa), 'initial_requests': len(tasks)}


def validate(t, r):
    u = json.loads(t['payload']['messages'][1]['content']); obj = core.decode(r)
    return core.candidates(obj, u['visible_A']) if t['stage'] in ['global', 'local'] else core.render(obj, u['visible_A'], u['candidates'])


def chosen(t, records):
    for r in records:
        if r['task_id'] == t['task_id']:
            try: validate(t, r); return r
            except (ValueError, TypeError, KeyError, IndexError, AttributeError): pass
    return None


def verify_frozen():
    m = read(DATA / 'manifest.json')
    assert hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest() == m['core_sha256'], 'Frozen inference code changed'
    assert hashlib.sha256((ROOT / 'ISC112_V2_PROTOCOL.md').read_bytes()).hexdigest() == m['protocol_sha256'], 'Frozen protocol changed'
    assert sha(read(DATA / 'visible_A.json')) == m['A_sha256']
    assert protected_files() == read(DATA / 'preservation_hashes.json'), 'Original files changed'


def run_phase(phase, key, max_attempts=4):
    assert max_attempts in {4, 12}
    if max_attempts > 4:
        amendment = read(DATA / 'recovery_manifest.json')
        assert amendment['max_total_attempts'] == max_attempts
        assert amendment['amendment_sha256'] == hashlib.sha256((ROOT / 'ISC112_V2_RECOVERY_AMENDMENT.md').read_bytes()).hexdigest()
    directory = OUT / phase; plan = read(directory / 'requests.json')
    rows = lines(directory / 'api_raw.jsonl'); starts = lines(directory / 'attempt_starts.jsonl')
    done = {r['attempt_id'] for r in rows}
    if any(a['attempt_id'] not in done for a in starts): raise RuntimeError('Unrecorded attempt requires audit before resume')
    pending = [t for t in plan if not chosen(t, rows)]
    lock = threading.Lock(); stop = threading.Event(); local = threading.local()
    def append(path, row):
        with lock:
            with path.open('a', encoding='utf-8') as f:
                f.write(json.dumps(row, ensure_ascii=False).replace(key, '[REDACTED]') + '\n'); f.flush()
    def execute(t):
        if stop.is_set(): return
        prior = [r for r in rows if r['task_id'] == t['task_id']]
        for n in range(len(prior) + 1, max_attempts + 1):
            if stop.is_set(): return
            aid = sha({'task': t['task_id'], 'attempt': n})[:24]
            stamp = datetime.now(timezone.utc).isoformat()
            append(directory / 'attempt_starts.jsonl', {'task_id': t['task_id'], 'attempt_id': aid, 'attempt': n, 'utc': stamp})
            row = {k: v for k, v in t.items() if k != 'payload'}
            row.update(attempt_id=aid, attempt=n, started_utc=stamp)
            start = time.monotonic()
            try:
                if not hasattr(local, 'session'): local.session = requests.Session()
                response = local.session.post(URL, json=t['payload'], headers={'Authorization': 'Bearer ' + key}, timeout=(15, 300), allow_redirects=False)
                row['http_status'] = response.status_code
                try: row['body'] = response.json()
                except ValueError: row['error_type'] = 'non_json_response'
            except requests.RequestException as exc: row['error_type'] = type(exc).__name__
            row['elapsed_seconds'] = round(time.monotonic() - start, 3)
            try: validate(t, row); row['valid'] = True
            except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc: row.update(valid=False, validation_error=str(exc))
            append(directory / 'api_raw.jsonl', row)
            print(json.dumps({k: row.get(k) for k in ['dialogue_id', 'stage', 'attempt', 'http_status', 'valid', 'validation_error']}, ensure_ascii=False), flush=True)
            status = row.get('http_status')
            if status and 400 <= status < 500 and status != 429:
                stop.set(); return
            if row['valid']: return
            time.sleep(min(30, 2 ** n + (5 if status == 429 else 0)))
    with ThreadPoolExecutor(max_workers=4) as pool: list(pool.map(execute, pending))
    rows = lines(directory / 'api_raw.jsonl')
    missing = [t['task_id'] for t in plan if not chosen(t, rows)]
    save(directory / 'status.json', {'logical_requests': len(plan), 'actual_attempts': len(rows), 'missing_task_ids': missing})
    if missing: raise RuntimeError(f'{phase}: {len(missing)} requests unresolved; see status and raw records')


def dependent():
    initial = read(OUT / 'initial/requests.json'); rows = lines(OUT / 'initial/api_raw.jsonl')
    lookup = {(t['dialogue_id'], t['stage']): t for t in initial}; tasks = []; audit = []
    for d in read(DATA / 'visible_A.json'):
        src = [lookup[d['id'], s] for s in ['global', 'local']]
        cs = [validate(t, chosen(t, rows) or {}) for t in src]
        merged = core.union(*cs)
        audit.append({'dialogue_id': d['id'], 'global': cs[0], 'local': cs[1], 'merged': merged})
        tasks.append(task(d['id'], 'judge', read(DATA / 'prompts.json')['judge'],
                          {'visible_A': d['visible_A'], 'candidates': merged}, [t['task_id'] for t in src]))
    random.Random(2026110209).shuffle(tasks)
    freeze(OUT / 'dependent/requests.json', tasks); freeze(OUT / 'candidates.json', audit)


def export():
    ps = []; costs = []; selection = []; missing = []
    for phase in ['initial', 'dependent']:
        if not (OUT / phase / 'requests.json').exists(): continue
        tasks = read(OUT / phase / 'requests.json'); rows = lines(OUT / phase / 'api_raw.jsonl')
        for r in rows:
            body = r.get('body', {}); u = body.get('usage', {}); ch = body.get('choices', [{}])[0]
            msg = ch.get('message', {})
            costs.append({k: r.get(k) for k in ['task_id', 'attempt_id', 'dialogue_id', 'arm', 'stage', 'http_status', 'valid', 'elapsed_seconds']} |
                         {'returned_model': body.get('model'), 'finish_reason': ch.get('finish_reason'),
                          'prompt_tokens': u.get('prompt_tokens'), 'completion_tokens': u.get('completion_tokens'),
                          'reasoning_tokens': u.get('completion_tokens_details', {}).get('reasoning_tokens'),
                          'reasoning_chars': len(msg.get('reasoning_content') or ''), 'total_tokens': u.get('total_tokens')})
        for t in tasks:
            r = chosen(t, rows)
            if not r: missing.append({k: t[k] for k in ['task_id', 'dialogue_id', 'stage']}); continue
            selection.append({'task_id': t['task_id'], 'attempt_id': r['attempt_id'], 'selection': 'first_structurally_valid'})
            if t['stage'] == 'judge': ps.append({k: t[k] for k in ['task_id', 'dialogue_id', 'arm', 'stage']} | validate(t, r))
    save(OUT / 'predictions.json', ps); save(OUT / 'cost_ledger.json', costs)
    save(OUT / 'selection_bindings.json', selection); save(OUT / 'remaining_missing.json', missing)
    return {'valid_final_dialogues': len(ps), 'actual_calls': len(costs), 'total_tokens': sum(r.get('total_tokens') or 0 for r in costs), 'missing': len(missing)}


def run():
    verify_frozen()
    key = os.environ.get('DASHSCOPE_API_KEY') or (getpass.getpass('API key (hidden): ') if sys.stdin.isatty() else sys.stdin.readline().strip())
    if not key: raise RuntimeError('Missing API key')
    try:
        run_phase('initial', key); dependent(); run_phase('dependent', key)
    finally: print(export(), flush=True)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['prepare', 'run', 'export', 'early', 'review', 'analyze', 'report', 'check'])
    args = parser.parse_args()
    if args.action == 'prepare': print(prepare())
    elif args.action == 'run': run()
    elif args.action == 'export': print(export())
    else:
        from . import evaluation
        print(getattr(evaluation, args.action)())
