"""Offline evaluation. Missing/invalid responses never become unknown predictions."""
import collections
import csv
import json
import math
import platform
import re
from pathlib import Path
import numpy as np
from scipy.stats import beta, spearmanr
from isc3_common import *
from isc3_prepare import read_content

THRESHOLDS=[0,.5,.7,.8,.9,.95,.99,1,1.1]
METHODS=['direct','direct_review','graph','recover','open','recon_one','recon_multi','recon_one_v2','recon_multi_v2']

def write_csv(path, rows):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if not rows:path.write_text('',encoding='utf-8');return
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fields);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})

def parse():
    cases={c['case_id']:c for c in read(DATA/'cases.json')};rows=[];errors=[];unmatched=[]
    for stage in ['initial','dependent','reconstruction_v2_extract']:
        binding_path=DATA/f'bindings_{stage}.json'
        if not binding_path.exists():continue
        plan={t['task_id']:t for t in read(OUT/stage/'requests.json')};raw=raw_index(OUT/stage)
        cache={}
        for b in read(binding_path):
            if b['method'] not in METHODS:continue
            c=cases[b['case_id']];t=plan[b['task_id']]
            try:
                if t['task_id'] not in cache:cache[t['task_id']]=decode(raw[t['task_id']])
                obj=cache[t['task_id']]
                # Normalization has no A input; the source binding defines allowed citations.
                visible=[v for v in c['visible_A'] if v['turn'] in b['visible_turns']]
                if b['condition'] in ('chinese','template_ood','holder_A'):
                    source=read_content(t)
                    visible=source['visible_A']
                facts=validate_facts(obj,c['catalogue'],visible)
                if b['method']=='open':
                    source=read_content(t);claims=source['claims']
                    for f in facts:
                        ix=f.get('source_claim_indices',[])
                        if not isinstance(ix,list) or any(type(i) is not int or not 0<=i<len(claims) for i in ix):raise ValueError('Invalid open mapping indices')
                        if f['label']!='unknown' and not ix:raise ValueError('Unattributed open assertion')
                        if f['label']!='unknown':
                            if f['confidence']>max(claims[i]['confidence'] for i in ix)+1e-6:raise ValueError('Normalization inflated confidence')
                            if not set(f['evidence_turns']).issubset({j for i in ix for j in claims[i]['evidence_turns']}):raise ValueError('Normalization invented evidence')
                    declared=obj.get('unmatched_claim_indices',[])
                    for ix in declared:
                        if type(ix) is not int or not 0<=ix<len(claims):raise ValueError('Invalid unmatched index')
                    used={i for f in facts if f['label']!='unknown' for i in f.get('source_claim_indices',[])}
                    for ix in range(len(claims)):
                        if ix not in used:
                            unmatched.append({'case_id':c['case_id'],'dataset':c['dataset'],'claim_index':ix,
                                              'normalizer_reported_unmatched':ix in declared,**claims[ix]})
                gold={f['id']:f for f in c['facts']}
                current=[]
                for f in facts:
                    g=gold[f['id']];visible_set={v['turn'] for v in visible}
                    support_available=(g['a_support']!='unknown' and bool(g['support_turns']) and set(g['support_turns']).issubset(visible_set))
                    # Other surface/language variants retain full semantic support but use other turn layouts.
                    if b['condition'] in ('chinese','template_ood','holder_A'):support_available=g['a_support']!='unknown'
                    current.append({'case_id':c['case_id'],'dataset':c['dataset'],'group':c['group'],
                        'cluster':c['template_family'] if c['dataset']=='controlled' else c['group'],
                        'domain':g['domain'],'mechanism':c.get('mechanism','natural'),'split':c['split'],
                        'arm':c.get('arm','structured'),
                        'method':b['method'],'condition':b['condition'],'attribute':f['id'],
                        'truth':g['truth'],'a_support':g['a_support'],'support_available':support_available,
                        'support_turns':g['support_turns'],'prediction':f['label'],'confidence':f['confidence'],
                        'evidence_turns':f['evidence_turns'],'evidence_complete':bool(g['support_turns']) and set(g['support_turns']).issubset(f['evidence_turns']),
                        'visible_turns':[v['turn'] for v in visible],'total_A_turns':len(c['visible_A']),
                        'sensitive_annotation':g.get('sensitive_to_annotation_policy',False),'task_id':t['task_id'],
                        'source_task_id':b.get('source_task_id')})
                rows.extend(current)
            except (ValueError,TypeError,KeyError) as exc:
                errors.append({**b,'error_kind':'missing_response' if t['task_id'] not in raw else 'invalid_response','error':str(exc)})
    save(OUT/'predictions.json',rows);write_csv(OUT/'predictions.csv',rows)
    save(OUT/'validation_errors.json',errors);write_csv(OUT/'unmatched_open_facts.csv',unmatched)
    return cases,rows,errors

def asserted(r,tau):return r['prediction']!='unknown' and r['confidence']>=tau

def metric(rows,tau=0,with_ci=False):
    selected=[r for r in rows if asserted(r,tau)];n=len(selected)
    correct=[r for r in selected if r['prediction']==r['truth'] and r['truth']!='unknown']
    wrong=[r for r in selected if r['truth']!='unknown' and r['prediction']!=r['truth']]
    unverified=[r for r in selected if r['truth']=='unknown']
    grounded=[r for r in correct if r['support_available'] and r['prediction']==r['a_support'] and r['evidence_turns']]
    unsupported=[r for r in selected if not (r['support_available'] and r['prediction']==r['a_support'] and r['evidence_turns'])]
    pos=[r for r in correct if r['prediction']=='true'];gp=[r for r in grounded if r['prediction']=='true']
    num_cases=len({r['case_id'] for r in rows});num_true=sum(r['truth']=='true' for r in rows)
    result={'views':num_cases,'decisions':len(rows),'assertions':n,'correct_definite':len(correct),
            'true_positive_recoveries':len(pos),'grounded_true_recoveries':len(gp),
            'grounded_definite_recoveries':len(grounded),'known_truth_errors':len(wrong),
            'grounded_true_with_complete_prelabelled_citations':sum(r['evidence_complete'] for r in gp),
            'grounded_definite_with_complete_prelabelled_citations':sum(r['evidence_complete'] for r in grounded),
            'unverified_assertions':len(unverified),'unsupported_assertions':len(unsupported),
            'known_error_fraction':len(wrong)/n if n else None,
            'nonverified_fraction':(len(wrong)+len(unverified))/n if n else None,
            'unsupported_fraction':len(unsupported)/n if n else None,
            'selective_coverage':n/len(rows) if rows else None,
            'true_recovery_rate':len(pos)/num_true if num_true else None,
            'true_facts_per_100_views':100*len(pos)/num_cases if num_cases else None,
            'grounded_facts_per_100_views':100*len(gp)/num_cases if num_cases else None,
            'known_positive_truths':num_true,'threshold':tau}
    if with_ci and rows:
        result['true_recovery_cluster_ci']=ratio_ci(rows,lambda r:int(asserted(r,tau) and r['prediction']=='true' and r['truth']=='true'),lambda r:int(r['truth']=='true'))
        result['true_per_100_views_cluster_ci']=view_ci(rows,lambda r:int(asserted(r,tau) and r['prediction']=='true' and r['truth']=='true'))
        result['grounded_per_100_views_cluster_ci']=view_ci(rows,lambda r:int(asserted(r,tau) and r['prediction']=='true' and r['truth']=='true' and r['support_available'] and r['a_support']=='true' and bool(r['evidence_turns'])))
        result['nonverified_cluster_ci']=ratio_ci(rows,lambda r:int(asserted(r,tau) and r['prediction']!=r['truth']),lambda r:int(asserted(r,tau)))
    return result

