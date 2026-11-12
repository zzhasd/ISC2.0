"""Resumable AGD evaluation. Credentials are process-environment only."""
import argparse, concurrent.futures as cf, hashlib, json, os, threading, time, re, shutil
from pathlib import Path
from datetime import datetime, timezone
import requests
import agd_eval as agd

ROOT = Path(__file__).resolve().parent
WORK = ROOT / 'final_eval'
LOCK = threading.Lock()
STOP = threading.Event()
MODEL = agd.MODEL_DEFAULT
URL = agd.BASE_URL + '/chat/completions'

def log(row):
    with LOCK:
        with (ROOT/'attempts.jsonl').open('a',encoding='utf8') as f:
            f.write(json.dumps(row,ensure_ascii=False)+'\n')

def call(stage,did,index,system,payload,validator,tokens):
    budget=8192 if stage=='pool' else 4096
    binding={'model':MODEL,'system':system,'payload':payload,'max_tokens':tokens,'temperature':0,'thinking_budget':budget}
    digest=agd.stable_hash(binding)
    cache=WORK/'calls'/stage/did/(str(index)+'_'+digest[:16]+'.json')
    if cache.exists():
        result=agd.read(cache)
        try:
            validator(result['output']);return result['output'],result['usage']
        except ValueError:
            pass  # Preserve a cached response rejected by stronger structural validation.
    for attempt in range(1,5):
        if STOP.is_set():raise RuntimeError('provider circuit open')
        started=time.monotonic()
        row={'stage':stage,'dialogue_id':did,'batch':index,'input_sha256':digest,'attempt':attempt,'utc':datetime.now(timezone.utc).isoformat()}
        try:
            response=requests.post(URL,headers={'Authorization':'Bearer '+os.environ['DASHSCOPE_API_KEY']},json={
                'model':MODEL,'messages':[{'role':'system','content':system},{'role':'user','content':json.dumps(payload,ensure_ascii=False)}],
                'temperature':0,'response_format':{'type':'json_object'},'max_tokens':tokens,
                'stream':True,'stream_options':{'include_usage':True},'thinking_budget':budget},timeout=(20,90),allow_redirects=False,stream=True)
            row['http_status']=response.status_code
            if response.status_code in (401,403,404):STOP.set()
            response.raise_for_status()
            content=[];reasoning=[];usage={};finish=None;response_id=None
            for line in response.iter_lines():
                if not line or not line.startswith(b'data:'):continue
                raw=line[5:].strip()
                if raw==b'[DONE]':break
                chunk=json.loads(raw);response_id=chunk.get('id',response_id)
                if chunk.get('usage'):usage=chunk['usage']
                for choice in chunk.get('choices',[]):
                    delta=choice.get('delta',{})
                    if delta.get('content'):content.append(delta['content'])
                    if delta.get('reasoning_content'):reasoning.append(delta['reasoning_content'])
                    if choice.get('finish_reason'):finish=choice['finish_reason']
            body={'id':response_id,'model':MODEL,'usage':usage,'choices':[{'finish_reason':finish,'message':{'content':''.join(content),'reasoning_content':''.join(reasoning)}}]}
            row['response']=body
            row['usage']=body.get('usage',{})
            if body['choices'][0]['finish_reason']!='stop':raise ValueError('incomplete model output')
            output=json.loads(body['choices'][0]['message']['content']);validator(output)
            row['valid']=True
            agd.dump(cache,{'binding':binding,'output':output,'usage':row['usage']})
            return output,row['usage']
        except Exception as e:
            row['valid']=False;row['error']=(type(e).__name__+': '+str(e)).replace(os.environ['DASHSCOPE_API_KEY'],'[REDACTED]')[:1000]
            if STOP.is_set() or attempt==4:raise RuntimeError(row['error']) from None
            time.sleep(min(12,2**attempt))
        finally:
            row['elapsed_seconds']=round(time.monotonic()-started,3);log(row)

def blinded(candidates):
    mapping={f'c{i:04d}':c['id'] for i,c in enumerate(candidates)}
    return [{'id':k,'claim':c['claim']} for k,c in zip(mapping,candidates)],mapping

def normalize_id(value,expected,prefix):
    if value in expected:return value
    if isinstance(value,str) and re.fullmatch(prefix+r'\d+',value):
        matches=[x for x in expected if re.fullmatch(prefix+r'\d+',x) and int(x[1:])==int(value[1:])]
        if len(matches)==1:return matches[0]
    return value

def validate_support(obj,candidates,turns):
    expected={x['id'] for x in candidates}
    if isinstance(obj,dict) and isinstance(obj.get('items'),list):
        for item in obj['items']:item['id']=normalize_id(item.get('id'),expected,'c')
    return agd.validate_support(obj,candidates,turns)

