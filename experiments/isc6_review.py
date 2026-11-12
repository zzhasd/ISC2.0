"""Review preparation and paired analysis; never used by the inference module."""
import argparse
import collections
import csv
import statistics
from isc4_open import ROOT,read,save,sha
from isc4_analyze import maximum_match,bootstrap
from isc5_review import key

OUT=ROOT/'results/isc6'
METHODS=['direct','selfcheck','ledger_verify','atomic_contrast']


def prepare():
    queue=[]
    for p in sorted(read(OUT/'predictions.json'),key=lambda p:p['dialogue_id']):
        for i,f in enumerate(p['facts']):
            queue.append({'index':len(queue),'dialogue_id':p['dialogue_id'],'fact_index':i,
                'review_id':sha({'dialogue_id':p['dialogue_id'],'fact':f})[:20],**f,
                'reference_ids':[],'partial_reference_ids':[],'A_grounded':None,
                'source_status':'unreviewed','verdict':'unreviewed','rationale':''})
    save(OUT/'review_queue.json',queue)
    refs={r['dialogue_id']:r['facts'] for r in read(ROOT/'data/isc5/full_AB_reference.json')}
    ds={d['id']:d for d in read(ROOT/'data/isc6/dialogues.json')}
    lines=[]
    for did in sorted(ds):
        lines.append('\nDIALOGUE '+did)
        lines.extend(f"{i+1} {'A' if i%2==0 else 'B'}: {s}" for i,s in enumerate(ds[did]['turns']))
        lines.append('REFERENCE: '+str([(f['id'],f['claim'],bool(f['A_support_sets'])) for f in refs[did]]))
        lines.append('PREDICTIONS:')
        lines.extend(str({k:r[k] for k in ['index','claim','time','evidence_turns']}) for r in queue if r['dialogue_id']==did)
    (OUT/'review_packet.txt').write_text('\n'.join(lines),encoding='utf-8')
    print({'new_assertions_to_review':len(queue)})