def ratio_ci(rows,num,den,draws=2000):
    groups=collections.defaultdict(lambda:[0,0])
    for r in rows:
        groups[r['cluster']][0]+=num(r);groups[r['cluster']][1]+=den(r)
    values=np.array(list(groups.values()),dtype=float)
    if not len(values) or values[:,1].sum()==0:return None
    rng=np.random.default_rng(SEED);ix=rng.integers(0,len(values),(draws,len(values)))
    boot=values[ix].sum(axis=1);valid=boot[:,1]>0;scores=boot[valid,0]/boot[valid,1]
    return {'estimate':float(values[:,0].sum()/values[:,1].sum()),'ci95':np.quantile(scores,[.025,.975]).tolist(),
            'clusters':len(values),'draws':draws,'zero_denominator_draws':int((~valid).sum())}

def view_ci(rows,value):
    first={}
    for r in rows:first.setdefault(r['case_id'],r)
    decisions=collections.Counter(r['case_id'] for r in rows)
    return ratio_ci(rows,lambda r:100*value(r),lambda r:1/decisions[r['case_id']])

def calibration(rows,delta):
    candidates=[]
    for tau in THRESHOLDS:
        m=metric(rows,tau);ci=ratio_ci(rows,lambda r:int(asserted(r,tau) and r['prediction']!=r['truth']),lambda r:int(asserted(r,tau)),draws=2000)
        upper=ci['ci95'][1] if ci else 0
        # Also expose a conservative cluster-any-error bound: a different estimand.
        active=collections.defaultdict(list)
        for r in rows:
            if asserted(r,tau):active[r['cluster']].append(r)
        bad=sum(any(r['prediction']!=r['truth'] for r in rs) for rs in active.values());total=len(active)
        any_upper=float(beta.ppf(.95,bad+1,total-bad)) if total and bad<total else (1 if total else None)
        candidates.append({**m,'bootstrap_upper_nonverified':upper,'cluster_any_error_upper95':any_upper,
                           'active_clusters':total,'error_clusters':bad,'eligible':upper<=delta})
    eligible=[c for c in candidates if c['eligible']]
    best=max(eligible,key=lambda c:(c['grounded_definite_recoveries'],-c['bootstrap_upper_nonverified'],c['threshold']))
    return {'delta':delta,'threshold':best['threshold'],'selected_calibration':best,'grid':candidates,
            'caution':'Exploratory cluster-bootstrap selection; no finite-sample or population FDR guarantee. Zero-error bootstrap intervals can be degenerate; cluster-any-error upper bound is a separate sensitivity estimand.'}

def e1(rows):
    result={};curves=[];operating=[]
    cases=read(DATA/'cases.json')
    for dataset in ['controlled','natural']:
        result[dataset]={}
        planned=[c for c in cases if c['dataset']==dataset and c['split']=='test']
        planned_decisions=sum(len(c['facts']) for c in planned)
        planned_positives=sum(f['truth']=='true' for c in planned for f in c['facts'])
        def attach_planned(m):
            return {**m,'planned_test_views':len(planned),'planned_test_decisions':planned_decisions,
                    'valid_view_fraction':m['views']/len(planned),
                    'grounded_facts_per_100_planned_views':100*m['grounded_true_recoveries']/len(planned),
                    'true_facts_per_100_planned_views':100*m['true_positive_recoveries']/len(planned),
                    'coverage_over_all_planned_decisions':m['assertions']/planned_decisions,
                    'true_recovery_over_all_planned_positives':m['true_positive_recoveries']/planned_positives if planned_positives else None}
        for method in METHODS:
            subset=[r for r in rows if r['dataset']==dataset and r['method']==method and r['condition']=='full']
            cal=[r for r in subset if r['split']=='calibration'];test=[r for r in subset if r['split']=='test']
            if not subset:continue
            result[dataset][method]={'calibration_views':len({r['case_id'] for r in cal}),
                'test_views':len({r['case_id'] for r in test}),'unthresholded_test':attach_planned(metric(test,0,True)),'operating_points':{}}
            for tau in THRESHOLDS:curves.append({'dataset':dataset,'method':method,**attach_planned(metric(test,tau))})
            for delta in [.05,.1,.2]:
                selection=calibration(cal,delta);tau=selection['threshold'];m=attach_planned(metric(test,tau,True))
                result[dataset][method]['operating_points'][str(delta)]={'selection':selection,'test':m}
                operating.append({'dataset':dataset,'method':method,'target_delta':delta,'calibration_views':len({r['case_id'] for r in cal}),**m})
    save(OUT/'E1.json',result);write_csv(OUT/'E1_risk_curves.csv',curves);write_csv(OUT/'E1_operating_points.csv',operating)
    return result