def dialogue(did,d):
    turns=d['visible_turns'];d=dict(d,_work=str(WORK))
    for stage in ['sweep','pred','gold','sweep_support','pool']:
        target=agd.path_for(WORK,stage,did)
        if target.exists():
            if stage!='pool':continue
            try:
                validate_pool(agd.read(target),agd.pool_atoms(WORK,did));continue
            except ValueError:
                rejected=WORK/'quality_rejected'/'pool'/did
                rejected.mkdir(parents=True,exist_ok=True)
                shutil.copy2(target,rejected/('raw_'+hashlib.sha256(target.read_bytes()).hexdigest()[:16]+'.json'))
        usage=[];bindings=[]
        if stage=='sweep':
            payload={'visible_turns':turns}
            obj,u=call(stage,did,0,agd.SWEEP_SYSTEM,payload,lambda x:agd.validate_sweep(x,turns),16000)
            obj['claims']=[dict(c,id='s_'+did+'_'+str(i)) for i,c in enumerate(obj['claims'])];usage.append(u)
        elif stage in ('pred','gold','sweep_support'):
            batches=agd.make_support_batches(did,d,'sweep' if stage=='sweep_support' else stage,12)
            obj={'items':[]}
            for i,batch in enumerate(batches):
                blind,mapping=blinded(batch)
                payload={'visible_turns':turns,'candidates':blind}
                res,u=call(stage,did,i,agd.SUPPORT_SYSTEM,payload,lambda x:validate_support(x,blind,turns),12000)
                obj['items'].extend(dict(x,id=mapping[x['id']]) for x in res['items']);usage.append(u)
        else:
            atoms=agd.pool_atoms(WORK,did)
            # Hash order and neutral IDs conceal prediction/reference/discovery provenance.
            atoms=sorted(atoms,key=lambda a:agd.stable_hash(a['atom_id']))
            mapping={f'a{i:04d}':a['atom_id'] for i,a in enumerate(atoms)}
            blind=[dict(a,atom_id=k) for k,a in zip(mapping,atoms)]
            if not atoms:obj={'facts':[]}
            else:
                payload={'visible_turns':turns,'atoms':blind}
                obj,u=call(stage,did,0,agd.POOL_SYSTEM,payload,lambda x:validate_pool(x,blind),30000)
                obj=json.loads(json.dumps(obj))
                for fact in obj['facts']:
                    for member in fact['members']:member['atom_id']=mapping[member['atom_id']]
                usage.append(u)
        obj['_meta']={'stage':stage,'model':MODEL,'usage':usage,'pipeline_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        agd.dump(target,obj)
    return did

def validate_pool(obj,atoms):
    expected={x['atom_id'] for x in atoms}
    if isinstance(obj,dict) and isinstance(obj.get('facts'),list):
        for fact in obj['facts']:
            for member in fact.get('members',[]):member['atom_id']=normalize_id(member.get('atom_id'),expected,'a')
    agd.validate_pool(obj,atoms)
    for f in obj['facts']:
        if not f['members']:raise ValueError('fact without members')
        if not any(s['required'] for s in f['slots']):raise ValueError('no required slots')
        if any(s['core'] and not s['required'] for s in f['slots']):raise ValueError('core must be required')
        covered={sid for member in f['members'] for sid in member['slot_ids']}
        if any(s['id'] not in covered for s in f['slots']):raise ValueError('slot lacks an input-atom coverage link')
    return obj

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int);parser.add_argument('--workers',type=int,default=8);parser.add_argument('--dialogue-ids',nargs='+');args=parser.parse_args()
    if not os.environ.get('DASHSCOPE_API_KEY'):raise ValueError('DASHSCOPE_API_KEY required')
    data=agd.read(WORK/'data.json')['dialogues'];ids=sorted(data)
    if args.dialogue_ids:ids=[did for did in ids if did in set(args.dialogue_ids)]
    if args.limit:ids=ids[:args.limit]
    failures=[];done=0
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(dialogue,did,data[did]):did for did in ids}
        for future in cf.as_completed(futures):
            did=futures[future]
            try:future.result();done+=1;print('COMPLETE',done,'/',len(ids),did,flush=True)
            except Exception as e:
                failures.append({'dialogue_id':did,'error':str(e)});print('FAILED',did,str(e),flush=True)
                if STOP.is_set():
                    for f in futures:f.cancel()
    agd.dump(ROOT/('run_status_subset.json' if args.dialogue_ids else 'run_status.json'),{'complete':done,'requested':len(ids),'failures':failures,'model':MODEL})
    if failures:raise SystemExit(1)

if __name__=='__main__':main()
