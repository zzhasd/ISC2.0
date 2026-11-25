"""Compare all completed metrics to the unmodified AGD score function, offline.

Only the two method names and dataset adapter differ. Old-Gold novelty fields
and the reference scorer's prefix-level bootstrap are deliberately discarded.
Formal confidence intervals come only from analyze.py's whole-dialogue bootstrap.
"""
from collections import defaultdict
import contextlib
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

from prepare_evaluation import HERE,agd,read,scoring_input_fingerprint

ALGORITHMS=('direct_thinking','elara_v1')
COUNT_FIELDS={
    'raw_count':'raw_count','raw_grounded':'valid_raw_count',
    'atom_count':'atom_count','atom_grounded':'valid_atom_count',
    'invalid_unique_text_approx':'invalid_unique_text_approx',
    'semantic_redundant_valid':'semantic_redundant_valid',
    'unique_core_found':'unique_core_count','pool_total':'pool_count',
    'pool_full':'full_count','pool_core':'unique_core_count',
    'slot_weight_hit':'slot_weight_hit','slot_weight_total':'slot_weight_total',
    'E1_core':'e1_core_count','E2_core':'e2_core_count'}

def csvread(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def main():
    prefixes=read(HERE/'data/prefix_inputs.json');assert len(prefixes)==341
    private=read(HERE/'agd_eval/private_source_mapping.json')
    exported=csvread(HERE/'results/prefix_metrics.csv');assert len(exported)==682
    matrix={(f'{r["dialogue_id"]}__k{int(r["prefix_k"]):02d}',r['algorithm']):r for r in exported}
    assert len(matrix)==682
    input_fingerprint=scoring_input_fingerprint()
    assert read(HERE/'results/scoring_status.json')['input_fingerprint']==input_fingerprint
    source=HERE.parent/'agd_eval_20261106/agd_eval.py'
    source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    assert source_hash==read(HERE/'judge_prompt_manifest.json')['rubric_file_sha256']
    spec=importlib.util.spec_from_file_location('_agd_offline_reference',source)
    reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
    reference.METHODS={a:a for a in ALGORITHMS}
    def forbidden(*args,**kwargs):raise AssertionError('Reference scoring must never call a model')
    reference.model_call=reference.judge=forbidden
    validation=HERE/'validation';validation.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='original_agd_',dir=validation) as temp:
        work=Path(temp).resolve();assert work.parent==validation.resolve()
        dialogues={}
        for p in prefixes:
            pid=p['prefix_id'];data=private[pid]
            dialogues[pid]={'visible_turns':p['visible_turns'],'direction':'A_to_B',
                            'predictions':data['predictions'],'pred_candidates':data['candidates'],
                            'references':[],'gold_candidates':[]}
            for target,source_stage in [('pred','support'),('pool','pool'),('sweep','sweep')]:
                reference.dump(work/'judgments'/target/(pid+'.json'),read(HERE/'agd_eval/judgments'/source_stage/(pid+'.json')))
            for target in ('gold','sweep_support'):
                reference.dump(work/'judgments'/target/(pid+'.json'),{'items':[]})
        reference.dump(work/'data.json',{'dialogues':dialogues,'methods':reference.METHODS})
        # Bootstrap=1 only permits the unchanged reference function to finish.
        # Its CI/novelty outputs stay in this temporary directory and are discarded.
        with contextlib.redirect_stdout(io.StringIO()):
            reference.score(SimpleNamespace(work=str(work),allow_incomplete=False,bootstraps=1))
        controls=csvread(work/'results/per_dialogue.csv');assert len(controls)==682
        reference_facts=csvread(work/'results/per_fact.csv')
        for control in controls:
            actual=matrix[(control['dialogue_id'],control['algorithm'])]
            for original,new in COUNT_FIELDS.items():
                assert int(control[original])==int(actual[new]),(control['dialogue_id'],control['algorithm'],original)
            assert int(control['raw_text_unique'])==int(actual['raw_count'])-int(actual['exact_text_repetition_count'])
            for name,numerator,denominator in [('p_raw','valid_raw_count','raw_count'),('r_core','unique_core_count','pool_count'),
                    ('r_full','full_count','pool_count'),('slot_coverage','slot_weight_hit','slot_weight_total')]:
                expected=int(actual[numerator])/int(actual[denominator]) if int(actual[denominator]) else None
                observed=float(actual[name]) if actual[name] else None
                assert observed==expected,(control['dialogue_id'],name)
    by_prefix={p['prefix_id']:p for p in prefixes};identity={};uids={}
    for did in {p['dialogue_id'] for p in prefixes}:
        alignment=read(HERE/'alignment/judgments'/(did+'.json'))
        uids[did]={f['id'] for f in alignment['unified_facts']}
        for m in alignment['mapping']:identity[(m['prefix_id'],m['fact_id'])]=m['unified_fact_id']
    fact_rows={};core_sets=defaultdict(set)
    for f in reference_facts:
        pid=f['dialogue_id'];local=f['fact_id'].rsplit('::',1)[1]
        uid=identity[(pid,local)];fact_rows[(pid,f['algorithm'],uid)]=f
        if int(f['core_hit']):core_sets[(pid,f['algorithm'])].add(uid)
    trajectories=csvread(HERE/'results/fact_trajectory.csv')
    observed={(r['dialogue_id'],r['algorithm'],int(r['prefix_k']),r['unified_fact_id']):r for r in trajectories}
    expected_keys={(did,a,k,u) for did,us in uids.items() for a in ALGORITHMS for k in range(1,12) for u in us}
    assert len(observed)==len(trajectories) and set(observed)==expected_keys
    for did,us in uids.items():
        for a in ALGORITHMS:
            history=set();previous=set()
            for k in range(1,12):
                pid=f'{did}__k{k:02d}';current=core_sets[(pid,a)];new=current-history
                m=matrix[(pid,a)]
                assert int(m['first_new_count'])==len(new) and int(m['ever_found_count'])==len(history|current)
                assert int(m['reappeared_count'])==len((current&history)-previous)
                assert int(m['disappeared_count'])==len(previous-current)
                for uid in us:
                    r=observed[(did,a,k,uid)];f=fact_rows.get((pid,a,uid))
                    assert int(r['supported_at_k'])==int(f is not None)
                    assert int(r['core_hit'])==int(uid in current)
                    assert int(r['full_hit'])==(int(f['full_hit']) if f else 0)
                    assert r['evidence_level']==(f['level'] if f else '')
                    assert int(r['first_discovered'])==int(uid in new)
                    assert int(r['reappeared'])==int(uid in current and uid in history and uid not in previous)
                history|=current;previous=current
    assert scoring_input_fingerprint()==input_fingerprint,'Judgments changed during the crosscheck'
    result={'complete':True,'metric_rows_compared':682,'trajectory_rows_compared':len(trajectories),
            'original_score_sha256':source_hash,'input_fingerprint':input_fingerprint,
            'matching_count_fields':COUNT_FIELDS,'raw_text_dedup_and_ratios_match':True,
            'first_discovery_and_reappearance_match_reference_fact_hits':True,
            'model_api_calls':0,'reference_novelty_and_prefix_bootstrap_outputs':'discarded; not study results'}
    agd.dump(validation/'original_agd_crosscheck.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