def paired(rows,a,b,condition_a='full',condition_b='full',tau_a=0,tau_b=0):
    aa={(r['case_id'],r['attribute']):r for r in rows if r['method']==a and r['condition']==condition_a}
    bb={(r['case_id'],r['attribute']):r for r in rows if r['method']==b and r['condition']==condition_b}
    # Only complete catalogue views on both sides enter paired comparisons.
    keys=sorted(set(aa)&set(bb));out=[]
    for key in keys:
        x,y=aa[key],bb[key];p=asserted(x,tau_a);q=asserted(y,tau_b)
        grounded=lambda r,active:active and r['prediction']=='true' and r['truth']=='true' and r['support_available'] and r['a_support']=='true' and bool(r['evidence_turns'])
        unsupported=lambda r,active:active and not (r['support_available'] and r['prediction']==r['a_support'] and bool(r['evidence_turns']))
        out.append({**x,'positive_delta':int(q and y['prediction']=='true' and y['truth']=='true')-int(p and x['prediction']=='true' and x['truth']=='true'),
                    'grounded_delta':int(grounded(y,q))-int(grounded(x,p)),
                    'unsupported_delta':int(unsupported(y,q))-int(unsupported(x,p)),
                    'error_delta':int(q and y['truth']!='unknown' and y['prediction']!=y['truth'])-int(p and x['truth']!='unknown' and x['prediction']!=x['truth'])})
    return {'paired_views':len({r['case_id'] for r in out}),'paired_decisions':len(out),
            **{name+'_per_100_views':view_ci(out,lambda r,n=name:r[n]) for name in ['positive_delta','grounded_delta','unsupported_delta','error_delta']}}

def e2(rows):
    result={}
    for dataset in ['controlled','natural']:
        current=[r for r in rows if r['dataset']==dataset and r['split']=='test']
        result[dataset]={'methods':{m:metric([r for r in current if r['method']==m and r['condition']=='full'],0,True) for m in ['direct','direct_review','recon_one','recon_multi','open']},
                         'comparisons':{m+'_minus_direct':paired(current,'direct',m) for m in ['recon_one','recon_multi','recon_one_v2','recon_multi_v2','open']}}
        for method in ['recon_one_v2','recon_multi_v2']:
            result[dataset]['methods'][method]=metric([r for r in current if r['method']==method and r['condition']=='full'],0,True)
        for method in ['recon_one','recon_multi','recon_one_v2','recon_multi_v2','open']:
            result[dataset]['comparisons'][method+'_minus_direct_review']=paired(current,'direct_review',method)
    save(OUT/'E2.json',result);return result

def positive_key(r,tau=0,grounded=False):
    return asserted(r,tau) and r['prediction']=='true' and r['truth']=='true' and (not grounded or (r['support_available'] and r['a_support']=='true' and bool(r['evidence_turns'])))

def accumulation(cases,rows,e1_result):
    index=collections.defaultdict(list)
    for r in rows:
        if r['method'] in ('direct','recover') and (r['condition']=='full' or r['condition'].startswith('prefix_')):
            index[(r['case_id'],r['method'],r['condition'])].append(r)
    normalized=[];absolute=[];paths=[];summary={};references=[];fixed_k=[]
    for dataset in ['controlled','natural']:
        cohort=[c for c in cases.values() if c['dataset']==dataset and c['split']=='test']
        summary[dataset]={}
        common_complete=[c for c in cohort if all(index.get((c['case_id'],method,'full' if k==len(c['visible_A']) else f'prefix_{k}'))
                         for method in ['direct','recover'] for k in range(len(c['visible_A'])+1))]
        for fraction in [0,.25,.5,.75,1]:
            supported=0;truths=0
            for c in common_complete:
                k=math.ceil(len(c['visible_A'])*fraction)
                truths+=sum(f['truth']=='true' for f in c['facts'])
                supported+=sum(f['truth']=='true' and f['a_support']=='true' and bool(f['support_turns']) and set(f['support_turns']).issubset(range(1,k+1)) for f in c['facts'])
            references.append({'dataset':dataset,'fraction':fraction,'views':len(common_complete),
                'annotation_supported_true_per_100_views':100*supported/len(common_complete) if common_complete else None,
                'full_world_known_true_per_100_views':100*truths/len(common_complete) if common_complete else None,
                'interpretation':'Author-coded sufficient-evidence reference, not proven recoverability upper bound; natural truth is AI provisional.'})
        for method in ['direct','recover']:
            tau=e1_result.get(dataset,{}).get(method,{}).get('operating_points',{}).get('0.1',{}).get('selection',{}).get('threshold',1.1)
            for threshold_name,threshold in [('nominal',0),('calibrated_delta_0.1',tau)]:
                for fraction in [0,.25,.5,.75,1]:
                    selected=[];missing=[c['case_id'] for c in cohort if c not in common_complete]
                    for c in common_complete:
                        n=len(c['visible_A']);k=math.ceil(n*fraction);cond='full' if k==n else f'prefix_{k}'
                        rs=index.get((c['case_id'],method,cond),[])
                        if rs:selected.extend(rs)
                        else:raise AssertionError('A common complete path cannot have a missing point')
                    normalized.append({'dataset':dataset,'method':method,'operating_point':threshold_name,'fraction':fraction,
                                       'expected_views':len(cohort),'missing_views':len(missing),**metric(selected,threshold,True)})
            for k in range(max(len(c['visible_A']) for c in cohort)+1):
                eligible=[c for c in cohort if len(c['visible_A'])>=k];selected=[]
                for c in eligible:
                    cond='full' if k==len(c['visible_A']) else f'prefix_{k}'
                    selected.extend(index.get((c['case_id'],method,cond),[]))
                absolute.append({'dataset':dataset,'method':method,'k':k,'eligible_views':len(eligible),**metric(selected)})
            for endpoint in [2,4,8]:
                fixed=[c for c in common_complete if len(c['visible_A'])>=endpoint]
                if not fixed:continue
                for k in range(endpoint+1):
                    selected=[]
                    for c in fixed:
                        cond='full' if k==len(c['visible_A']) else f'prefix_{k}'
                        selected.extend(index[(c['case_id'],method,cond)])
                    fixed_k.append({'dataset':dataset,'method':method,'cohort_minimum_A_turns':endpoint,'k':k,**metric(selected,0,True)})
            complete=[];gains=[];losses=[];nonmonotonic=0
            for c in cohort:
                chain=[]
                for k in range(len(c['visible_A'])+1):
                    cond='full' if k==len(c['visible_A']) else f'prefix_{k}'
                    rs=index.get((c['case_id'],method,cond))
                    if rs is None:break
                    m=metric(rs)
                    chain.append(m['true_positive_recoveries'])
                    paths.append({'case_id':c['case_id'],'dataset':dataset,'method':method,'k':k,
                                  'n':len(c['visible_A']),'true_recovered':m['true_positive_recoveries'],
                                  'grounded_recovered':m['grounded_true_recoveries'],'unsupported':m['unsupported_assertions'],
                                  'correct_definite':m['correct_definite']})
                if len(chain)!=len(c['visible_A'])+1:continue
                complete.append(c);diffs=np.diff(chain);gains.extend(int(x) for x in diffs if x>0);losses.extend(int(-x) for x in diffs if x<0)
                nonmonotonic+=int(any(x<0 for x in diffs))
            dsrows=[r for r in rows if r['dataset']==dataset and r['split']=='test']
            summary[dataset][method]={'complete_prefix_paths':len(complete),'expected_paths':len(cohort),
                'paths_with_declines':nonmonotonic,'positive_step_fact_gains':sum(gains),'negative_step_fact_losses':sum(losses),
                'full_minus_empty':paired(dsrows,method,method,'prefix_0','full'),
                'calibrated_threshold':tau,'absolute_k_caveat':'Eligible cohort changes with k; do not interpret as a fixed-cohort causal growth curve.'}
            summary[dataset][method]['common_complete_curve_views']=len(common_complete)
    write_csv(OUT/'turn_accumulation_normalized.csv',normalized);write_csv(OUT/'turn_accumulation_absolute.csv',absolute)
    write_csv(OUT/'turn_accumulation_paths.csv',paths);save(OUT/'turn_accumulation.json',summary)
    write_csv(OUT/'turn_accumulation_references.csv',references)
    write_csv(OUT/'turn_accumulation_fixed_k_cohorts.csv',fixed_k)
    return normalized,summary

