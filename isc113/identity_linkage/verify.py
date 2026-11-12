"""Offline audit of source binding, requests, evidence and complete outcome coverage."""
import argparse
from collections import Counter
import json
from pathlib import Path
from .core import ENDPOINT, HERE, SOURCE, digest, elara_v1, load, save, validate_item
from .api import Client
from . import prompts
from .run import check_inputs, code_binding, item_for


def verify(folder):
    groups=load(folder/'inputs.json')
    check_inputs(groups)
    by_group={g['group_id']:g for g in groups}
    config=load(folder/'inference_manifest.json')
    if config['code_sha256']!=code_binding() or config['inputs_digest']!=digest(groups):
        raise ValueError('Inference source/input binding changed')
    rows=[json.loads(s) for s in (folder/'attempts.jsonl').read_text(encoding='utf-8').splitlines()]
    starts={r['attempt_id']:r for r in rows if r['event']=='start'}
    completions={r['attempt_id']:r for r in rows if r['event']=='complete'}
    if starts.keys()!=completions.keys():
        raise ValueError('Unresolved/orphan request attempts')
    tasks={r['task_id']:r for r in starts.values()}
    recovered={r['attempt_id'] for r in rows if r['event']=='wrapper_recovery'}
    valid_tasks={r['task_id'] for aid,r in completions.items() if r.get('valid') or aid in recovered}
    predictions=0
    attributes=0
    claim_counts=[]
    evidence_levels=Counter()
    audit_verdicts=Counter()
    method_usage={}
    for g in groups:
        inventories=[]
        for d in g['dialogues']:
            p=load(folder/'attributes'/f"{g['group_id']}_{d['dialogue']}.json")
            pred=p['prediction']
            if pred['method']!='elara_evidence_lattice_v1' or pred['item_id']!=item_for(g,d)['item_id']:
                raise ValueError('Wrong ELARA source/item')
            if not set(pred['task_ids'])<=valid_tasks:
                raise ValueError('ELARA task not grounded in valid response')
            for c in pred['claims']:
                if not elara_v1().valid_evidence(c['evidence'],d['visible_turns']):
                    raise ValueError('Extracted claim citation mismatch')
                evidence_levels[c['audited_evidence_level']]+=1
                audit_verdicts[c['audit_verdict']]+=1
            claim_counts.append(len(pred['claims']))
            inventories.append(dict(dialogue=d['dialogue'],claims=[dict(c,claim_id=f'c{i}') for i,c in enumerate(pred['claims'],1)]))
            attributes+=1
        for method,records,prompt in [('elara',inventories,prompts.ASSOCIATE),('direct',g['dialogues'],prompts.DIRECT)]:
            out=load(folder/'predictions'/f"{g['group_id']}_{method}.json")
            prompts.validate_partition(out['prediction'],records,method)
            tid=out['task_id']
            if tid not in valid_tasks:
                raise ValueError('Prediction lacks valid task')
            payload=tasks[tid]['request']
            data=json.loads(payload['messages'][1]['content'])
            if data['dialogues']!=records or payload['messages'][0]['content']!=prompt:
                raise ValueError('Prediction did not use frozen prompt/records')
            if set(data)!={'setting','observer_configuration','dialogues'}:
                raise ValueError('Unexpected model metadata')
            if any(k in json.dumps(data) for k in ('true_k','b_id','a_id','source_dialogue_id')):
                raise ValueError('Gold metadata leaked')
            predictions+=1
    # Audit EVERY dispatched payload, including invalid/retried generations.
    allowed_turns={item_for(g,d)['item_id']:d['visible_turns'] for g in groups for d in g['dialogues']}
    for row in starts.values():
        payload=row['request']
        if digest(dict(name=row['logical_name'],endpoint=config['endpoint'],payload=payload))!=row['task_id']:
            raise ValueError('Request task/payload binding mismatch')
        if payload['model']!='qwen3.8-flash' or not payload['enable_thinking']:
            raise ValueError('Wrong model/thinking configuration')
        name=row['logical_name']
        data=json.loads(payload['messages'][1]['content'])
        if '/elara/' in name:
            item_id=name.split('/elara/',1)[0]
            if item_id not in allowed_turns or data['visible_turns']!=allowed_turns[item_id]:
                raise ValueError('Extraction received non-A text')
            if set(data)-{'visible_turns','target','existing_claims','candidates'}:
                raise ValueError('Unexpected extraction metadata')
            if payload['thinking_budget']!=512:
                raise ValueError('Changed original extraction budget')
        elif name.endswith('/direct') or name.endswith('/elara'):
            if payload['thinking_budget']!=2048 or payload['max_tokens']!=8192:
                raise ValueError('Unmatched direct/linkage budget')
        else:
            raise ValueError('Unknown task')
    # Count returned usage for all attempts, including malformed responses.
    for aid,r in completions.items():
        name=r['logical_name']
        phase='extraction' if '/elara/' in name else name.rsplit('/',1)[-1]
        usage=method_usage.setdefault(phase,dict(attempts=0,returned_total_tokens=0,usage_missing_attempts=0,billing_unknown_attempts=0))
        usage['attempts']+=1
        u=r.get('body',{}).get('usage')
        if u:
            usage['returned_total_tokens']+=u.get('total_tokens',0)
        else:
            usage['usage_missing_attempts']+=1
        usage['billing_unknown_attempts']+=int(r.get('billing_unknown',False))
    result=dict(passed=True,groups=len(groups),attribute_inventories=attributes,predictions=predictions,
                extracted_claims=sum(claim_counts),empty_inventories=sum(n==0 for n in claim_counts),
                min_claims=min(claim_counts),max_claims=max(claim_counts),
                audited_evidence_levels=dict(evidence_levels),audit_verdicts=dict(audit_verdicts),
                dispatched_attempts=len(starts),method_usage=method_usage,
                wrapper_recoveries=len(recovered),gold_fields_in_model_requests=False,
                source_and_input_binding_verified=True,original_elara_source=str(SOURCE))
    save(folder/'verification.json',result)
    print(json.dumps(result,ensure_ascii=True),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--folder',type=Path,default=HERE/'runs/pilot_final')
    verify(p.parse_args().folder)
