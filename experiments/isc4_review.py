"""Build an explicit claim/evidence-level semantic review queue; no automatic judge."""
import collections
import csv
import json
from isc4_open import OUT, DATA, read, save, sha

def review_key(did, fact):
    # Evidence differences matter: identical claims can be valid at one prefix only.
    return sha({'dialogue_id':did,'claim':fact['claim'],'evidence':fact['evidence']})[:20]

def build():
    queue={}
    for p in read(OUT/'predictions.json'):
        for i,f in enumerate(p['facts']):
            key=review_key(p['dialogue_id'],f)
            q=queue.setdefault(key,{'review_id':key,'dialogue_id':p['dialogue_id'],
                'claim':f['claim'],'evidence':f['evidence'],'occurrences':[],
                'verdict':'unreviewed','reference_ids':[],'canonical_id':'','rationale':''})
            q['occurrences'].append({'task_id':p['task_id'],'k':p['k'],'K':p['K'],'fact_index':i})
    values=sorted(queue.values(),key=lambda q:(q['dialogue_id'],q['claim'],q['review_id']))
    save(OUT/'review_queue.json',values)
    with (OUT/'review_queue.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['review_id','dialogue_id','claim','evidence','prefixes','verdict','reference_ids','canonical_id','rationale']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for q in values:w.writerow({**{k:q[k] for k in fields if k not in ('prefixes','evidence')},
             'evidence':json.dumps(q['evidence'],ensure_ascii=False),
             'prefixes':json.dumps(sorted(o['k'] for o in q['occurrences']))})
    print({'unique_claim_evidence_reviews':len(values),'prediction_fact_occurrences':sum(len(p['facts']) for p in read(OUT/'predictions.json'))})
if __name__=='__main__':build()
