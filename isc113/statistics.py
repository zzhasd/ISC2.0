"""Dialogue-cluster statistics and one-to-one reference recovery."""
import math
import random

def matching(edges):
    """Maximum cardinality bipartite matching; prediction IDs -> reference IDs."""
    owner={}
    def visit(p,seen):
        for r in sorted(edges[p]):
            if r in seen:continue
            seen.add(r)
            if r not in owner or visit(owner[r],seen):owner[r]=p;return True
        return False
    for p in sorted(edges):visit(p,set())
    return {p:r for r,p in owner.items()}

def ratio(a,b):return a/b if b else None

def four_metrics(rows):
    """Closed-reference factual P/R, grounded R and actual tokens per input.

    Precision counts output assertions, while both recalls count one-to-one
    reference hits. Legacy grounded-bound metrics below remain available.
    """
    counts={k:sum(r[k] for r in rows) for k in ['predictions','correct_output_assertions',
            'true_tp','true_reference','supported_tp','supported_reference','tokens']}
    return {'precision':ratio(counts['correct_output_assertions'],counts['predictions']),
            'recall':ratio(counts['true_tp'],counts['true_reference']),
            'grounded_recall':ratio(counts['supported_tp'],counts['supported_reference']),
            'mean_tokens':None if any(r.get('missing_usage_attempts',0) for r in rows) else ratio(counts['tokens'],len(rows)),
            'single_sided_inputs':len(rows),'output_assertions':counts['predictions'],
            'correct_output_assertions':counts['correct_output_assertions'],
            'recovered_reference_attributes':counts['true_tp'],'true_reference_attributes':counts['true_reference'],
            'recovered_grounded_reference_attributes':counts['supported_tp'],
            'grounded_reference_attributes':counts['supported_reference'],'tokens':counts['tokens']}

def metrics(rows):
    keys=['predictions','supported_tp','true_tp','supported_reference','e1_reference','e2_reference',
          'e1_hits','e2_hits','e12_disputed_reference','e12_disputed_hits','unsupported_correct','unresolved','valid_citations','tokens',
          'correct_output_assertions','true_reference']
    sums={k:sum(r.get(k,0) for r in rows) for k in keys}
    p=ratio(sums['supported_tp'],sums['predictions']);r=ratio(sums['supported_tp'],sums['supported_reference'])
    upper=ratio(sums['supported_tp']+sums['unresolved'],sums['predictions'])
    sums.update(precision_lower=p,precision_upper=min(1,upper) if upper is not None else None,
                precision=p if not sums['unresolved'] else None,recall=r,
                f1_lower=2*p*r/(p+r) if p is not None and r is not None and p+r else (0 if p==0 and r==0 else None),
                truth_precision_lower=ratio(sums['true_tp'],sums['predictions']),
                full_reference_recall=ratio(sums['true_tp'],sums['true_reference']),
                grounded_recall=r,
                e1_recall=ratio(sums['e1_hits'],sums['e1_reference']),
                e2_recall=ratio(sums['e2_hits'],sums['e2_reference']),
                citation_validity=ratio(sums['valid_citations'],sums['predictions']),
                abstention_rate=ratio(sum(r['predictions']==0 for r in rows),len(rows)),
                mean_tokens=ratio(sums['tokens'],len(rows)),n_direction_items=len(rows),
                n_dialogue_clusters=len({r['dialogue_id'] for r in rows}),
                zero_reference_direction_items=sum(r['supported_reference']==0 for r in rows))
    sums['failed_abstentions']=sum(bool(r.get('failed_abstention')) for r in rows)
    if sums['e2_reference']:
        sums['e2_recall_layer_uncertainty_bounds']=[
            sums['e2_hits']/(sums['e2_reference']+sums['e12_disputed_reference']-sums['e12_disputed_hits']),
            (sums['e2_hits']+sums['e12_disputed_hits'])/(sums['e2_reference']+sums['e12_disputed_hits'])]
    else:sums['e2_recall_layer_uncertainty_bounds']=[None,None]
    return sums

def quantile(xs,p):
    xs=sorted(xs)
    if not xs:return None
    x=(len(xs)-1)*p;i=int(x);return xs[i]+(xs[min(i+1,len(xs)-1)]-xs[i])*(x-i)

def cluster_bootstrap(rows,metric='recall',n=2000,seed=113):
    by={}
    for r in rows:by.setdefault(r['dialogue_id'],[]).append(r)
    ids=sorted(by);rng=random.Random(seed);draws=[]
    if not ids:return {'estimate':None,'ci95':[None,None],'clusters':0}
    for _ in range(n):
        sampled=[r for _ in ids for r in by[rng.choice(ids)]]
        v=metrics(sampled).get(metric)
        if v is not None:draws.append(v)
    return {'estimate':metrics(rows).get(metric),'ci95':[quantile(draws,.025),quantile(draws,.975)],
            'clusters':len(ids),'resamples':n,'valid_resamples':len(draws)}

def paired_bootstrap(a,b,metric='recall',n=2000,seed=113):
    aa={(r['dialogue_id'],r['direction']):r for r in a};bb={(r['dialogue_id'],r['direction']):r for r in b}
    shared=aa.keys() & bb.keys();by={}
    for k in shared:by.setdefault(k[0],[]).append(k)
    ids=sorted(by);rng=random.Random(seed);draws=[]
    for _ in range(n):
        ks=[k for _ in ids for k in by[rng.choice(ids)]]
        va=metrics([aa[k] for k in ks]).get(metric);vb=metrics([bb[k] for k in ks]).get(metric)
        if va is not None and vb is not None:draws.append(va-vb)
    return {'delta_a_minus_b':metrics([aa[k] for k in shared]).get(metric)-metrics([bb[k] for k in shared]).get(metric)
            if shared and metrics([aa[k] for k in shared]).get(metric) is not None and metrics([bb[k] for k in shared]).get(metric) is not None else None,
            'ci95':[quantile(draws,.025),quantile(draws,.975)],'shared_direction_items':len(shared),'clusters':len(ids),'resamples':n}

def holm(pvalues):
    ordered=sorted(pvalues,key=pvalues.get);n=len(ordered);result={};previous=0
    for i,k in enumerate(ordered):
        previous=max(previous,min(1,(n-i)*pvalues[k]));result[k]=previous
    return result
