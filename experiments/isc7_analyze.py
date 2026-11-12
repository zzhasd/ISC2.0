"""Offline review preparation and paired factorial analysis, no API calls."""
import argparse
import collections
import csv
import statistics
from isc4_open import read,save,sha
from isc4_analyze import maximum_match,bootstrap
from isc7_run import OUT,DATA,ARMS


def review_key(did,f):
    return sha({'dialogue_id':did,'claim':f['claim'],'time':f['time']})[:20]


def prepare_review():
    entries={};bindings=[]
    for p in read(OUT/'predictions.json'):
        for i,f in enumerate(p['facts']):
            rid=review_key(p['dialogue_id'],f)
            q=entries.setdefault(rid,{'review_id':rid,'dialogue_id':p['dialogue_id'],'claim':f['claim'],
                'time':f['time'],'evidence_variants':[],'reference_ids':[],'partial_reference_ids':[],
                'A_grounded':None,'source_status':'unreviewed','verdict':'unreviewed','rationale':''})
            if f['evidence_turns'] not in q['evidence_variants']:q['evidence_variants'].append(f['evidence_turns'])
            bindings.append({'review_id':rid,'task_id':p['task_id'],'arm':p['arm'],'dialogue_id':p['dialogue_id'],'fact_index':i})
    queue=sorted(entries.values(),key=lambda q:(q['dialogue_id'],q['claim'],q['time']))
    for i,q in enumerate(queue):q['index']=i
    save(OUT/'review_queue.json',queue);save(OUT/'review_bindings.json',bindings)
    print({'unique_claim_time_pairs':len(queue),'fact_occurrences':len(bindings)})


