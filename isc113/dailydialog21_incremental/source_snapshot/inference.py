"""A-only inference. This module deliberately cannot load reference or full-dialogue files."""
import json
from . import prompts
from .common import digest, validate_input

METHODS = ['direct_thinking','direct_multisample_verifier','route1_only','route2_only',
           'dual_without_verifier','dual_with_verifier']

def decode(body):
    c = body['choices'][0]
    if c.get('finish_reason') != 'stop': raise ValueError('Truncated or incomplete completion')
    s = c['message']['content'].strip()
    if s.startswith('```'): s = s.split('\n',1)[1].rsplit('```',1)[0]
    return json.loads(s)

def valid_evidence(evidence, turns):
    by = {t['turn_id']:t['text'] for t in turns}
    return isinstance(evidence,list) and bool(evidence) and all(
        isinstance(e,dict) and isinstance(e.get('turn_id'),int) and e['turn_id'] in by
        and isinstance(e.get('quote'),str) and bool(e['quote'].strip()) and e['quote'] in by[e['turn_id']]
        for e in evidence)

def validate_claims(obj, turns):
    if not isinstance(obj,dict) or not isinstance(obj.get('claims'),list): raise ValueError('Missing claims list')
    if len(obj['claims']) > 10: raise ValueError('Too many claims')
    for c in obj['claims']:
        if not isinstance(c.get('claim'),str) or not c['claim'].strip(): raise ValueError('Empty claim')
        if not isinstance(c.get('attribute'),str): raise ValueError('Missing attribute')
        if c.get('certainty') not in ['asserted','qualified']: raise ValueError('Missing epistemic status')
        if c.get('mechanism') not in ['explicit','presupposition','coreference','causal','cross_turn']: raise ValueError('Bad mechanism')
        if not isinstance(c.get('confidence'),(int,float)) or not 0 <= c['confidence'] <= 1: raise ValueError('Bad confidence')
        if not isinstance(c.get('evidence'),list): raise ValueError('Missing evidence list')
        # Bad citations are an experimental outcome, never a reason to sample for a better answer.
        c['evidence_span_valid'] = valid_evidence(c['evidence'],turns)
    return obj['claims']

def merge(*groups):
    found = {}
    for group in groups:
        for c in group:
            # Only deterministic exact normalization; semantic duplication is evaluated separately.
            k = ' '.join(c['claim'].lower().split())
            if k not in found: found[k] = dict(c, candidate_id=f'c{len(found)+1}')
    return list(found.values())

def validate_verdicts(obj, turns, candidates):
    ds = obj.get('decisions') if isinstance(obj,dict) else None
    wanted = {c['candidate_id'] for c in candidates}
    if not isinstance(ds,list) or len(ds)!=len(wanted) or {d.get('candidate_id') for d in ds} != wanted:
        raise ValueError('Verifier must cover each candidate exactly once')
    for d in ds:
        if d.get('verdict') not in ['supported','weak','unsupported','contradicted']: raise ValueError('Bad verdict')
        if d.get('evidence_level') not in ['E1','E2','E3','E4']: raise ValueError('Bad evidence level')
        if not isinstance(d.get('confidence'),(int,float)) or not 0<=d['confidence']<=1: raise ValueError('Bad confidence')
        if d['verdict']=='supported' and (d['evidence_level'] not in ['E1','E2'] or not valid_evidence(d.get('evidence'),turns)):
            d['render_rejection']='Verifier supported without exact visible evidence'
            d['verdict']='unsupported'
    return ds

def accept(candidates, decisions):
    by = {d['candidate_id']:d for d in decisions}
    return [dict(c,confidence=by[c['candidate_id']]['confidence'],
                 evidence=by[c['candidate_id']]['evidence'], verifier=by[c['candidate_id']])
            for c in candidates if by[c['candidate_id']]['verdict']=='supported']

def payload(prompt, content, limit=2048, sample=False):
    return {'model':'qwen3.8-flash','temperature':.7 if sample else 0,'enable_thinking':True,
            'thinking_budget':512,'max_tokens':limit,
            'messages':[{'role':'system','content':prompt},{'role':'user','content':json.dumps(content,ensure_ascii=False)}]}

def pipeline(client, item):
    # item is a strictly serialized A-only record, not a full dialogue.
    validate_input(item)
    turns = item['visible_turns']; content = {'visible_turns':turns,'target':'hidden partner'}
    calls = {}
    def generation(stage,prompt,sample=False):
        obj, tid = client.call(item['item_id']+'/'+stage, payload(prompt,content,2048,sample),
                               lambda x:validate_claims(x,turns))
        calls[stage] = tid
        return obj
    direct = generation('direct',prompts.DIRECT)
    second = generation('direct_sample2',prompts.DIRECT,True)
    r1 = generation('route1',prompts.ROUTE1)
    r2 = generation('route2',prompts.ROUTE2)
    dc = merge(direct,second); uc = merge(r1,r2)
    def verify(stage,cs):
        if not cs: return []
        obj,tid = client.call(item['item_id']+'/'+stage,payload(prompts.VERIFY,{'visible_turns':turns,'candidates':cs},3072),
                              lambda x:validate_verdicts(x,turns,cs))
        calls[stage]=tid
        return obj
    dv=verify('direct_verifier',dc); uv=verify('dual_verifier',uc)
    arms = {
        'direct_thinking':(direct,['direct']),
        'direct_multisample_verifier':(accept(dc,dv),['direct','direct_sample2','direct_verifier']),
        'route1_only':(r1,['route1']), 'route2_only':(r2,['route2']),
        'dual_without_verifier':(uc,['route1','route2']),
        'dual_with_verifier':(accept(uc,uv),['route1','route2','dual_verifier'])}
    return [dict(item_id=item['item_id'],dialogue_id=item['dialogue_id'],direction=item['direction'],dataset=item['dataset'],
                 method=arm,claims=cs,task_ids=[calls[s] for s in stages if s in calls]) for arm,(cs,stages) in arms.items()]
