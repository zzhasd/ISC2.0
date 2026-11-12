"""Inference reads inputs.json only; scoring is a separate, gold-aware command."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import os
from pathlib import Path
import re
import time
from .api import Client
from .core import ENDPOINT, HERE, SOURCE, digest, elara_v1, freeze, load, save, validate_item
from . import prompts


def code_binding():
    paths=[SOURCE]+[HERE/n for n in ('core.py','api.py','prompts.py','run.py','prepare.py')]
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def check_inputs(groups):
    seen=set()
    for g in groups:
        if set(g)!={'group_id','setting','dialogues'} or not re.fullmatch('[0-9a-f]{20}',g['group_id']) or g['group_id'] in seen:
            raise ValueError('Unsafe group input')
        seen.add(g['group_id'])
        if g['setting'] not in ('same_a','different_a') or len(g['dialogues'])!=10:
            raise ValueError('Invalid group setting/size')
        if [d['dialogue'] for d in g['dialogues']]!=[f'D{i}' for i in range(1,11)]:
            raise ValueError('Wrong local dialogue IDs')
        for d in g['dialogues']:
            if set(d)!={'dialogue','visible_turns'}:
                raise ValueError('Unsafe dialogue fields')
            validate_item(item_for(g,d))


def item_for(group,dialogue):
    opaque=group['group_id']+'_'+dialogue['dialogue']
    return dict(item_id=f'realpersonachat/{opaque}/A_to_B',dialogue_id=opaque,
                direction='A_to_B',dataset='realpersonachat',visible_turns=dialogue['visible_turns'])


def batch(jobs,fn,workers,label,folder):
    failures=[]
    start=time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(fn,job):job for job in jobs}
        for i,future in enumerate(as_completed(futures),1):
            try:
                future.result()
            except Exception as e:
                failures.append(dict(job=futures[future],error=type(e).__name__+': '+str(e)))
            print(f'{label} {i}/{len(jobs)} failures={len(failures)} elapsed={time.monotonic()-start:.1f}s',flush=True)
    save(folder/f'{label}_status.json',dict(total=len(jobs),completed=len(jobs)-len(failures),failures=failures))
    return failures


def run(folder,workers=8,methods=('direct','elara'),endpoint=ENDPOINT):
    # Deliberately no read of gold.json or sampling.json anywhere in inference.
    groups=load(folder/'inputs.json')
    check_inputs(groups)
    config=dict(inputs_digest=digest(groups),endpoint=endpoint,code_sha256=code_binding(),
                model='qwen3.8-flash',extraction='unmodified isc113/new_algorithm.py pipeline',
                adapter='private package validator only; source and prompts unchanged',
                extraction_thinking_budget=512,extraction_max_tokens=4096,
                linkage_and_direct_thinking_budget=2048,linkage_and_direct_max_tokens=8192,
                temperature=0,method_names=['direct','elara'],gold_access=False)
    freeze(folder/'inference_manifest.json',config)
    client=Client(os.getenv('QWEN_API_KEY') or os.getenv('DASHSCOPE_API_KEY'),folder,endpoint)
    group_by={g['group_id']:g for g in groups}
    failures=[]
    def predict(gid,method):
        g=group_by[gid]
        records=g['dialogues']
        if method=='elara':
            records=[]
            for d in g['dialogues']:
                path=folder/'attributes'/f"{gid}_{d['dialogue']}.json"
                attrs=load(path)['prediction']['claims']
                # Pass the complete v1 inventory, including disputed claims and provenance.
                claims=[dict(c,claim_id=f'c{i}') for i,c in enumerate(attrs,1)]
                records.append(dict(dialogue=d['dialogue'],claims=claims))
        data=dict(setting=g['setting'],observer_configuration='one fixed A' if g['setting']=='same_a' else 'ten distinct A; A and B sets disjoint',dialogues=records)
        payload=prompts.request(prompts.ASSOCIATE if method=='elara' else prompts.DIRECT,data)
        obj,tid=client.call(f'{gid}/{method}',payload,lambda x:prompts.validate_partition(x,records,method))
        freeze(folder/'predictions'/f'{gid}_{method}.json',dict(group_id=gid,setting=g['setting'],method=method,task_id=tid,prediction=obj))
    if 'direct' in methods:
        failures+=batch(list(group_by),lambda gid:predict(gid,'direct'),workers,'direct',folder)
    if 'elara' in methods:
        algorithm=elara_v1()
        jobs=[(g['group_id'],d['dialogue']) for g in groups for d in g['dialogues']]
        def extract(job):
            gid,did=job
            g=group_by[gid]
            d=next(x for x in g['dialogues'] if x['dialogue']==did)
            item=item_for(g,d)
            # Always replay the cached full pipeline on resume; source/config hashes are frozen.
            prediction,audit=algorithm.pipeline(client,item)
            freeze(folder/'attributes'/f'{gid}_{did}.json',dict(prediction=prediction,audit=audit))
        failed_extract=batch(jobs,extract,workers,'extraction',folder)
        failures+=failed_extract
        ready=[gid for gid in group_by if all((folder/'attributes'/f'{gid}_D{i}.json').exists() for i in range(1,11))]
        failures+=batch(ready,lambda gid:predict(gid,'elara'),workers,'association',folder)
    save(folder/'run_status.json',dict(success=not failures,failures=failures))
    if failures:
        raise SystemExit('Some requests failed; see stage status files. Rerun exact command to resume safely.')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--folder',type=Path,default=HERE/'runs/pilot')
    p.add_argument('--workers',type=int,default=8)
    p.add_argument('--methods',nargs='+',choices=['direct','elara'],default=['direct','elara'])
    p.add_argument('--endpoint',default=ENDPOINT)
    a=p.parse_args()
    if a.workers<1:
        p.error('workers must be positive')
    run(a.folder,a.workers,a.methods,a.endpoint)
