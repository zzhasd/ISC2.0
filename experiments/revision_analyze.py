"""Analyze saved revision responses; no network calls or gold edits."""
import argparse
import collections
import contextlib
import csv
import io
import json
import math
from pathlib import Path
import numpy as np
from sklearn.metrics import f1_score
from revision_api import ROOT,OUT,read,save
import analyze as pilot
import stage2_analyze as s2

LABELS=['true','false','unknown']
def calls(name):
    p=OUT/name/'api_raw.jsonl'
    return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines()] if p.exists() else []
def successful(name):
    return {r['task_id']:r for r in calls(name) if r.get('http_status')==200}
def decoded(r):
    c=r['body']['choices'][0]
    assert c.get('finish_reason')=='stop','Truncated/incomplete generation'
    return json.loads(c['message']['content'])
def write_csv(path,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})
def intervals(values,groups,seed=20261101):
    values=np.array(values,dtype=float);groups=np.array(groups)
    unique=np.unique(groups)
    if not len(unique):return None
    by=[values[groups==g] for g in unique]
    sums=np.array([v.sum() for v in by]);ns=np.array([len(v) for v in by])
    rng=np.random.default_rng(seed);sample=rng.integers(0,len(by),(5000,len(by)))
    means=sums[sample].sum(1)/ns[sample].sum(1)
    return {'estimate':float(values.mean()),'ci95':np.quantile(means,[.025,.975]).tolist(),'clusters':len(by),'bootstrap_draws':5000}

def legacy():
    pilot.OUT=OUT/'stage1'
    # The historical sample has seven normalized train/test overlaps; retain
    # its original exclusion sensitivity when changing output directories.
    save(pilot.OUT/'data_audit.json',read(ROOT/'results/data_audit.json'))
    with contextlib.redirect_stdout(io.StringIO()):pilot.main()
    s=read(pilot.OUT/'summary.json');s['probe_calls']=0;s['probe_tokens']=0
    s['probe_accounting']='Shared revision connection probe: 1 call, 29 tokens; counted only in aggregate report'
    save(pilot.OUT/'summary.json',s)
    s2.OUT=OUT/'stage2'
    with contextlib.redirect_stdout(io.StringIO()):s2.main()
    main={(r['dataset'],r['id']):r for r in read(OUT/'stage1/predictions.json') if r['condition']=='a_only'}
    singleton_rows=[];singleton_errors=[]
    for r in calls('singletons'):
        try:
            a=decoded(r)['answers'];assert len(a)==1,'Expected singleton'
            a=a[0];reference=main[(r['dataset'],r['item_id'])]
            assert a['label'] in LABELS
            singleton_rows.append({'dataset':r['dataset'],'item_id':r['item_id'],
                'main_label':reference['prediction'],'singleton_label':a['label'],
                'changed':a['label']!=reference['prediction'],'truth':reference['truth'],
                'main_correct':reference['prediction']==reference['truth'],'singleton_correct':a['label']==reference['truth']})
        except (KeyError,ValueError,AssertionError,TypeError) as e:singleton_errors.append({'task_id':r['task_id'],'error':str(e)})
    save(OUT/'singletons/summary.json',{'items':singleton_rows,'validation_errors':singleton_errors,
        'changed_labels':sum(r['changed'] for r in singleton_rows),
        'selection_caveat':'Eight probes were chosen after old qwen-plus errors; not random or representative'})

