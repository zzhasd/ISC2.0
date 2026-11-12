"""Prospective secondary annotation of explicit claims in generated B hypotheses."""
import collections
import json
from isc3_common import *
from isc3_analyze import write_csv, metric

SYSTEM='''Annotate explicit personal-property assertions in HYPOTHETICAL B replies.
These are invented replies, not verified observations. Do not infer missing assertions
from the catalogue or from a bare yes/no. First-person I/my in a B reply refers to B;
you/your refers to A. Assertions about A or a third party do not establish B facts.
For each hypothesis report only catalogue properties explicitly asserted true or false
about B. Do not output unknown properties. Preserve exact contiguous supporting quotes
from one reply. Hypothetical, possible and merely questioned claims do not count.
Return JSON {"assertions":[{"hypothesis":0,"id":"catalogue id",
"label":"true|false","quote":"exact quote","holder":"B"}]}.
Index hypotheses from 0. At most one assertion per hypothesis/catalogue id.
Do not decide whether these invented assertions are actually true or supported by A.'''

def prepare():
    cases={c['case_id']:c for c in read(DATA/'cases.json')};raw=raw_index(OUT/'initial')
    plan=[];bindings=[];errors=[]
    tasks={t['task_id']:t for t in read(OUT/'initial/requests.json')}
    for b in read(DATA/'bindings_initial.json'):
        if b['method'] not in ('recon_one_generate','recon_multi_generate'):continue
        try:
            obj=decode(raw[b['task_id']]);hs=obj['hypotheses'];expected=1 if b['method']=='recon_one_generate' else 3
            if not isinstance(hs,list) or len(hs)!=expected:raise ValueError('Incorrect hypothesis count')
            c=cases[b['case_id']]
            content={'hypotheses':hs,'catalogue':c['catalogue']}
            t=make_task(SYSTEM,content,'reconstruction_claim_audit',c['case_id'],'full',2600,source_task_id=b['task_id'],source_method=b['method'])
            plan.append(t);bindings.append({'task_id':t['task_id'],'case_id':c['case_id'],
                                          'source_method':b['method'],'source_task_id':b['task_id']})
        except (KeyError,ValueError,TypeError) as exc:errors.append({**b,'error':str(exc)})
    freeze(OUT/'reconstruction_audit/requests.json',list({t['task_id']:t for t in plan}.values()))
    freeze(DATA/'bindings_reconstruction_audit.json',bindings);save(OUT/'reconstruction_audit/source_errors.json',errors)
    print({'audit_requests':len(plan),'source_errors':len(errors)})

def analyze():
    cases={c['case_id']:c for c in read(DATA/'cases.json')};raw=raw_index(OUT/'reconstruction_audit')
    plans={t['task_id']:t for t in read(OUT/'reconstruction_audit/requests.json')};records=[];errors=[];view_records=[]
    for b in read(DATA/'bindings_reconstruction_audit.json'):
        try:
            c=cases[b['case_id']];t=plans[b['task_id']];obj=decode(raw[t['task_id']])
            content=json.loads(t['payload']['messages'][1]['content']);hs=content['hypotheses'];g={f['id']:f for f in c['facts']}
            seen=set();temporary=[]
            for a in obj['assertions']:
                ix=a['hypothesis'];key=(ix,a['id'])
                if type(ix) is not int or not 0<=ix<len(hs) or a['id'] not in g or key in seen:raise ValueError('Invalid/duplicate assertion ID')
                seen.add(key)
                if a['label'] not in ('true','false') or a['holder']!='B':raise ValueError('Invalid assertion label/holder')
                if not isinstance(a['quote'],str) or not a['quote'] or not any(a['quote'] in r['text'] for r in hs[ix]['replies']):raise ValueError('Quote not exactly present in generated reply')
                f=g[a['id']]
                temporary.append({'case_id':c['case_id'],'dataset':c['dataset'],'split':c['split'],
                    'cluster':c['template_family'] if c['dataset']=='controlled' else c['group'],
                    'method':b['source_method'],'hypothesis':ix,'attribute':a['id'],'label':a['label'],'quote':a['quote'],
                    'truth':f['truth'],'a_support':f['a_support'],
                    'known_truth_error':f['truth']!='unknown' and a['label']!=f['truth'],
                    'unverified':f['truth']=='unknown','unsupported':a['label']!=f['a_support'],
                    'correct_true':a['label']=='true' and f['truth']=='true'})
            records.extend(temporary)
            view_records.append({'case_id':c['case_id'],'dataset':c['dataset'],'split':c['split'],'method':b['source_method'],
                'hypotheses':len(hs),'explicit_assertions':len(temporary),
                'unsupported':sum(a['unsupported'] for a in temporary),'known_truth_errors':sum(a['known_truth_error'] for a in temporary),
                'unverified':sum(a['unverified'] for a in temporary),'correct_true':sum(a['correct_true'] for a in temporary)})
        except (KeyError,ValueError,TypeError) as exc:errors.append({**b,'error':str(exc)})
    result={'methods':{},'validation_errors':errors,
            'caution':'Same-family AI explicit-assertion annotation; exact quotes are validated but holder/entailment accuracy and omitted assertions lack independent human verification. This does not score implicit yes/no replies.'}
    for ds in ['controlled','natural']:
        result['methods'][ds]={}
        for m in ['recon_one_generate','recon_multi_generate']:
            rs=[r for r in view_records if r['dataset']==ds and r['method']==m and r['split']=='test'];n=sum(r['hypotheses'] for r in rs)
            result['methods'][ds][m]={'views':len(rs),'hypotheses':n,
                **{k:sum(r[k] for r in rs) for k in ['explicit_assertions','unsupported','known_truth_errors','unverified','correct_true']},
                'unsupported_per_100_hypotheses':100*sum(r['unsupported'] for r in rs)/n if n else None}
    save(OUT/'E2_reconstruction_assertions.json',result);write_csv(OUT/'E2_reconstruction_assertions.csv',records)
    write_csv(OUT/'E2_reconstruction_audit_views.csv',view_records)
    print({'audited_views':len(view_records),'assertions':len(records),'validation_errors':len(errors)})

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','analyze']);args=p.parse_args()
    {'prepare':prepare,'analyze':analyze}[args.stage]()
