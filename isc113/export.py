"""Recover method-level outcomes from retained stage logs, including failed arms."""
from .common import BASE,read,save,jsonlines,require_dataset,validate_input,run_folder
from .inference import decode,validate_claims,validate_verdicts,merge,accept

STAGES={'direct_thinking':['direct'],'direct_multisample_verifier':['direct','direct_sample2','direct_verifier'],
        'route1_only':['route1'],'route2_only':['route2'],'dual_without_verifier':['route1','route2'],
        'dual_with_verifier':['route1','route2','dual_verifier']}

def reconstruct(dataset='dailydialog',run_id=None):
    require_dataset(dataset)
    folder=run_folder(run_id) if run_id is not None else BASE/'runs/dailydialog'
    rows=jsonlines(folder/'attempts.jsonl');by={}
    for r in rows:
        if r['event']=='complete':by.setdefault(r['logical_name'],[]).append(r)
    allout=[];bindings=[]
    for item in read(folder/'inputs.json' if run_id is not None else BASE/f'inputs/{dataset}.json'):
        validate_input(item)
        turns=item['visible_turns'];groups={};tasks={};failure={}
        for stage in ['direct','direct_sample2','route1','route2','direct_verifier','dual_verifier']:
            prior=by.get(item['item_id']+'/'+stage,[])
            if prior:tasks[stage]=prior[0]['task_id']
            good=next((r for r in prior if r.get('valid')),None)
            if good:
                obj=decode(good['body'])
                if 'verifier' not in stage:groups[stage]=validate_claims(obj,turns)
                else:
                    stages=['direct','direct_sample2'] if stage=='direct_verifier' else ['route1','route2']
                    if all(s in groups for s in stages):groups[stage]=validate_verdicts(obj,turns,merge(*(groups[s] for s in stages)))
                bindings.append({'logical_name':item['item_id']+'/'+stage,'task_id':good['task_id'],'attempt_id':good['attempt_id']})
            elif prior:failure[stage]='provider_blocked' if any(r.get('http_status')==400 for r in prior) else 'attempt_limit_or_invalid_response'
            else:failure[stage]='not_executed_after_upstream_failure'
        for method,stages in STAGES.items():
            required=list(stages)
            # Empty candidate union does not need a verifier request.
            if required[-1].endswith('verifier') and all(s in groups for s in required[:-1]) and not merge(*(groups[s] for s in required[:-1])):
                required=required[:-1]
            complete=all(s in groups for s in required)
            if complete:
                if method in ['direct_thinking','route1_only','route2_only']:claims=groups[required[0]]
                else:
                    claims=merge(*(groups[s] for s in stages[:2]))
                    if method.endswith('verifier') and method!='dual_without_verifier':
                        claims=accept(claims,groups.get(stages[-1],[])) if claims else []
            else:claims=[]
            out={k:item[k] for k in ['item_id','dialogue_id','direction','dataset']}|{
                'method':method,'claims':claims,'task_ids':[tasks[s] for s in stages if s in tasks],
                'outcome':'complete' if complete else 'failed_abstention',
                'missing_stages':{s:failure.get(s,'unavailable') for s in required if s not in groups}}
            allout.append(out)
    return allout,bindings

def export(dataset='dailydialog',run_id=None):
    from .common import freeze
    allout,bindings=reconstruct(dataset,run_id)
    if run_id is None:
        freeze(BASE/f'runs/main/exports/{dataset}.json',allout)
        freeze(BASE/f'runs/main/selection_bindings/{dataset}.json',bindings)
    else:
        folder=run_folder(run_id)
        save(folder/'exports/dailydialog.json',allout)
        save(folder/'selection_bindings.json',bindings)
    return {'dataset':dataset,'outcomes':len(allout),'complete':sum(x['outcome']=='complete' for x in allout),
            'failed_abstentions':sum(x['outcome']!='complete' for x in allout)}

if __name__=='__main__':
    print(export())
