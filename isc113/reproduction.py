"""Exact offline reconstruction from raw responses and actual usage."""
from collections import Counter
from unittest.mock import patch
from .common import BASE,read,save,digest,filehash
from .inference import METHODS,pipeline
from .client import Client
from .evaluation import predictions,reference_map,current_matches,cost_map,score_item
from .statistics import four_metrics


def reproduce():
    from .annotation import rebuild_human_reference
    rebuilt=rebuild_human_reference()
    baseline=read(BASE/'audit/experiment_baseline.json')
    refs=reference_map('dailydialog');ps=predictions('dailydialog')
    if filehash(BASE/'references/dailydialog_human_adjudicated_588.json')!=baseline['reference_sha256']:
        raise ValueError('Frozen reference bytes changed')
    if filehash(BASE/'data/confirmatory_dailydialog300.json')!=baseline['full_dialogues_sha256']:
        raise ValueError('Frozen 300 full dialogues changed')
    if digest(ps)!=baseline['predictions_sha256']:raise ValueError('Frozen predictions changed')
    mm=current_matches('dailydialog',ps,refs);costs=cost_map()
    if set(mm)!=set(refs):raise ValueError('Missing or stale semantic matches')
    if len(ps)!=6*len(refs) or len({(p['item_id'],p['method']) for p in ps})!=len(ps):
        raise ValueError('Missing or duplicate method/input outcomes')
    expected={r['method']:r for r in baseline['methods']};tables=[]
    broader_expected={r['method']:r for r in read(BASE/'results/broader_counted_as_hit/four_metrics.json')}
    for method in METHODS:
        rows=[score_item(p,refs[p['dialogue_id'],p['direction']],mm[p['dialogue_id'],p['direction']],costs)
              for p in ps if p['method']==method]
        actual=four_metrics(rows)
        if any(actual[k]!=expected[method][k] for k in actual):raise ValueError('Metric drift: '+method)
        tables.append({'method':method,**actual})
        broader_rows=[score_item(p,refs[p['dialogue_id'],p['direction']],mm[p['dialogue_id'],p['direction']],costs,
                       accepted_relations=('equivalent','broader')) for p in ps if p['method']==method]
        broader=four_metrics(broader_rows)
        if any(broader[k]!=broader_expected[method][k] for k in broader):raise ValueError('Broader sensitivity drift: '+method)
    client=Client('offline-replay-placeholder',run_id='dailydialog')
    by={}
    for p in ps:by.setdefault(p['item_id'],[]).append(p)
    replayed=0
    with patch('requests.Session.post',side_effect=AssertionError('Offline reproduction attempted network')):
        for item in read(BASE/'inputs/dailydialog.json'):
            actual=pipeline(client,item)
            for a,b in zip(actual,by[item['item_id']]):
                if a['method']!=b['method'] or a['claims']!=b['claims'] or a['task_ids']!=b['task_ids']:
                    raise ValueError('Raw response replay drift: '+item['item_id'])
            replayed+=1
    result={'passed':True,'scope':'A_to_B','dialogues':len(refs),
        'reference_attributes':sum(map(len,refs.values())),
        'evidence_levels':dict(Counter(r['evidence_level'] for rr in refs.values() for r in rr)),
        'raw_prediction_counts':{m:sum(len(p['claims']) for p in ps if p['method']==m) for m in METHODS},
        'raw_response_replayed_inputs':replayed,'semantic_match_inputs':len(mm),
        'all_four_metrics_equal_to_original':True,'broader_sensitivity_also_reproduced':True,
        'human_reference_rebuilt_from_63_decisions':rebuilt['reconstructed'],
        'network_requests':0,'methods':tables}
    save(BASE/'results/reproduction_check.json',result)
    return {k:v for k,v in result.items() if k!='methods'}
