"""Frozen two-stage development pilot; reuse audited ISC5 transport only."""
import argparse
import getpass
import hashlib
import json
import os
import sys
import isc5_run as transport
from isc4_open import ROOT,read,save,freeze,sha,visible
from isc6_module import PROPOSE,SELECT,clause_units,validate_candidates,collect_selection

OUT=ROOT/'results/isc6'
DATA=ROOT/'data/isc6'


def configure():
    transport.OUT=OUT


def prepare():
    ds=read(ROOT/'data/isc4/dialogues.json')
    freeze(DATA/'dialogues.json',ds)
    tasks=[]
    for d in ds:
        turns=visible(d)
        tasks.append(transport.make_task(d['id'],'development','atomic_propose',PROPOSE,
                     {'visible_A':turns,'clause_units':clause_units(turns)}))
    freeze(OUT/'initial/requests.json',tasks)
    freeze(DATA/'manifest.json',{'dialogues':len(ds),'model':'qwen3.8-flash',
        'planned_calls':2*len(ds),'initial_requests_sha256':sha(tasks),
        'dialogues_sha256':sha(ds),'protocol_sha256':hashlib.sha256((ROOT/'ISC6_PROTOCOL.md').read_bytes()).hexdigest(),
        'module_sha256':hashlib.sha256((ROOT/'experiments/isc6_module.py').read_bytes()).hexdigest(),
        'reference_sha256':hashlib.sha256((ROOT/'data/isc5/full_AB_reference.json').read_bytes()).hexdigest(),
        'historical_comparators':'ISC5; same model settings, not contemporaneous or token-matched',
        'status':'development, not independent held-out evaluation'})
    print({'prepared':len(tasks),'planned_total':2*len(ds)})


def dependent():
    plan={t['task_id']:t for t in read(OUT/'initial/requests.json')};tasks=[];errors=[]
    for r in transport.records('initial'):
        t=plan[r['task_id']];content=json.loads(t['payload']['messages'][1]['content'])
        try:
            obj=validate_candidates(transport.decode(r),content['visible_A'])
            tasks.append(transport.make_task(t['dialogue_id'],'development','atomic_contrast',SELECT,
                {'visible_A':content['visible_A'],'candidates':obj['candidates']},t['task_id']))
        except (ValueError,KeyError,TypeError,IndexError) as exc:
            errors.append({'dialogue_id':t['dialogue_id'],'task_id':t['task_id'],'error':str(exc)})
    freeze(OUT/'dependent/requests.json',tasks);save(OUT/'dependent/source_errors.json',errors)
    print({'dependent':len(tasks),'invalid_sources':len(errors)})


def export():
    predictions=[];candidates=[];errors=[];audit=[]
    for phase in ['initial','dependent']:
        if not (OUT/phase/'requests.json').exists():continue
        plan={t['task_id']:t for t in read(OUT/phase/'requests.json')}
        for r in transport.records(phase):
            t=plan[r['task_id']];content=json.loads(t['payload']['messages'][1]['content'])
            audit.append({'task_id':t['task_id'],'dialogue_id':t['dialogue_id'],'stage':t['stage'],
                'tokens':r.get('body',{}).get('usage',{}).get('total_tokens'),
                'returned_model':r.get('body',{}).get('model'),'http_status':r.get('http_status'),
                'elapsed_seconds':r['elapsed_seconds']})
            try:
                obj=transport.decode(r)
                if phase=='initial':
                    obj=validate_candidates(obj,content['visible_A'])
                    candidates.append({'dialogue_id':t['dialogue_id'],**obj})
                else:
                    obj=collect_selection(obj,content['candidates'],content['visible_A'])
                    predictions.append({k:t[k] for k in ['task_id','dialogue_id','stage','split']}|obj)
            except (ValueError,KeyError,TypeError,IndexError) as exc:
                errors.append({'dialogue_id':t['dialogue_id'],'stage':t['stage'],'error':str(exc)})
    save(OUT/'predictions.json',predictions);save(OUT/'candidates.json',candidates)
    save(OUT/'validation_errors.json',errors);save(OUT/'execution_audit.json',audit)
    print({'valid_predictions':len(predictions),'errors':len(errors),'http_records':len(audit)})


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');configure()
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','dependent','export']);args=p.parse_args()
    if args.action=='prepare':prepare()
    elif args.action=='export':export()
    elif args.action=='dependent':dependent()
    else:
        key=os.getenv('DASHSCOPE_API_KEY') or (getpass.getpass('API key (hidden): ') if sys.stdin.isatty() else sys.stdin.readline().strip())
        if not key:raise SystemExit('No API key')
        # Plan bounds are stricter than the reused transport's global safeguard.
        if len(read(OUT/'initial/requests.json'))!=32:raise RuntimeError('Unexpected plan')
        if not transport.run_stage('initial',key):export();raise SystemExit(2)
        dependent()
        if not transport.run_stage('dependent',key):export();raise SystemExit(2)
        export()
