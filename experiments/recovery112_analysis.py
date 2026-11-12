"""Merge first-valid responses, reuse fixed references and audit semantic completeness."""
import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path
import isc4_review as r4
import isc4_analyze as a4
import isc7_analyze as a7
from isc4_open import ROOT,read,save,sha,freeze
from recovery112 import OUT,DATA

def prepare_reviews():
    r4.OUT=OUT/'isc4';r4.build()
    a7.OUT=OUT/'isc7';a7.prepare_review()
    for kind,name in [('isc4','assistant_semantic_review.json'),('isc7','semantic_review.json')]:
        existing=read(ROOT/'results/merged112'/kind/name)
        by={r['review_id']:r for r in existing};queue=read(OUT/kind/'review_queue.json')
        missing=[r for r in queue if r['review_id'] not in by]
        for i,q in enumerate(missing):q['index']=i
        save(OUT/kind/'review_additions_queue.json',missing)
        save(OUT/kind/'reused_reviews.json',[{**q,**by[q['review_id']]} for q in queue if q['review_id'] in by])
        print({'kind':kind,'reused':len(queue)-len(missing),'new_reviews':len(missing)})

def merge_reviews():
    for kind,name in [('isc4','assistant_semantic_review.json'),('isc7','semantic_review.json')]:
        queue=read(OUT/kind/'review_queue.json');fresh={q['review_id']:q for q in queue}
        combined=read(OUT/kind/'reused_reviews.json')+read(OUT/kind/'review_additions.json')
        assert len({r['review_id'] for r in combined})==len(combined)==len(queue)
        assert set(fresh)=={r['review_id'] for r in combined}
        fields=['kind','verdict','reference_ids','partial_reference_ids','A_grounded','source_status','rationale','canonical_id','conjunctive_atoms','grounded_reference_ids','reviewer']
        result=[{**fresh[r['review_id']],**{k:r[k] for k in fields if k in r}} for r in combined]
        # An old source-supported discovery has explicitly unresolved A support (None).
        # Preserve that existing uncertainty rather than converting it to a new verdict.
        assert all(r['rationale'] and r['verdict']!='unreviewed' and r['A_grounded'] in [True,False,None] for r in result)
        assert all(isinstance(r['A_grounded'],bool) for r in read(OUT/kind/'review_additions.json'))
        save(OUT/kind/name,result)

def analyze(label):
    idsall=read(DATA/'dialogues.json');refsall=read(DATA/'reference.json')
    oldids={d['id'] for d in read(ROOT/'data/isc4/dialogues.json')}
    ids={d['id'] for d in idsall if label=='merged' or (d['id'] in oldids)==(label=='old32')}
    dest=OUT if label=='merged' else OUT/label;dd=ROOT/'data/recovery112'/label
    ds=[d for d in idsall if d['id'] in ids];refs=[r for r in refsall if r['dialogue_id'] in ids]
    plan=[e['task'] for e in read(OUT/'original_tasks.json') if e['kind']=='isc4' and (e['task']['dialogue_id'] in ids or e['task']['dialogue_id']=='shared_prior')]
    freeze(dd/'dialogues.json',ds);freeze(dd/'reference.json',refs);freeze(dd/'full_AB_reference_v2.json',refs)
    freeze(dd/'manifest.json',{'request_sha256':sha(plan),'dialogues':len(ds),'reference_sha256':sha(refs)})
    freeze(dest/'isc4/baseline/requests.json',plan)
    if label!='merged':
        for kind,files in [('isc4',['predictions.json','assistant_semantic_review.json']),('isc7',['predictions.json','semantic_review.json','execution_audit.json'])]:
            for f in files:
                rows=[r for r in read(OUT/kind/f) if r.get('dialogue_id') in ids or r.get('dialogue_id')=='shared_prior']
                save(dest/kind/f,rows)
    a4.DATA=dd;a4.OUT=dest/'isc4';a4.main()
    s=read(a4.OUT/'summary.json');s['limitations']=[x for x in s['limitations'] if not x.startswith('32 previously') and not x.startswith('reference finished')]
    s['limitations']+=['Additional first-valid retries authorized by user; pre-recovery results preserved separately','New80 reference frozen before new original Qwen outputs; old reference timing unchanged','Provisional same-assistant reference and review; no independent human gold']
    save(a4.OUT/'summary.json',s)
    a7.DATA=dd;a7.OUT=dest/'isc7';a7.calculate()
    s=read(a7.OUT/'summary.json');s['interpretation']='Same fixed prompts/settings with user-authorized first-valid failure recovery; costs include all failed attempts and retries; not single-attempt native success.'
    save(a7.OUT/'summary.json',s)

