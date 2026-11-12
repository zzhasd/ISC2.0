"""Run ELARA v3 on the frozen 298 A-only conversations and original evaluator.

Put next to ELARA-v3.py, client.py, common.py, evaluation.py and inputs/.
Install: pip install requests tqdm
Full: python run_ELARA_v3.py --workers 12 --eval-workers 12
Smoke: python run_ELARA_v3.py --limit 3 --run-id elara_v3_smoke
Resume: repeat exact command, keep runs/<run-id> directory.
Eval only: python run_ELARA_v3.py --evaluate-only
Inferences and evaluations have separate concurrent progress bars.
The API key is read from QWEN_API_KEY / DASHSCOPE_API_KEY or entered securely.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import getpass
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import threading
import types

HERE=Path(__file__).resolve().parent
if '_elara_project' not in sys.modules:
    pkg=types.ModuleType('_elara_project');pkg.__path__=[str(HERE)];pkg.__package__='_elara_project'
    sys.modules['_elara_project']=pkg
common=importlib.import_module('_elara_project.common')
clientmod=importlib.import_module('_elara_project.client')
ALGO_PATH=HERE/'ELARA-v3.py'
spec=importlib.util.spec_from_file_location('_elara_project.elara_v3',ALGO_PATH)
algorithm=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=algorithm
spec.loader.exec_module(algorithm)
from tqdm import tqdm


def inputs(limit):
    p=HERE/'inputs'/'dailydialog.json'
    records=common.read(p)
    if len(records)!=298 or len({r['item_id'] for r in records})!=298:
        raise RuntimeError('Expected frozen 298 unique A-only inputs')
    for r in records:common.validate_input(r)
    return records if limit is None else records[:limit]


def api_key():
    key=os.getenv('QWEN_API_KEY') or os.getenv('DASHSCOPE_API_KEY')
    if not key and sys.stdin.isatty():
        key=getpass.getpass('请输入 Qwen DashScope API Key（输入不显示）：').strip()
    if not key:raise RuntimeError('No API Key: set QWEN_API_KEY or use an interactive terminal')
    return key


def parse_embedded_json(body, validator):
    """Recover a COMPLETE object only; validate with the original schema.

    Parse embedded JSON wrapped in commentary/fences but never parse truncated
    JSON or invent model decisions. This is for malformed-wrapper retries.
    """
    if not isinstance(body,dict) or not body.get('choices'):return None
    choice=body['choices'][0]
    if choice.get('finish_reason')!='stop':return None
    content=(choice.get('message') or {}).get('content')
    if not isinstance(content,str):return None
    dec=json.JSONDecoder()
    for match in re.finditer(r'\{',content):
        try:
            obj,_=dec.raw_decode(content,match.start())
            return validator(obj)
        except (ValueError, TypeError, KeyError, AttributeError):pass
    return None


class RecoverableClient:
    """Reuse original Client's full request ledger, 3x retry, backoff, locks.

    After 3 malformed replies, safely recover complete valid JSON from its
    audit log. Otherwise allow bounded NEW task identity retries (never after
    an unresolved in-flight request, auth error, or a provider 4xx refusal).
    """
    def __init__(self,key,run_id,max_rounds=2):
        self.raw=clientmod.Client(key,run_id=run_id)
        self.max_rounds=max_rounds
        self.lock=threading.Lock()

    def _recover(self,name,payload,validator):
        tid=common.digest({'logical_name':name,'payload':payload})
        # original client rows are appended concurrently; snapshot under lock
        with self.raw.lock:rows=list(self.raw.rows)
        complete=[r for r in rows if r.get('event')=='complete' and r.get('task_id')==tid
                  and r.get('http_status')==200 and 'body' in r]
        for row in complete:
            result=parse_embedded_json(row['body'],validator)
            if result is not None:return result,tid
        return None

    def call(self,name,payload,validator):
        for k in range(self.max_rounds):
            suffix='' if k==0 else '/format_retry_'+str(k)
            logical=name+suffix
            recovered=self._recover(logical,payload,validator)
            if recovered is not None:return recovered
            try:return self.raw.call(logical,payload,validator)
            except Exception as exc:
                recovered=self._recover(logical,payload,validator)
                if recovered is not None:return recovered
                # Do not defeat original client's interruption/auth guards.
                if 'Attempt limit exceeded' not in str(exc) or k+1>=self.max_rounds:
                    raise
        raise RuntimeError('No valid response')


def _valid_prediction(path,item):
    if not path.exists():return False
    try:
        x=common.read(path)
        return (isinstance(x,list) and len(x)==1 and x[0]['method']==algorithm.METHOD
                and x[0]['item_id']==item['item_id'] and isinstance(x[0]['claims'],list))
    except (OSError,ValueError,KeyError,TypeError):return False


def infer(records,run_id,workers,key,rounds):
    root=common.run_folder(run_id)
    out=root/'predictions';out.mkdir(parents=True,exist_ok=True)
    diag=root/'diagnostics';diag.mkdir(parents=True,exist_ok=True)
    todo=[r for r in records if not _valid_prediction(out/(r['dialogue_id']+'__A_to_B.json'),r)]
    print(f'[推断] 总数 {len(records)}，已完成 {len(records)-len(todo)}，待处理 {len(todo)}，并发 {workers}',flush=True)
    if not todo:return []
    api=RecoverableClient(key,run_id,rounds)
    errors=[]
    def job(item):
        pred,trace=algorithm.pipeline(api,item)
        common.save(diag/(item['dialogue_id']+'__A_to_B.json'),trace)
        common.save(out/(item['dialogue_id']+'__A_to_B.json'),[pred])
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs={pool.submit(job,r):r for r in todo}
        with tqdm(total=len(todo),desc='ELARA v3 推断',unit='段') as bar:
            for fut in as_completed(jobs):
                try:fut.result()
                except Exception as e:
                    errors.append({'item_id':jobs[fut]['item_id'],'error':str(e)})
                bar.update();bar.set_postfix(failed=len(errors))
    common.save(root/'inference_errors.json',errors)
    return errors


def export(records,run_id):
    root=common.run_folder(run_id);allp=[]
    for r in records:
        p=root/'predictions'/(r['dialogue_id']+'__A_to_B.json')
        if not _valid_prediction(p,r):raise RuntimeError('Missing/invalid prediction: '+str(p))
        allp+=common.read(p)
    common.save(root/'exports'/'dailydialog.json',allp)
    return allp


def evaluate(records,run_id,workers,key,rounds):
    # Keep references inaccessible to the algorithm: evaluation import occurs
    # only here, after all predictions are frozen and exported.
    evaluation=importlib.import_module('_elara_project.evaluation')
    root=common.run_folder(run_id)
    predictions=evaluation.predictions('dailydialog',run_id)
    ids={r['dialogue_id'] for r in records}
    if len(predictions)!=len(records) or {x['dialogue_id'] for x in predictions}!=ids:
        raise RuntimeError('Evaluation scope mismatch')
    refs=evaluation.reference_map('dailydialog')
    matchdir=root/'evaluation'/'matches';matchdir.mkdir(parents=True,exist_ok=True)
    todo=[];cached=0
    for p in predictions:
        did=p['dialogue_id'];rr=refs[(did,p['direction'])]
        inv={common.digest(x['claim']):x['claim'] for x in p['claims']}
        pp=[{'prediction_id':k,'claim':v} for k,v in sorted(inv.items())]
        ri=[{'claim_id':r['claim_id'],'claim':r['claim']} for r in rr]
        content=evaluation.matching_content(pp,ri,p['direction'])
        binding=common.digest(content)
        target=matchdir/(did+'__A_to_B.json')
        if target.exists() and common.read(target).get('binding')==binding:
            evaluation.validate_matches(common.read(target),pp,ri)
            cached+=1;continue
        todo.append((did,pp,ri,content,binding,target))
    print(f'[评价] 总数 {len(predictions)}，已完成 {cached}，待处理 {len(todo)}，并发 {workers}',flush=True)
    api=RecoverableClient(key,run_id+'/evaluation',rounds) if any(p and r for _,p,r,*_ in todo) else None
    errors=[]
    def job(t):
        did,pp,rr,content,binding,target=t
        if not pp:matches=[];tid=None
        elif not rr:
            matches=[{'prediction_id':p['prediction_id'],'reference_ids':[],'relation':'none'} for p in pp];tid=None
        else:
            name='dailydialog/'+did+'/A_to_B/'+binding
            matches,tid=api.call(name,evaluation.payload(evaluation.MATCH,content,4096),
                                lambda obj:evaluation.validate_matches(obj,pp,rr))
        common.save(target,{'binding':binding,'matches':matches,'task_id':tid,
                 'evaluation_model':algorithm.MODEL,'independent_human_correctness_review':False})
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(job,t):t[0] for t in todo}
        with tqdm(total=len(todo),desc='ELARA v3 评价',unit='段') as bar:
            for fut in as_completed(futures):
                try:fut.result()
                except Exception as e:
                    errors.append({'dialogue_id':futures[fut],'error':str(e)})
                bar.update();bar.set_postfix(failed=len(errors))
    common.save(root/'evaluation'/'match_errors.json',errors)
    if errors:
        raise RuntimeError(f'评价仍有 {len(errors)} 项失败；已成功部分保留，下次运行自动续跑。详见 match_errors.json')
    summary=evaluation.analyze('dailydialog',bootstrap=False,run_id=run_id)
    if summary['missing_evaluation_items']:
        raise RuntimeError('There are incomplete/stale evaluation bindings')
    metrics=summary['methods'][algorithm.METHOD]
    print('[严格评价]')
    for k in ('precision','recall','grounded_recall','e1_recall','e2_recall',
              'output_assertions','correct_output_assertions','mean_tokens'):
        print('  '+k+':',metrics.get(k))
    # Lenient: all original saved matches; never re-ask the model. Different
    # acceptance relations are the ONLY difference from strict metrics.
    from _elara_project.statistics import matching
    true_ref=ground_ref=pred_total=correct=0
    e1_total=e2_total=e1_hits=e2_hits=0
    for p in predictions:
        rr=refs[(p['dialogue_id'],p['direction'])]
        byref={r['claim_id']:r for r in rr}
        match=common.read(matchdir/(p['dialogue_id']+'__A_to_B.json'))['matches']
        rel={m['prediction_id']:m for m in match}
        true_ref+=sum(r['truth']=='true' for r in rr)
        ground_ref+=sum(r['truth']=='true' and r['evidence_level'] in ('E1','E2') for r in rr)
        e1_total+=sum(r['truth']=='true' and r['evidence_level']=='E1' for r in rr)
        e2_total+=sum(r['truth']=='true' and r['evidence_level']=='E2' for r in rr)
        edges={};ground={}
        for i,c in enumerate(p['claims']):
            pred_total+=1
            m=rel.get(common.digest(c['claim']),{'relation':'none','reference_ids':[]})
            valid=m['reference_ids'] if m['relation'] in ('equivalent','broader') else []
            ids={v for v in valid if v in byref and byref[v]['truth']=='true'}
            correct+=bool(ids);edges[str(i)]=ids
            ground[str(i)]={v for v in ids if byref[v]['evidence_level'] in ('E1','E2')}
        tp=matching(edges);gp=matching(ground)
        for v in gp.values():
            if byref[v]['evidence_level']=='E1':e1_hits+=1
            elif byref[v]['evidence_level']=='E2':e2_hits+=1
    rat=lambda a,b: a/b if b else None
    # One-to-one recall must be recomputed within each dialogue.
    lenient_tp=0;lenient_gp=0
    for p in predictions:
        rr=refs[(p['dialogue_id'],p['direction'])];byref={r['claim_id']:r for r in rr}
        ms=common.read(matchdir/(p['dialogue_id']+'__A_to_B.json'))['matches']
        lookup={m['prediction_id']:m for m in ms};edges={};gedges={}
        for i,c in enumerate(p['claims']):
            m=lookup.get(common.digest(c['claim']),{'relation':'none','reference_ids':[]})
            ids=set(m['reference_ids']) if m['relation'] in ('equivalent','broader') else set()
            ids={k for k in ids if k in byref and byref[k]['truth']=='true'}
            edges[str(i)]=ids;gedges[str(i)]={k for k in ids if byref[k]['evidence_level'] in ('E1','E2')}
        lenient_tp+=len(matching(edges));lenient_gp+=len(matching(gedges))
    lenient={'precision':rat(correct,pred_total),'recall':rat(lenient_tp,true_ref),
             'grounded_recall':rat(lenient_gp,ground_ref),
             'e1_recall':rat(e1_hits,e1_total),'e2_recall':rat(e2_hits,e2_total),
             'output_assertions':pred_total,'correct_output_assertions':correct}
    print('[宽松评价 equivalent + broader]')
    for k,v in lenient.items():print('  '+k+':',v)
    common.save(root/'results'/'elara_v3_comparison.json',{
        'run_id':run_id,'method':algorithm.METHOD,'strict':metrics,'lenient':lenient,
        'notes':'Same original matcher outputs; no ground-truth is used in inference.'})
    print('[完成] ',root/'results',flush=True)


def main():
    p=argparse.ArgumentParser(description='ELARA v3 A-only 298-dialogue benchmark')
    p.add_argument('--run-id',default='elara_v3_append')
    p.add_argument('--workers',type=int,default=12)
    p.add_argument('--eval-workers',type=int,default=12)
    p.add_argument('--request-rounds',type=int,default=2,
        help='Each round permits original client 3 retries; only safe exhausted tasks are reissued')
    p.add_argument('--limit',type=int,default=None)
    p.add_argument('--infer-only',action='store_true')
    p.add_argument('--evaluate-only',action='store_true')
    a=p.parse_args()
    if a.infer_only and a.evaluate_only:p.error('Cannot select both phase-only options')
    if a.workers<1 or a.eval_workers<1 or not 1<=a.request_rounds<=4 or (a.limit is not None and not 1<=a.limit<=298):
        p.error('Invalid workers/rounds/limit')
    records=inputs(a.limit);run=common.run_folder(a.run_id)
    # Freeze input scope & version (changing algorithm during resume is unsafe).
    common.freeze(run/'inputs.json',records)
    common.freeze(run/'method_manifest.json',{
       'method':algorithm.METHOD,'version':algorithm.VERSION,'model':algorithm.MODEL,
       'inputs_sha256':common.digest(records),
       'algorithm_sha256':common.filehash(ALGO_PATH),
       'reference_access_during_inference':False,
       'evaluator':'original ISC113 semantic matcher and four_metrics',
       'scope_count':len(records)})
    if not a.evaluate_only:
        waiting=any(not _valid_prediction(run/'predictions'/(r['dialogue_id']+'__A_to_B.json'),r) for r in records)
        key=api_key() if waiting else None
        errors=infer(records,a.run_id,a.workers,key,a.request_rounds)
        if errors:
            print('未完成的推断任务：',errors[:5],file=sys.stderr)
            raise SystemExit(1)
    export(records,a.run_id)
    if not a.infer_only:
        if a.evaluate_only or key is None:key=api_key()
        evaluate(records,a.run_id,a.eval_workers,key,a.request_rounds)

if __name__=='__main__':main()