def controlled(name='controlled',data_name='controlled.json'):
    gold={r['id']:r for r in read(ROOT/'data/revision'/data_name)}
    plan=read(OUT/name/'requests.json');raw=successful(name);rows=[];errors=[]
    for t in plan:
        try:
            answers=decoded(raw[t['task_id']])['answers']
            assert len(answers)==len(t['mapping']) and {a['id'] for a in answers}==set(t['mapping']),'Mismatched answer IDs'
            tmp=[]
            for a in answers:
                g=gold[t['mapping'][a['id']]['item_id']]
                p=[float(a['p_'+k]) for k in LABELS]
                assert all(math.isfinite(x) and 0<=x<=1 for x in p) and abs(sum(p)-1)<=.02,'Invalid probabilities'
                assert a['label'] in LABELS,'Invalid label'
                p=[x/sum(p) for x in p]
                tmp.append({k:v for k,v in g.items() if k!='conditions'}|{'condition':t['condition'],
                    'prediction':a['label'],'probabilities':p,'evidence':a.get('evidence',''),'task_id':t['task_id']})
            rows.extend(tmp)
        except (KeyError,AssertionError,TypeError,ValueError) as e:errors.append({'task_id':t['task_id'],'error':str(e)})
    summary={'predictions':len(rows),'expected_predictions':1920,'validation_errors':errors,'conditions':{},'mechanisms':{},'comparisons':{}}
    by={c:[r for r in rows if r['condition']==c] for c in ['a_only','narrative','shuffled','word_bag']}
    for c,rs in by.items():
        if not rs:continue
        pairs=collections.defaultdict(list)
        for r in rs:pairs[r['group']].append(r)
        complete=[p for p in pairs.values() if len(p)==2]
        summary['conditions'][c]={**pilot.metrics(rs),'abstentions':sum(r['prediction']=='unknown' for r in rs),
            'forced_binary_accuracy_ties_false':float(np.mean([('true' if r['probabilities'][0]>r['probabilities'][1] else 'false')==r['truth'] for r in rs])),
            'complete_pairs':len(complete),'both_pair_members_correct':sum(all(r['prediction']==r['truth'] for r in p) for p in complete)/len(complete) if complete else None,
            'probability_separation':float(np.mean([next(r for r in p if r['truth']=='true')['probabilities'][0]-next(r for r in p if r['truth']=='false')['probabilities'][0] for p in complete])) if complete else None,
            'accuracy_bootstrap':{unit:intervals([r['prediction']==r['truth'] for r in rs],[r[unit] for r in rs]) for unit in ['group','template_family','lexical_assignment','mechanism']}}
        for m in sorted({r['mechanism'] for r in rs}):
            current=[r for r in rs if r['mechanism']==m]
            summary['mechanisms'].setdefault(m,{})[c]=pilot.metrics(current)
    pvals=[]
    for c in ['narrative','shuffled','word_bag']:
        aa={r['id']:r for r in by['a_only']};bb={r['id']:r for r in by[c]};ids=sorted(set(aa)&set(bb))
        if not ids:continue
        diffs=[int(aa[i]['prediction']==aa[i]['truth'])-int(bb[i]['prediction']==bb[i]['truth']) for i in ids]
        lossdiff=[pilot.item_loss(bb[i])-pilot.item_loss(aa[i]) for i in ids]
        groups=[aa[i]['template_family'] for i in ids];unique=sorted(set(groups))
        means=np.array([np.mean([d for d,g in zip(diffs,groups) if g==u]) for u in unique])
        rng=np.random.default_rng(20261101)
        signs=rng.choice([-1,1],size=(10000,len(means)))
        pvalue=float((1+np.sum(np.abs((signs*means).mean(1))>=abs(means.mean())-1e-12))/10001)
        summary['comparisons']['a_only_minus_'+c]={'paired_items':len(ids),'accuracy_delta_template_cluster':intervals(diffs,groups),
            'log_score_gain_nats_template_cluster':intervals(lossdiff,groups),'paired_template_signflip_p':pvalue,
            'signflip_caveat':'20 hand-authored mechanism/surface template clusters; conditional exploratory test, not population proof'}
        pvals.append((c,pvalue))
    previous=0
    for rank,(c,pvalue) in enumerate(sorted(pvals,key=lambda x:x[1])):
        adjusted=max(previous,min(1,pvalue*(len(pvals)-rank)));previous=adjusted
        summary['comparisons']['a_only_minus_'+c]['holm_adjusted_p']=adjusted
    from sklearn.feature_extraction.text import CountVectorizer
    from sklearn.linear_model import LogisticRegression
    baseline={}
    all_gold=list(gold.values())
    for baseline_name,ngram in [('unigram',(1,1)),('unigram_bigram',(1,2))]:
        for unit in ['lexical_assignment','template_family','mechanism']:
            predicted=[];truths=[];folds={}
            for holdout in sorted({r[unit] for r in all_gold}):
                tr=[r for r in all_gold if r[unit]!=holdout];te=[r for r in all_gold if r[unit]==holdout]
                v=CountVectorizer(ngram_range=ngram);x=v.fit_transform([r['conditions']['a_only'] for r in tr])
                model=LogisticRegression(C=1,max_iter=2000,random_state=20261101).fit(x,[r['truth']=='true' for r in tr])
                pp=model.predict(v.transform([r['conditions']['a_only'] for r in te]));yy=np.array([r['truth']=='true' for r in te])
                predicted.extend(pp.tolist());truths.extend(yy.tolist());folds[str(holdout)]=float(np.mean(pp==yy))
            baseline[baseline_name+'/leave_'+unit+'_out']={'accuracy':float(np.mean(np.array(predicted)==truths)),'fold_accuracy':folds,'n':len(truths)}
    summary['exploratory_supervised_baselines']=baseline
    bagpairs=collections.defaultdict(list)
    for r in by['word_bag']:bagpairs[r['group']].append(r)
    gaps=[max(abs(x-y) for x,y in zip(p[0]['probabilities'],p[1]['probabilities'])) for p in bagpairs.values() if len(p)==2]
    summary['identical_word_bag_probability_variation']={'complete_pairs':len(gaps),'max_abs_gap':max(gaps) if gaps else None,
        'mean_abs_max_gap':float(np.mean(gaps)) if gaps else None,'note':'Inputs identical within pair; batch neighbours differ, so any variation is context/numerical sensitivity.'}
    save(OUT/name/'predictions.json',rows);write_csv(OUT/name/'predictions.csv',rows)
    save(OUT/name/'summary.json',summary);save(OUT/name/'validation_errors.json',errors)

