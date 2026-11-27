"""Append ELARA v1 ablations to the original AGD's frozen scoring view."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
import csv
import getpass
import hashlib
import os
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace

from . import common
from .run_ELARA_v1_ablation import AGD, ALGORITHM, METHODS, RUN, TOKEN_PLAN, VARIANTS

APPEND = common.BASE / 'agd_append_elara_v1_1_20261123'
sys.path.insert(0, str(APPEND))
try:
    import append_eval as append
finally:
    sys.path.remove(str(APPEND))
agd, transport = append.a, append.transport
WORK = RUN / 'agd'
JUDGE = 'qwen3.8-max'
OLD_JUDGE = 'qwen3.8-max-0902'
BOOTSTRAPS = 2000


def check_protocol(base):
    manifest = common.read(AGD.parent / 'judge_prompt_manifest.json')
    if manifest['model'] != OLD_JUDGE or base['model'] != OLD_JUDGE:
        raise ValueError('Historic AGD evaluation model changed')
    for name, expected in manifest['systems_sha256'].items():
        if hashlib.sha256(getattr(agd, name).encode()).hexdigest() != expected:
            raise ValueError('Historic AGD prompt changed: ' + name)
    paths = [AGD / 'data.json', AGD / 'results' / 'summary.json']
    facts = []
    for did in base['dialogues']:
        for stage in ('pred', 'sweep', 'gold', 'sweep_support', 'pool'):
            paths.append(agd.path_for(AGD, stage, did))
        facts.extend(common.read(agd.path_for(AGD, 'pool', did))['facts'])
    slots = [slot for fact in facts for slot in fact['slots']]
    if (len(base['dialogues']) != 298 or len(facts) != 1630 or len(slots) != 3985
            or Counter(f['level'] for f in facts) != {'E1': 511, 'E2': 1119}
            or sum(s['weight'] for s in slots) != 6352
            or any(not s['required'] or s['weight'] != (2 if s['core'] else 1) for s in slots)):
        raise ValueError('Unexpected frozen AGD denominator or slot weights')
    protocol = {
        'historical_judge': OLD_JUDGE, 'requested_append_judge': JUDGE,
        'provider_reported_model_in_preflight': JUDGE,
        'append_endpoint': TOKEN_PLAN, 'judge_temperature': 0,
        'support_batch_size': 12, 'support_output_tokens': 12000, 'support_thinking_budget': 4096,
        'mapping_output_tokens': 16000, 'mapping_thinking_budget': 8192,
        'mapping_prompt_sha256': hashlib.sha256(append.MATCH_SYSTEM.encode()).hexdigest(),
        'original_prompt_sha256': manifest['systems_sha256'], 'paired_bootstraps': BOOTSTRAPS,
        'frozen_source_sha256': {str(path.relative_to(AGD)): common.filehash(path) for path in paths},
    }
    common.freeze(WORK / 'protocol.json', protocol)
    return protocol


def prediction_paths(did):
    return {variant: RUN / 'predictions' / variant / f'{did}.json' for variant in VARIANTS}


def collect(did, dialogue, paths):
    updated = deepcopy(dialogue)
    known = {candidate['id']: candidate for candidate in updated['pred_candidates']}
    new = {}
    counts = {}
    for variant, path in paths.items():
        prediction = common.read(path)
        method = METHODS[variant]
        if prediction['dialogue_id'] != did or prediction['method'] != method:
            raise ValueError('Prediction identity mismatch: ' + str(path))
        counts[variant] = {'raw_predictions': len(prediction['claims']), 'new_raw_predictions': 0}
        for index, claim in enumerate(prediction['claims']):
            text = claim['claim']
            candidate_id = 'p_' + agd.stable_hash({'did': did, 'text': agd.clean_claim(text)})[:14]
            prior = known.get(candidate_id) or new.get(candidate_id)
            if prior and agd.clean_claim(prior['claim']) != agd.clean_claim(text):
                raise ValueError('AGD candidate ID collision')
            if candidate_id not in known:
                new.setdefault(candidate_id, {'id': candidate_id, 'claim': text})
                counts[variant]['new_raw_predictions'] += 1
            updated['predictions'].append({'id': method + ':' + str(index), 'algorithm': method,
                                           'claim': text, 'candidate_id': candidate_id})
    new = sorted(new.values(), key=lambda candidate: candidate['id'])
    updated['pred_candidates'].extend(new)
    return updated, new, counts


def match_atoms(did, turns, assessed, pool):
    atoms = [{'atom_id': item['id'] + '::' + str(index), 'claim': atom['text'],
              'turn_ids': atom['turn_ids'], 'level': atom['label']}
             for item in assessed for index, atom in enumerate(item['atoms']) if atom['label'] in agd.VALID]
    atoms.sort(key=lambda a: agd.stable_hash(a['atom_id']))
    ids = {f'a{index:04d}': atom['atom_id'] for index, atom in enumerate(atoms)}
    blind = [dict(atom, atom_id=short) for short, atom in zip(ids, atoms)]
    facts = [{k: deepcopy(fact[k]) for k in ('id', 'canonical_claim', 'level', 'slots')}
             for fact in pool['facts']]
    if not blind:
        return [], []
    if not facts:
        return [], [dict(atom, fact_id=None, slot_ids=[], reason='Frozen pool is empty', outside_detail='')
                    for atom in atoms]
    result, _ = transport.call(
        'append_coverage', did, 0, append.MATCH_SYSTEM,
        {'visible_turns': turns, 'atoms': blind, 'frozen_facts': facts},
        lambda obj: append.validate_matches(obj, blind, facts), 16000,
    )
    mapped, outside = [], []
    atom_text = {atom['atom_id']: atom['claim'] for atom in atoms}
    for row in result['assignments']:
        aid = ids[row['atom_id']]
        assignment = dict(row, atom_id=aid, claim=atom_text[aid])
        if row['fact_id'] is None or row.get('outside_detail'):
            outside.append(assignment)
        if row['fact_id'] is not None:
            mapped.append(assignment)
    return mapped, outside


def process(did, dialogue, paths):
    reviewed = WORK / 'complete' / f'{did}.json'
    while not all(path.exists() for path in paths.values()):
        if transport.STOP.is_set() or (RUN / 'inference_status.json').exists():
            raise RuntimeError('Incomplete inference or stopped provider')
        time.sleep(3)
    digests = {variant: common.filehash(path) for variant, path in paths.items()}
    if reviewed.exists():
        result = common.read(reviewed)
        if result['predictions_sha256'] == digests:
            return result
    updated, candidates, counts = collect(did, dialogue, paths)
    turns = dialogue['visible_turns']
    original_pred = common.read(agd.path_for(AGD, 'pred', did))
    pool = common.read(agd.path_for(AGD, 'pool', did))
    assessed = []
    batches = agd.make_support_batches(did, {'pred_candidates': candidates}, 'pred', 12)
    for index, batch in enumerate(batches):
        rows, mapping = transport.blinded(batch)
        result, _ = transport.call('append_pred', did, index, agd.SUPPORT_SYSTEM,
                                   {'visible_turns': turns, 'candidates': rows},
                                   lambda obj: transport.validate_support(obj, rows, turns), 12000)
        assessed.extend(dict(row, id=mapping[row['id']]) for row in result['items'])
    pred = dict(original_pred, items=original_pred['items'] + assessed)
    agd.validate_support(pred, updated['pred_candidates'], turns)
    mapped, outside = match_atoms(did, turns, assessed, pool)
    facts = {fact['id']: fact for fact in pool['facts']}
    for row in mapped:
        facts[row['fact_id']]['members'].append({'atom_id': row['atom_id'], 'slot_ids': row['slot_ids']})
    for stage, result in (('pred', pred), ('pool', pool)):
        common.save(agd.path_for(WORK, stage, did), result)
    for stage in ('sweep', 'gold', 'sweep_support'):
        path = agd.path_for(WORK, stage, did)
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(agd.path_for(AGD, stage, did), path)
    result = {'predictions_sha256': digests, 'dialogue': updated, 'counts': counts, 'outside': outside,
              'new_unique_candidate_count': len(candidates)}
    common.save(reviewed, result)
    return result


def judge(base, workers):
    key = os.environ.get('TOKEN_PLAN_API_KEY') or getpass.getpass('Token Plan credential: ').strip()
    if not key:
        raise ValueError('TOKEN_PLAN_API_KEY is required')
    os.environ['DASHSCOPE_API_KEY'] = key  # Interface used by the existing AGD transport.
    transport.ROOT, transport.WORK = WORK, WORK
    transport.MODEL, transport.URL = JUDGE, TOKEN_PLAN + '/chat/completions'
    WORK.mkdir(parents=True, exist_ok=True)
    dialogues = base['dialogues']
    completed, errors = {}, {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process, did, dialogues[did], prediction_paths(did)): did
                   for did in sorted(dialogues)}
        for i, future in enumerate(as_completed(futures), 1):
            did = futures[future]
            try:
                completed[did] = future.result()
            except Exception as exc:
                errors[did] = str(exc).replace(key, '[REDACTED]')
                if len(errors) <= 5:
                    print('AGD ERROR', did, errors[did], flush=True)
            if i % 25 == 0 or i == len(futures):
                print(f'AGD complete {len(completed)}/{len(dialogues)}. Errors: {len(errors)}', flush=True)
    common.save(WORK / 'status.json', {'complete': len(completed), 'errors': errors})
    if errors:
        raise RuntimeError(f'AGD has incomplete dialogues: {len(errors)}')
    return completed


def score(base, reviewed, protocol):
    agd.METHODS = dict(base['methods'], **{METHODS[v]: name for v, name in VARIANTS.items()})
    base['methods'] = agd.METHODS
    for did, result in reviewed.items():
        base['dialogues'][did] = result['dialogue']
        before = common.read(agd.path_for(AGD, 'pool', did))['facts']
        after = common.read(agd.path_for(WORK, 'pool', did))['facts']
        if len(before) != len(after):
            raise ValueError('Frozen facts changed: ' + did)
        for orig, new in zip(before, after):
            expected = dict(new, members=new['members'][:len(orig['members'])])
            if expected != orig:
                raise ValueError('Frozen fields or prior coverage changed: ' + did)
    base['prediction_counts'] = dict(Counter(p['algorithm'] for d in base['dialogues'].values()
                                            for p in d['predictions']))
    common.save(WORK / 'data.json', base)
    agd.score(SimpleNamespace(work=str(WORK), allow_incomplete=False, bootstraps=BOOTSTRAPS))
    output = WORK / 'results'
    summary = common.read(output / 'summary.json')
    previous = common.read(AGD / 'results' / 'summary.json')
    for method, old in previous.items():
        if any(summary[method].get(key) != value for key, value in old.items() if key != 'counts'):
            raise ValueError('Historical result changed: ' + method)
    for path, digest in protocol['frozen_source_sha256'].items():
        if common.filehash(AGD / path) != digest:
            raise ValueError('Historical file changed: ' + path)
    pairs = common.read(output / 'paired_differences_CI95.json')
    metrics = ('P_raw', 'R_full', 'R_E1_full', 'R_E2_full', 'slot_coverage', 'useful_yield')
    baseline = summary[ALGORITHM.METHOD]
    fields = ('condition', 'raw_predictions', *metrics, 'delta_P_raw', 'delta_R_full',
              'delta_R_full_CI95_low', 'delta_R_full_CI95_high')
    rows = []
    for method in (ALGORITHM.METHOD, *METHODS.values()):
        current = summary[method]
        if (current['n_dialogues'], current['denom_pool'], current['denom_E1'], current['denom_E2']) != (298, 1630, 511, 1119):
            raise ValueError('An arm is missing frozen evaluation denominators')
        interval = pairs.get(method + ' - ' + ALGORITHM.METHOD)
        if method == ALGORITHM.METHOD:
            interval = [0, 0]
        elif interval is None:
            low, high = pairs[ALGORITHM.METHOD + ' - ' + method]
            interval = [-high, -low]
        row = {k: current[k] for k in ('raw_predictions', *metrics)}
        row.update(condition=agd.METHODS[method], delta_P_raw=current['P_raw'] - baseline['P_raw'],
                   delta_R_full=current['R_full'] - baseline['R_full'],
                   delta_R_full_CI95_low=interval[0], delta_R_full_CI95_high=interval[1])
        rows.append(row)
    with (output / 'ablation_metrics.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    outside = [dict(row, dialogue_id=did) for did, result in reviewed.items() for row in result['outside']]
    common.save(output / 'outside_pool_grounded_atoms.json', outside)
    common.save(output / 'checks.json', {'old_six_metrics_identical': True, 'frozen_files_unchanged': True,
                                        'dialogues': 298, 'facts': 1630, 'slots': 3985,
                                        'new_unique_candidates': sum(result['new_unique_candidate_count']
                                                                     for result in reviewed.values()),
                                        'outside_pool_grounded_atoms': sum(r['fact_id'] is None for r in outside)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=12)
    parser.add_argument('--score-only', action='store_true')
    args = parser.parse_args()
    base = common.read(AGD / 'data.json')
    protocol = check_protocol(base)
    if args.score_only:
        reviewed = {}
        for did in base['dialogues']:
            result = common.read(WORK / 'complete' / f'{did}.json')
            hashes = {variant: common.filehash(path) for variant, path in prediction_paths(did).items()}
            if result['predictions_sha256'] != hashes:
                raise ValueError('Predictions changed since review: ' + did)
            reviewed[did] = result
    else:
        reviewed = judge(base, args.workers)
    score(base, reviewed, protocol)


if __name__ == '__main__':
    main()
