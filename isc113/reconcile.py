"""Align independent inventories without creating or revising their attribute truths."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import sys
from .common import BASE,read,save,digest,require_dataset
from .client import Client
from .inference import payload
from .prompts import MATCH
from .evaluation import validate_matches
from .statistics import matching

def source(n,dataset):
    require_dataset(dataset)
    name='new_dailydialog_reference.json'
    p=BASE/f'annotations/annotator_{n}/{name}'
    return {(x['dialogue_id'],x['direction']):x['claims'] for x in read(p)} if p.exists() else {}

def reconcile(dataset,key,workers=16):
    aa=source(1,dataset);bb=source(2,dataset)
    cached=all((p:=BASE/'evaluation/alignment'/dataset/(k[0]+'__'+k[1]+'.json')).exists() and read(p).get('binding')==digest({'a':aa.get(k,[]),'b':bb.get(k,[])}) for k in aa.keys()|bb.keys())
    client=None if cached else Client(key,run_id='evaluation_alignment_'+dataset)
    keys=sorted(aa.keys() | bb.keys());errors=[]
    def work(k):
        a=aa.get(k,[]);b=bb.get(k,[]);binding=digest({'a':a,'b':b})
        path=BASE/'evaluation/alignment'/dataset/(k[0]+'__'+k[1]+'.json')
        if path.exists() and read(path).get('binding')==binding:return
        if not a or not b:pairs={};tid=None
        else:
            pp=[{'prediction_id':x['claim_id'],'claim':x['claim']} for x in a];rr=[{'claim_id':x['claim_id'],'claim':x['claim']} for x in b]
            ms,tid=client.call(dataset+'/'+k[0]+'/'+k[1]+'/'+binding,payload(MATCH,{'predictions':pp,'reference':rr},4096),lambda x:validate_matches(x,pp,rr))
            pairs=matching({x['prediction_id']:set(x['reference_ids']) if x['relation']=='equivalent' else set() for x in ms})
        save(path,{'binding':binding,'pairs':pairs,'task_id':tid,'model':'qwen3.8-flash' if tid else 'fixed shared IDs / empty inventory'})
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fs={pool.submit(work,k):k for k in keys}
        for f in as_completed(fs):
            try:f.result()
            except Exception as e:errors.append({'item':fs[f],'error':str(e)})
    save(BASE/'evaluation'/f'{dataset}_alignment_errors.json',errors)
    return {'items':len(keys),'errors':len(errors)}

def compile(dataset):
    aa=source(1,dataset);bb=source(2,dataset);out=[];disputes=[];counts={}
    for k in sorted(aa.keys() | bb.keys()):
        a=aa.get(k,[]);b=bb.get(k,[]);bby={x['claim_id']:x for x in b}
        p=BASE/'evaluation/alignment'/dataset/(k[0]+'__'+k[1]+'.json')
        pairs=read(p)['pairs'] if p.exists() else {};rows=[]
        for x in a:
            row=dict(x);cid=x['claim_id'];y=bby.get(pairs.get(cid))
            if y:
                row['independent_second_label']=y;row['review_status']='reviewed';row['review_source']='two_independent_AI_labels_semantically_aligned'
                if x['truth']!=y['truth']:row['truth']='uncertain';row['review_status']='pending_adjudication'
                if x['evidence_level']!=y['evidence_level']:
                    la,lb=x['evidence_level'],y['evidence_level']
                    if {la,lb}<= {'E1','E2'}:
                        row['evidence_level']='E1_E2_disputed';row['support_consensus']=True
                    elif {la,lb}<= {'E3','E4'}:
                        row['evidence_level']='E3_E4_disputed';row['unsupported_consensus']=True
                    else:row['review_status']='pending_adjudication'
                    disputes.append({'dataset':dataset,'dialogue_id':k[0],'direction':k[1],'claim_id':cid,'first':x,'second':y,'kind':'evidence_level'})
                if x.get('sensitivity')!=y.get('sensitivity'):row['sensitivity']='disputed'
            else:
                row.update(review_status='single_annotation',review_source='independent_inventory_not_selected_by_second_annotator')
            rows.append(row)
        paired_b=set(pairs.values())
        for y in b:
            if y['claim_id'] not in paired_b:
                rows.append(dict(y,review_status='single_annotation',review_source='independent_inventory_not_selected_by_first_annotator'))
        for r in rows:counts[r['review_status']]=counts.get(r['review_status'],0)+1
        record={'dialogue_id':k[0],'direction':k[1],'dataset':dataset,'claims':rows}
        out.append(record)
    save(BASE/f'annotations/{dataset}_aligned_draft.json',out)
    save(BASE/f'annotations/{dataset}_aligned_disputes.json',disputes)
    report={'dataset':dataset,'direction_items':len(out),'annotator1_direction_items':len(aa),'annotator2_direction_items':len(bb),
            'claims':sum(len(x['claims']) for x in out),'claim_review_statuses':counts,
            'missing_both_direction_items':'must compare with planned input cohort; no absent item is assigned an empty gold inventory',
            'scope':'closed-inventory evaluation on aligned labels; unmatched inventory remains unresolved; pooled exploratory labels saved separately'}
    save(BASE/f'results/{dataset}_reference_coverage.json',report)
    return report

if __name__=='__main__':
    dataset=sys.argv[1]
    if len(sys.argv)>2 and sys.argv[2]=='compile':print(compile(dataset))
    else:print(reconcile(dataset,sys.stdin.readline().strip()));print(compile(dataset))
