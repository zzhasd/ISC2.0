"""Compute agreement only from actually entered independent human annotations."""
import csv
import math
from sklearn.metrics import cohen_kappa_score
from revision_api import OUT,save

def main():
    path=OUT/'human_review/blind_annotations.csv'
    with path.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    result={'status':'pending','rows':len(rows),'dimensions':{},'AI_labels_used':False}
    for dimension in ['truth','A_support']:
        pairs=[]
        for r in rows:
            a=r.get('human1_'+dimension,'').strip();b=r.get('human2_'+dimension,'').strip()
            if a and a not in ['true','false','unknown']:raise ValueError('Invalid human1 label')
            if b and b not in ['true','false','unknown']:raise ValueError('Invalid human2 label')
            if a and b:pairs.append((a,b))
        if not pairs:
            result['dimensions'][dimension]={'paired_completed':0,'percent_agreement':None,'cohen_kappa':None};continue
        aa,bb=zip(*pairs)
        k=float(cohen_kappa_score(aa,bb)) if len(set(aa)|set(bb))>1 else None
        result['dimensions'][dimension]={'paired_completed':len(pairs),'percent_agreement':sum(a==b for a,b in pairs)/len(pairs),
            'cohen_kappa':k if k is not None and math.isfinite(k) else None}
    if any(x['paired_completed'] for x in result['dimensions'].values()):result['status']='partial'
    if all(x['paired_completed']==len(rows) for x in result['dimensions'].values()):result['status']='complete'
    save(OUT/'human_review/agreement_status.json',result)
    print(result)

if __name__=='__main__':main()
