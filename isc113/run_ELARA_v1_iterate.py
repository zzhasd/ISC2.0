"""Run one ELARA-v1 ablation on 298 A-only dialogues, then score frozen AGD.

Run from the repository root. Use --replay for a change that leaves every
Flash request unchanged and emits only claims already judged in frozen AGD.
Without --replay, use QWEN_API_KEY or DASHSCOPE_API_KEY for live inference
and for any novel claims that require Max judgments. With --reuse-baseline-flash,
only stages passed via --live-stage are requested from Flash again.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from fnmatch import fnmatchcase
from getpass import getpass
from importlib import import_module
import os
from pathlib import Path
import sys

from isc113 import common
from isc113.client import Client
from isc113.inference import decode


BASELINE_METHOD = 'elara_evidence_lattice_v1'
BASELINE_RUN = common.BASE / 'runs/elara_append_v1'
FROZEN_INPUTS = common.BASE / 'inputs/dailydialog.json'
METRICS = {
    'P_raw': ('P_raw', 'raw_grounded', 'raw_count'),
    'R_full': ('R_full', 'pool_full', 'pool_total'),
    'R_E1_full': ('E1 Recall', 'E1_full', 'E1_total'),
    'R_E2_full': ('E2 Recall', 'E2_full', 'E2_total'),
    'slot_coverage': ('Slot Coverage', 'slot_weight_hit', 'slot_weight_total'),
    'useful_yield': ('Useful Yield', 'unique_core_found', 'raw_count'),
}


class RecordedFlash:
    """Use the original answer only when the logical name and payload match."""

    def __init__(self, ledger, recover=False):
        self.requests = {}
        self.answers = {}
        for row in common.jsonlines(ledger):
            task_id = row['task_id']
            if row['event'] == 'start':
                self.requests[task_id] = (row['logical_name'], row['request'])
            elif row['event'] == 'complete' and 'body' in row:
                if row.get('valid') or (recover and row.get('http_status') == 200):
                    self.answers.setdefault(task_id, []).append(row['body'])

    def call(self, name, payload, validate):
        task_id = common.digest({'logical_name': name, 'payload': payload})
        if (self.requests.get(task_id) != (name, payload)
                or task_id not in self.answers or payload['model'] != 'qwen3.8-flash'):
            raise ValueError(f'No exact valid Flash response for {name}')
        for answer in self.answers[task_id]:
            try:
                return validate(decode(answer)), task_id
            except (ValueError, KeyError, TypeError, IndexError):
                continue
        raise ValueError(f'No archive response passes validation for {name}')


def run_jobs(items, worker, workers, label):
    failures = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(worker, item): item for item in items}
        for done, job in enumerate(as_completed(futures), 1):
            try:
                job.result()
            except Exception as error:
                failures.append(str(error))
                print(f'{label} failed: {error}', flush=True)
            if done % 25 == 0 or done == len(futures):
                print(f'{label} {done}/{len(futures)}', flush=True)
    if failures:
        raise RuntimeError(f'{label} had {len(failures)} failures; see progress log')


def infer(algorithm, records, run, replay, key, workers, live_stages=(), recovery_ledger=None):
    mode = 'replay' if replay else ('paired' if live_stages else 'live')
    inputs_sha = common.digest(records)
    manifest = {
        'algorithm_sha256': common.filehash(algorithm.__file__),
        'inputs_sha256': inputs_sha,
        'method': algorithm.METHOD,
        'model': algorithm.MODEL,
        'scope_count': len(records),
        'mode': mode,
    }
    if live_stages:
        manifest['live_stages'] = list(live_stages)
    if replay or live_stages:
        original = common.read(BASELINE_RUN / 'method_manifest.json')
        if (inputs_sha != original['inputs_sha256'] or algorithm.MODEL != original['model']
                or common.filehash(common.BASE / 'ELARA-v1.py') != original['algorithm_sha256']):
            raise ValueError('The input, model or v1 source differs from the original run')
        ledger = BASELINE_RUN / 'attempts.jsonl'
        manifest['flash_ledger_sha256'] = common.filehash(ledger)
        recorded = RecordedFlash(ledger)
    if replay:
        client = recorded
    elif live_stages:
        live = Client(key, run_id=run.name)
        recovered = None
        if recovery_ledger is not None:
            manifest['recovered_ledger_sha256'] = common.filehash(recovery_ledger)
            recovered = RecordedFlash(recovery_ledger, recover=True)

        class PairedFlash:
            def call(self, name, payload, validate):
                stage = name.rsplit('/', 1)[-1]
                if not any(fnmatchcase(stage, pattern) for pattern in live_stages):
                    return recorded.call(name, payload, validate)
                if recovered is not None:
                    try:
                        return recovered.call(name, payload, validate)
                    except ValueError:
                        pass
                return live.call(name, payload, validate)

        client = PairedFlash()
    else:
        client = Client(key, run_id=run.name)
    common.freeze(run / 'method_manifest.json', manifest)
    common.freeze(run / 'inputs.json', records)

    def prediction_path(item):
        return run / 'predictions' / (item['dialogue_id'] + '__A_to_B.json')

    def work(item):
        prediction, diagnostics = algorithm.pipeline(client, item)
        common.save(run / 'diagnostics' / prediction_path(item).name, diagnostics)
        common.save(prediction_path(item), [prediction])

    pending = [item for item in records if not prediction_path(item).exists()]
    run_jobs(pending, work, workers, f'Flash {mode}')
    exports = []
    for item in records:
        prediction, = common.read(prediction_path(item))
        if (prediction['method'] != algorithm.METHOD
                or any(prediction[k] != item[k] for k in ('item_id', 'dialogue_id', 'direction', 'dataset'))):
            raise ValueError(f'Invalid prediction artifact for {item["item_id"]}')
        exports.append(prediction)
    if replay or live_stages:
        original_exports = common.read(BASELINE_RUN / 'exports/dailydialog.json')
        by_id = {row['item_id']: row for row in original_exports}
        if len(original_exports) != len(records) or set(by_id) != {row['item_id'] for row in exports}:
            raise ValueError('Original prediction identities do not match replay')
        for row in exports:
            parent = by_id[row['item_id']]
            if live_stages:
                expected = [
                    task_id for task_id in parent['task_ids']
                    if not any(fnmatchcase(recorded.requests[task_id][0].rsplit('/', 1)[-1], pattern)
                               for pattern in live_stages)
                ]
                reused = [task_id for task_id in row['task_ids'] if task_id in expected]
                if reused != expected:
                    raise ValueError(f'Paired control changed the unchanged calls for {row["item_id"]}')
            elif (row['task_ids'] != parent['task_ids']
                  or any(claim not in parent['claims'] for claim in row['claims'])):
                raise ValueError(f'Replay must use the original Flash calls and a subset of outputs: {row["item_id"]}')
    common.freeze(run / 'exports/dailydialog.json', exports)
    return exports


def evaluate(algorithm, records, exports, run, replay, key, workers, display_name):
    from isc113.agd_append_1sc_20261123 import evaluate as shared

    work = run / 'agd'
    shared.WORK = shared.append.ROOT = shared.append.WORK = work
    shared.transport.ROOT = shared.transport.WORK = work
    shared.SNAPSHOT = work / 'frozen/baseline'
    shared.RECON = algorithm.METHOD
    shared.METHODS = {algorithm.METHOD: display_name}
    data = shared.prepare()
    agd = shared.agd
    if replay and shared.transport.MODEL != 'qwen3.8-max-0902':
        raise ValueError('The frozen judgments use qwen3.8-max-0902')
    by_id = {row['dialogue_id']: row for row in exports}
    if set(by_id) != set(data['dialogues']):
        raise ValueError('Inference and AGD use different dialogue scopes')
    new_candidates = 0
    for item in records:
        did = item['dialogue_id']
        dialogue = data['dialogues'][did]
        if item['visible_turns'] != dialogue['visible_turns']:
            raise ValueError(f'Different visible turns in inference and AGD: {did}')
        known = {c['id'] for c in dialogue['pred_candidates']}
        added = {}
        prediction = by_id[did]
        new_predictions = []
        for i, claim in enumerate(prediction['claims']):
            claim_text = claim['claim']
            cid = 'p_' + agd.stable_hash({'did': did, 'text': agd.clean_claim(claim_text)})[:14]
            if cid not in known:
                added.setdefault(cid, {'id': cid, 'claim': claim_text})
            new_predictions.append({
                'id': f'{algorithm.METHOD}:{i}', 'algorithm': algorithm.METHOD,
                'claim': claim_text, 'candidate_id': cid,
            })
        dialogue['append_candidates'] = sorted(added.values(), key=lambda c: c['id'])
        dialogue['pred_candidates'].extend(dialogue['append_candidates'])
        dialogue['predictions'].extend(new_predictions)
        new_candidates += len(added)
    if replay and new_candidates:
        raise ValueError(f'Replay would need new Max judgments for {new_candidates} candidates')
    data['methods'].update(shared.METHODS)
    data['prediction_counts'][algorithm.METHOD] = sum(len(p['claims']) for p in exports)
    common.freeze(work / 'data.json', data)

    if key:
        os.environ['DASHSCOPE_API_KEY'] = key
    dialogues = data['dialogues']
    pending = [did for did in dialogues if not (work / 'complete' / f'{did}.json').exists()]
    run_jobs(pending, lambda did: shared.append.process(did, dialogues[did]), workers, 'AGD')
    for did in dialogues:
        before = agd.read(agd.path_for(shared.SNAPSHOT, 'pred', did))['items']
        after = agd.read(agd.path_for(work, 'pred', did))['items']
        if before != after[:len(before)]:
            raise ValueError(f'Frozen Max support judgments changed: {did}')
    shared.append.score()
    return work, shared.transport.MODEL, new_candidates


def report(work, method, model, new_candidates, mode):
    results = work / 'results'
    summary = common.read(results / 'summary.json')
    baseline, trial = summary[BASELINE_METHOD], summary[method]
    counts = {name: Counter() for name in (BASELINE_METHOD, method)}
    count_keys = {field for _, numerator, denominator in METRICS.values()
                  for field in (numerator, denominator)}
    with (results / 'per_dialogue.csv').open(encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle):
            if row['algorithm'] in counts:
                counts[row['algorithm']].update({key: int(row[key]) for key in count_keys})
    metrics = {}
    for key, (label, num, den) in METRICS.items():
        metrics[label] = {
            'baseline': baseline[key], 'trial': trial[key],
            'delta_pp': (trial[key] - baseline[key]) * 100,
            'baseline_counts': [counts[BASELINE_METHOD][num], counts[BASELINE_METHOD][den]],
            'trial_counts': [counts[method][num], counts[method][den]],
        }
    deltas = [row['delta_pp'] for row in metrics.values()]
    result = {
        'benefit': all(delta >= 0 for delta in deltas) and any(delta > 0 for delta in deltas),
        'criterion': 'No metric decreases and at least one increases',
        'inference_mode': mode,
        'new_flash_requests': sum(row['event'] == 'start'
                                  for row in common.jsonlines(work.parent / 'attempts.jsonl')),
        'agd_model': model,
        'new_max_candidates': new_candidates,
        'metrics': metrics,
    }
    common.save(results / 'comparison.json', result)
    print(f'Benefit: {result["benefit"]}', flush=True)
    for label, row in metrics.items():
        print(f'{label}: {row["baseline"]:.4%} -> {row["trial"]:.4%} ({row["delta_pp"]:+.4f} pp)')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iteration', type=int, default=1)
    parser.add_argument('--workers', type=int, default=12)
    parser.add_argument('--eval-workers', type=int, default=24)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--replay', action='store_true')
    modes.add_argument('--reuse-baseline-flash', action='store_true')
    parser.add_argument('--live-stage', action='append', default=[],
                        help='Stage name or glob to call live in paired mode')
    parser.add_argument('--recover-flash-ledger', type=Path,
                        help='Reuse matching responses from a prior paired Flash attempt')
    parser.add_argument('--prompt-key', action='store_true',
                        help='Read a DashScope key via the hidden terminal prompt')
    args = parser.parse_args()
    if min(args.iteration, args.workers, args.eval_workers) < 1:
        parser.error('The iteration and worker counts must be positive')
    if args.reuse_baseline_flash != bool(args.live_stage):
        parser.error('--reuse-baseline-flash and --live-stage must be used together')
    if args.recover_flash_ledger is not None and not args.reuse_baseline_flash:
        parser.error('--recover-flash-ledger requires --reuse-baseline-flash')
    key = None if args.replay else (os.getenv('QWEN_API_KEY') or os.getenv('DASHSCOPE_API_KEY'))
    if not args.replay and not key and args.prompt_key:
        if not sys.stdin.isatty():
            parser.error('--prompt-key requires an interactive terminal')
        key = getpass('DashScope API key: ').strip()
    if not args.replay and not key:
        parser.error('Set QWEN_API_KEY or DASHSCOPE_API_KEY for a live run, or use --replay')
    algorithm = import_module(f'isc113.ELARA-v1-temp{args.iteration}')
    records = common.read(FROZEN_INPUTS)
    if len(records) != 298 or len({row['item_id'] for row in records}) != 298:
        raise ValueError('Expected exactly 298 distinct frozen inputs')
    for row in records:
        common.validate_input(row)
    mode = 'replay' if args.replay else ('paired' if args.live_stage else 'live')
    suffix = '_recovered' if args.recover_flash_ledger is not None else ''
    run = common.run_folder(f'elara_v1_temp{args.iteration}_{mode}{suffix}')
    exports = infer(algorithm, records, run, args.replay, key, args.workers,
                    args.live_stage, args.recover_flash_ledger)
    display_name = f'ELARA v1-temp{args.iteration}'
    work, model, new_candidates = evaluate(algorithm, records, exports, run, args.replay,
                                           key, args.eval_workers, display_name)
    report(work, algorithm.METHOD, model, new_candidates, mode)


if __name__ == '__main__':
    main()