def controlled_v2():controlled('controlled_v2','controlled_v2.json')

def parse_catalogue(t,r,gold,dialogues):
    obj=decoded(r);targets=obj['targets']
    hidden=t.get('target_source_speaker')
    target='S'+str(hidden) if t['condition']=='full' else 'B'
    assert isinstance(targets,list) and len(targets)==1 and targets[0]['target']==target,'Unexpected target schema'
    facts=targets[0]['facts'];inventory={a['id'] for a in read(ROOT/'data/stage2/inventory.json')}
    assert len(facts)==len(inventory) and {f['id'] for f in facts}==inventory,'Invalid catalogue'
    transcript=json.loads(t['payload']['messages'][1]['content'])['transcript'];rows=[]
    for f in facts:
        assert f['label'] in LABELS,'Invalid label'
        ev=f.get('evidence_turns',[])
        assert isinstance(ev,list) and all(type(x)==int and 1<=x<=len(transcript) for x in ev),'Invalid evidence turn'
        if t['condition']=='prior':
            rows.append({'attribute':f['id'],'prediction':f['label']});continue
        g=gold[(t['dialogue_id'],hidden,f['id'])]
        visible=[i+1 for i in range(len(dialogues[t['dialogue_id']]['turns'])) if i%2!=hidden]
        original=ev if t['condition']=='full' else [visible[x-1] for x in ev]
        rows.append({**g,'condition':t['condition'],'prediction':f['label'],'model_evidence_turns':ev,
            'model_evidence_original_turns':original,'request_id':t['task_id'],
            'evidence_intersects_prelabelled_support':bool(set(original)&set(g['full_evidence_turns'] if t['condition']=='full' else g['a_evidence_turns'])),
            'definite_without_evidence':f['label']!='unknown' and not ev})
    return rows

