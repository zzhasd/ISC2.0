"""Analyze saved raw responses; no model calls and no gold-label changes."""
from pathlib import Path
import collections
import csv
import hashlib
import importlib.metadata
import json
import math
import platform
import sys
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, average_precision_score, f1_score, log_loss

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results'
LABELS=['true','false','unknown']
BOOT=5000
EPS=1e-6

def item_loss(row):
    p=np.maximum(np.array(row['probabilities'],dtype=float),EPS)
    p/=p.sum()
    return -math.log(p[LABELS.index(row['truth'])])

def dump(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

def ece(y,p):
    pred=p.argmax(1); conf=p.max(1); bins=np.minimum((conf*10).astype(int),9)
    return float(sum(np.mean(bins==b)*abs(np.mean(pred[bins==b]==y[bins==b])-np.mean(conf[bins==b]))
                     for b in range(10) if np.any(bins==b)))

def metrics(rows):
    y=np.array([LABELS.index(r['truth']) for r in rows]); p=np.array([r['probabilities'] for r in rows])
    pred=np.array([LABELS.index(r['prediction']) for r in rows])
    present=np.unique(y)
    known=y!=2
    return {'n':len(rows),'accuracy':float(accuracy_score(y,pred)),
            'macro_f1_present_gold_classes':float(f1_score(y,pred,labels=present,average='macro',zero_division=0)),
            'log_loss_nats':float(np.mean([item_loss(r) for r in rows])),
            'brier_multiclass':float(np.mean(np.sum((p-np.eye(3)[y])**2,axis=1))),
            'ece_10_bins':ece(y,p),
            'positive_auprc_truth_known_only':float(average_precision_score(y[known]==0,p[known,0])) if len(np.unique(y[known]==0))>1 else None,
            'truth_known_n':int(known.sum())}

def ci_cluster(values,groups,seed=37):
    values=np.asarray(values,dtype=float); groups=np.asarray(groups)
    unique=np.unique(groups)
    # All comparisons in this pilot have equal rows per cluster. Average within
    # cluster first, then resample independent clusters, never template variants.
    means=np.array([values[groups==g].mean() for g in unique])
    rng=np.random.default_rng(seed)
    samples=means[rng.integers(0,len(means),size=(BOOT,len(means)))].mean(1)
    return {'estimate':float(means.mean()),'ci95':[float(x) for x in np.quantile(samples,[.025,.975])],
            'clusters':len(means)}

def paired(a,b,measure):
    ia={r['id']:r for r in a}; ib={r['id']:r for r in b}; ids=sorted(set(ia)&set(ib))
    return ci_cluster([measure(ia[i])-measure(ib[i]) for i in ids],[ia[i]['group'] for i in ids])

def load():
    gold={}
    for name in ['natural_pilot.json','controlled_pilot.json']:
        for row in json.loads((ROOT/'data'/name).read_text(encoding='utf-8')):
            gold[(row['dataset'],row['id'])]=row
    records=[]; errors=[]; calls=[]
    seen=set()
    for line in (OUT/'api_raw.jsonl').read_text(encoding='utf-8').splitlines():
        call=json.loads(line); calls.append(call)
        if call.get('http_status')!=200:
            errors.append({'task_id':call['task_id'],'error':'HTTP failure','status':call.get('http_status')});continue
        try:
            body=call['body']; content=body['choices'][0]['message']['content']
            obj=json.loads(content); answers=obj['answers']
            ids=[a['id'] for a in answers]
            if len(ids)!=len(set(ids)) or set(ids)!=set(call['mapping']):
                raise ValueError('Missing, duplicate or unexpected response ids')
            parsed=[]
            for answer in answers:
                meta=call['mapping'][answer['id']]; row=gold[(call['dataset'],meta['item_id'])]
                probs=[float(answer['p_'+label]) for label in LABELS]
                if any(not math.isfinite(x) or x<0 or x>1 for x in probs) or abs(sum(probs)-1)>.02:
                    raise ValueError('Invalid probability vector')
                probs=(np.array(probs)/sum(probs)).tolist()
                unique=(call['dataset'],row['id'],call['condition'])
                if unique in seen: continue
                seen.add(unique)
                probability_pred=LABELS[int(np.argmax(probs))]
                declared=answer.get('label')
                if declared not in LABELS:
                    raise ValueError('Invalid declared label')
                pred=declared
                parsed.append({'id':row['id'],'group':row['group'],'dataset':row['dataset'],
                                'condition':call['condition'],'domain':row['domain'],
                                'mechanism':row.get('mechanism'),'claim':row['claim'],
                                'truth':row['truth'],'support':row['support'],'probabilities':probs,
                                'prediction':pred,'model_label':declared,'probability_argmax':probability_pred,
                                'has_probability_tie':sum(abs(p-max(probs))<1e-10 for p in probs)>1,
                                'label_agrees_with_argmax':declared==probability_pred,
                                'evidence':answer.get('evidence',''),'task_id':call['task_id']})
            records.extend(parsed)
        except (KeyError,ValueError,TypeError) as exc:
            errors.append({'task_id':call['task_id'],'error':str(exc)})
    return records,errors,calls,gold

def supervised_baselines(gold):
    rows=[r for r in gold.values() if r['dataset']=='controlled']
    output={}
    # Six lexical domains are held out one at a time; both pair members always stay
    # in the same fold. Template families are shared: this is not template transfer.
    for name,ngram in [('unigram',(1,1)),('unigram_bigram',(1,2))]:
        all_pred=[]; all_y=[]; each={}
        for holdout in range(6):
            te=[r for r in rows if int(r['group'].rsplit('_',1)[1])==holdout]
            tr=[r for r in rows if r not in te]
            vectorizer=CountVectorizer(ngram_range=ngram)
            xtr=vectorizer.fit_transform([r['conditions']['a_only'] for r in tr])
            xte=vectorizer.transform([r['conditions']['a_only'] for r in te])
            ytr=np.array([r['truth']=='true' for r in tr]); yte=np.array([r['truth']=='true' for r in te])
            model=LogisticRegression(C=1,max_iter=2000,random_state=20261031).fit(xtr,ytr)
            pred=model.predict(xte); all_pred.extend(pred.tolist());all_y.extend(yte.tolist())
            each[str(holdout)]=float(np.mean(pred==yte))
        output[name]={'accuracy':float(accuracy_score(all_y,all_pred)),
                      'macro_f1':float(f1_score(all_y,all_pred,average='macro')),
                      'fold_accuracy':each,'n':len(all_y)}
    # Exploratory stress check, added after seeing the baseline (before final
    # report): hold out an entire mechanism family. No data or prompt retuning.
    exploratory={}
    for mechanism in sorted(set(r['mechanism'] for r in rows)):
        tr=[r for r in rows if r['mechanism']!=mechanism]
        te=[r for r in rows if r['mechanism']==mechanism]
        v=CountVectorizer(ngram_range=(1,2))
        xtr=v.fit_transform([r['conditions']['a_only'] for r in tr])
        xte=v.transform([r['conditions']['a_only'] for r in te])
        model=LogisticRegression(C=1,max_iter=2000,random_state=20261031).fit(xtr,[r['truth']=='true' for r in tr])
        exploratory[mechanism]=float(accuracy_score([r['truth']=='true' for r in te],model.predict(xte)))
    output['exploratory_bigram_leave_mechanism_out']=exploratory
    return output

def main():
    records,errors,calls,gold=load()
    dump(OUT/'predictions.json',records)
    dump(OUT/'validation_errors.json',errors)
    summary={'completed_predictions':len(records),'validation_errors':errors,
             'api_calls':len(calls),'probe_calls':1,'probe_tokens':14,
             'token_usage':{key:sum(c.get('body',{}).get('usage',{}).get(key,0) for c in calls)
                            for key in ['prompt_tokens','completion_tokens','total_tokens']},
             'returned_models':sorted(set(c.get('body',{}).get('model','') for c in calls)),
             'finish_reasons':dict(collections.Counter(c.get('body',{}).get('choices',[{}])[0].get('finish_reason','missing') for c in calls)),
             'conditions':{},'comparisons':{},'natural_evidence':{},'controlled_mechanisms':{},
             'simple_supervised_baselines':supervised_baselines(gold)}
    by={}
    for r in records: by.setdefault((r['dataset'],r['condition']),[]).append(r)
    correct=lambda r: float(r['prediction']==r['truth'])
    loss=item_loss
    for (dataset,cond),rows in by.items():
        stats=metrics(rows); stats['accuracy_cluster_ci']=ci_cluster([correct(r) for r in rows],[r['group'] for r in rows])
        if dataset=='controlled':
            stats['forced_binary_accuracy_ties_false']=float(np.mean([
                ('true' if r['probabilities'][0]>r['probabilities'][1] else 'false')==r['truth'] for r in rows]))
            stats['abstention_rate']=float(np.mean([r['prediction']=='unknown' for r in rows]))
            paired_rows=collections.defaultdict(list)
            for r in rows:paired_rows[r['group']].append(r)
            stats['both_pair_members_correct']=float(np.mean([all(correct(r) for r in pair) for pair in paired_rows.values() if len(pair)==2]))
            separations=[]
            for pair in paired_rows.values():
                if len(pair)==2:
                    pos=next(r for r in pair if r['truth']=='true');neg=next(r for r in pair if r['truth']=='false')
                    separations.append(pos['probabilities'][0]-neg['probabilities'][0])
            stats['mean_p_true_separation']=float(np.mean(separations))
        summary['conditions'][dataset+'/'+cond]=stats
    for dataset,conditions in [('dailydialog',['prior','full','word_bag','shuffled']),('controlled',['narrative','word_bag','shuffled'])]:
        a=by.get((dataset,'a_only'),[])
        if not a:continue
        for cond in conditions:
            b=by.get((dataset,cond),[])
            if not b:continue
            summary['comparisons'][dataset+'/a_only_minus_'+cond]={
                'accuracy_delta':paired(a,b,correct),
                'log_score_gain_nats':paired(b,a,loss)}
    natural=by.get(('dailydialog','a_only'),[])
    for cond in ['prior','full','a_only','shuffled','word_bag']:
        rows=by.get(('dailydialog',cond),[])
        if not rows:continue
        unsupported=[r for r in rows if r['support']=='unknown']
        known_true=[r for r in rows if r['truth']=='true']
        unknown_truth=[r for r in rows if r['truth']=='unknown']
        # A-only support strata are held fixed across views, even for full input.
        summary['natural_evidence'][cond]={
          'true_fact_disclosure':{'n':len(known_true),'assertions':sum(r['prediction']=='true' for r in known_true),
                                  'rate':float(np.mean([r['prediction']=='true' for r in known_true]))},
          'assertions_on_A_unsupported_items':{'n':len(unsupported),
                   'assertions':sum(r['prediction']=='true' for r in unsupported),
                   'rate':float(np.mean([r['prediction']=='true' for r in unsupported]))},
          'definite_assertions_on_A_unsupported_items':{'n':len(unsupported),
                   'positive':sum(r['prediction']=='true' for r in unsupported),
                   'negative':sum(r['prediction']=='false' for r in unsupported),
                   'rate':float(np.mean([r['prediction']!='unknown' for r in unsupported]))},
          'assertions_on_unknown_truth':{'n':len(unknown_truth),'positive':sum(r['prediction']=='true' for r in unknown_truth),
                                         'negative':sum(r['prediction']=='false' for r in unknown_truth)},
          'A_support_alignment_accuracy':float(np.mean([r['prediction']==r['support'] for r in rows])) if cond=='a_only' else None}
    for mechanism in ['confirmation','reference','correction','cross_turn']:
        a=[r for r in by.get(('controlled','a_only'),[]) if r['mechanism']==mechanism]
        n=[r for r in by.get(('controlled','narrative'),[]) if r['mechanism']==mechanism]
        if a and n:
            summary['controlled_mechanisms'][mechanism]={
                'a_only':metrics(a),'narrative':metrics(n),
                'a_only_accuracy_ci':ci_cluster([correct(r) for r in a],[r['group'] for r in a]),
                'a_only_minus_narrative_accuracy':paired(a,n,correct)}
    paired_bag=by.get(('controlled','word_bag'),[])
    invariance=[]
    for group in set(r['group'] for r in paired_bag):
        pair=[r for r in paired_bag if r['group']==group]
        if len(pair)==2:
            invariance.append(float(np.max(np.abs(np.array(pair[0]['probabilities'])-pair[1]['probabilities']))))
    summary['identical_word_bag_max_probability_differences']=invariance
    summary['model_label_argmax_disagreements']=sum(not r['label_agrees_with_argmax'] for r in records)
    audit_path=OUT/'data_audit.json'
    if audit_path.exists():
        overlaps=set(json.loads(audit_path.read_text(encoding='utf-8'))['selected_normalized_test_train_overlap'])
        summary['natural_nonoverlap_sensitivity']={
            cond:metrics([r for r in rs if r['id'] not in overlaps])
            for (ds,cond),rs in by.items() if ds=='dailydialog' and any(r['id'] not in overlaps for r in rs)}
    dump(OUT/'summary.json',summary)
    with (OUT/'predictions.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['dataset','id','group','condition','mechanism','domain','claim','truth','support','prediction','p_true','p_false','p_unknown','evidence'])
        writer.writeheader()
        for r in records:
            row={k:r[k] for k in writer.fieldnames if k in r}
            row.update(zip(['p_true','p_false','p_unknown'],r['probabilities']));writer.writerow(row)
    versions={p:importlib.metadata.version(p) for p in ['numpy','scipy','scikit-learn','requests','matplotlib']}
    dump(OUT/'environment.json',{'python':sys.version,'platform':platform.platform(),'packages':versions})
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
