"""Morphology-complete form of the declared attributed-observation safeguard."""
import hashlib
import re
from .guarded import combine as original_combine
from .run import ROOT, DATA, OUT, read, freeze, verify
from isc112_v2.runner import sha


def normalize_observation(text):
    # Used only for rule matching; no original text or model evidence is rewritten.
    return re.sub(r"\byou\s*(?:are\s+|['’]\s*re\s+)(looking|seeming|sounding)\b",
                  lambda m:'you '+{'looking':'look','seeming':'seem','sounding':'sound'}[m.group(1).lower()],text,flags=re.I)


def combine(prior,refined,turns):
    normalized=[{**t,'text':normalize_observation(t['text'])} for t in turns]
    result,audit=original_combine(prior,refined,normalized)
    result['arm']='guarded_v2'
    return result,audit


def build():
    verify();prior={p['dialogue_id']:p for p in read(DATA/'baseline_predictions.json')}
    aa={d['id']:d['visible_A'] for d in read(DATA/'visible_A.json')};refined=read(OUT/'refined/predictions.json')
    assert len(refined)==112
    freeze(DATA/'guarded_v2_manifest.json',{'protocol_sha256':hashlib.sha256((ROOT/'ISC112_V3_GUARDED_V2_PROTOCOL.md').read_bytes()).hexdigest(),
        'code_sha256':hashlib.sha256((ROOT/'isc112_v3/guarded_v2.py').read_bytes()).hexdigest(),
        'parent_code_sha256':hashlib.sha256((ROOT/'isc112_v3/guarded.py').read_bytes()).hexdigest(),
        'refined_sha256':sha(refined),'new_API_calls':0,'selection':'uniform morphology correction to A-only observation matching; no semantic-score input'})
    ps=[];audit=[]
    for p in refined:
        final,checks=combine(prior[p['dialogue_id']],p,aa[p['dialogue_id']]);ps.append(final)
        audit.append({'dialogue_id':p['dialogue_id'],'retained_prior_items':checks})
    freeze(OUT/'guarded_v2/predictions.json',ps);freeze(OUT/'guarded_v2/retention_audit.json',audit)
    freeze(OUT/'guarded_v2/cost_ledger.json',read(OUT/'refined/cost_ledger.json'))
    return {'dialogues':len(ps),'fact_occurrences':sum(len(p['facts']) for p in ps),'new_API_calls':0}


if __name__=='__main__':print(build())