def e3(rows):
    result={};details=[]
    for method in ['direct','recover']:
        base=[r for r in rows if r['dataset']=='controlled' and r['method']==method]
        singles=collections.defaultdict(list)
        for r in base:
            if r['condition'].startswith('single_'):singles[(r['case_id'],r['attribute'])].append(r)
        full=[r for r in base if r['condition']=='full' and len(singles.get((r['case_id'],r['attribute']),[]))==r['total_A_turns']]
        synergistic=[];lost=[]
        for r in full:
            ss=singles[(r['case_id'],r['attribute'])]
            # A correct full positive absent from every independently queried singleton.
            synergy=positive_key(r) and not any(positive_key(s) for s in ss)
            union=any(positive_key(s) for s in ss)
            details.append({'case_id':r['case_id'],'cluster':r['cluster'],'method':method,'attribute':r['attribute'],
                            'full_correct_positive':positive_key(r),'any_singleton_correct_positive':union,
                            'joint_only_positive':synergy,'full_grounded':positive_key(r,grounded=True)})
            synergistic.append({**r,'synergy':int(synergy),'union_delta':int(positive_key(r))-int(union)})
        deletion={}
        for cond in sorted({r['condition'] for r in base if r['condition'].startswith('delete_')}):
            relevant={r['case_id'] for r in base if r['condition']==cond}
            ds=[r for r in base if r['case_id'] in relevant]
            deletion[cond]=paired(ds,method,method,'full',cond)
        random_cases={r['case_id'] for r in base if r['condition']=='random_half'}
        half=[]
        for r in base:
            k=max(1,r['total_A_turns']//2)
            if r['case_id'] in random_cases and r['condition']==f'prefix_{k}':half.append({**r,'condition':'ordered_half'})
        result[method]={'views_with_singleton_controls':len({r['case_id'] for r in full}),
            'joint_only_correct_positive_facts':sum(r['synergy'] for r in synergistic),
            'joint_only_per_100_views':view_ci(synergistic,lambda r:r['synergy']),
            'full_minus_union_singletons_per_100_views':view_ci(synergistic,lambda r:r['union_delta']),
            'deletion_comparisons':deletion,
            'random_half_minus_ordered_half':paired(base+half,method,method,'ordered_half','random_half'),
            'caution':'Correctness against full-world truth is separate from available evidence. A union of singleton outputs may include unsupported lucky guesses. Joint-only counts are not proof of a new inference mechanism.'}
    save(OUT/'E3.json',result);write_csv(OUT/'E3_joint_only_facts.csv',details);return result

def e4(rows):
    result={}
    for method in ['direct','recover']:
        full=[r for r in rows if r['dataset']=='controlled' and r['method']==method and r['condition']=='full' and r['attribute']=='property_p']
        pairs=collections.defaultdict(list)
        for r in full:pairs[r['group']].append(r)
        complete=[p for p in pairs.values() if len(p)==2]
        bymechanism={}
        for m in sorted({r['mechanism'] for r in full}):
            ps=[p for p in complete if p[0]['mechanism']==m]
            bymechanism[m]={'pairs':len(ps),'both_correct':sum(all(r['prediction']==r['truth'] for r in p) for p in ps),
                            'prediction_flips':sum(p[0]['prediction']!=p[1]['prediction'] for p in ps)}
        private=[r for r in rows if r['dataset']=='controlled' and r['method']==method and r['condition']=='full' and r['attribute']=='iguana']
        unknown=[r for r in rows if r['dataset']=='controlled' and r['method']==method and r['condition']=='full' and r['attribute']=='sailboat']
        tests=[r for r in rows if r['dataset']=='controlled' and r['method']==method and r['split']=='test']
        holder_pairs=collections.defaultdict(list)
        for r in tests:
            if r['condition']=='holder_A' and r['attribute']=='property_p':holder_pairs[r['group']].append(r)
        hp=[p for p in holder_pairs.values() if len(p)==2]
        result[method]={'opposite_holder_pairs':len(complete),'both_correct_pairs':sum(all(r['prediction']==r['truth'] for r in p) for p in complete),
            'by_mechanism':bymechanism,'holder_A_minus_Casey':paired(tests,method,method,'full','holder_A'),
            'opposite_A_vs_B_holder_pairs':{'pairs':len(hp),'both_correct':sum(all(r['prediction']==r['truth'] for r in p) for p in hp),
                'prediction_flips':sum(p[0]['prediction']!=p[1]['prediction'] for p in hp)},
            'hidden_true_or_false_iguana':{'views':len(private),'unknown':sum(r['prediction']=='unknown' for r in private),
                'unsupported_definite_guesses':sum(r['prediction']!='unknown' for r in private),
                'counter_worlds_use_identical_A_and_same_request':True,
                'logical_limit':'Any fixed true/false guess fails one of the two equally weighted opposite private worlds; only unknown is evidence-correct.'},
            'unspecified_sailboat':{'views':len(unknown),'unknown':sum(r['prediction']=='unknown' for r in unknown),
                                   'definite_claims':sum(r['prediction']!='unknown' for r in unknown)}}
    save(OUT/'E4.json',result);return result

def e5(rows,e1_result):
    quality=surface_quality_audit()
    flagged_groups=set(quality['flagged_groups'])
    result={'independent_model_family':'NOT RUN: user specified qwen3.8-flash only',
            'model':MODEL,'caution':'Prompted frozen model, no task training. Test-only variants evaluate operating-threshold transfer, not a trained model zero-shot holdout claim.',
            'methods':{},'surface_quality':quality}
    for method in ['direct','recover']:
        base=[r for r in rows if r['method']==method and r['dataset']=='controlled' and r['split']=='test']
        tau=e1_result['controlled'].get(method,{}).get('operating_points',{}).get('0.1',{}).get('selection',{}).get('threshold',1.1)
        natural=[r for r in rows if r['method']==method and r['dataset']=='natural' and r['split']=='test' and r['condition']=='full']
        domains={d:metric([r for r in base if r['domain']==d and r['condition']=='full'],0,True) for d in sorted({r['domain'] for r in base})}
        result['methods'][method]={'controlled_calibrated_threshold':tau,'domains':domains,
            'conditions':{cond:{'nominal':metric([r for r in base if r['condition']==cond],0,True),
                                'transferred_threshold':metric([r for r in base if r['condition']==cond],tau,True),
                                'paired_minus_base':paired(base,method,method,'full',cond)}
                          for cond in ['full','template_ood','chinese','holder_A']},
            'natural_transfer':{'nominal':metric(natural,0,True),'controlled_threshold':metric(natural,tau,True)}}
        clean=[r for r in base if r['group'] not in flagged_groups]
        result['methods'][method]['surface_issue_excluded_sensitivity']={
            'rule':'Exclude an entire opposite-holder group if any English variant contains the documented surface pronoun/agreement pattern; no gold/threshold retuning.',
            'conditions':{cond:metric([r for r in clean if r['condition']==cond],0,True) for cond in ['full','template_ood','chinese','holder_A']}}
    result['historical_model_comparison']=historical_model_comparison()
    save(OUT/'E5.json',result);return result

def surface_quality_audit():
    cases={c['case_id']:c for c in read(DATA/'cases.json')}
    tasks={t['task_id']:t for t in read(OUT/'initial/requests.json')};flags=[]
    patterns=[('object_me_in_subject_position',re.compile(r'\bme\s+(?:would|is|was|has)\b|\bme,\s+rather than',re.I)),
              ('you_is_agreement',re.compile(r'\byou,\s+rather than[^.]{0,60},\s+is\b',re.I))]
    for b in read(DATA/'bindings_initial.json'):
        c=cases[b['case_id']]
        if c['dataset']!='controlled' or c['split']!='test' or b['method']!='direct' or b['condition'] not in ('full','holder_A','template_ood','chinese'):continue
        for v in read_content(tasks[b['task_id']])['visible_A']:
            for name,pattern in patterns:
                if pattern.search(v['text']):flags.append({'case_id':c['case_id'],'group':c['group'],'condition':b['condition'],'turn':v['turn'],'issue':name,'text':v['text']})
    write_csv(OUT/'surface_quality_flags.csv',flags)
    return {'flagged_turns':len(flags),'flagged_cases':len({f['case_id'] for f in flags}),
            'flagged_groups':sorted({f['group'] for f in flags}),
            'caution':'Conservative hand-coded grammar/pronoun flags, not exhaustive human naturalness ratings. Primary frozen data preserved; secondary sensitivity excludes whole paired groups without reading outcomes.'}

def historical_model_comparison():
    """Reuse exact-prompt historical A-only reruns; never invent probabilities."""
    cases={c['case_id']:c for c in read(DATA/'cases.json') if c['dataset']=='natural'}
    rows=[]
    sources=[('qwen-plus',ROOT/'results/stage2/predictions.json'),
             ('qwen3.8-flash',ROOT/'results/qwen38/stage2/predictions.json')]
    for model,path in sources:
        for r in read(path):
            if r['condition']!='a_only' or r['view_id'] not in cases:continue
            c=cases[r['view_id']];g=next(f for f in c['facts'] if f['id']==r['attribute'])
            rows.append({'case_id':c['case_id'],'attribute':r['attribute'],'cluster':c['group'],
                'split':c['split'],'method':model,'condition':'full','truth':r['truth'],
                'prediction':r['prediction'],'confidence':1,
                'a_support':g['a_support'],'support_available':g['a_support']!='unknown',
                'evidence_turns':r['model_evidence_turns'],
                'evidence_complete':bool(g['support_turns']) and set(g['support_turns']).issubset(r['model_evidence_turns'])})
    old={(t['dialogue_id'],t['target_source_speaker']):t for t in read(ROOT/'results/stage2/requests.json') if t['condition']=='a_only'}
    new={(t['dialogue_id'],t['target_source_speaker']):t for t in read(ROOT/'results/qwen38/stage2/requests.json') if t['condition']=='a_only'}
    same=0
    for key in set(old)&set(new):
        a=dict(old[key]['payload']);b=dict(new[key]['payload']);a.pop('model');b.pop('model')
        same+=a==b
    result={'exact_payload_pairs_ignoring_model':same,'available_prompt_pairs':len(set(old)&set(new)),
        'source':'Preserved ISC2 stage-2 runs; new ISC3 methods/prompts are different. No new qwen-plus calls.',
        'probability_note':'Historical catalogue responses contain no confidence probabilities; metrics here are unthresholded only. Internal confidence=1 is an inclusion marker, never a calibration estimate.',
        'family_independence':False,'cohorts':{}}
    for scope in ['all_64_views','current_test_only']:
        rs=rows if scope=='all_64_views' else [r for r in rows if r['split']=='test']
        result['cohorts'][scope]={'models':{m:metric([r for r in rs if r['method']==m],0,True) for m,_ in sources},
                                 'qwen38_minus_plus':paired(rs,'qwen-plus','qwen3.8-flash')}
    return result

def audit(cases,rows,errors):
    manifest=read(DATA/'manifest_initial.json');input_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in manifest['inputs'].items()}
    stages={};tokens=0;attempts=0;requestids=set();http=collections.Counter();models=collections.Counter();finish=collections.Counter()
    for stage in ['initial','dependent','reconstruction_v2_generate','reconstruction_v2_extract']:
        path=OUT/stage/'requests.json'
        if not path.exists():continue
        plan=read(path);raw=raw_index(OUT/stage);rs=[]
        rawpath=OUT/stage/'api_raw.jsonl'
        if rawpath.exists():rs=[json.loads(x) for x in rawpath.read_text(encoding='utf-8').splitlines()]
        stages[stage]={'planned':len(plan),'successful_http_tasks':len(raw),'missing_http_tasks':len([t for t in plan if t['task_id'] not in raw]),
                       'attempts':len(rs),'tokens':sum(r.get('body',{}).get('usage',{}).get('total_tokens',0) for r in rs)}
        tokens+=stages[stage]['tokens'];attempts+=len(rs)
        for r in rs:
            http[str(r.get('http_status','transport_error'))]+=1
            if r.get('http_status')==200:
                models[r['body'].get('model','missing')]+=1
                for ch in r['body'].get('choices',[]):finish[ch.get('finish_reason','missing')]+=1
        for t in plan:
            if digest(t['payload'])!=t['request_sha256']:raise ValueError('Payload hash mismatch')
            if t['payload']['model']!=MODEL:raise ValueError('Unauthorized model change')
            public=json.dumps(t['payload'],ensure_ascii=False)
            if 'sk-ws-' in public or 'Bearer ' in public:raise ValueError('Potential secret in public request')
        requestids.update(t['task_id'] for t in plan)
    result={'input_hashes_unchanged':input_hashes,'protocol_unchanged':hashlib.sha256((ROOT/'ISC3_PROTOCOL.md').read_bytes()).hexdigest()==manifest['protocol_sha256'],
            'calling_script_hashes_unchanged':{name:hashlib.sha256((ROOT/'experiments'/name).read_bytes()).hexdigest()==h for name,h in manifest['scripts'].items()},
            'case_gold_sha256_unchanged':digest(list(cases.values()))==manifest['case_sha256'],
            'stages':stages,'recorded_tokens':tokens,'recorded_attempts':attempts,'http_status':dict(http),
            'returned_models':dict(models),'finish_reasons':dict(finish),'validation_error_bindings':len(errors),
            'validation_error_kinds':dict(collections.Counter(e['error_kind'] for e in errors)),
            'validated_prediction_rows':len(rows),'python':platform.python_version(),
            'dependent_source_error_bindings':len(read(OUT/'dependent/source_errors.json')) if (OUT/'dependent/source_errors.json').exists() else None,
            'v2_reconstruction_source_errors':len(read(OUT/'reconstruction_v2_extract/source_errors.json')) if (OUT/'reconstruction_v2_extract/source_errors.json').exists() else None,
            'within_protocol_recorded_attempt_limit':attempts<=6000,
            'within_protocol_recorded_token_limit':tokens<=8_000_000,
            'statistical_unit':'natural dialogue / controlled mechanism × surface template',
            'natural_gold':'AI provisional, not independent human or real-person truth',
            'notes':['All original inputs preserved. Full-world and gold fields are outside request payloads.',
                     'One unique prior output can bind to several worlds; bindings are not independent calls.',
                     'Recorded tokens are not a currency bill; failed server work can have unknown cost.',
                     'No model-family independence, trained SGCI, independent human adjudication or open-world recall gold.']}
    result['dependent_payload_boundary']=verify_dependent_boundary()
    result['reconstruction_v2_payload_boundary']=verify_v2_boundary()
    vp=DATA/'manifest_reconstruction_v2.json'
    if vp.exists():
        vm=read(vp)
        result['v2_protocol_hash_unchanged']=hashlib.sha256((ROOT/'ISC3_RECONSTRUCTION_V2_PROTOCOL.md').read_bytes()).hexdigest()==vm['protocol_sha256']
        result['v2_calling_script_hash_unchanged']=hashlib.sha256((ROOT/'experiments/isc3_reconstruction_v2.py').read_bytes()).hexdigest()==vm['script_sha256']
    save(OUT/'audit.json',result);return result

