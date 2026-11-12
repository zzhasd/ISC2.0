"""Offline asymmetric-visibility scoring and dialogue-clustered prefix analysis."""
import collections
import csv
import hashlib
import math
import random
import statistics
from pathlib import Path
from isc4_open import DATA, OUT, ROOT, read, save, sha
from isc4_review import review_key

def write_csv(path, rows):
    if not rows:return
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def maximum_match(edges):
    """One-to-one matching; duplicate paraphrases cannot recover a fact twice."""
    assigned={}
    def add(i,visited):
        for fact in edges[i]:
            if fact in visited:continue
            visited.add(fact)
            if fact not in assigned or add(assigned[fact],visited):assigned[fact]=i;return True
        return False
    for i in range(len(edges)):add(i,set())
    return set(assigned)

def bootstrap(values, seed=20261101):
    if not values:return None
    rng=random.Random(seed);n=len(values)
    samples=sorted(statistics.mean(rng.choices(values,k=n)) for _ in range(3000))
    return {'mean':statistics.mean(values),'low':samples[74],'high':samples[2924],'dialogues':n}

def main():
    ds=read(DATA/'dialogues.json');refs=read(DATA/'full_AB_reference_v2.json')
    byref={r['dialogue_id']:r['facts'] for r in refs};facts={f['id']:f for r in refs for f in r['facts']}
    reviews={r['review_id']:r for r in read(OUT/'assistant_semantic_review.json')}
    predictions=read(OUT/'predictions.json');by={(p['dialogue_id'],p['k']):p for p in predictions}
    paths=[];fullrows=[];factrows=[]
    for d in ds:
        did=d['id'];K=(len(d['turns'])+1)//2;cumulative=set()
        for k in range(1,K+1):
            available={f['id'] for f in byref[did] if f['first_A_prefix'] is not None and f['first_A_prefix']<=k}
            p=by.get((did,k));valid=p is not None
            edges=[];ground_edges=[];ground=set();partial=set();statuses=collections.Counter()
            for i,f in enumerate(p['facts'] if valid else []):
                r=reviews[review_key(did,f)];kind=r['kind'];statuses[kind]+=1
                targets=r['reference_ids'] if kind=='match' else []
                edges.append(targets)
                good=r['A_grounded'] is True and r['source_status']=='consistent'
                if kind=='match':ground_edges.append([fid for fid in targets if good and fid in available])
                else:ground_edges.append([])
                if kind in ('match','partial') and good:
                    for fid in r['reference_ids']:
                        if fid in available:ground.add(fid)
                if kind=='supported_new' and good:ground.add(r['canonical_id'])
                if kind=='partial':partial.update(r['reference_ids'])
                if k==K:
                    factrows.append({'dialogue_id':did,'claim':f['claim'],'review_id':r['review_id'],
                        'kind':kind,'source_status':r['source_status'],'A_grounded':r['A_grounded'],
                        'reference_ids':'|'.join(r['reference_ids']),'rationale':r['rationale']})
            exact=maximum_match(edges);ground_exact=maximum_match(ground_edges)
            if valid:cumulative|=ground
            row={'dialogue_id':did,'arm':d['arm'],'K':K,'k':k,'original_A_end':2*k-1,
                'valid':valid,'raw_claims':len(p['facts']) if valid else None,
                'exact_reference_matches':len(exact) if valid else None,
                'grounded_exact_reference_matches':len(ground_exact) if valid else None,
                'grounded_attribute_count_including_partial':len(ground) if valid else None,
                'cumulative_grounded_attribute_count':len(cumulative) if valid else None,
                'A_reference_available':len(available),'full_reference_count':len(byref[did]),
                'grounded_ids':'|'.join(sorted(ground)) if valid else ''}
            paths.append(row)
            if k==K:fullrows.append({**row,'partial_reference_ids':'|'.join(sorted(partial)),
                'known_contradicted_claims':sum(reviews[review_key(did,f)]['source_status']=='contradicted' for f in p['facts']) if valid else None,
                'A_ungrounded_or_uncertain_claims':sum(reviews[review_key(did,f)]['A_grounded'] is not True for f in p['facts']) if valid else None,
                'review_kinds':dict(statuses)})
    valid=[r for r in fullrows if r['valid']]
    nref=sum(r['full_reference_count'] for r in valid);nA=sum(r['A_reference_available'] for r in valid)
    nraw=sum(r['raw_claims'] for r in valid);nexact=sum(r['exact_reference_matches'] for r in valid)
    nground=sum(r['grounded_exact_reference_matches'] for r in valid)
    precision=nexact/nraw if nraw else None;recall=nexact/nref if nref else None
    # This is REFERENCE AGREEMENT, not verified real-person accuracy.
    f1=2*precision*recall/(precision+recall) if precision and recall else 0
    complete=[d['id'] for d in ds if all((d['id'],k) in by for k in range(1,(len(d['turns'])+1)//2+1))]
    pathindex={(r['dialogue_id'],r['k']):r for r in paths}
    prior=by[('shared_prior',0)]
    if prior['facts']:raise ValueError('Nonempty prior needs explicit semantic review, not forced zero')
    normalized=[]
    for fraction in [0,.25,.5,.75,1]:
        selected=[]
        for did in complete:
            K=(len(next(d for d in ds if d['id']==did)['turns'])+1)//2
            if fraction==0:selected.append({'raw_claims':0,'grounded_attribute_count_including_partial':0,
                'cumulative_grounded_attribute_count':0,'A_reference_available':0})
            else:selected.append(pathindex[(did,math.ceil(K*fraction))])
        for measure in ['raw_claims','grounded_attribute_count_including_partial','cumulative_grounded_attribute_count','A_reference_available']:
            stat=bootstrap([r[measure] for r in selected]);normalized.append({'fraction':fraction,'measure':measure,**stat})
    fixed=[]
    for K in sorted({r['K'] for r in paths}):
        ids={d['id'] for d in ds if (len(d['turns'])+1)//2==K and d['id'] in complete}
        if not ids:continue
        for k in range(1,K+1):
            for measure in ['raw_claims','grounded_attribute_count_including_partial','A_reference_available']:
                stat=bootstrap([pathindex[(did,k)][measure] for did in sorted(ids)])
                fixed.append({'fixed_K':K,'k':k,'measure':measure,**stat})
    declines=[]
    for did in complete:
        pp=sorted([r for r in paths if r['dialogue_id']==did],key=lambda r:r['k'])
        for prev,cur in zip(pp,pp[1:]):
            if cur['grounded_attribute_count_including_partial']<prev['grounded_attribute_count_including_partial']:
                declines.append({'dialogue_id':did,'from_k':prev['k'],'to_k':cur['k'],
                    'from_count':prev['grounded_attribute_count_including_partial'],'to_count':cur['grounded_attribute_count_including_partial']})
    deltas=[next(r for r in paths if r['dialogue_id']==did and r['k']==r['K'])['grounded_attribute_count_including_partial']-
            pathindex[(did,1)]['grounded_attribute_count_including_partial'] for did in complete]
    summary={'visibility':{'reference':'current assistant observes full A+B','Qwen':'A only'},
        'planned_dialogues':len(ds),'valid_full_dialogues':len(valid),'invalid_full_dialogues':[r['dialogue_id'] for r in fullrows if not r['valid']],
        'all_dialogues_full_reference_facts':sum(len(r['facts']) for r in refs),
        'valid_cohort_full_reference_facts':nref,'valid_cohort_A_supported_reference_facts':nA,
        'full_raw_claims':nraw,'exact_reference_matches':nexact,'grounded_exact_reference_matches':nground,
        'shared_prior_raw_claims':len(prior['facts']),
        'strict_reference_agreement_precision':precision,'strict_full_reference_coverage':recall,'strict_reference_agreement_F1':f1,
        'A_supported_subset_exact_recovery':nground/nA if nA else None,
        'raw_known_contradicted_claims':sum(r['known_contradicted_claims'] for r in valid),
        'raw_A_ungrounded_or_uncertain_claims':sum(r['A_ungrounded_or_uncertain_claims'] for r in valid),
        'full_review_kinds':dict(sum((collections.Counter(r['review_kinds']) for r in valid),collections.Counter())),
        'complete_prefix_paths':len(complete),'paths_with_declines':len({r['dialogue_id'] for r in declines}),
        'first_to_full_grounded_attribute_delta':bootstrap(deltas),
        'partial_match_policy':'weaker attributes separate; they do not count as exact full-reference recovery',
        'missing_policy':'Invalid generations stay missing; main coverage denominators use the same valid full-dialogue cohort',
        'limitations':['AI provisional reference and same-assistant adjudication','reference finished after partial Qwen inspection',
          'unequal model inputs; NOT a pure capability gap','32 previously observed exploratory dialogues; not all 1000 test dialogues',
          'reference A support is provisional and incomplete, not a proven information ceiling','no independent GPT prefix runs',
          'confidence is self-reported; agreement F1 is not factual accuracy','coarse and specific assertions can be statistically dependent']}
    save(OUT/'summary.json',summary);save(OUT/'prefix_analysis.json',{'normalized':normalized,'fixed_K':fixed,'declines':declines})
    write_csv(OUT/'prefix_paths.csv',paths);write_csv(OUT/'full_dialogue_scores.csv',fullrows)
    write_csv(OUT/'full_claim_review.csv',factrows);write_csv(OUT/'prefix_normalized.csv',normalized);write_csv(OUT/'prefix_fixed_K.csv',fixed)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),constrained_layout=True)
    labels={'grounded_attribute_count_including_partial':'Qwen: currently grounded attributes',
        'cumulative_grounded_attribute_count':'Qwen: cumulative discovered attributes',
        'A_reference_available':'Reference: A evidence available (not GPT inference)'}
    for measure,label in labels.items():
        rr=[r for r in normalized if r['measure']==measure]
        axes[0].plot([r['fraction'] for r in rr],[r['mean'] for r in rr],marker='o',label=label)
        if measure=='grounded_attribute_count_including_partial':axes[0].fill_between([r['fraction'] for r in rr],[r['low'] for r in rr],[r['high'] for r in rr],alpha=.15)
    axes[0].set(xlabel='Observed fraction of each A-side conversation (ceil)',ylabel='Mean attributes per dialogue',title=f'Fixed cohort: {len(complete)} complete paths; clustered 95% CI')
    axes[0].legend(fontsize=7);axes[0].grid(alpha=.2)
    arms=collections.defaultdict(list)
    for r in valid:arms[r['arm']].append(r)
    armnames=sorted(arms);width=.24
    for j,(field,label,color) in enumerate([('full_reference_count','Full A+B reference','#8796a5'),
            ('exact_reference_matches','Qwen A-only exact','#6389cf'),
            ('grounded_exact_reference_matches','Qwen grounded exact','#51a58b')]):
        values=[sum(r[field] for r in arms[arm]) for arm in armnames]
        positions=[i+(j-1)*width for i in range(len(armnames))]
        axes[1].bar(positions,values,width=width,label=label,color=color)
        for x,v in zip(positions,values):axes[1].text(x,v+.3,str(v),ha='center',fontsize=9)
    axes[1].set_xticks(range(len(armnames)),[f'{arm} (n={len(arms[arm])})' for arm in armnames])
    axes[1].legend(fontsize=8)
    axes[1].set(ylabel='Reference facts / one-to-one matches',title='Unequal visibility: recovery coverage, not model ability')
    fig.savefig(OUT/'results.png',dpi=170);plt.close(fig)
    # Hash actual final scripts separately from the preserved preparation snapshot.
    audit={'requests_sha256_unchanged':sha(read(OUT/'baseline/requests.json'))==read(DATA/'manifest.json')['request_sha256'],
        'reference_v2_sha256':sha(refs),'review_sha256':sha(list(reviews.values())),
        'scripts':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.glob('experiments/*isc4*.py')},
        'annotation_status':'source-aware provisional; no independent human review'}
    save(OUT/'audit.json',audit)
    print(summary)
if __name__=='__main__':main()