def natural():
    gs=read(ROOT/'data/revision/gold.json');gold={(r['dialogue_id'],r['target_source_speaker'],r['attribute']):r for r in gs}
    ds={d['id']:d for d in read(ROOT/'data/revision/dialogues.json')}
    raw=successful('natural');rows=[];errors=[];prior=None
    for t in read(OUT/'natural/requests.json'):
        try:
            parsed=parse_catalogue(t,raw[t['task_id']],gold,ds)
            if t['condition']=='prior':prior=parsed
            else:rows.extend(parsed)
        except (KeyError,ValueError,TypeError,AssertionError,IndexError) as e:errors.append({'task_id':t['task_id'],'condition':t['condition'],'error':str(e)})
    if prior:
        for g in gs:
            f=next(x for x in prior if x['attribute']==g['attribute'])
            rows.append({**g,'condition':'prior','prediction':f['prediction'],'model_evidence_turns':[],
                'model_evidence_original_turns':[],'evidence_intersects_prelabelled_support':False,
                'definite_without_evidence':f['prediction']!='unknown','request_id':'shared_prior'})
    summary={'expected_decisions_per_condition':len(gs),'validation_errors':errors,'conditions':{},'strict_sensitivity':{},'paired_comparisons':{},'attributes':{}}
    for arm in ['all','random','enriched']:
        subset=[r for r in rows if arm=='all' or r['arm']==arm]
        summary['paired_comparisons'][arm]=s2.paired_bootstrap(subset)
        for c in ['prior','a_only','full']:
            rs=[r for r in subset if r['condition']==c]
            if not rs:continue
            summary['conditions'][arm+'/'+c]={**s2.counts(rs),'recovery_cluster_bootstrap':s2.recovery_bootstrap(rs),
                'macro_f1_present_gold_classes_secondary':float(f1_score([r['truth'] for r in rs],[r['prediction'] for r in rs],labels=sorted({r['truth'] for r in rs}),average='macro',zero_division=0))}
            strict=[r for r in rs if not r['sensitive_to_annotation_policy']]
            summary['strict_sensitivity'][arm+'/'+c]=s2.counts(strict)
    for a in sorted({r['attribute'] for r in rows}):
        summary['attributes'][a]={c:s2.counts([r for r in rows if r['condition']==c and r['attribute']==a]) for c in ['a_only','full']}
    save(OUT/'natural/predictions.json',rows);write_csv(OUT/'natural/predictions.csv',rows)
    save(OUT/'natural/summary.json',summary);save(OUT/'natural/validation_errors.json',errors)

def repeats():
    gs=read(ROOT/'data/stage2/gold.json');gold={(r['dialogue_id'],r['target_source_speaker'],r['attribute']):r for r in gs}
    ds={d['id']:d for d in read(ROOT/'data/stage2/dialogues.json')};raw=successful('repeats')
    main=read(OUT/'stage2/predictions.json');main={(r['view_id'],r['attribute']):r for r in main if r['condition']=='a_only'}
    rows=[];errors=[]
    for t in read(OUT/'repeats/requests.json'):
        try:
            for r in parse_catalogue(t,raw[t['task_id']],gold,ds):
                r.update(temperature=t['payload']['temperature'],trial=t['trial'])
                ref=main.get((r['view_id'],r['attribute']))
                r['reference_prediction']=None if ref is None else ref['prediction']
                r['changed_from_t0_main']=None if ref is None else r['prediction']!=ref['prediction']
                rows.append(r)
        except (KeyError,ValueError,TypeError,AssertionError,IndexError) as e:errors.append({'task_id':t['task_id'],'error':str(e)})
    summary={'validation_errors':errors,'conditions':{}}
    for c in ['repeat_t0','repeat_t07']:
        rs=[r for r in rows if r['condition']==c];compared=[r for r in rs if r['changed_from_t0_main'] is not None]
        viewtrials=collections.defaultdict(list)
        for r in compared:viewtrials[(r['view_id'],r['trial'])].append(r)
        byfact=collections.defaultdict(list)
        for r in rs:byfact[(r['view_id'],r['attribute'])].append(r)
        summary['conditions'][c]={'views':len({r['view_id'] for r in rs}),'view_trials':len(viewtrials),
            'decisions':len(rs),'changed_decisions_from_t0_main':sum(r['changed_from_t0_main'] for r in compared),
            'compared_decisions':len(compared),'view_trials_with_any_change':sum(any(r['changed_from_t0_main'] for r in vs) for vs in viewtrials.values()),
            'attributes_with_trial_disagreement':sum(len({r['prediction'] for r in vs})>1 for vs in byfact.values()),
            'true_recoveries':sum(r['truth']=='true' and r['prediction']=='true' for r in rs),
            'truth_positive_decisions':sum(r['truth']=='true' for r in rs)}
    save(OUT/'repeats/predictions.json',rows);write_csv(OUT/'repeats/predictions.csv',rows)
    save(OUT/'repeats/summary.json',summary)

