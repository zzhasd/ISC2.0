"""Run semantic ELARA v1-temp3 on the 298 frozen inputs and score frozen AGD.

Run from the repository root with:
    python -m isc113.run_ELARA_v1_temp3 --prompt-key

QWEN_API_KEY and DASHSCOPE_API_KEY are also supported. Run the same command
again to resume. All prediction, request, and evaluation files use the
elara_v1_temp3_semantic run directory.
"""
from argparse import ArgumentParser
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from getpass import getpass
from importlib.util import module_from_spec, spec_from_file_location
import os

from . import common
from .client import Client


SOURCE = common.BASE / 'elara_temp3_semantic' / 'ELARA-v1-temp3.py'
INPUTS = common.BASE / 'inputs' / 'dailydialog.json'
RUN_ID = 'elara_v1_temp3_semantic'
DISPLAY_NAME = 'ELARA v1-temp3 (E4 + semantic equivalence)'
BASELINE = 'elara_evidence_lattice_v1'
JUDGE = 'qwen3.8-max'
METRICS = {
    'P_raw': 'P_raw',
    'R_full': 'R_full',
    'R_E1_full': 'E1 Recall',
    'R_E2_full': 'E2 Recall',
    'slot_coverage': 'Slot Coverage',
    'useful_yield': 'Useful Yield',
}


class Temp3Client(Client):
    def call(self, name, payload, validate):
        try:
            return super().call(name, payload, validate)
        except RuntimeError as error:
            if str(error) != f'Attempt limit exceeded: {name}':
                raise
        # Client has recorded a terminal result for every original attempt.
        # Preserve those records and retry the identical payload under a new name.
        return super().call(name + '/retry', payload, validate)


def run_jobs(items, work, workers, label):
    failures = []
    # Confirm the first uncached job succeeds before sending concurrent requests.
    if items:
        work(items[0])
        print(f'{label}: 1/{len(items)} new', flush=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(work, item): item for item in items[1:]}
        for done, future in enumerate(as_completed(futures), 2):
            try:
                future.result()
            except Exception as error:
                item = futures[future]
                name = item['item_id'] if isinstance(item, dict) else item
                failures.append(name)
                print(f'{label} failed for {name}: {error}', flush=True)
            if done % 10 == 0 or done == len(items):
                print(f'{label}: {done}/{len(items)} new; {len(failures)} failed', flush=True)
    if failures:
        raise RuntimeError(f'{label} failed for {len(failures)} dialogues')


def infer(run, records, key, workers):
    spec = spec_from_file_location('isc113._elara_temp3_semantic', SOURCE)
    algorithm = module_from_spec(spec)
    spec.loader.exec_module(algorithm)
    common.freeze(run / 'inference_manifest.json', {
        'source_sha256': common.filehash(SOURCE),
        'input_sha256': common.filehash(INPUTS),
        'count': len(records),
        'model': algorithm.MODEL,
        'method': algorithm.METHOD,
    })
    client = Temp3Client(key, run_id=RUN_ID)

    def prediction_path(item):
        return run / 'predictions' / f'{item["item_id"]}.json'

    def diagnostics_path(item):
        return run / 'diagnostics' / f'{item["dialogue_id"]}__A_to_B.json'

    def predict(item):
        prediction, diagnostics = algorithm.pipeline(client, item)
        common.save(diagnostics_path(item), diagnostics)
        common.freeze(prediction_path(item), [prediction])

    pending = [
        item for item in records
        if not prediction_path(item).exists() or not diagnostics_path(item).exists()
    ]
    print(f'Flash: {len(records) - len(pending)}/{len(records)} already complete', flush=True)
    run_jobs(pending, predict, workers, 'Flash')
    exports = []
    for item in records:
        prediction, = common.read(prediction_path(item))
        if prediction['method'] != algorithm.METHOD or any(
            prediction[field] != item[field] for field in ('item_id', 'dialogue_id', 'direction', 'dataset')
        ):
            raise ValueError(f'Prediction binding mismatch for {item["item_id"]}')
        exports.append(prediction)
    common.freeze(run / 'exports' / 'dailydialog.json', exports)
    return algorithm.METHOD, exports


