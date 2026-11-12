"""A-only deterministic consistency safeguards, no evaluation imports."""
import copy
import hashlib
import re
from .run import ROOT, DATA, OUT, read, save, freeze, verify


def norm(s): return ' '.join(s.lower().split())


def still_accepted(item):
    return (item.get('holder')=='B' and item.get('scope')=='profile' and item.get('status')=='active'
            and item.get('support') in {'explicit','entailed','presupposed'})


def attributed_B_guard(original, revised, turns):
    if norm(original['claim']) != norm(revised['claim']) or revised.get('holder')!='A': return False
    claim=original['claim']
    target=bool(re.search(r"\bB(?:'s|’s)?\b.*\b(?:described|evaluated|judged|considered|regarded)\b.*\bby A\b",claim,re.I)
                or re.search(r'^A\s+(?:describes|evaluates|judges|considers|regards)\s+B\b',claim,re.I))
    if not target:return False
    # Require a direct positive address assertion, not a question or a hypothetical.
    observation=re.compile(r'^(?:(?:hey|well|oh|wow)\s*[,!]\s*)?you\s+(?:look|seem|sound)\b',re.I)
    matches=[t['turn'] for t in turns if observation.search(t['text'].strip())]
    return bool(matches) and max(matches) in original['evidence_turns']


def combine(prior, refined, turns):
    if refined.get('outcome')=='provider_blocked_baseline_fallback':return copy.deepcopy(refined),[]
    items={i['id']:i for i in refined['items']};facts=list(refined['facts']);audit=[]
    for n,f in enumerate(prior['facts']):
        item=items[f'b{n+1}'];rule=None
        if still_accepted(item):rule='prior_item_still_accepted'
        elif attributed_B_guard(f,item,turns):rule='attributed_B_profile_target_consistency'
        if rule:
            facts.append(f);audit.append({'prior_index':n,'revision_id':item['id'],'rule':rule})
    found={}
    for f in facts:found.setdefault((norm(f['claim']),norm(f['time'])),f)
    return {**refined,'arm':'guarded','facts':list(found.values())},audit


def build():
    verify();prior={p['dialogue_id']:p for p in read(DATA/'baseline_predictions.json')}
    aa={d['id']:d['visible_A'] for d in read(DATA/'visible_A.json')};refined=read(OUT/'refined/predictions.json')
    assert len(refined)==112
    freeze(DATA/'guarded_manifest.json',{'protocol_sha256':hashlib.sha256((ROOT/'ISC112_V3_GUARDED_PROTOCOL.md').read_bytes()).hexdigest(),
        'code_sha256':hashlib.sha256((ROOT/'isc112_v3/guarded.py').read_bytes()).hexdigest(),
        'refined_sha256':__import__('isc112_v2.runner',fromlist=['sha']).sha(refined),'new_API_calls':0,
        'selection':'same uniform A-only self-decision and attributed-target rules, no reference/semantic-score access'})
    ps=[];audit=[]
    for p in refined:
        final,checks=combine(prior[p['dialogue_id']],p,aa[p['dialogue_id']]);ps.append(final)
        audit.append({'dialogue_id':p['dialogue_id'],'retained_prior_items':checks})
    freeze(OUT/'guarded/predictions.json',ps);freeze(OUT/'guarded/retention_audit.json',audit)
    freeze(OUT/'guarded/cost_ledger.json',read(OUT/'refined/cost_ledger.json'))
    return {'dialogues':len(ps),'fact_occurrences':sum(len(p['facts']) for p in ps),'guard_rule_occurrences':sum(len(x['retained_prior_items']) for x in audit),'new_API_calls':0}


if __name__=='__main__':print(build())
