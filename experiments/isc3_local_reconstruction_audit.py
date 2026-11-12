"""No-network, conservative canonical-phrase audit of fictional structured replies."""
import json
import re
from isc3_common import *
from isc3_analyze import write_csv

def patterns(claim):
    predicate=claim.removeprefix('B ').removesuffix('.')
    if predicate.startswith('has '):
        rest=re.escape(predicate[4:]);positive=[r'I\s+have\s+',r"I['’]ve\s+got\s+"]
        negative=[r'I\s+do\s+not\s+have\s+',r"I\s+don['’]t\s+have\s+"]
    elif predicate.startswith('is '):
        rest=re.escape(predicate[3:]);positive=[r'I\s+am\s+',r"I['’]m\s+"]
        negative=[r'I\s+am\s+not\s+',r"I['’]m\s+not\s+"]
    else:
        verb,resttext=predicate.split(' ',1);rest=re.escape(resttext)
        base={'smokes':'smoke','drinks':'drink','owns':'own'}[verb]
        positive=[r'I\s+'+base+r'\s+']
        negative=[r'I\s+do\s+not\s+'+base+r'\s+',r"I\s+don['’]t\s+"+base+r'\s+']
    lead=r'(?:^|(?<=[.!])\s+)(?:(?:yes|no|well|actually|thanks|thank you|correct|indeed)[,!]\s+)?'
    return [(label,re.compile(lead+'('+pre+rest+r')(?=\b|[.!?,]|$)',re.I))
            for label,pres in [('true',positive),('false',negative)] for pre in pres]

def main():
    cases={c['case_id']:c for c in read(DATA/'cases.json')}
    gen_methods=['recon_one_generate','recon_multi_generate','recon_one_v2_generate','recon_multi_v2_generate']
    work=[]
    for stage in ['initial','reconstruction_v2_generate']:
        path=DATA/f'bindings_{stage}.json'
        if not path.exists() or not (OUT/stage/'api_raw.jsonl').exists():continue
        source=raw_index(OUT/stage)
        work.extend((b,source) for b in read(path) if b['method'] in gen_methods)
    records=[];views=[];errors=[];human=[];coverage=[]
    for b,raw in work:
        c=cases[b['case_id']]
        try:
            obj=decode(raw[b['task_id']]);hs=obj['hypotheses']
            expected={v['turn'] for v in c['visible_A']}
            for ix,h in enumerate(hs):
                present={r['after_turn'] for r in h['replies']}
                coverage.append({'case_id':c['case_id'],'dataset':c['dataset'],'split':c['split'],
                    'method':b['method'],'hypothesis':ix,'expected_replies':len(expected),
                    'actual_replies':len(h['replies']),'unique_covered_turns':len(present),
                    'complete_turn_coverage':present==expected,'coverage_fraction':len(present)/len(expected)})
            if c['dataset']=='natural':
                human.append({'case_id':c['case_id'],'method':b['method'],'hypotheses':hs,
                              'human_assertions':[],'status':'Not automatically semantically scored'})
                continue
            gold={f['id']:f for f in c['facts']};tmp=[]
            for ix,h in enumerate(hs):
                for attr in c['catalogue']:
                    found={}
                    for label,pattern in patterns(attr['claim']):
                        for reply in h['replies']:
                            for match in pattern.finditer(reply['text']):
                                after=reply['text'][match.end():];sentence=after.split('.')[0].split('!')[0]
                                if '?' in sentence or re.search(r'\b(?:maybe|perhaps|hypothetically|if)\b',sentence,re.I):continue
                                found.setdefault(label,match.group(1))
                    for label,quote in found.items():
                        f=gold[attr['id']]
                        tmp.append({'case_id':c['case_id'],'dataset':c['dataset'],'split':c['split'],
                            'cluster':c['template_family'],'method':b['method'],'hypothesis':ix,'attribute':attr['id'],
                            'label':label,'quote':quote,'truth':f['truth'],'a_support':f['a_support'],
                            'known_truth_error':f['truth']!='unknown' and label!=f['truth'],
                            'unverified':f['truth']=='unknown','unsupported':label!=f['a_support'],
                            'correct_true':label=='true' and f['truth']=='true','contradictory':len(found)>1})
            records.extend(tmp)
            views.append({'case_id':c['case_id'],'dataset':'controlled','split':c['split'],'method':b['method'],
                'hypotheses':len(hs),'explicit_assertions':len(tmp),'unsupported':sum(a['unsupported'] for a in tmp),
                'known_truth_errors':sum(a['known_truth_error'] for a in tmp),'unverified':sum(a['unverified'] for a in tmp),
                'correct_true':sum(a['correct_true'] for a in tmp)})
        except (ValueError,KeyError,TypeError) as exc:errors.append({**b,'error':str(exc)})
    result={'kind':'offline_canonical_phrase_lower_bound','methods':{'controlled':{}},'validation_errors':errors,
        'caution':'Offline regex detects only sentence-initial canonical first-person predicates in fictional structured B replies. Counts are lower bounds on matched explicit assertions, not exhaustive semantic annotations. Natural generated replies are exported for human review and are not automatically scored.',
        'external_audit':'Automatic approval review rejected extra external annotation; no extra reconstruction-audit network calls were made.'}
    result['reply_coverage']={}
    for ds in ['controlled','natural']:
        result['reply_coverage'][ds]={}
        for method in gen_methods:
            rs=[v for v in coverage if v['dataset']==ds and v['method']==method and v['split']=='test']
            result['reply_coverage'][ds][method]={'hypotheses':len(rs),'fully_covered_hypotheses':sum(v['complete_turn_coverage'] for v in rs),
                'mean_turn_coverage':sum(v['coverage_fraction'] for v in rs)/len(rs) if rs else None,
                'empty_hypotheses':sum(v['actual_replies']==0 for v in rs)}
    for method in gen_methods:
        rs=[v for v in views if v['method']==method and v['split']=='test'];n=sum(v['hypotheses'] for v in rs)
        result['methods']['controlled'][method]={'views':len(rs),'hypotheses':n,
            **{k:sum(v[k] for v in rs) for k in ['explicit_assertions','unsupported','known_truth_errors','unverified','correct_true']},
            'unsupported_per_100_hypotheses':100*sum(v['unsupported'] for v in rs)/n if n else None}
    save(OUT/'E2_reconstruction_assertions.json',result);write_csv(OUT/'E2_reconstruction_assertions.csv',records)
    write_csv(OUT/'E2_reconstruction_audit_views.csv',views);save(OUT/'human_review/natural_reconstructions.json',human)
    write_csv(OUT/'E2_reconstruction_coverage.csv',coverage)
    print({'offline_audited_structured_views':len(views),'canonical_assertions':len(records),'validation_errors':len(errors),'natural_review_views':len(human)})

if __name__=='__main__':main()
