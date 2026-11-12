"""Offline EFCR-v2 bottleneck study. No API calls or historical writes.

Reuses the frozen joint matcher; uncached proposal texts remain unknown.
Selectors are post-hoc development analyses, not new independent experiments.
"""
from collections import Counter, defaultdict
from pathlib import Path
import random
import json

from .common import BASE, read, save, digest, filehash, jsonlines
from .inference import decode
from .evaluation import score_item, reference_map, cost_map
from .statistics import four_metrics
from . import EFCR_v2 as alg

OUT = BASE / 'results/efcr_v2_research'


def main():
    source = BASE / 'results/efcr_append_v2'
    ps = read(BASE / 'runs/efcr_append_v2/exports/dailydialog.json')
    refs = reference_map('dailydialog')
    costs = cost_map('efcr_append_v2')
    inputs = {r['dialogue_id']: r for r in read(BASE / 'inputs/dailydialog.json')}
    matches = {p['dialogue_id']: read(source / 'matches' /
               (p['dialogue_id']+'__A_to_B.json'))['matches'] for p in ps}
    matchby = {did: {m['prediction_id']: m for m in ms} for did, ms in matches.items()}
    both = lambda c: len(c['proposal_sources']) == 2

    def rows_for(selector):
        return [score_item(dict(p, claims=[c for c in p['claims'] if selector(c)]),
                           refs[(p['dialogue_id'], p['direction'])], matches[p['dialogue_id']], costs)
                for p in ps]

    rules = {
        'v2_primary': lambda c: True,
        'global_090': lambda c: c['confidence'] >= .9,
        'agreement_only': lambda c: both(c),
        'agreement_or_090': lambda c: both(c) or c['confidence'] >= .9,
        'explicit_085_other_090': lambda c: c['confidence'] >= (.85 if c['mechanism']=='explicit' else .9),
        'explicit_085_other_095': lambda c: c['confidence'] >= (.85 if c['mechanism']=='explicit' else .95),
        'agreement_080_explicit_085_other_090': lambda c: c['confidence'] >= (
            .8 if both(c) else .85 if c['mechanism']=='explicit' else .9),
        'agreement_080_explicit_085_other_095': lambda c: c['confidence'] >= (
            .8 if both(c) else .85 if c['mechanism']=='explicit' else .95),
        'source_aware': lambda c: c['confidence'] >= (.8 if both(c) else .9
            if c['proposal_sources']==['direct_scan_v2'] else .95),
        'without_causal': lambda c: c['mechanism'] != 'causal',
    }
    selected_rows = {name: rows_for(rule) for name, rule in rules.items()}
    tables = [dict(rule=name, **four_metrics(rows)) for name, rows in selected_rows.items()]
    expected = read(source / 'equivalent_only/four_metrics.json')[-1]
    assert {k:v for k,v in tables[0].items() if k!='rule'} == {k:v for k,v in expected.items() if k!='method'}
    assert all(t['single_sided_inputs']==298 and t['tokens']==expected['tokens'] for t in tables)
    save(OUT / 'posthoc_selector_ablations.json', dict(posthoc=True, model_calls=0,
         inference_cost_unchanged=True, tables=tables))
    for name in ['source_aware','agreement_or_090']:
        method = 'efcr_v2_posthoc_' + name
        derived = [dict(p,method=method,claims=[c for c in p['claims'] if rules[name](c)]) for p in ps]
        assert len(derived)==298
        save(OUT / name / 'predictions.json', derived)
        save(OUT / name / 'per_input.json', [dict(r,method=method) for r in selected_rows[name]])
        save(OUT / name / 'manifest.json',dict(method=method,posthoc=True,online_rerun=False,
             source_predictions_sha256=digest(ps),derived_predictions_sha256=digest(derived),
             reference_access_during_selection=False,original_inference_cost_retained=True,
             rule=('both-sources >= .8; direct-only >= .9; evidence-only >= .95'
                   if name=='source_aware' else 'both sources OR confidence >= .9')))
    # Stratified reliability is reference-match frequency, not true factual
    # calibration: even supported but unlisted facts may fail this closed score.
    bins = defaultdict(Counter)
    examples = defaultdict(list)
    none_population = []
    for p in ps:
        did = p['dialogue_id']
        rby = {r['claim_id']: r for r in refs[(did, 'A_to_B')]}
        for c in p['claims']:
            m = matchby[did][digest(c['claim'])]
            bucket = '%.2f' % c['confidence']
            for key in ['confidence:'+bucket,
                        'judge_level:'+c['verifier']['evidence_level'],
                        'mechanism:'+c['mechanism'],
                        'source:'+','.join(c['proposal_sources']),
                        'source_conf:'+','.join(c['proposal_sources'])+':'+bucket]:
                bins[key]['outputs'] += 1
                bins[key][m['relation']] += 1
            if len(examples[m['relation']]) < 25:
                examples[m['relation']].append(dict(dialogue_id=did, prediction=c,
                    reference=[rby[rid] for rid in m['reference_ids']],
                    visible_turns=inputs[did]['visible_turns']))
            if m['relation']=='none':
                none_population.append(dict(dialogue_id=did,prediction=c,match=m,
                    visible_turns=inputs[did]['visible_turns'],references=refs[(did,'A_to_B')]))
    save(OUT / 'stratified_reference_match_frequencies.json', dict(bins))
    save(OUT / 'examples.json', dict(examples))
    sample = random.Random(113).sample(sorted(none_population,
             key=lambda x:(x['dialogue_id'],x['prediction']['claim'])),12)
    save(OUT / 'random_none_sample.json',dict(seed=113,n=12,population=len(none_population),items=sample))
    # Stage accounting and a partial candidate-ceiling audit. The judge saw
    # candidates with their generator confidences/sources in the actual log.
    raw = jsonlines(BASE / 'runs/efcr_append_v2/attempts.jsonl')
    valid, requests = {}, {}
    stage_costs = defaultdict(Counter)
    for row in raw:
        if row['event'] == 'start':
            requests[row['task_id']] = row['request']
        if row['event'] != 'complete':
            continue
        stage = row['logical_name'].split('/')[-1]
        stage_costs[stage]['attempts'] += 1
        u = row.get('body', {}).get('usage', {}).get('total_tokens')
        stage_costs[stage]['tokens_observed'] += u or 0
        stage_costs[stage]['prompt_tokens'] += row.get('body', {}).get('usage', {}).get('prompt_tokens',0)
        stage_costs[stage]['completion_tokens'] += row.get('body', {}).get('usage', {}).get('completion_tokens',0)
        stage_costs[stage]['unknown_usage_attempts'] += u is None
        if row.get('valid'):
            valid.setdefault(row['task_id'], row)
    stages = Counter()
    coverage = defaultdict(Counter)
    pool_by_did = {}
    unknown_candidates = []
    for p in ps:
        did = p['dialogue_id']; turns = inputs[did]['visible_turns']
        groups = []
        for i, name in enumerate(['evidence_first_v2', 'direct_scan_v2']):
            cs = alg.validate_claims(decode(valid[p['task_ids'][i]]['body']), turns)
            stages[name+'_proposals'] += len(cs)
            stages[name+'_invalid_quotes'] += sum(not c['evidence_span_valid'] for c in cs)
            stages[name+'_rendered_quotes'] += sum(any(e.get('rendering') for e in c['evidence']) for c in cs)
            stages[name+'_at_ten_cap'] += len(cs) == 10
            groups.append([dict(c,proposal_sources=[name]) for c in cs
                           if c['evidence_span_valid'] and (i==0 or c['confidence']>=.8)])
        candidates = alg.merge(*groups)
        stages['merged_candidates'] += len(candidates)
        pool_by_did[did] = candidates
        if len(p['task_ids']) < 3:
            continue
        req = json.loads(requests[p['task_ids'][2]]['messages'][1]['content'])
        assert req['candidates'] == candidates
        stages['judge_requests_with_generator_confidence'] += all('confidence' in c for c in req['candidates'])
        ds = alg.validate_decisions(decode(valid[p['task_ids'][2]]['body']),turns,candidates)
        by = {d['candidate_id']:d for d in ds}
        for c in candidates:
            d = by[c['candidate_id']]
            stages['judge_'+d['verdict']] += 1
            stages['keep_below_070'] += d['verdict']=='keep' and d['confidence']<.7
            m = matchby[did].get(digest(c['claim']))
            category = 'final' if d['verdict']=='keep' and d['confidence']>=.7 else 'excluded'
            coverage[category]['total'] += 1
            coverage[category]['cached'] += m is not None
            if m is not None:
                coverage[category][m['relation']] += 1
            else:
                unknown_candidates.append(dict(dialogue_id=did,claim=c,decision=d))
    save(OUT / 'stage_accounting.json', dict(counts=dict(stages),costs=dict(stage_costs),
        original_model_tokens=sum(c['tokens_observed'] for c in stage_costs.values()),
        filtering_does_not_reduce_inference_tokens=True))
    save(OUT / 'proposal_match_coverage.json', dict(groups=dict(coverage),
         caution='Missing exact cached matches are unknown, never treated as false.'))
    save(OUT / 'uncached_proposals.json', unknown_candidates)
    # Maximum matching with broader edges is a diagnostic ceiling of the
    # available semantic overlaps, not an achievable strict-equivalence result.
    diagnostic = []
    for policy in [('equivalent',), ('equivalent','broader')]:
        rows = [score_item(p, refs[(p['dialogue_id'],p['direction'])],
                matches[p['dialogue_id']],costs,accepted_relations=policy) for p in ps]
        diagnostic.append(dict(accepted=list(policy), **four_metrics(rows)))
    save(OUT / 'granularity_diagnostic.json', diagnostic)
    # Internal cross-fitting only. V2 and the rule family were already informed
    # by the full development set, so this is NOT an untouched test evaluation.
    params = [(a,b) for a in [.8,.85,.9,.95] for b in [.85,.9,.95]]
    pool = {(a,b):rows_for(lambda c,a=a,b=b: c['confidence'] >=
                         (a if c['mechanism']=='explicit' else b)) for a,b in params}
    ids = sorted(p['dialogue_id'] for p in ps)
    random.Random(113).shuffle(ids)
    folds = {did:i%5 for i,did in enumerate(ids)}
    assembled, selections = [], []
    for fold in range(5):
        choices = []
        for par, rows in pool.items():
            train = four_metrics([r for r in rows if folds[r['dialogue_id']]!=fold])
            if train['precision'] is not None and train['precision'] >= .20:
                choices.append((train['grounded_recall'],train['recall'],train['precision'],par))
        if choices:
            par = max(choices)[-1]
            test = [r for r in pool[par] if folds[r['dialogue_id']]==fold]
        else:
            par = None
            test = [dict(r,predictions=0,correct_output_assertions=0,true_tp=0,supported_tp=0)
                    for r in selected_rows['v2_primary'] if folds[r['dialogue_id']]==fold]
        assembled.extend(test)
        selections.append(dict(fold=fold,parameters=par,test_inputs=len(test)))
    assert len(assembled)==298
    save(OUT / 'internal_crossfit.json', dict(folds=5,seed=113,train_precision_floor=.20,
         selections=selections,metrics=four_metrics(assembled),independent_test=False,
         caution='Only threshold choice is out of fold; prompts and rule family have full-development-set history.'))
    # Inputs/protected artifacts are hashed to make the analysis reviewable.
    save(OUT / 'manifest.json',dict(new_api_calls=0,original_artifacts_modified=False,
        inputs_sha256=filehash(BASE/'inputs/dailydialog.json'),
        prediction_sha256=filehash(BASE/'runs/efcr_append_v2/exports/dailydialog.json'),
        reference_sha256=filehash(BASE/'references/dailydialog_human_adjudicated_588.json'),
        joint_results_sha256=filehash(source/'four_metrics_both_policies.json'),
        script_sha256=filehash(Path(__file__))))
    print('SELECTORS',[(r['rule'],r['precision'],r['recall'],r['grounded_recall'],r['output_assertions']) for r in tables])
    print('STAGES',dict(stages))
    print('COSTS',dict(stage_costs))
    print('COVERAGE',dict(coverage))
    print('CROSSFIT',four_metrics(assembled))


if __name__ == '__main__':
    main()
