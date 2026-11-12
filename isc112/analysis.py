"""Score all 112 dialogues together using the existing frozen semantic decisions."""
import collections
import math
import statistics

from .io import DATA, OUT, read, save, write_csv, review_key
from .statistics import maximum_match, bootstrap_mean, bootstrap_ratio

ARMS = ['direct_off', 'direct_on', 'dual_off', 'dual_on']
ARM_LABELS = {'direct_off': '直接＋关', 'direct_on': '直接＋开', 'dual_off': '双路＋关', 'dual_on': '双路＋开'}
CONTRASTS = {
    'thinking_in_direct': {'direct_on': 1, 'direct_off': -1},
    'thinking_in_dual': {'dual_on': 1, 'dual_off': -1},
    'pipeline_without_thinking': {'dual_off': 1, 'direct_off': -1},
    'pipeline_with_thinking': {'dual_on': 1, 'direct_on': -1},
    'interaction': {'dual_on': 1, 'dual_off': -1, 'direct_on': -1, 'direct_off': 1},
}

def prefix_experiments(dialogues, refs):
    reviews = {r['review_id']: r for r in read(DATA / 'e1_e2/reviews.json')}
    predictions = read(DATA / 'e1_e2/predictions.json')
    by = {(p['dialogue_id'], p['k']): p for p in predictions}
    paths, full, claim_rows = [], [], []
    for d in dialogues:
        did = d['id']; K = (len(d['turns']) + 1) // 2; cumulative = set()
        for k in range(1, K + 1):
            p = by[did, k]
            available = {f['id'] for f in refs[did] if f['first_A_prefix'] is not None and f['first_A_prefix'] <= k}
            edges, grounded_edges, grounded = [], [], set()
            statuses = collections.Counter(); unsupported = contradicted = 0
            for f in p['facts']:
                r = reviews[review_key(did, f, 'e1_e2')]; kind = r['kind']; statuses[kind] += 1
                targets = r['reference_ids'] if kind == 'match' else []
                good = r['A_grounded'] is True and r['source_status'] == 'consistent'
                edges.append(targets)
                grounded_edges.append([fid for fid in targets if good and fid in available])
                if kind in ['match', 'partial'] and good:
                    grounded.update(fid for fid in r['reference_ids'] if fid in available)
                if kind == 'supported_new' and good:
                    grounded.add(r['canonical_id'])
                unsupported += r['A_grounded'] is not True
                contradicted += r['source_status'] == 'contradicted'
                if k == K:
                    claim_rows.append({'dialogue_id': did, 'claim': f['claim'], 'review_id': r['review_id'],
                        'kind': kind, 'A_grounded': r['A_grounded'], 'source_status': r['source_status'],
                        'reference_ids': '|'.join(r['reference_ids']), 'rationale': r['rationale']})
            cumulative |= grounded
            row = {'dialogue_id': did, 'K': K, 'k': k, 'raw_claims': len(p['facts']),
                'exact_reference_matches': len(maximum_match(edges)),
                'grounded_exact_reference_matches': len(maximum_match(grounded_edges)),
                'current_attributes': len(grounded), 'cumulative_attributes': len(cumulative),
                'available_reference_count': len(available), 'full_reference_count': len(refs[did]),
                'grounded_ids': sorted(grounded)}
            paths.append(row)
            if k == K:
                full.append({**row, 'unsupported_or_uncertain': unsupported, 'source_contradicted': contradicted,
                             'review_kinds': dict(statuses)})
    index = {(r['dialogue_id'], r['k']): r for r in paths}
    fullref = [r['full_reference_count'] for r in full]; supported = [r['available_reference_count'] for r in full]
    exact = [r['exact_reference_matches'] for r in full]; ground = [r['grounded_exact_reference_matches'] for r in full]
    normalized = []
    for fraction in [0, .25, .5, .75, 1]:
        for measure in ['raw_claims', 'current_attributes', 'cumulative_attributes', 'available_reference_count']:
            vals = [0 if fraction == 0 else index[d['id'], math.ceil(((len(d['turns']) + 1) // 2) * fraction)][measure] for d in dialogues]
            normalized.append({'fraction': fraction, 'measure': measure, **bootstrap_mean(vals)})
    fixed = []
    for K in sorted({r['K'] for r in paths}):
        ids = sorted(r['dialogue_id'] for r in full if r['K'] == K)
        for k in range(1, K + 1):
            vals = [index[did, k]['current_attributes'] for did in ids]
            fixed.append({'K': K, 'k': k, **bootstrap_mean(vals)})
    declines, deltas = [], []
    for r in full:
        did = r['dialogue_id']; K = r['K']; first = index[did, 1]['current_attributes']
        deltas.append({'dialogue_id': did, 'K': K, 'first': first, 'final': r['current_attributes'], 'delta': r['current_attributes'] - first})
        for k in range(2, K + 1):
            before, after = index[did, k - 1]['current_attributes'], index[did, k]['current_attributes']
            if after < before:
                declines.append({'dialogue_id': did, 'from_k': k - 1, 'to_k': k, 'from_count': before, 'to_count': after})
    raw = sum(r['raw_claims'] for r in full); nmatch = sum(exact); p = nmatch / raw; recall = nmatch / sum(fullref)
    summary = {'dialogues': len(dialogues), 'valid_full_dialogues': len(full), 'complete_prefix_paths': len(full),
        'full_reference_count': sum(fullref), 'A_supported_reference_count': sum(supported), 'raw_claims': raw,
        'exact_reference_matches': nmatch, 'grounded_exact_reference_matches': sum(ground),
        'full_reference_coverage': bootstrap_ratio(exact, fullref),
        'grounded_full_reference_coverage': bootstrap_ratio(ground, fullref),
        'A_supported_recovery': bootstrap_ratio(ground, supported),
        'reference_agreement_precision': p, 'reference_agreement_F1': 2 * p * recall / (p + recall),
        'unsupported_or_uncertain': sum(r['unsupported_or_uncertain'] for r in full),
        'source_contradicted': sum(r['source_contradicted'] for r in full),
        'first_to_full_delta': bootstrap_mean([r['delta'] for r in deltas]),
        'positive_delta_paths': sum(r['delta'] > 0 for r in deltas), 'zero_delta_paths': sum(r['delta'] == 0 for r in deltas),
        'negative_delta_paths': sum(r['delta'] < 0 for r in deltas),
        'paths_with_declines': len({r['dialogue_id'] for r in declines}), 'declining_transitions': len(declines)}
    save(OUT / 'e1_e2/summary.json', summary); save(OUT / 'e1_e2/dialogue_scores.json', full)
    save(OUT / 'e1_e2/prefix_scores.json', paths)
    save(OUT / 'e1_e2/prefix_analysis.json', {'normalized': normalized, 'fixed_K': fixed, 'declines': declines, 'first_final_deltas': deltas})
    write_csv(OUT / 'e1_e2/full_claim_review.csv', claim_rows)
    write_csv(OUT / 'e1_e2/dialogue_scores.csv', [{k: v for k, v in r.items() if k not in ['grounded_ids', 'review_kinds']} for r in full])
    write_csv(OUT / 'e1_e2/prefix_scores.csv', [{**r, 'grounded_ids': '|'.join(r['grounded_ids'])} for r in paths])
    return summary, full

def factorial_experiment(dialogues, refs):
    reviews = {r['review_id']: r for r in read(DATA / 'e3/reviews.json')}
    predictions = {(p['dialogue_id'], p['arm']): p for p in read(DATA / 'e3/predictions.json')}
    ledger = read(DATA / 'e3/cost_ledger.json'); costs = collections.defaultdict(list)
    for r in ledger:
        costs[r['dialogue_id'], r['arm']].append(r)
    rows = []
    for d in dialogues:
        did = d['id']; supported = {f['id'] for f in refs[did] if f['A_support_sets']}
        for arm in ARMS:
            p = predictions[did, arm]; atoms, edges, new = set(), [], set()
            unsupported = outscope = contradicted = grounded_raw = 0
            for f in p['facts']:
                r = reviews[review_key(did, f, 'e3')]
                assert len(r['reference_ids']) <= 1 or r.get('conjunctive_atoms') is True
                exact = [fid for fid in r['reference_ids'] if fid in supported and r['A_grounded'] is True]
                core = r.get('grounded_reference_ids', exact)
                assert set(core) <= set(r['reference_ids'])
                edges.append(exact); atoms.update(fid for fid in core if fid in supported)
                unsupported += r['A_grounded'] is not True
                outscope += r['verdict'] == 'out_of_scope'
                contradicted += r['source_status'] == 'contradicted'
                grounded_raw += r['A_grounded'] is True and r['source_status'] == 'consistent' and r['verdict'] != 'out_of_scope'
                if r['verdict'] == 'supported_new':
                    new.add(r.get('canonical_id', r['review_id']))
            calls = costs[did, arm]
            total = lambda key: sum(r.get(key) or 0 for r in calls)
            rows.append({'dialogue_id': did, 'arm': arm, 'A_reference_count': len(supported), 'full_reference_count': len(refs[did]),
                'atomic_coverage': len(atoms), 'one_to_one_coverage': len(maximum_match(edges)), 'atomic_ids': sorted(atoms),
                'raw_claims': len(p['facts']), 'hypotheses': len(p['hypotheses']), 'unsupported_or_uncertain': unsupported,
                'out_of_scope': outscope, 'source_contradicted': contradicted, 'grounded_in_scope_raw': grounded_raw,
                'supported_new': len(new), 'actual_calls': len(calls), 'total_tokens': total('total_tokens'),
                'reasoning_tokens': total('reasoning_tokens'), 'recorded_call_seconds': total('elapsed_seconds')})
    by = {(r['dialogue_id'], r['arm']): r for r in rows}; ids = [d['id'] for d in dialogues]
    metrics = ['A_reference_count', 'full_reference_count', 'atomic_coverage', 'one_to_one_coverage', 'raw_claims',
               'hypotheses', 'unsupported_or_uncertain', 'out_of_scope', 'source_contradicted', 'grounded_in_scope_raw', 'supported_new', 'actual_calls', 'total_tokens']
    methods = []
    for arm in ARMS:
        rr = [by[did, arm] for did in ids]
        methods.append({'arm': arm, 'label': ARM_LABELS[arm], 'dialogues': len(rr),
            **{m: sum(r[m] for r in rr) for m in metrics},
            'coverage': bootstrap_ratio([r['atomic_coverage'] for r in rr], [r['A_reference_count'] for r in rr]),
            'unsupported_fraction': bootstrap_ratio([r['unsupported_or_uncertain'] for r in rr], [r['raw_claims'] for r in rr]),
            'tokens_per_dialogue': bootstrap_mean([r['total_tokens'] for r in rr]),
            'mean_reasoning_tokens': statistics.mean(r['reasoning_tokens'] for r in rr)})
    largest = max(ids, key=lambda did: len([f for f in refs[did] if f['A_support_sets']]))
    effects = []
    for name, weights in CONTRASTS.items():
        values = [sum(w * by[did, arm]['atomic_coverage'] for arm, w in weights.items()) for did in ids]
        without = [v for did, v in zip(ids, values) if did != largest]
        effects.append({'name': name, 'weights': weights, 'net_reference_count': sum(values), 'per_dialogue': bootstrap_mean(values),
            'without_high_density': bootstrap_mean(without), 'excluded_dialogue': largest,
            'positive': sum(v > 0 for v in values), 'zero': sum(v == 0 for v in values), 'negative': sum(v < 0 for v in values),
            'dialogue_differences': dict(zip(ids, values))})
    sets = {arm: set().union(*(set(by[did, arm]['atomic_ids']) for did in ids)) for arm in ARMS}
    universe = [f['id'] for did in ids for f in refs[did] if f['A_support_sets']]
    patterns = collections.Counter(''.join('1' if fid in sets[arm] else '0' for arm in ARMS) for fid in universe)
    intersections = {'universe': len(universe), 'method_order': ARMS,
        'patterns': [{'pattern': k, 'count': v} for k, v in sorted(patterns.items(), key=lambda kv: (kv[0] == '0000', -kv[1], kv[0]))],
        'covered_by_any': len(set().union(*sets.values())), 'covered_by_all': len(set.intersection(*sets.values())),
        'uncovered_by_all': patterns['0000'],
        'exclusive_to': {arm: len(sets[arm] - set().union(*(s for a, s in sets.items() if a != arm))) for arm in ARMS}}
    summary = {'dialogues': len(ids), 'methods': methods, 'effects': effects, 'actual_calls': len(ledger),
               'actual_tokens': sum(r.get('total_tokens') or 0 for r in ledger), 'high_density_dialogue': largest}
    save(OUT / 'e3/summary.json', summary); save(OUT / 'e3/dialogue_scores.json', rows)
    save(OUT / 'e3/reference_intersections.json', intersections)
    write_csv(OUT / 'e3/dialogue_scores.csv', [{**r, 'atomic_ids': '|'.join(r['atomic_ids'])} for r in rows])
    write_csv(OUT / 'e3/method_scores.csv', [{k: v for k, v in m.items() if k not in ['coverage', 'unsupported_fraction', 'tokens_per_dialogue']} for m in methods])
    return summary, rows

def analyze():
    from .data import check
    check(); ds = read(DATA / 'dialogues.json'); refs = {r['dialogue_id']: r['facts'] for r in read(DATA / 'reference.json')}
    s12, full = prefix_experiments(ds, refs); s3, factor = factorial_experiment(ds, refs)
    baseline = {r['dialogue_id']: r for r in factor if r['arm'] == 'direct_off'}
    den = [r['available_reference_count'] for r in full]
    e1 = [r['grounded_exact_reference_matches'] for r in full]
    e3 = [baseline[r['dialogue_id']]['one_to_one_coverage'] for r in full]
    assert all(r['available_reference_count'] == baseline[r['dialogue_id']]['A_reference_count'] for r in full)
    alignment = {'dialogues': len(full), 'A_supported_reference_count': sum(den),
                 'e1': bootstrap_ratio(e1, den), 'e3_direct_off': bootstrap_ratio(e3, den),
                 'paired_difference': bootstrap_ratio([b - a for a, b in zip(e1, e3)], den),
                 'policy': 'same 112 dialogues, same 138 frozen A-supported references, grounded one-to-one strict matching; prompts differ'}
    save(OUT / 'baseline_alignment.json', alignment)
    prefix_ledger = read(DATA / 'e1_e2/cost_ledger.json')
    accounting = {'dialogues': 112, 'nonempty_prefix_calls': 458, 'shared_empty_input_calls': 1,
        'logical_factorial_calls': 896, 'logical_final_results': 448,
        'actual_prefix_calls_including_failed_attempts': len(prefix_ledger), 'actual_factorial_calls_including_failed_attempts': s3['actual_calls'],
        'actual_total_calls': len(prefix_ledger) + s3['actual_calls'],
        'actual_total_tokens': sum(r.get('total_tokens') or 0 for r in prefix_ledger) + s3['actual_tokens']}
    save(OUT / 'accounting.json', accounting)
    return {'dialogues': 112, 'full_reference_coverage': s12['full_reference_coverage']['estimate'],
            'A_supported_recovery': s12['A_supported_recovery']['estimate'], 'actual_total_calls': accounting['actual_total_calls']}
