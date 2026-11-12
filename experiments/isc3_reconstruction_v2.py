"""Completeness-controlled E2 rerun, using only the originally authorized Qwen task."""
import json
import os
import sys
from isc3_common import *

ADDENDUM='''
Completeness requirement: fill every text slot in output_skeleton. Return exactly the
requested number of hypotheses. In EACH hypothesis, return exactly one nonempty short
reply for EACH supplied after_turn, in that order. Do not omit later turns or return
only a fragment. The skeleton contains positions only, no missing speech or answers.
Use the SAME JSON hypotheses/replies schema and replace every empty text with a reply.'''

def validate_hypotheses(obj,visible,count):
    hs=obj['hypotheses'];expected=[v['turn'] for v in visible]
    if not isinstance(hs,list) or len(hs)!=count:raise ValueError('Wrong v2 hypothesis count')
    for h in hs:
        if not isinstance(h,dict) or not isinstance(h.get('replies'),list):raise ValueError('Invalid v2 hypothesis')
        replies=h['replies']
        if len(replies)!=len(expected) or [r.get('after_turn') for r in replies]!=expected:raise ValueError('Incomplete or duplicate v2 reply positions')
        if any(not isinstance(r.get('text'),str) or not r['text'].strip() for r in replies):raise ValueError('Empty v2 reply')
    return hs

def prepare_generate():
    plan=[];bindings=[]
    for c in read(DATA/'cases.json'):
        for count,method,system in [(1,'recon_one_v2_generate',RECON),(3,'recon_multi_v2_generate',MULTI)]:
            content={'visible_A':c['visible_A'],'output_skeleton':{'hypotheses':[
                {'replies':[{'after_turn':v['turn'],'text':''} for v in c['visible_A']]} for _ in range(count)]}}
            t=make_task(system+ADDENDUM,content,method,c['case_id'],'full',3200,required_hypotheses=count)
            plan.append(t);bindings.append({'task_id':t['task_id'],'case_id':c['case_id'],'method':method,'condition':'full',
                'visible_turns':[v['turn'] for v in c['visible_A']],'required_hypotheses':count})
    freeze(OUT/'reconstruction_v2_generate/requests.json',list({t['task_id']:t for t in plan}.values()))
    freeze(DATA/'bindings_reconstruction_v2_generate.json',bindings)
    freeze(DATA/'manifest_reconstruction_v2.json',{'protocol_sha256':hashlib.sha256((ROOT/'ISC3_RECONSTRUCTION_V2_PROTOCOL.md').read_bytes()).hexdigest(),
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'cases_sha256':digest(read(DATA/'cases.json')),
        'generation_unique_requests':len({t['task_id'] for t in plan}),'maximum_extraction_requests':368,
        'source_data':'Same public scripted DailyDialog excerpts and fictional controlled worlds as the original user-authorized E2.'})
    print({'v2_generation_requests':len({t['task_id'] for t in plan})})

def prepare_extract():
    raw=raw_index(OUT/'reconstruction_v2_generate');cases={c['case_id']:c for c in read(DATA/'cases.json')}
    plan=[];bindings=[];errors=[]
    for b in read(DATA/'bindings_reconstruction_v2_generate.json'):
        c=cases[b['case_id']]
        try:
            hs=validate_hypotheses(decode(raw[b['task_id']]),c['visible_A'],b['required_hypotheses'])
            method='recon_one_v2' if b['required_hypotheses']==1 else 'recon_multi_v2'
            content={'visible_A':c['visible_A'],'catalogue':c['catalogue'],'hypothetical_B':hs}
            t=make_task(EXTRACT,content,method,c['case_id'],'full',3200 if len(c['catalogue'])>4 else 1600,source_task_id=b['task_id'])
            plan.append(t);bindings.append({'task_id':t['task_id'],'case_id':c['case_id'],'method':method,
                'condition':'full','visible_turns':[v['turn'] for v in c['visible_A']],'source_task_id':b['task_id']})
        except (ValueError,KeyError,TypeError,AttributeError) as exc:errors.append({**b,'error':str(exc)})
    freeze(OUT/'reconstruction_v2_extract/requests.json',list({t['task_id']:t for t in plan}.values()))
    freeze(DATA/'bindings_reconstruction_v2_extract.json',bindings);save(OUT/'reconstruction_v2_extract/source_errors.json',errors)
    print({'v2_extraction_requests':len({t['task_id'] for t in plan}),'source_errors':len(errors)})

def run():
    key=os.environ.get('DASHSCOPE_API_KEY') or sys.stdin.readline().strip()
    if not key:raise SystemExit('Missing API key')
    from isc3_run import run_plan
    if not run_plan('reconstruction_v2_generate',key):raise SystemExit(2)
    prepare_extract()
    if not run_plan('reconstruction_v2_extract',key):raise SystemExit(2)
    import isc3_finish
    isc3_finish.main()

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','run']);a=p.parse_args()
    {'prepare':prepare_generate,'run':run}[a.stage]()