def evaluate(run, method, records, exports, workers):
    from .agd_append_1sc_20261123 import evaluate as shared

    work = run / 'agd'
    shared.WORK = shared.append.ROOT = shared.append.WORK = work
    shared.transport.ROOT = shared.transport.WORK = work
    shared.SNAPSHOT = work / 'frozen' / 'baseline'
    shared.RECON = method
    shared.METHODS = {method: DISPLAY_NAME}
    shared.transport.MODEL = shared.agd.MODEL_DEFAULT = JUDGE
    data = shared.prepare()
    agd = shared.agd
    dialogues = data['dialogues']
    if {item['dialogue_id'] for item in records} != set(dialogues):
        raise ValueError('Inference and frozen AGD dialogue IDs differ')

    for item, prediction in zip(records, exports, strict=True):
        did = item['dialogue_id']
        dialogue = dialogues[did]
        if dialogue['visible_turns'] != item['visible_turns']:
            raise ValueError(f'Visible-turn mismatch for {did}')
        candidates = {}
        for index, claim in enumerate(prediction['claims']):
            text = claim['claim']
            # Use new candidate IDs so every temp3 claim is independently judged
            # with JUDGE, even when its text occurs in the frozen judgments.
            cid = 'temp3_' + agd.stable_hash({'did': did, 'text': agd.clean_claim(text)})[:14]
            candidates.setdefault(cid, {'id': cid, 'claim': text})
            dialogue['predictions'].append({
                'id': f'{method}:{index}', 'algorithm': method, 'claim': text, 'candidate_id': cid,
            })
        dialogue['append_candidates'] = sorted(candidates.values(), key=lambda c: c['id'])
        dialogue['pred_candidates'].extend(dialogue['append_candidates'])

    data['methods'].update(shared.METHODS)
    data['prediction_counts'][method] = sum(len(row['claims']) for row in exports)
    common.freeze(work / 'data.json', data)
    pending = [did for did in dialogues if not (work / 'complete' / f'{did}.json').exists()]
    print(f'Max: {len(dialogues) - len(pending)}/{len(dialogues)} already complete', flush=True)
    run_jobs(pending, lambda did: shared.append.process(did, dialogues[did]), workers, 'Max')
    for did in dialogues:
        original = agd.read(agd.path_for(shared.SNAPSHOT, 'pred', did))['items']
        appended = agd.read(agd.path_for(work, 'pred', did))['items']
        if appended[:len(original)] != original:
            raise ValueError(f'Original support judgments changed for {did}')
    shared.append.score()
    return work / 'results'


def report(run, method, results):
    summary = common.read(results / 'summary.json')
    baseline = summary[BASELINE]
    trial = summary[method]
    metrics = {
        label: {
            'baseline': baseline[field], 'temp3': trial[field],
            'delta_pp': 100 * (trial[field] - baseline[field]),
        }
        for field, label in METRICS.items()
    }
    effects = Counter()
    paths = list((run / 'diagnostics').glob('*__A_to_B.json'))
    if len(paths) != 298:
        raise ValueError('Expected 298 separate inference diagnostics')
    for path in paths:
        diagnostics = common.read(path)
        effects['rejected_E4'] += sum(c['action'] == 'reject_unsupported_e4' for c in diagnostics['candidates'])
        effects['rejected_contradiction'] += sum(c['action'] == 'reject_contradiction' for c in diagnostics['candidates'])
        effects['merged_duplicates'] += sum(len(row['merged']) for row in diagnostics['merge_log'])
        effects['final_claims'] += diagnostics['final_claims']
    common.save(results / 'comparison.json', {
        'dialogues': 298,
        'frozen_facts': 1630,
        'inference_model': 'qwen3.8-flash',
        'temp3_judge': JUDGE,
        'baseline_judge': 'qwen3.8-max-0902',
        'metrics': metrics,
        'inference_counts': dict(effects),
    })
    for label, row in metrics.items():
        print(f'{label}: {row["baseline"]:.4%} -> {row["temp3"]:.4%} ({row["delta_pp"]:+.4f} pp)', flush=True)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=12)
    parser.add_argument('--eval-workers', type=int, default=12)
    parser.add_argument('--prompt-key', action='store_true')
    args = parser.parse_args()
    if min(args.workers, args.eval_workers) < 1:
        parser.error('Worker counts must be positive')
    key = os.getenv('QWEN_API_KEY') or os.getenv('DASHSCOPE_API_KEY')
    if args.prompt_key:
        key = getpass('DashScope API key: ').strip()
    if not key:
        parser.error('Set QWEN_API_KEY or DASHSCOPE_API_KEY, or pass --prompt-key')
    os.environ['DASHSCOPE_API_KEY'] = key
    records = common.read(INPUTS)
    if len(records) != 298 or len({item['item_id'] for item in records}) != 298:
        raise ValueError('Expected exactly 298 distinct frozen inputs')
    for item in records:
        common.validate_input(item)
    run = common.run_folder(RUN_ID)
    method, exports = infer(run, records, key, args.workers)
    results = evaluate(run, method, records, exports, args.eval_workers)
    report(run, method, results)


if __name__ == '__main__':
    main()