def verify_dependent_boundary():
    path=OUT/'dependent/requests.json'
    if not path.exists():return {'checked':0,'all_sources_match':None}
    source_plan={t['task_id']:t for t in read(OUT/'initial/requests.json')}
    source_raw=raw_index(OUT/'initial');cases={c['case_id']:c for c in read(DATA/'cases.json')}
    cache={};checked=0
    for t in read(path):
        source_id=t['source_task_id'];source=source_plan[source_id];origin=read_content(source);content=read_content(t)
        if source_id not in cache:cache[source_id]=decode(source_raw[source_id])
        obj=cache[source_id];method=t['method']
        if content['catalogue']!=cases[t['case_id']]['catalogue']:raise ValueError('Dependent catalogue changed')
        if method in ('recover','direct_review'):
            if set(content)!={'visible_A','catalogue','draft'} or content['draft']!=obj:raise ValueError('Unproven verification draft')
            if content['visible_A']!=origin['visible_A']:raise ValueError('Verification source transcript changed')
        elif method in ('recon_one','recon_multi'):
            if set(content)!={'visible_A','catalogue','hypothetical_B'} or content['hypothetical_B']!=obj['hypotheses']:raise ValueError('Unproven B hypothesis input')
            if content['visible_A']!=origin['visible_A']:raise ValueError('Reconstruction source transcript changed')
        elif method=='open':
            if set(content)!={'claims','catalogue'} or content['claims']!=obj['claims']:raise ValueError('Open normalization input changed')
        else:raise ValueError('Unexpected dependent method')
        checked+=1
    return {'checked':checked,'all_sources_match':True,'gold_or_hidden_B_fields_added':False,
            'open_normalization_sees_A':False}

