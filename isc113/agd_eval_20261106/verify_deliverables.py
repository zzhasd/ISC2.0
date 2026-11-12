from pathlib import Path
import csv,json,hashlib
from collections import Counter
import agd_eval as a
R=Path(__file__).resolve().parent;W=R/'scored_eval';O=W/'results'
def readcsv(name):return list(csv.DictReader((O/name).open(encoding='utf-8-sig')))
def main():
    data=a.read(W/'data.json');summary=a.read(O/'summary.json')
    preds=readcsv('per_prediction.csv');rows=readcsv('per_dialogue.csv');facts=readcsv('per_fact.csv')
    assert len(preds)==7868 and len(rows)==298*6
    assert Counter(p['algorithm'] for p in preds)==data['prediction_counts']
    assert len({s['denom_pool'] for s in summary.values()})==1
    assert len({s['denom_E1'] for s in summary.values()})==1
    assert len({s['denom_E2'] for s in summary.values()})==1
    for m,s in summary.items():
        rr=[r for r in rows if r['algorithm']==m];pp=[p for p in preds if p['algorithm']==m]
        assert len(rr)==298
        assert sum(int(p['all_grounded']) for p in pp)==s['grounded_raw']
        assert abs(s['P_raw']-s['grounded_raw']/len(pp))<1e-12
        assert abs(s['R_full']-sum(int(r['pool_full']) for r in rr)/s['denom_pool'])<1e-12
        assert s['counts']['valid_novel_core_found']<=s['counts']['unique_core_found']
    for f in facts:
        assert int(f['full_hit'])<=int(f['core_hit'])
        assert int(f['slot_weight_hit'])<=int(f['slot_weight_total'])
    for did in data['dialogues']:
        raw=R/'final_eval/judgments/pool'/f'{did}.json';norm=W/'judgments/pool'/f'{did}.json'
        obj=a.read(norm);assert obj['_scoring_policy']['raw_pool_sha256']==hashlib.sha256(raw.read_bytes()).hexdigest()
        for f in obj['facts']:
            assert all(s['required'] and s['weight']==(2 if s['core'] else 1) for s in f['slots'])
    status={'prediction_rows':len(preds),'dialogue_algorithm_rows':len(rows),'fact_algorithm_rows':len(facts),'all_298_dialogues_all_6_methods':True,'shared_denominators':True,'independent_count_checks_passed':True,'raw_judgment_provenance_passed':True,'human_calibrated':False}
    a.dump(O/'delivery_checks.json',status);print(json.dumps(status))
if __name__=='__main__':main()
