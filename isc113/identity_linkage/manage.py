"""Explicit audited transport recovery and combining disjoint method stages."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from .core import freeze, load, save


def rows(path):
    return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []


def import_probe(source,destination):
    if (destination/'attempts.jsonl').exists():
        raise ValueError('Import requires a fresh destination')
    for name in ('inputs.json','gold.json','sampling.json','census.json'):
        freeze(destination/name,load(source/name))
    selected=[r for r in rows(source/'attempts.jsonl') if '/elara/' in r.get('logical_name','')]
    completed={r['attempt_id'] for r in selected if r['event']=='complete'}
    interrupted=[]
    for r in list(selected):
        if r['event']=='start' and r['attempt_id'] not in completed:
            selected.append(dict(event='complete',task_id=r['task_id'],attempt_id=r['attempt_id'],logical_name=r['logical_name'],
                                 valid=False,billing_unknown=True,operator_interrupted=True,error='Superseded connection-probe process terminated; no response recorded',utc=datetime.now(timezone.utc).isoformat()))
            interrupted.append(r['attempt_id'])
    acknowledged=[]
    for r in list(selected):
        if r['event']=='complete' and r.get('billing_unknown'):
            selected.append(dict(event='network_retry_acknowledged',task_id=r['task_id'],attempt_id=r['attempt_id'],logical_name=r['logical_name'],
                                 reason='Explicit recovery of superseded transport probe; unsuccessful responses are not results; billing remains uncertain'))
            acknowledged.append(r['attempt_id'])
    with (destination/'attempts.jsonl').open('w',encoding='utf-8') as f:
        for r in selected:
            f.write(json.dumps(r,ensure_ascii=False)+'\n')
    for p in (source/'attributes').glob('*.json'):
        freeze(destination/'attributes'/p.name,load(p))
    freeze(destination/'transport_recovery.json',dict(source=str(source),imported_rows=len(selected),interrupted_attempts=interrupted,
                                                   acknowledged_network_failures=acknowledged,only_extraction_requests_imported=True))
    print('Imported extraction cache and explicit transport audit:',len(selected),'rows')


def combine(source,destination):
    # Call only after BOTH processes have exited. Require identical experiment/code bindings.
    for name in ('inputs.json','gold.json','sampling.json','census.json','inference_manifest.json'):
        if load(source/name)!=load(destination/name):
            raise ValueError('Incompatible stage: '+name)
    src=rows(source/'attempts.jsonl')
    dst=rows(destination/'attempts.jsonl')
    dst_tasks={r['task_id'] for r in dst}
    src_tasks={r['task_id'] for r in src}
    if src_tasks & dst_tasks:
        raise ValueError('Method stages must have disjoint API task IDs')
    for category in ('attributes','predictions'):
        for p in (source/category).glob('*.json'):
            freeze(destination/category/p.name,load(p))
    with (destination/'attempts.jsonl').open('a',encoding='utf-8') as f:
        for r in src:
            f.write(json.dumps(r,ensure_ascii=False)+'\n')
    freeze(destination/'combined_stages.json',dict(source=str(source),imported_rows=len(src),
                                                note='Identical code, input, endpoint and parameters; disjoint extraction/linkage vs direct task IDs.'))
    if (source/'transport_recovery.json').exists():
        freeze(destination/'transport_recovery.json',load(source/'transport_recovery.json'))
    print('Combined method stages:',len(src),'ledger rows')


def acknowledge_network(source,destination):
    if source.resolve()!=destination.resolve():
        raise ValueError('Acknowledgment source/destination must be the same run')
    records=rows(source/'attempts.jsonl')
    started={r['attempt_id'] for r in records if r['event']=='start'}
    completed={r['attempt_id'] for r in records if r['event']=='complete'}
    if started-completed:
        raise ValueError('A process may still be running; unresolved starts require separate audit')
    acknowledged={r['attempt_id'] for r in records if r['event']=='network_retry_acknowledged'}
    additions=[]
    for r in records:
        if r['event']=='complete' and r.get('billing_unknown') and r['attempt_id'] not in acknowledged:
            additions.append(dict(event='network_retry_acknowledged',task_id=r['task_id'],attempt_id=r['attempt_id'],logical_name=r['logical_name'],
                                  reason='Explicit operator recovery of recorded network failure for the authorized experiment; missing usage remains unknown',utc=datetime.now(timezone.utc).isoformat()))
    with (source/'attempts.jsonl').open('a',encoding='utf-8') as f:
        for r in additions:
            f.write(json.dumps(r,ensure_ascii=False)+'\n')
    print('Acknowledged network retry records:',len(additions))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['import-probe','combine','acknowledge-network'])
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--destination',type=Path,required=True)
    a=p.parse_args()
    {'import-probe':import_probe,'combine':combine,'acknowledge-network':acknowledge_network}[a.action](a.source,a.destination)
