"""Run the six algorithms on isolated A turns in a separate new run."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from .common import BASE, read, save, freeze, visible, filehash, require_dataset, validate_input,run_folder
from .client import Client
from .inference import pipeline


def prepare_inputs(dataset='dailydialog', scope='primary'):
    require_dataset(dataset)
    if scope not in ['primary','all300']:raise ValueError('Unknown scope')
    ds=read(BASE/'data/confirmatory_dailydialog300.json')
    wanted={x['dialogue_id'] for x in read(BASE/'references/dailydialog_human_adjudicated_588.json')}
    records=[validate_input({'item_id':'dailydialog/'+d['id']+'/A_to_B',
               'dialogue_id':d['id'],'direction':'A_to_B','dataset':dataset,
               'visible_turns':visible(d,'A_to_B')}) for d in ds if scope=='all300' or d['id'] in wanted]
    freeze(BASE/'inputs'/('dailydialog.json' if scope=='primary' else 'dailydialog300.json'),records)
    return records


def run(dataset='dailydialog', workers=8, limit=None, key=None, run_id='a_to_b', scope='primary'):
    run_folder(run_id)
    if workers<1 or (limit is not None and limit<1):raise ValueError('workers and limit must be positive')
    records=prepare_inputs(dataset,scope)
    if limit is not None:records=records[:limit]
    folder=BASE/'runs'/run_id
    pending=[r for r in records if not (folder/'predictions'/(r['dialogue_id']+'__A_to_B.json')).exists()]
    resolved_key=key or os.environ.get('QWEN_API_KEY') or os.environ.get('DASHSCOPE_API_KEY')
    if pending and not resolved_key:raise ValueError('Missing QWEN_API_KEY or DASHSCOPE_API_KEY')
    freeze(folder/'inputs.json',records)
    freeze(folder/'method_manifest.json',{'code_sha256':{p:filehash(BASE/p) for p in ['inference.py','prompts.py','client.py']},
        'model':'qwen3.8-flash','direction':'A_to_B','scope':scope,
        'thinking_budget':512,'generation_max_tokens':2048,'verifier_max_tokens':3072,
        'reference_access':False,'hidden_turn_access':False})
    out=folder/'predictions';out.mkdir(parents=True,exist_ok=True)
    client=Client(resolved_key,run_id=run_id) if pending else None
    errors=[]
    def work(item):
        save(out/(item['dialogue_id']+'__A_to_B.json'),pipeline(client,item))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(work,r):r for r in pending}
        for f in as_completed(futures):
            try:f.result()
            except Exception as e:errors.append({'item_id':futures[f]['item_id'],'error':str(e)})
    save(folder/'errors.json',errors)
    return {'run_id':run_id,'requested_items':len(records),'cached':len(records)-len(pending),
            'completed_files':sum((out/(r['dialogue_id']+'__A_to_B.json')).exists() for r in records),'errors':len(errors)}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('dataset',nargs='?',choices=['dailydialog'],default='dailydialog')
    p.add_argument('--workers',type=int,default=8);p.add_argument('--limit',type=int)
    p.add_argument('--run-id',default='a_to_b');p.add_argument('--scope',choices=['primary','all300'],default='primary')
    a=p.parse_args();result=run(a.dataset,a.workers,a.limit,run_id=a.run_id,scope=a.scope);print(result)
    if result['errors']:raise SystemExit(1)