def calculate():
    ds=read(DATA/'dialogues.json');ids=[d['id'] for d in ds]
    refs={r['dialogue_id']:r['facts'] for r in read(DATA/'reference.json')}
    reviews={r['review_id']:r for r in read(OUT/'semantic_review.json')}
    ps=read(OUT/'predictions.json');by={(p['dialogue_id'],p['arm']):p for p in ps}
    audit=read(OUT/'execution_audit.json');cost=collections.defaultdict(list)
    for a in audit:cost[a['dialogue_id'],a['arm']].append(a)
    assert all(r['verdict']!='unreviewed' for r in reviews.values())
    assert set(reviews)=={review_key(p['dialogue_id'],f) for p in ps for f in p['facts']}
    rows=[]
    for did in ids:
        supported={f['id'] for f in refs[did] if f['A_support_sets']}
        for arm in ARMS:
            p=by.get((did,arm));atoms=set();edges=[];unsupported=0;outscope=0;contradicted=0;usable=0;discoveries=set()
            for f in p['facts'] if p else []:
                r=reviews[review_key(did,f)]
                if len(r['reference_ids'])>1:assert r.get('conjunctive_atoms') is True
                exact=[x for x in r['reference_ids'] if x in supported and r['A_grounded'] is True]
                edges.append(exact)
                atomic=r.get('grounded_reference_ids',exact)
                assert set(atomic)<=set(r['reference_ids'])
                atoms.update(x for x in atomic if x in supported)
                unsupported+=r['A_grounded'] is not True
                outscope+=r['verdict']=='out_of_scope'
                contradicted+=r['source_status']=='contradicted'
                usable+=r['A_grounded'] is True and r['source_status']=='consistent' and r['verdict']!='out_of_scope'
                if r['verdict']=='supported_new':discoveries.add(r.get('canonical_id',r['review_id']))
            calls=cost[did,arm];times={a['stage']:a['elapsed_seconds'] for a in calls}
            def total(k):return sum(a[k] for a in calls if a[k] is not None)
            rows.append({'dialogue_id':did,'arm':arm,'valid':p is not None,'A_reference_count':len(supported),
                'full_reference_count':len(refs[did]),'atomic_coverage':len(atoms) if p else None,
                'legacy_strict':len(maximum_match(edges)) if p else None,'atomic_ids':sorted(atoms),
                'raw_claims':len(p['facts']) if p else None,'hypotheses':len(p['hypotheses']) if p else None,
                'A_unsupported_or_uncertain':unsupported if p else None,'out_of_scope':outscope if p else None,
                'source_contradicted':contradicted if p else None,'grounded_in_scope_raw':usable if p else None,
                'supported_new':len(discoveries) if p else None,'calls':len(calls),
                'prompt_tokens':total('prompt_tokens'),'completion_tokens':total('completion_tokens'),
                'reasoning_tokens':total('reasoning_tokens'),'reasoning_usage_complete':all(a['reasoning_tokens'] is not None for a in calls),
                'total_tokens':total('total_tokens'),'latency_sum':total('elapsed_seconds'),
                'latency_critical_path':times.get('direct',max(times.get('global',0),times.get('local',0))+times.get('judge',0))})
    rb={(r['dialogue_id'],r['arm']):r for r in rows}
    common=[did for did in ids if all(rb[did,a]['valid'] for a in ARMS)]
    metrics=['A_reference_count','full_reference_count','atomic_coverage','legacy_strict','raw_claims','hypotheses',
             'A_unsupported_or_uncertain','out_of_scope','source_contradicted','grounded_in_scope_raw','supported_new']
    summaries=[]
    for arm in ARMS:
        rr=[rb[did,arm] for did in common];allr=[rb[did,arm] for did in ids];calls=[a for a in audit if a['arm']==arm]
        row={'arm':arm,'planned':len(ids),'valid':sum(r['valid'] for r in allr),'common':len(common)}
        row.update({m:sum(r[m] for r in rr) for m in metrics})
        row.update({f'mean_{m}':statistics.mean(r[m] for r in rr) if rr else None
                    for m in ['total_tokens','prompt_tokens','completion_tokens','reasoning_tokens','latency_sum','latency_critical_path']})
        row.update({'actual_calls_all_planned':len(calls),'total_tokens_all_planned':sum(a['total_tokens'] or 0 for a in calls),
            'reasoning_response_calls':sum(a['reasoning_chars']>0 for a in calls),
            'reasoning_tokens_reported':sum(a['reasoning_tokens'] is not None for a in calls)})
        summaries.append(row)
    contrasts={'thinking_in_direct':{'direct_on':1,'direct_off':-1},
        'thinking_in_dual':{'dual_on':1,'dual_off':-1},
        'pipeline_without_thinking':{'dual_off':1,'direct_off':-1},
        'pipeline_with_thinking':{'dual_on':1,'direct_on':-1},
        'interaction':{'dual_on':1,'dual_off':-1,'direct_on':-1,'direct_off':1}}
    effects=[]
    for name,weights in contrasts.items():
        def values(subset,exclude_policy=False):
            return [sum(w*(len(set(rb[d,a]['atomic_ids'])-{'test_91_broadcast','test_39_profession'}) if exclude_policy else rb[d,a]['atomic_coverage']) for a,w in weights.items()) for d in subset]
        vals=values(common)
        effects.append({'name':name,'weights':weights,'net_reference_count':sum(vals),'per_dialogue':bootstrap(vals),
            'without_medical':bootstrap(values([d for d in common if d!='test_526'])),
            'without_policy_sensitive':bootstrap(values(common,True)),
            'dialogue_differences':dict(zip(common,vals))})
    result={'methods':summaries,'effects':effects,'common_ids':common,'actual_calls':len(audit),
        'actual_tokens':sum(a['total_tokens'] or 0 for a in audit),'returned_models':sorted({a['returned_model'] for a in audit if a['returned_model']}),
        'review_count':len(reviews),'reference_status':'source-aware same-assistant provisional; no independent human gold',
        'interpretation':'development 2x2 comparison at 2048 thinking budget; not token-matched or held-out confirmation'}
    save(OUT/'summary.json',result);save(OUT/'dialogue_scores.json',rows)
    with (OUT/'method_scores.csv').open('w',encoding='utf-8-sig',newline='') as f:
        wr=csv.DictWriter(f,fieldnames=list(summaries[0]));wr.writeheader();wr.writerows(summaries)
    print({'methods':summaries,'effects':[{k:e[k] for k in ['name','net_reference_count','per_dialogue','without_medical']} for e in effects]})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','analyze']);a=p.parse_args()
    prepare_review() if a.action=='prepare' else calculate()