def align():
    rows=list(csv.DictReader((OUT/'isc4/full_dialogue_scores.csv').open(encoding='utf-8-sig')))
    a={r['dialogue_id']:r for r in rows if r['valid']=='True'}
    s7=read(OUT/'isc7/summary.json');b={r['dialogue_id']:r for r in read(OUT/'isc7/dialogue_scores.json') if r['arm']=='direct_off' and r['valid']}
    ids=sorted(set(a)&set(s7['common_ids']));den=sum(int(a[d]['A_reference_available']) for d in ids)
    assert all(int(a[d]['A_reference_available'])==b[d]['A_reference_count'] for d in ids)
    n1=sum(int(a[d]['grounded_exact_reference_matches']) for d in ids);n3=sum(b[d]['legacy_strict'] for d in ids)
    save(OUT/'metric_alignment.json',{'dialogues':len(ids),'ids':ids,'A_supported_reference_count':den,
        'experiment1':{'matches':n1,'rate':n1/den},'experiment3_direct_off':{'matches':n3,'rate':n3/den},
        'difference_percentage_points':100*(n3-n1)/den,'matching':'same A-supported references, same valid cohort, grounded one-to-one strict matching'})

def finish():
    from recovery112 import attempts,valid,chosen
    entries=read(OUT/'original_tasks.json');extra=read(OUT/'new_dependent_requests.json')
    starts=[json.loads(s) for s in (OUT/'attempt_starts.jsonl').read_text(encoding='utf-8').splitlines()];rs=attempts()
    checks={'all_attempts_recorded':len(starts)==len(rs) and {r['attempt_id'] for r in starts}=={r['attempt_id'] for r in rs},
        'old_files_unchanged':all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in read(OUT/'preservation_hashes.json').items()),
        'fixed_dialogues':len(read(DATA/'dialogues.json'))==112,
        'no_credential_in_artifacts':not any('sk-ws-' in p.read_text(encoding='utf-8-sig') for p in OUT.rglob('*') if p.is_file() and p.suffix in ['.json','.jsonl','.md','.py','.csv'])}
    by={(e['kind'],e['task']['task_id']):e['task'] for e in entries}
    by.update({('isc7',t['task_id']):t for t in extra})
    checks['unchanged_payloads']=all(sha(t['payload'])==t['request_sha256'] for t in by.values())
    allowed={(e['kind'],e['task']['task_id']) for e in read(OUT/'repair_plan.json')}|{('isc7',t['task_id']) for t in extra}
    checks['no_valid_original_retried']=all((r['kind'],r['task_id']) in allowed for r in rs)
    checks['retry_cap_respected']=all(sum(r['kind']==k and r['task_id']==tid for r in rs)<=3 for k,tid in by)
    bindings=read(OUT/'selection_bindings.json')
    for b in bindings:
        if b['selection']=='original_valid':continue
        successful=[r for r in rs if r['kind']==b['kind'] and r['task_id']==b['task_id'] and r['valid']]
        assert successful[0]['attempt_id']==b['attempt_id']
    checks['first_valid_selection']=True
    for kind,key,name in [('isc4',r4.review_key,'assistant_semantic_review.json'),('isc7',a7.review_key,'semantic_review.json')]:
        expected={key(p['dialogue_id'],f) for p in read(OUT/kind/'predictions.json') for f in p['facts']}
        reviews=read(OUT/kind/name)
        checks[kind+'_review_complete']=len(reviews)==len(expected) and {r['review_id'] for r in reviews}==expected
    checks['all_selected_claims_reviewed']=checks['isc4_review_complete'] and checks['isc7_review_complete']
    result={'checks':checks,'all_checks_passed':all(checks.values()),**read(OUT/'execution_status.json'),
        'all_failures_recovered':not read(OUT/'remaining_missing.json'),'recovery_not_single_attempt_success':True}
    save(OUT/'final_checks.json',result);assert result['all_checks_passed']
    print(result)

if __name__=='__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser();p.add_argument('action',choices=['queues','merge','analyze','finish']);a=p.parse_args()
    if a.action=='queues':prepare_reviews()
    elif a.action=='merge':merge_reviews()
    elif a.action=='finish':finish()
    else:
        for label in ['old32','new80','merged']:analyze(label)
        align()
