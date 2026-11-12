"""Independent prefix inference using frozen original algorithms; no evaluation API."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import getpass
import importlib
import json
import os
from pathlib import Path
import sys
import types

HERE=Path(__file__).resolve().parent

def package(name, path):
    module=types.ModuleType(name)
    module.__path__=[str(path)]
    module.__package__=name
    sys.modules[name]=module

package('_incremental_frozen', HERE/'source_snapshot')
package('_incremental_transport', HERE/'source_snapshot/transport')
direct=importlib.import_module('_incremental_frozen.inference')
elara=importlib.import_module('_incremental_frozen.new_algorithm')
prompts=importlib.import_module('_incremental_frozen.prompts')
common=importlib.import_module('_incremental_frozen.common')
Transport=importlib.import_module('_incremental_transport.api').Client

def read(p): return json.loads(p.read_text(encoding='utf-8'))
def save(p,o):
    p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_suffix('.tmp')
    temp.write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(p)

class PredictorClient:
    def __init__(self, transport, model): self.transport=transport; self.model=model
    def call(self, name, payload, validate):
        if self.model != 'qwen3.8-flash':
            raise ValueError('Frozen experiment requires qwen3.8-flash; no implicit model fallback')
        payload=dict(payload,model=self.model)
        return self.transport.call(name,payload,validate)

def safe_item(p):
    # Synthetic ID makes each prefix a separate logical ISC113 inference task.
    item={'dialogue_id':p['prefix_id'],'item_id':f"dailydialog/{p['prefix_id']}/A_to_B",
          'direction':'A_to_B','dataset':'dailydialog','visible_turns':p['visible_turns']}
    common.validate_input(item)
    assert len(item['visible_turns'])==p['prefix_k']
    assert [t['turn_id'] for t in item['visible_turns']]==list(range(1,2*p['prefix_k'],2))
    return item

def execute_one(api,p,algorithm):
    target=HERE/'inference'/algorithm/(p['prefix_id']+'.json')
    if target.exists():
        prior=read(target)
        assert prior['input_sha256']==common.digest(safe_item(p))
        return
    item=safe_item(p)
    if algorithm=='direct_thinking':
        data={'visible_turns':item['visible_turns'],'target':'hidden partner'}
        claims,tid=api.call(item['item_id']+'/direct',direct.payload(prompts.DIRECT,data),
                            lambda o:direct.validate_claims(o,item['visible_turns']))
        prediction={'claims':claims,'task_ids':[tid]}
    else:
        prediction,diagnostics=elara.pipeline(api,item)
        save(HERE/'inference/diagnostics'/(p['prefix_id']+'.json'),diagnostics)
    task_ids=set(prediction['task_ids'])
    attempts=[r for r in api.transport.rows if r['task_id'] in task_ids and r['event']=='complete']
    usage={}
    for r in attempts:
        for k,v in r.get('body',{}).get('usage',{}).items():
            if isinstance(v,(int,float)): usage[k]=usage.get(k,0)+v
    prediction.update(dialogue_id=p['dialogue_id'],prefix_id=p['prefix_id'],prefix_k=p['prefix_k'],
                      split=p['split'],algorithm=algorithm,model=api.model,usage=usage,
                      input_sha256=common.digest(item),api_attempt_count=len(attempts),
                      format_failure_count=sum(not r.get('valid',False) for r in attempts),
                      truncated_attempt_count=sum(r.get('body',{}).get('choices',[{}])[0].get('finish_reason')=='length' for r in attempts))
    save(target,prediction)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers',type=int,default=6)
    parser.add_argument('--limit',type=int)
    parser.add_argument('--start-index',type=int,default=0,help='Prefix offset for a disjoint inference shard')
    parser.add_argument('--stop-index',type=int,help='Exclusive prefix offset')
    parser.add_argument('--ledger-name',default='api',help='Separate ledger directory for an inference shard')
    parser.add_argument('--endpoint',default=os.getenv('DASHSCOPE_URL','https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'))
    args=parser.parse_args()
    key=os.getenv('QWEN_API_KEY') or os.getenv('DASHSCOPE_API_KEY')
    if not key and sys.stdin.isatty(): key=getpass.getpass('Qwen API key: ')
    if not key: raise RuntimeError('Set QWEN_API_KEY in process environment')
    inputs=read(HERE/'data/prefix_inputs.json')
    inputs=inputs[args.start_index:args.stop_index]
    if args.limit: inputs=inputs[:args.limit]
    if not inputs:raise ValueError('Empty inference shard')
    if not args.ledger_name.replace('_','').isalnum():raise ValueError('Unsafe ledger name')
    transport=Transport(key,HERE/'inference'/args.ledger_name,endpoint=args.endpoint)
    api=PredictorClient(transport,'qwen3.8-flash')
    # Probe one genuine prediction before launching concurrent paid work.
    execute_one(api,inputs[0],'direct_thinking')
    tasks=[(p,a) for p in inputs for a in ('direct_thinking','elara_v1')]
    errors=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(execute_one,api,p,a):(p,a) for p,a in tasks}
        for index,f in enumerate(as_completed(futures),1):
            p,a=futures[f]
            try:f.result()
            except Exception as exc:
                errors.append({'prefix_id':p['prefix_id'],'algorithm':a,'error':str(exc).replace(key,'[REDACTED]')})
            if index%10==0 or index==len(tasks):
                print(f'Inference {index}/{len(tasks)}; failures {len(errors)}',flush=True)
    save(HERE/'inference'/('errors_'+args.ledger_name+'.json'),errors)
    if errors:raise RuntimeError(f'{len(errors)} inference tasks failed; inspect inference/errors.json')

if __name__=='__main__':main()
