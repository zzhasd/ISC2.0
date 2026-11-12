"""Read-only EFCR diagnosis and exploratory cached-output ablations.

No model calls, prompt edits, or modifications to published experiment artifacts.
New artifacts are written only to results/efcr_diagnostics.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from .common import BASE, read, save, jsonlines, digest
from .inference import METHODS, decode
from .evaluation import reference_map, score_item
from .statistics import four_metrics, matching
from . import EFCR

OUT = BASE / 'results/efcr_diagnostics'


def main():
    inputs = {r['dialogue_id']: r for r in read(BASE / 'inputs/dailydialog.json')}
    refs = reference_map('dailydialog')
    ef = {p['dialogue_id']: p for p in read(BASE / 'runs/efcr_append_v1/exports/dailydialog.json')}
    old = defaultdict(dict)
    for p in read(BASE / 'runs/main/exports/dailydialog.json'):
        old[p['dialogue_id']][p['method']] = p
    em = {did: {m['prediction_id']: m for m in read(BASE / 'results/efcr_append_v1/matches' /
            (did + '__A_to_B.json'))['matches']} for did in inputs}
    bm = {did: {m['prediction_id']: m for m in read(BASE / 'results/prompts_v2/matches' /
            (did + '__A_to_B.json'))['matches']} for did in inputs}
    # Identical strings occasionally get different judgements in separately
    # supplied inventories. Never silently overwrite those inconsistencies.
    conflicts = []
    for did in inputs:
        for pid in em[did].keys() & bm[did].keys():
            if em[did][pid] != bm[did][pid]:
                conflicts.append(dict(dialogue_id=did, prediction_id=pid,
                                      efcr=em[did][pid], baseline=bm[did][pid]))
    save(OUT / 'exact_text_matcher_conflicts.json', conflicts)

    def evaluate(groups, policy=('equivalent',), mixed=False):
        rows = []
        for did, cs in groups.items():
            p = dict(ef[did], claims=cs, task_ids=[])
            ms = dict(bm[did]) if mixed else {}
            ms.update(em[did])  # fixed EFCR judgement takes precedence for overlaps
            assert all(digest(c['claim']) in ms for c in cs)
            rows.append(score_item(p, refs[(did, 'A_to_B')], list(ms.values()), {},
                                   accepted_relations=policy))
        result = four_metrics(rows)
        result.pop('mean_tokens')
        result.pop('tokens')
        return result, rows

    base, base_rows = evaluate({did: p['claims'] for did, p in ef.items()})
    stage = Counter()
    candidate_rows, proposal_examples, invalid_quotes = [], [], []
    by_task = {}
    for row in jsonlines(BASE / 'runs/efcr_append_v1/attempts.jsonl'):
        if row['event'] == 'complete' and row.get('valid'):
            by_task.setdefault(row['task_id'], row)
    for did, p in ef.items():
        turns = inputs[did]['visible_turns']
        proposed = EFCR.validate_claims(decode(by_task[p['task_ids'][0]]['body']), turns)
        candidates = EFCR.evidence_candidates(proposed)
        stage['proposed'] += len(proposed)
        stage['invalid_citation'] += sum(not c['evidence_span_valid'] for c in proposed)
        stage['valid_candidates'] += len(candidates)
        stage['proposal_empty_dialogues'] += not proposed
        stage['at_10_claim_cap'] += len(proposed) == 10
        for c in proposed:
            if not c['evidence_span_valid']:
                invalid_quotes.append(dict(dialogue_id=did, claim=c, visible_turns=turns,
                    exact_cached_match=em[did].get(digest(c['claim'])) or bm[did].get(digest(c['claim']))))
        ds = []
        if len(p['task_ids']) == 2:
            ds = EFCR.validate_counterfactual(decode(by_task[p['task_ids'][1]]['body']), turns, candidates)
        decision = {d['candidate_id']: d for d in ds}
        for d in ds:
            stage[d['verdict']] += 1
            if d.get('render_rejection'):
                stage['citation_or_level_render_rejection'] += 1
        for c in candidates:
            d = decision[c['candidate_id']]
            pid = digest(c['claim'])
            match = em[did].get(pid) or bm[did].get(pid)
            candidate_rows.append(dict(dialogue_id=did, original=c, decision=d,
                                       original_cached_match=match))
            if match and match['relation'] == 'equivalent' and d['verdict'] != 'keep':
                proposal_examples.append(dict(dialogue_id=did, candidate=c, decision=d,
                                               original_match=match, visible_turns=turns))
    stage['final_outputs'] = sum(len(p['claims']) for p in ef.values())
    stage['final_empty_dialogues'] = sum(not p['claims'] for p in ef.values())
    save(OUT / 'candidate_trace.json', candidate_rows)
    save(OUT / 'stage_counts.json', dict(stage))
    save(OUT / 'known_correct_candidates_changed.json', proposal_examples)
    save(OUT / 'invalid_quote_examples.json', invalid_quotes)
    # Counts by final claim properties, using frozen semantic matches.
    subgroups = defaultdict(Counter)
    examples = defaultdict(list)
    for did, p in ef.items():
        rby = {r['claim_id']: r for r in refs[(did, 'A_to_B')]}
        for c in p['claims']:
            m = em[did][digest(c['claim'])]
            keys = ['all', 'verdict:' + c['verifier']['verdict'],
                    'mechanism:' + c['mechanism'], 'certainty:' + c['certainty'],
                    'judge_level:' + c['verifier']['evidence_level']]
            for key in keys:
                subgroups[key][m['relation']] += 1
                subgroups[key]['total'] += 1
            if len(examples[m['relation']]) < 30:
                examples[m['relation']].append(dict(dialogue_id=did, prediction=c,
                    matches=[rby[rid] for rid in m['reference_ids']], visible_turns=inputs[did]['visible_turns']))
    save(OUT / 'claim_relations_by_group.json', dict(subgroups))
    save(OUT / 'relation_examples.json', dict(examples))
    levels = Counter(r['evidence_level'] for rs in refs.values() for r in rs)
    level_table = []
    for name in METHODS + ['EFCR']:
        hits = Counter()
        for did in inputs:
            p = ef[did] if name == 'EFCR' else old[did][name]
            ms = em[did] if name == 'EFCR' else bm[did]
            row = score_item(dict(p, task_ids=[]), refs[(did, 'A_to_B')], list(ms.values()), {})
            hits['E1'] += row['e1_hits']
            hits['E2'] += row['e2_hits']
            hits['non_grounded_additional'] += row['true_tp'] - row['supported_tp']
        level_table.append(dict(method=name, hits=dict(hits), denominators=dict(levels)))
    save(OUT / 'recall_by_reference_level.json', level_table)
    # All offline ablations are exploratory on the same 298 examples, never a
    # new independent experiment. No reference information enters their selectors.
    ablations = []
    def unique_union(core, extras):
        cs = list(core)
        seen = {digest(c['claim']) for c in cs}
        for c in extras:
            pid = digest(c['claim'])
            if pid not in seen:
                cs.append(c)
                seen.add(pid)
        return cs

    candidate_combos = {}
    for core_name, selector in [('no_repair', lambda c: c['verifier']['verdict'] == 'keep'),
                                ('confidence_0.7', lambda c: c['confidence'] >= .7)]:
        core = {did: [c for c in p['claims'] if selector(c)] for did, p in ef.items()}
        result, _ = evaluate(core)
        ablations.append(dict(name='EFCR_' + core_name, **result))
        for threshold in [.8, .9]:
            groups = {did: unique_union(core[did], [c for c in old[did]['route1_only']['claims']
                       if c['confidence'] >= threshold and c.get('evidence_span_valid')]) for did in inputs}
            result, rows = evaluate(groups, mixed=True)
            name = 'EFCR_' + core_name + '_plus_route1_' + str(threshold)
            ablations.append(dict(name=name, exploratory_cached_union=True, **result))
            candidate_combos[name] = dict(groups=groups, rows=rows)
    for threshold in [0, .7, .8, .85, .9, .95]:
        groups = {did: [c for c in p['claims'] if c['confidence'] >= threshold] for did, p in ef.items()}
        result, _ = evaluate(groups)
        ablations.append(dict(name='EFCR_confidence_' + str(threshold), **result))
    for mechanism in ['explicit', 'presupposition', 'coreference', 'causal', 'cross_turn']:
        groups = {did: [c for c in p['claims'] if c['mechanism'] != mechanism] for did, p in ef.items()}
        result, _ = evaluate(groups)
        ablations.append(dict(name='EFCR_without_' + mechanism, **result))
    for source in ['route1_only', 'direct_thinking', 'dual_with_verifier']:
        for threshold in [0, .8, .9, .95]:
            groups = {}
            for did, p in ef.items():
                cs = list(p['claims'])
                seen = {digest(c['claim']) for c in cs}
                for c in old[did][source]['claims']:
                    pid = digest(c['claim'])
                    if pid not in seen and c['confidence'] >= threshold and c.get('evidence_span_valid'):
                        cs.append(c)
                        seen.add(pid)
                groups[did] = cs
            result, _ = evaluate(groups, mixed=True)
            ablations.append(dict(name='EFCR_plus_' + source + '_confidence_' + str(threshold),
                                  exploratory_cached_union=True, **result))
    save(OUT / 'offline_ablations.json', ablations)
    # Paired dialogue bootstrap for uncertainty on an exploratory union;
    # intervals do not correct for trying several selectors on the same data.
    import random
    from .statistics import quantile
    intervals = {}
    for name, combo in candidate_combos.items():
        rng = random.Random(113)
        lookup = {r['dialogue_id']: r for r in base_rows}
        pairs = [(lookup[r['dialogue_id']], r) for r in combo['rows']]
        draws = defaultdict(list)
        for _ in range(2000):
            sample = [rng.choice(pairs) for _ in pairs]
            for metric, numerator, denominator in [('precision', 'correct_output_assertions', 'predictions'),
                    ('recall', 'true_tp', 'true_reference'),
                    ('grounded_recall', 'supported_tp', 'supported_reference')]:
                a = sum(x[numerator] for x, y in sample) / sum(x[denominator] for x, y in sample)
                b = sum(y[numerator] for x, y in sample) / sum(y[denominator] for x, y in sample)
                draws[metric].append(b-a)
        intervals[name] = {metric: [quantile(vals, .025), quantile(vals, .975)] for metric, vals in draws.items()}
    save(OUT / 'exploratory_paired_bootstrap.json', dict(
         intervals=intervals, resamples=2000, seed=113,
         warning='In-sample exploratory comparison; confidence intervals do not correct for selector search.'))
    empty = [did for did, p in ef.items() if not p['claims']]
    save(OUT / 'empty_output_analysis.json', dict(dialogues=len(empty),
         true_references=sum(len(refs[(did, 'A_to_B')]) for did in empty),
         reference_levels=dict(Counter(r['evidence_level'] for did in empty for r in refs[(did, 'A_to_B')]))))
    # Exact cached matches are only partial coverage of rejected/raw proposals.
    known = [r for r in candidate_rows if r['original_cached_match'] is not None]
    save(OUT / 'proposal_match_coverage.json', dict(total=len(candidate_rows),
         exact_cached_match_available=len(known),
         by_verdict={v: dict(total=sum(r['decision']['verdict'] == v for r in candidate_rows),
             cached=sum(r['decision']['verdict'] == v for r in known),
             known_equivalent=sum(r['decision']['verdict'] == v and
                 r['original_cached_match']['relation'] == 'equivalent' for r in known))
             for v in ['keep', 'repair', 'reject']},
         caution='No semantic judgement for uncached original candidates; no attribution beyond exact cache coverage.'))
    save(OUT / 'summary.json', dict(baseline=base, stage_counts=dict(stage),
         matcher_conflicts=len(conflicts), reference_levels=dict(levels),
         new_api_calls=0, original_artifacts_modified=False))
    print('stage', dict(stage))
    print('groups', dict(subgroups))
    print('levels', level_table)
    print('ablations', ablations)
    print('conflicts', len(conflicts))


if __name__ == '__main__':
    main()