def verify_v2_boundary():
    path=OUT/'reconstruction_v2_extract/requests.json'
    if not path.exists():return {'checked':0,'all_sources_match':None}
    from isc3_reconstruction_v2 import validate_hypotheses
    raw=raw_index(OUT/'reconstruction_v2_generate')
    generated={t['task_id']:t for t in read(OUT/'reconstruction_v2_generate/requests.json')}
    cases={c['case_id']:c for c in read(DATA/'cases.json')};checked=0
    for t in read(path):
        c=cases[t['case_id']];origin=read_content(generated[t['source_task_id']]);content=read_content(t)
        if set(origin)!={'visible_A','output_skeleton'} or origin['visible_A']!=c['visible_A']:raise ValueError('V2 generation boundary violation')
        hs=validate_hypotheses(decode(raw[t['source_task_id']]),c['visible_A'],1 if t['method']=='recon_one_v2' else 3)
        if set(content)!={'visible_A','catalogue','hypothetical_B'} or content['hypothetical_B']!=hs or content['visible_A']!=c['visible_A'] or content['catalogue']!=c['catalogue']:raise ValueError('V2 extraction boundary violation')
        checked+=1
    return {'checked':checked,'all_sources_match':True,'strict_complete_reply_positions':True,'gold_or_hidden_B_fields_added':False}