def defense(name='defense_judge',output_name=None,reviews=None):
    output_name=output_name or name
    reviews=reviews or {}
    gs=read(ROOT/'data/stage2/gold.json');gold={(r['dialogue_id'],r['target_source_speaker'],r['attribute']):r for r in gs}
    raw=successful(name);rows=[];viewrows=[];errors=[]
    inv={r['id'] for r in read(ROOT/'data/stage2/inventory.json')}
    for t in read(OUT/name/'requests.json'):
        try:
            o=decoded(raw[t['task_id']]);facts=o['facts'];utility=o['utility']
            assert len(facts)==20 and {f['id'] for f in facts}==inv,'Catalogue IDs invalid'
            source=json.loads(t['payload']['messages'][1]['content']);summary=source['summary']
            vr={'dialogue_id':t['dialogue_id'],'view_id':f'{t["dialogue_id"]}_target{t["target_source_speaker"]}',
                'method':t['method'],'summary':summary,'summary_words':len(summary.split()),'arm':t['arm'],
                'retention':utility.get('retention'),'consistency':utility.get('consistency'),'utility_reason':utility.get('reason',''),
                'true_disclosures':0,'new_true_disclosures':0,'unsupported_definite':0,'known_truth_errors':0,'unverified_positive':0,
                'strict_true_disclosures':0,'strict_new_true_disclosures':0,'strict_unsupported_definite':0,
                'rejected_by_AI_assertion_review':0,
                'quote_validation_failures':0,'source_summary_task_id':t['source_summary_task_id']}
            for k in ['retention','consistency']:
                assert vr[k] is None or type(vr[k])==int and 0<=vr[k]<=4,'Invalid utility rating'
            tmp=[]
            for f in facts:
                assert f['label'] in LABELS,'Invalid assertion label'
                g=gold[(t['dialogue_id'],t['target_source_speaker'],f['id'])]
                raw_label=f['label'];label=raw_label;raw_quote=f.get('quote','');quote=raw_quote
                if name=='defense_judge_v2':
                    assert f.get('holder') in ['B','none'],'Invalid assertion holder'
                    assert label=='unknown' or f.get('holder')=='B','Non-B assertion cannot label B'
                review=reviews.get((t['task_id'],f['id']))
                if review and review['decision']=='reject':
                    label='unknown';vr['rejected_by_AI_assertion_review']+=1
                if review and review.get('corrected_quote'):
                    assert review['corrected_quote'] in summary,'Review quote is not a source substring'
                    quote=review['corrected_quote']
                exact=label=='unknown' or isinstance(quote,str) and bool(quote.strip()) and quote.lower() in summary.lower()
                vr['quote_validation_failures']+=int(not exact)
                # The annotation remains inspectable if quote validation fails.
                # The primary assertion counts require an actual summary quote.
                asserted=label!='unknown' and exact
                true_disclosure=asserted and label=='true' and g['truth']=='true'
                new_true=true_disclosure and g['a_support']!='true'
                unsupported=asserted and g['a_support']=='unknown'
                wrong=asserted and g['truth']!='unknown' and label!=g['truth']
                unverified=asserted and label=='true' and g['truth']=='unknown'
                vr['true_disclosures']+=int(true_disclosure);vr['new_true_disclosures']+=int(new_true)
                vr['unsupported_definite']+=int(unsupported);vr['known_truth_errors']+=int(wrong)
                vr['unverified_positive']+=int(unverified)
                if not g['sensitive_to_annotation_policy']:
                    vr['strict_true_disclosures']+=int(true_disclosure)
                    vr['strict_new_true_disclosures']+=int(new_true)
                    vr['strict_unsupported_definite']+=int(unsupported)
                tmp.append({**g,'method':t['method'],'prediction':label,'raw_judge_label':raw_label,
                    'AI_assertion_review':review,'quote':quote,'raw_judge_quote':raw_quote,'quote_exact':exact,
                    'true_disclosure':true_disclosure,'new_true_disclosure':new_true,'unsupported_definite':unsupported,
                    'known_truth_error':wrong,'assertion_holder':f.get('holder','unreported'), 'request_id':t['task_id']})
            rows.extend(tmp);viewrows.append(vr)
        except (KeyError,ValueError,TypeError,AssertionError,IndexError) as e:errors.append({'task_id':t['task_id'],'error':str(e)})
    summary={'validation_errors':errors,'methods':{},'paired_comparisons':{},'judge':'same-model, blinded to method/gold/B; model utility proxy, not human quality',
             'risk_definition':'New true disclosure: summary asserts a gold-true attribute with no prelabelled sufficient A support. Unsupported is a support proxy, not verified falsehood.'}
    for m in ['direct','ordinary','private','conservative']:
        rs=[r for r in viewrows if r['method']==m]
        if not rs:continue
        summary['methods'][m]={'views':len(rs),'catalogue_decisions':20*len(rs),
            **{k:sum(r[k] for r in rs) for k in ['true_disclosures','new_true_disclosures','unsupported_definite','known_truth_errors','unverified_positive','quote_validation_failures','strict_true_disclosures','strict_new_true_disclosures','strict_unsupported_definite','rejected_by_AI_assertion_review']},
            'mean_retention':float(np.mean([r['retention'] for r in rs if r['retention'] is not None])) if any(r['retention'] is not None for r in rs) else None,
            'retention_n':sum(r['retention'] is not None for r in rs),
            'mean_consistency':float(np.mean([r['consistency'] for r in rs if r['consistency'] is not None])) if any(r['consistency'] is not None for r in rs) else None,
            'mean_summary_words':float(np.mean([r['summary_words'] for r in rs]))}
    for m,reference in [('ordinary','direct'),('private','ordinary'),('conservative','direct')]:
        aa={r['view_id']:r for r in viewrows if r['method']==m};bb={r['view_id']:r for r in viewrows if r['method']==reference}
        ids=sorted(set(aa)&set(bb));cmp={'paired_views':len(ids)}
        for k in ['true_disclosures','new_true_disclosures','unsupported_definite','strict_new_true_disclosures','strict_unsupported_definite','known_truth_errors','retention','consistency']:
            eligible=[i for i in ids if aa[i][k] is not None and bb[i][k] is not None]
            cmp[k+'_delta_per_view']=intervals([aa[i][k]-bb[i][k] for i in eligible],[aa[i]['dialogue_id'] for i in eligible])
        summary['paired_comparisons'][m+'_minus_'+reference]=cmp
    summary['assertion_review']='Codex AI post-hoc check of definite candidates; not independent human annotation; missing assertions not measured' if reviews else 'No post-hoc candidate review'
    save(OUT/output_name/'predictions.json',rows);write_csv(OUT/output_name/'predictions.csv',rows)
    save(OUT/output_name/'view_results.json',viewrows);write_csv(OUT/output_name/'view_results.csv',viewrows)
    save(OUT/output_name/'summary.json',summary);save(OUT/output_name/'validation_errors.json',errors)
    save(OUT/output_name/'quote_validation_failures.json',[r for r in rows if not r['quote_exact']])

def defense_v2():defense('defense_judge_v2')

def defense_reviewed():
    decisions=read(OUT/'defense_judge_v2/assertion_review.json')
    reviews={(r['task_id'],r['attribute']):r for r in decisions['items']}
    assert decisions['all_definite_candidates_reviewed'],'Candidate review is incomplete'
    original=read(OUT/'defense_judge_v2/predictions.json')
    expected={(r['request_id'],r['attribute']) for r in original if r['prediction']!='unknown'}
    assert set(reviews)==expected,'Candidate review coverage does not match all definite model outputs'
    defense('defense_judge_v2','defense_reviewed',reviews)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('parts',nargs='+',choices=['legacy','controlled','controlled_v2','natural','repeats','defense','defense_v2','defense_reviewed']);args=p.parse_args()
    for part in args.parts:globals()[part]()
