"""Run ELARA on 298 frozen A-only dialogues and evaluate with ISC113's evaluator.

Usage (from any directory):
    python /path/to/isc113/run_new_algorithm.py
    python /path/to/isc113/run_new_algorithm.py --workers 6 --run-id elara_2026
    python /path/to/isc113/run_new_algorithm.py --limit 3   # smoke test
    python /path/to/isc113/run_new_algorithm.py --evaluate-only --run-id elara_2026

Install: pip install requests tqdm
Key: QWEN_API_KEY environment variable or secure interactive prompt (no key saved).
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import getpass
import importlib
import json
import os
from pathlib import Path
import sys
import traceback
import types

HERE=Path(__file__).resolve().parent
# A loadable package alias makes direct-script invocation work even if the folder is
# named 'isc113(7)' or the user runs from an unrelated current working directory.
if '_elara_project' not in sys.modules:
    pkg=types.ModuleType('_elara_project');pkg.__path__=[str(HERE)];pkg.__package__='_elara_project'
    sys.modules['_elara_project']=pkg
common=importlib.import_module('_elara_project.common')
clientmod=importlib.import_module('_elara_project.client')
algorithm=importlib.import_module('_elara_project.new_algorithm')

try:
    from tqdm import tqdm
except ImportError:
    class tqdm:
        def __init__(self,iterable=None,total=None,desc='',unit='it',**kwargs):
            self.iterable=iterable;self.total=total;self.n=0;self.desc=desc
            print(f'{desc}: 0/{total}',flush=True)
        def __enter__(self):return self
        def __exit__(self,*a):print(f'{self.desc}: {self.n}/{self.total}',flush=True)
        def __iter__(self):
            for v in self.iterable:
                yield v;self.update()
        def update(self,n=1):
            self.n+=n
            if self.n==self.total or self.n%10==0:print(f'\r{self.desc}: {self.n}/{self.total}',end='\n' if self.n==self.total else '',flush=True)
        def set_postfix(self,**kw):pass


def read_inputs(limit=None):
    p=HERE/'inputs'/'dailydialog.json'
    if not p.exists():raise FileNotFoundError(f'Frozen 298-sample input missing: {p}')
    records=common.read(p)
    if len(records)!=298:raise RuntimeError(f'Expected exactly 298 frozen primary inputs, got {len(records)}')
    if len({r['item_id'] for r in records})!=298:raise RuntimeError('Duplicate input IDs')
    for r in records:common.validate_input(r)
    return records[:limit] if limit is not None else records


def key_from_user():
    key=os.environ.get('QWEN_API_KEY') or os.environ.get('DASHSCOPE_API_KEY')
    if not key and sys.stdin.isatty():key=getpass.getpass('请输入 Qwen DashScope API Key（输入不显示）：').strip()
    if not key:raise RuntimeError('API Key missing. Set QWEN_API_KEY, or launch an interactive terminal.')
    return key


def execute(records,run_id,workers,key):
    out=common.run_folder(run_id)/'predictions';out.mkdir(parents=True,exist_ok=True)
    logdir=common.run_folder(run_id)/'diagnostics';logdir.mkdir(parents=True,exist_ok=True)
    saved=[r for r in records if (out/(r['dialogue_id']+'__A_to_B.json')).exists()]
    pending=[r for r in records if r not in saved]
    print(f'[推断] 目标 {len(records)} 段，已有 {len(saved)} 段，待执行 {len(pending)} 段。',flush=True)
    if not pending:return []
    api=clientmod.Client(key,run_id=run_id)
    errors=[]
    def work(item):
        result,diagnostics=algorithm.pipeline(api,item)
        common.save(logdir/(item['dialogue_id']+'__A_to_B.json'),diagnostics)
        common.save(out/(item['dialogue_id']+'__A_to_B.json'),[result])
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fs={pool.submit(work,r):r for r in pending}
        with tqdm(total=len(pending),desc='新算法推断',unit='段') as bar:
            for future in as_completed(fs):
                try:future.result()
                except Exception as exc:errors.append({'item_id':fs[future]['item_id'],'error':str(exc)})
                bar.update(1)
                if hasattr(bar,'set_postfix'):bar.set_postfix(failed=len(errors))
    common.save(common.run_folder(run_id)/'inference_errors.json',errors)
    return errors


def build_export(records,run_id,strict=True):
    folder=common.run_folder(run_id)
    exports=[];missing=[]
    for r in records:
        path=folder/'predictions'/(r['dialogue_id']+'__A_to_B.json')
        if not path.exists():missing.append(r['item_id']);continue
        rows=common.read(path)
        if not isinstance(rows,list) or len(rows)!=1 or rows[0]['method']!=algorithm.METHOD:
            raise ValueError('Invalid prediction file: '+str(path))
        exports+=rows
    if missing and strict:raise RuntimeError(f'Missing {len(missing)} predictions; rerun to resume')
    common.save(folder/'exports'/'dailydialog.json',exports)
    return exports


def evaluate(records,run_id,workers,key):
    # Import the evaluator only AFTER all inference predictions were finalized;
    # no reference data are ever sent to the algorithm's prompts.
    evaluation=importlib.import_module('_elara_project.evaluation')
    refs=evaluation.reference_map('dailydialog')
    pred=evaluation.predictions('dailydialog',run_id)
    target_ids={r['dialogue_id'] for r in records}
    if set(p['dialogue_id'] for p in pred)!=target_ids or len(pred)!=len(records):
        raise RuntimeError('Export does not exactly match selected inference inputs')
    match_dir=common.run_folder(run_id)/'evaluation'/'matches';match_dir.mkdir(parents=True,exist_ok=True)
    tasks=[];cache_count=0
    for p in pred:
        did=p['dialogue_id'];keyid=(did,p['direction']);rr=refs[keyid]
        inv={common.digest(c['claim']):c['claim'] for c in p['claims']}
        pp=[{'prediction_id':h,'claim':s} for h,s in sorted(inv.items())]
        ref_claims=[{'claim_id':c['claim_id'],'claim':c['claim']} for c in rr]
        content=evaluation.matching_content(pp,ref_claims,p['direction'])
        binding=common.digest(content)
        output=match_dir/(did+'__A_to_B.json')
        if output.exists() and common.read(output).get('binding')==binding:
            cache_count+=1;continue
        tasks.append((did,pp,ref_claims,content,binding,output))
    print(f'[评价] 共 {len(pred)} 段，已有匹配 {cache_count}，待匹配 {len(tasks)} 段。',flush=True)
    # No Qwen call needed for empty predictions or empty references.
    api=clientmod.Client(key,run_id=run_id+'/evaluation') if any(pp and rr for _,pp,rr,*_ in tasks) else None
    errors=[]
    def work(task):
        did,pp,rr,content,binding,target=task
        if not pp:matches=[];tid=None
        elif not rr:matches=[{'prediction_id':p['prediction_id'],'reference_ids':[],'relation':'none'} for p in pp];tid=None
        else:
            name='dailydialog/'+did+'/A_to_B/'+binding
            matches,tid=api.call(name,evaluation.payload(evaluation.MATCH,content,4096),
                                   lambda o:evaluation.validate_matches(o,pp,rr))
        common.save(target,{'binding':binding,'matches':matches,'task_id':tid,
                    'evaluation_model':algorithm.MODEL,'independent_human_correctness_review':False})
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fs={pool.submit(work,t):t[0] for t in tasks}
        with tqdm(total=len(tasks),desc='评价器匹配',unit='段') as bar:
            for future in as_completed(fs):
                try:future.result()
                except Exception as exc:errors.append({'dialogue_id':fs[future],'error':str(exc)})
                bar.update(1)
                if hasattr(bar,'set_postfix'):bar.set_postfix(failed=len(errors))
    common.save(common.run_folder(run_id)/'evaluation'/'match_errors.json',errors)
    if errors:raise RuntimeError(f'Evaluation has {len(errors)} failed items; rerun to resume')
    print('[评价] 开始计算精确率、召回率、Grounded Recall、token 成本及 E1/E2 命中。',flush=True)
    summary=evaluation.analyze('dailydialog',bootstrap=False,run_id=run_id)
    report=summary['methods'][algorithm.METHOD]
    for k in ['precision','recall','grounded_recall','e1_recall','e2_recall','mean_tokens','output_assertions','correct_output_assertions']:
        print(f'  {k}: {report.get(k)}')
    path=common.run_folder(run_id)/'results'/'dailydialog_summary.json'
    common.save(path,{'run_id':run_id,'method':algorithm.METHOD,'metrics':report,
       'scope_count':len(records),'note':'Model-based reference matching, not independent human correctness verification'})
    print('[完成] 结果目录：',common.run_folder(run_id)/'results',flush=True)


def main():
    p=argparse.ArgumentParser(description='ELARA: independent A-only inference and original ISC113 evaluation')
    p.add_argument('--run-id',default='elara_append_v1')
    p.add_argument('--workers',type=int,default=6)
    p.add_argument('--eval-workers',type=int,default=6)
    p.add_argument('--limit',type=int,default=None,help='Smoke test first N; for full 298 omit')
    p.add_argument('--evaluate-only',action='store_true')
    p.add_argument('--infer-only',action='store_true')
    a=p.parse_args()
    if a.workers<1 or a.eval_workers<1 or (a.limit is not None and not 1<=a.limit<=298):p.error('Invalid worker/limit value')
    if a.evaluate_only and a.infer_only:p.error('Choose at most one of --evaluate-only, --infer-only')
    records=read_inputs(a.limit)
    common.run_folder(a.run_id)
    run=common.run_folder(a.run_id)
    input_file=run/'inputs.json'
    # Preserve exact scope and dataset binding. Do not silently overwrite after a partial run.
    common.freeze(input_file,records)
    common.freeze(run/'method_manifest.json',{
        'method':algorithm.METHOD,'model':algorithm.MODEL,'direction':'A_to_B',
        'inputs_sha256':common.digest(records),'algorithm_sha256':common.filehash(HERE/'new_algorithm.py'),
        'reference_access_during_inference':False,'evaluation':'original ISC113 matching + four_metrics',
        'scope_count':len(records)})
    if a.evaluate_only:
        build_export(records,a.run_id)
        key=key_from_user();evaluate(records,a.run_id,a.eval_workers,key)
    else:
        pending=any(not (run/'predictions'/(r['dialogue_id']+'__A_to_B.json')).exists() for r in records)
        key=key_from_user() if pending or not a.infer_only else None
        errors=execute(records,a.run_id,a.workers,key)
        if errors:
            print(f'发生 {len(errors)} 个推断错误，保留中间结果和请求审计以供恢复。',file=sys.stderr)
            raise SystemExit(1)
        build_export(records,a.run_id)
        if not a.infer_only:
            if not key:key=key_from_user()
            evaluate(records,a.run_id,a.eval_workers,key)

if __name__=='__main__':main()