def costs_and_references(rows):
    raw={};plans={};bindings=[]
    for stage in ['initial','dependent','reconstruction_v2_generate','reconstruction_v2_extract']:
        p=OUT/stage/'requests.json'
        if not p.exists():continue
        raw.update(raw_index(OUT/stage));plans.update({t['task_id']:t for t in read(p)})
        bindings.extend(read(DATA/f'bindings_{stage}.json'))
    records=[]
    cases={c['case_id']:c for c in read(DATA/'cases.json')}
    for ds in ['controlled','natural']:
        for method in METHODS:
            use=[b for b in bindings if b['method']==method and b['condition']=='full' and cases[b['case_id']]['dataset']==ds]
            ids={b['task_id'] for b in use}
            for b in use:
                if b.get('source_task_id'):ids.add(b['source_task_id'])
            successful=[raw[i] for i in ids if i in raw]
            records.append({'dataset':ds,'method':method,'planned_views':len(use),'standalone_unique_stage_calls':len(ids),
                'successful_stage_calls':len(successful),
                'input_tokens':sum(r['body'].get('usage',{}).get('prompt_tokens',0) for r in successful),
                'output_tokens':sum(r['body'].get('usage',{}).get('completion_tokens',0) for r in successful),
                'total_tokens':sum(r['body'].get('usage',{}).get('total_tokens',0) for r in successful)})
    write_csv(OUT/'method_costs.csv',records)
    full=[]
    p=ROOT/'results/qwen38/stage2/predictions.json'
    if p.exists():
        full=[r for r in read(p) if r['condition']=='full']
    test_ids={c['case_id'] for c in cases.values() if c['dataset']=='natural' and c['split']=='test'}
    matched_full=[r for r in full if r['view_id'] in test_ids]
    save(OUT/'reference_controls.json',{'historical_stage2_full':{
        'views':len({r['view_id'] for r in full}),
        'known_positive_truths':sum(r['truth']=='true' for r in full),
        'correct_positive_recoveries':sum(r['prediction']=='true' and r['truth']=='true' for r in full),
        'matched_test_views':len({r['view_id'] for r in matched_full}),
        'matched_test_correct_positive_recoveries':sum(r['prediction']=='true' and r['truth']=='true' for r in matched_full),
        'matched_test_correct_positive_per_100_views':100*sum(r['prediction']=='true' and r['truth']=='true' for r in matched_full)/len(test_ids),
        'provenance':'results/qwen38/stage2/predictions.json; different prompt; descriptive only'},
        'method_costs':records})

def matched_risk_comparisons(rows,one):
    result={}
    for ds in ['controlled','natural']:
        rs=[r for r in rows if r['dataset']==ds and r['split']=='test']
        result[ds]={}
        for delta in [.05,.1,.2]:
            ops={m:one[ds][m]['operating_points'][str(delta)] for m in one[ds]}
            if 'direct' not in ops:continue
            for m in ['recover','direct_review','graph','open','recon_one','recon_multi','recon_one_v2','recon_multi_v2']:
                if m not in ops:continue
                ta=ops['direct']['selection']['threshold'];tb=ops[m]['selection']['threshold']
                p=paired(rs,'direct',m,tau_a=ta,tau_b=tb)
                p['both_test_nonverified_at_or_below_target']=all(op['test']['nonverified_fraction'] is None or op['test']['nonverified_fraction']<=delta for op in [ops['direct'],ops[m]])
                result[ds][f'{m}_minus_direct_delta_{delta}']=p
    save(OUT/'E1_paired_risk_comparisons.json',result)

def natural_sensitivity(rows,one):
    result={}
    for method in METHODS:
        if method not in one['natural']:continue
        full=[r for r in rows if r['dataset']=='natural' and r['split']=='test' and r['method']==method and r['condition']=='full']
        tau=one['natural'][method]['operating_points']['0.1']['selection']['threshold']
        strict=[r for r in full if not r['sensitive_annotation']]
        result[method]={'all_items_nominal':metric(full,0,True),'excluding_policy_sensitive_nominal':metric(strict,0,True),
            'excluding_policy_sensitive_frozen_threshold':metric(strict,tau,True),
            'sampling_arms':{arm:metric([r for r in full if r['arm']==arm],0,True) for arm in ['random','enriched']},
            'caution':'Gold and thresholds were not retuned; exclude policy-sensitive attribute items only. Random/enriched sampling is not a population privacy prevalence estimate.'}
    save(OUT/'natural_sensitivity.json',result)

