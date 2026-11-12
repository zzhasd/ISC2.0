"""Build method-hidden semantic review queue and separate method bindings."""
import collections
from isc4_open import sha,read,save
from isc5_run import OUT

def key(did,fact):
    return sha({'dialogue_id':did,'claim':fact['claim'],'evidence_turns':sorted(set(fact['evidence_turns']))})[:20]

def main():
    queue={};bindings=[]
    for p in read(OUT/'predictions.json'):
        for i,f in enumerate(p['facts']):
            rid=key(p['dialogue_id'],f)
            q=queue.setdefault(rid,{'review_id':rid,'dialogue_id':p['dialogue_id'],'claim':f['claim'],
                'evidence_turns':sorted(set(f['evidence_turns'])),'reference_ids':[],
                'partial_reference_ids':[],'time_variants':[],'A_grounded':None,'verdict':'unreviewed','rationale':''})
            if f.get('time') not in q['time_variants']:q['time_variants'].append(f.get('time'))
            bindings.append({'review_id':rid,'task_id':p['task_id'],'dialogue_id':p['dialogue_id'],
                'stage':p['stage'],'split':p['split'],'fact_index':i})
    values=sorted(queue.values(),key=lambda q:(q['dialogue_id'],q['claim'],q['review_id']))
    save(OUT/'review_queue.json',values);save(OUT/'review_bindings.json',bindings)
    print({'unique_claim_evidence_pairs':len(values),'fact_occurrences':len(bindings)})
if __name__=='__main__':main()