def analyze():
    ds=read(ROOT/'data/isc6/dialogues.json');ids=[d['id'] for d in ds]
    refs={r['dialogue_id']:r['facts'] for r in read(ROOT/'data/isc5/full_AB_reference.json')}
    old=[p for p in read(ROOT/'results/isc5/predictions.json') if p['dialogue_id'] in ids]
    new=read(OUT/'predictions.json');pred={(p['dialogue_id'],p['stage']):p for p in old+new}
    oldreview={r['review_id']:r for r in read(ROOT/'results/isc5/semantic_review.json')}
    newreview={(r['dialogue_id'],r['fact_index']):r for r in read(OUT/'semantic_review.json')}
    assert len(newreview)==sum(len(p['facts']) for p in new)
    assert all(r['verdict']!='unreviewed' for r in newreview.values())
    audit=read(ROOT/'results/isc5/execution_audit.json')+read(OUT/'execution_audit.json')
    costs={(a['dialogue_id'],a['stage']):a for a in audit}
    source_stages={'direct':['direct'],'selfcheck':['direct','selfcheck'],
        'ledger_verify':['ledger','ledger_verify'],'atomic_contrast':['atomic_propose','atomic_contrast']}
    rows=[]
    for did in ids:
        supported={f['id'] for f in refs[did] if f['A_support_sets']}
        for method in METHODS:
            p=pred.get((did,method));edges=[];atoms=set();nonsupported=0;contradicted=0;outscope=0;newids=set();usable=0
            for i,f in enumerate(p['facts'] if p else []):
                r=newreview[did,i] if method=='atomic_contrast' else oldreview[key(did,f)]
                rr=[fid for fid in r['reference_ids'] if fid in supported and r['A_grounded'] is True]
                edges.append(rr)
                # Exact IDs are conjunctions only when explicitly adjudicated so.
                if len(rr)>1:
                    assert r.get('conjunctive_atoms') is True or (did=='test_39' and f['claim']=='B is a professor named Clark.')
                atoms.update(rr)
                nonsupported+=r['A_grounded'] is not True
                contradicted+=r['source_status']=='contradicted'
                outscope+=r['verdict']=='out_of_scope'
                usable+=r['A_grounded'] is True and r['source_status']=='consistent' and r['verdict']!='out_of_scope'
                if r['verdict']=='supported_new':newids.add(r.get('canonical_id',r['review_id']))
            c=[costs[did,s] for s in source_stages[method] if (did,s) in costs]
            rows.append({'dialogue_id':did,'method':method,'valid':p is not None,
                'A_reference_count':len(supported),'full_reference_count':len(refs[did]),
                'legacy_strict':len(maximum_match(edges)) if p else None,
                'atomic_coverage':len(atoms) if p else None,'atomic_ids':sorted(atoms),
                'raw_claims':len(p['facts']) if p else None,'hypotheses':len(p['hypotheses']) if p else None,
                'A_unsupported_or_uncertain':nonsupported if p else None,'source_contradicted':contradicted if p else None,
                'out_of_scope':outscope if p else None,'supported_new':len(newids) if p else None,
                'grounded_in_scope_raw_claims':usable if p else None,
                'pipeline_tokens':sum(a['tokens'] or 0 for a in c),
                'pipeline_latency_seconds':sum(a['elapsed_seconds'] for a in c)})
    by={(r['dialogue_id'],r['method']):r for r in rows}
    common=[did for did in ids if all(by[did,m]['valid'] for m in METHODS)]
    summary=[]
    for method in METHODS:
        rr=[by[did,method] for did in common]
        entry={'method':method,'planned':len(ids),'valid':sum(by[did,method]['valid'] for did in ids),'common':len(common)}
        for field in ['A_reference_count','full_reference_count','legacy_strict','atomic_coverage','raw_claims','hypotheses',
                      'A_unsupported_or_uncertain','source_contradicted','out_of_scope','supported_new','grounded_in_scope_raw_claims']:
            entry[field]=sum(r[field] for r in rr)
        entry['mean_tokens']=statistics.mean(r['pipeline_tokens'] for r in rr) if rr else None
        entry['mean_latency_seconds']=statistics.mean(r['pipeline_latency_seconds'] for r in rr) if rr else None
        summary.append(entry)
    pairs=[]
    for other in METHODS[:-1]:
        pairs.append({'comparison':'atomic_contrast - '+other,
            'legacy_strict':bootstrap([by[d,'atomic_contrast']['legacy_strict']-by[d,other]['legacy_strict'] for d in common]),
            'atomic_coverage':bootstrap([by[d,'atomic_contrast']['atomic_coverage']-by[d,other]['atomic_coverage'] for d in common]),
            'without_medical_atomic':bootstrap([by[d,'atomic_contrast']['atomic_coverage']-by[d,other]['atomic_coverage'] for d in common if d!='test_526']),
            'without_policy_sensitive_atomic':bootstrap([len(set(by[d,'atomic_contrast']['atomic_ids'])-{'test_39_profession','test_91_broadcast'})-len(set(by[d,other]['atomic_ids'])-{'test_39_profession','test_91_broadcast'}) for d in common])})
    new_audit=read(OUT/'execution_audit.json')
    result={'methods':summary,'paired_comparisons':pairs,'common_dialogue_ids':common,
        'new_calls':len(new_audit),'new_tokens':sum(a['tokens'] or 0 for a in new_audit),
        'returned_models':sorted({a['returned_model'] for a in new_audit if a['returned_model']}),
        'status':'exploratory development; same source-aware assistant review; historical comparators; no matched-token control'}
    save(OUT/'summary.json',result);save(OUT/'dialogue_scores.json',rows)
    with (OUT/'method_scores.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(summary[0]));writer.writeheader();writer.writerows(summary)
    print(result)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','analyze']);args=p.parse_args()
    prepare() if args.action=='prepare' else analyze()