def export_case_studies(cases,rows):
    full={(r['case_id'],r['attribute'],r['method']):r for r in rows if r['condition']=='full' and r['split']=='test' and r['method'] in ('direct','recover')}
    disagreements=[];transitions=[]
    for c in cases.values():
        if c['split']!='test':continue
        catalogue={a['id']:a['claim'] for a in c['catalogue']}
        for fact in c['facts']:
            a=full.get((c['case_id'],fact['id'],'direct'));b=full.get((c['case_id'],fact['id'],'recover'))
            if not a or not b or a['prediction']==b['prediction']:continue
            known=a['truth']!='unknown'
            event='different_unverified_claims'
            if known and a['prediction']==a['truth'] and b['prediction']!=b['truth']:event='direct_correct_recover_abstains_or_changes'
            elif known and b['prediction']==b['truth'] and a['prediction']!=a['truth']:event='recover_correct_direct_abstains_or_changes'
            elif a['truth']=='unknown' and b['prediction']=='unknown':event='recover_abstains_on_unknown_truth'
            elif a['truth']=='unknown' and a['prediction']=='unknown':event='recover_adds_unverified_assertion'
            disagreements.append({'case_id':c['case_id'],'dataset':c['dataset'],'claim_id':fact['id'],
                'claim':catalogue[fact['id']],'truth':fact['truth'],'A_support':fact['a_support'],'event':event,
                'visible_A':c['visible_A'],'direct_label':a['prediction'],'direct_confidence':a['confidence'],
                'direct_evidence':a['evidence_turns'],'recover_label':b['prediction'],
                'recover_confidence':b['confidence'],'recover_evidence':b['evidence_turns']})
    chains={(r['case_id'],r['attribute'],r['method'],len(r['visible_turns'])):r for r in rows
            if r['split']=='test' and r['method'] in ('direct','recover') and (r['condition']=='full' or r['condition'].startswith('prefix_'))}
    for c in cases.values():
        if c['split']!='test':continue
        for f in c['facts']:
            if f['truth']!='true':continue
            for method in ['direct','recover']:
                for k in range(1,len(c['visible_A'])+1):
                    before=chains.get((c['case_id'],f['id'],method,k-1));after=chains.get((c['case_id'],f['id'],method,k))
                    if not before or not after or (before['prediction']=='true')==(after['prediction']=='true'):continue
                    transitions.append({'case_id':c['case_id'],'dataset':c['dataset'],'method':method,'claim_id':f['id'],
                        'event':'correct_positive_gained' if after['prediction']=='true' else 'correct_positive_lost',
                        'before_k':k-1,'after_k':k,'added_A_turn':c['visible_A'][k-1]['text'],
                        'prefix_A':c['visible_A'][:k],'truth':f['truth'],'A_support_full':f['a_support'],
                        'prelabelled_support_turns':f['support_turns'],'before_label':before['prediction'],
                        'after_label':after['prediction'],'before_confidence':before['confidence'],
                        'after_confidence':after['confidence'],'before_evidence':before['evidence_turns'],
                        'after_evidence':after['evidence_turns']})
    write_csv(OUT/'case_studies_method_disagreements.csv',disagreements)
    write_csv(OUT/'case_studies_prefix_transitions.csv',transitions)

def plots(e1_result,normalized):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    for ax,dataset in zip(axes,['controlled','natural']):
        for method in METHODS:
            if method not in e1_result[dataset]:continue
            points=[metric([r for r in GLOBAL_ROWS if r['dataset']==dataset and r['split']=='test' and r['condition']=='full' and r['method']==method],tau) for tau in THRESHOLDS]
            points=sorted([m for m in points if m['nonverified_fraction'] is not None],key=lambda m:m['nonverified_fraction'])
            planned=e1_result[dataset][method]['unthresholded_test']['planned_test_views']
            ax.plot([m['nonverified_fraction'] for m in points],[100*m['grounded_true_recoveries']/planned for m in points],marker='o',label=method,alpha=.8)
        ax.set(title=dataset,xlabel='Nonverified assertion fraction (not population FDR)',ylabel='Grounded true facts / 100 planned views');ax.grid(alpha=.2)
    axes[1].legend(loc='upper left',fontsize=8,bbox_to_anchor=(1.02,1));fig.tight_layout();fig.savefig(OUT/'E1_recovery_risk.png',dpi=170);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12.5,4.8))
    reference=list(csv.DictReader((OUT/'turn_accumulation_references.csv').open(encoding='utf-8-sig')))
    for ax,dataset in zip(axes,['controlled','natural']):
        for method in ['direct','recover']:
            for field,style in [('true_facts_per_100_views','-'),('grounded_facts_per_100_views','--')]:
                points=[p for p in normalized if p['dataset']==dataset and p['method']==method and p['operating_point']=='nominal']
                ax.plot([p['fraction'] for p in points],[p[field] for p in points],style,color={'direct':'#1f77b4','recover':'#e67e22'}[method],marker='o',label=method+(' factual' if style=='-' else ' grounded'))
        refs=[r for r in reference if r['dataset']==dataset]
        if refs and all(r['annotation_supported_true_per_100_views'] for r in refs):
            ax.plot([float(r['fraction']) for r in refs],[float(r['annotation_supported_true_per_100_views']) for r in refs],':',color='#777777',label='annotated A-support reference')
            ax.axhline(float(refs[-1]['full_world_known_true_per_100_views']),color='#222222',linestyle='-.',alpha=.6,label='full-world truth reference')
        ax.set(title=dataset,xlabel='Prefix fraction target (ceil(n*f) turns)',ylabel='Correct true facts / 100 target views',xticks=[0,.25,.5,.75,1]);ax.grid(alpha=.2)
    axes[1].legend(loc='upper left',fontsize=7,bbox_to_anchor=(1.02,1));fig.tight_layout();fig.savefig(OUT/'turn_accumulation.png',dpi=170);plt.close(fig)

def main():
    global GLOBAL_ROWS
    cases,rows,errors=parse();GLOBAL_ROWS=rows
    one=e1(rows);two=e2(rows);normalized,growth=accumulation(cases,rows,one)
    three=e3(rows);four=e4(rows);five=e5(rows,one);check=audit(cases,rows,errors)
    costs_and_references(rows);matched_risk_comparisons(rows,one)
    natural_sensitivity(rows,one)
    export_case_studies(cases,rows)
    plots(one,normalized)
    required=['initial','dependent']
    if (OUT/'reconstruction_v2_generate/requests.json').exists():required+=['reconstruction_v2_generate','reconstruction_v2_extract']
    complete=all(stage in check['stages'] and check['stages'][stage]['missing_http_tasks']==0 for stage in required)
    save(OUT/'analysis_status.json',{'provisional':not complete,'all_planned_http_tasks_returned':complete,
        'validation_error_bindings':len(errors),'independent_human_review':False,
        'caution':'While provisional, incomplete API coverage must not be interpreted as experimental effects.'})
    print(json.dumps({'validated_rows':len(rows),'validation_error_bindings':len(errors),'recorded_tokens':check['recorded_tokens'],'stages':check['stages']},ensure_ascii=False))

if __name__=='__main__':main()
