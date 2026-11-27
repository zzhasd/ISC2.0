"""Paired ELARA v1 ablations on the frozen AGD DailyDialog inputs."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
import getpass
import hashlib
import importlib
import os
from pathlib import Path

from . import client as inference_client, common
from .inference import decode

ALGORITHM = importlib.import_module('.ELARA-v1', __package__)
BASELINE = common.BASE / 'runs' / 'elara_append_v1'
RUN = common.BASE / 'runs' / 'elara_v1_ablation'
AGD = common.BASE / 'agd_eval_20261106' / 'scored_eval'
TOKEN_PLAN = 'https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1'
VARIANTS = {
    'no_explicit': 'ELARA v1 w/o explicit pass',
    'no_implicit': 'ELARA v1 w/o implicit pass',
    'no_gap_scan': 'ELARA v1 w/o gap scan',
    'no_audit': 'ELARA v1 w/o audit',
    'supported_only': 'ELARA v1 supported only',
}
METHODS = {variant: ALGORITHM.METHOD + '_' + variant for variant in VARIANTS}
SINGLE_PASS_GAP = ALGORITHM.GAP_SCAN.replace(
    'from two separate agents', 'from one earlier extraction pass'
).replace('omitted by BOTH candidate lists', 'omitted by the supplied candidate list')


class MissingReplay(Exception):
    """An exact request is absent from the archived inference responses."""


class PairedClient:
    def __init__(self, key=None):
        self.historical = {}
        for row in common.jsonlines(BASELINE / 'attempts.jsonl'):
            if row.get('event') == 'complete' and row.get('valid'):
                self.historical.setdefault(row['task_id'], row['body'])
        self.live = inference_client.Client(key, run_id=RUN.name) if key else None

    def call(self, name, payload, validate):
        tid = common.digest({'logical_name': name, 'payload': payload})
        if tid in self.historical:
            return validate(decode(deepcopy(self.historical[tid]))), tid
        if self.live is None:
            raise MissingReplay(name)
        return self.live.call(name, payload, validate)


def checked_inputs():
    manifest = common.read(BASELINE / 'method_manifest.json')
    source = Path(ALGORITHM.__file__)
    input_file = BASELINE / 'inputs.json'
    if hashlib.sha256(source.read_bytes()).hexdigest() != manifest['algorithm_sha256']:
        raise ValueError('ELARA source differs from the historical full baseline')
    records = common.read(input_file)
    data = common.read(AGD / 'data.json')['dialogues']
    if len(records) != 298 or len(data) != 298 or {r['dialogue_id'] for r in records} != set(data):
        raise ValueError('Expected the same 298 frozen AGD dialogue IDs')
    for record in records:
        common.validate_input(record)
        if record['visible_turns'] != data[record['dialogue_id']]['visible_turns']:
            raise ValueError('A-only input differs from frozen AGD: ' + record['dialogue_id'])
    return sorted(records, key=lambda row: row['dialogue_id'])


def predict(client, record, variant):
    turns = record['visible_turns']
    prefix = record['item_id'] + '/elara/'
    data = {'visible_turns': turns, 'target': 'hidden B, unseen partner'}
    groups, task_ids = [], []

    def generate(stage, prompt, payload):
        claims, task = client.call(prefix + stage, ALGORITHM.request(prompt, payload),
                                   lambda obj: ALGORITHM.validate_generation(obj, turns))
        task_ids.append(task)
        groups.append((stage, claims))

    if variant != 'no_explicit':
        generate('explicit', ALGORITHM.EXPLICIT, data)
    if variant != 'no_implicit':
        generate('implicit', ALGORITHM.IMPLICIT, data)
    if variant != 'no_gap_scan':
        proposals, _ = ALGORITHM._unite(groups)
        prompt = SINGLE_PASS_GAP if len(groups) == 1 else ALGORITHM.GAP_SCAN
        generate('gap_scan', prompt, dict(data, existing_claims=[c['claim'] for c in proposals]))
    candidates, rejected = ALGORITHM._unite(groups)
    for index, candidate in enumerate(candidates, 1):
        candidate['candidate_id'] = f'c{index}'

    decisions = {}
    if variant != 'no_audit':
        for start in range(0, len(candidates), 8):
            batch = candidates[start:start + 8]
            view = [{k: row[k] for k in ('candidate_id', 'claim', 'evidence', 'mechanism')}
                    for row in batch]
            audited, task = client.call(
                prefix + f'audit_{start // 8 + 1}',
                ALGORITHM.request(ALGORITHM.AUDIT, dict(data, candidates=view), 4096),
                lambda obj: ALGORITHM.validate_audit(obj, batch, turns),
            )
            task_ids.append(task)
            decisions.update((row['candidate_id'], row) for row in audited)

    output = []
    for candidate in candidates:
        decision = decisions.get(candidate['candidate_id'])
        if decision is None:
            output.append(dict(candidate))
            continue
        verdict = decision['verdict']
        if verdict == 'contradicted' or (variant == 'supported_only' and verdict != 'supported'):
            continue
        claim = dict(candidate, audit_verdict=verdict, audited_evidence_level=decision['evidence_level'],
                     audit_citation_valid=decision['citation_valid'])
        if decision['citation_valid'] and verdict == 'supported' and decision['evidence_level'] in ('E1', 'E2'):
            claim['evidence'] = decision['evidence']
        claim['evidence_span_valid'] = ALGORITHM.valid_evidence(claim['evidence'], turns)
        output.append(claim)

    prediction = {k: record[k] for k in ('item_id', 'dialogue_id', 'direction', 'dataset')}
    prediction.update(method=METHODS.get(variant, ALGORITHM.METHOD), claims=output, task_ids=task_ids)
    diagnostics = {'audits': decisions, 'rejected_candidates': rejected, 'candidate_count': len(candidates)}
    return prediction, diagnostics


def infer(limit, workers, offline):
    records = checked_inputs()[:limit]
    if not records:
        raise ValueError('No dialogues selected')
    client = PairedClient()
    archive = {row['dialogue_id']: row for row in common.read(BASELINE / 'exports' / 'dailydialog.json')}
    for record in records:
        full, _ = predict(client, record, 'full')
        did = record['dialogue_id']
        if full != archive[did]:
            raise ValueError('Full pipeline replay differs from the archived export: ' + did)
    print(f'Full prediction and task replay matches the archived baseline for {len(records)} dialogues.', flush=True)

    if not offline:
        key = os.environ.get('TOKEN_PLAN_API_KEY') or getpass.getpass('Token Plan credential: ').strip()
        inference_client.URL = TOKEN_PLAN + '/chat/completions'
        client.live = inference_client.Client(key, run_id=RUN.name)

    def do_dialogue(record):
        did = record['dialogue_id']
        completed, errors = [], []
        for variant in VARIANTS:
            target = RUN / 'predictions' / variant / f'{did}.json'
            if not target.exists():
                try:
                    prediction, diagnostics = predict(client, record, variant)
                    common.save(RUN / 'diagnostics' / variant / f'{did}.json', diagnostics)
                    common.save(target, prediction)
                except (MissingReplay, RuntimeError) as exc:
                    errors.append({'dialogue_id': did, 'variant': variant, 'error': str(exc)})
                    continue
            completed.append(variant)
        return completed, errors

    counts = dict.fromkeys(VARIANTS, 0)
    errors = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(do_dialogue, record) for record in records]
        for index, future in enumerate(as_completed(futures), 1):
            completed, failed = future.result()
            errors.extend(failed)
            for variant in completed:
                counts[variant] += 1
            if index % 25 == 0 or index == len(records):
                print(f'Dialogues processed {index}/{len(records)}. Variants complete: {counts}', flush=True)

    for variant, count in counts.items():
        if count == len(records) == 298:
            rows = [common.read(RUN / 'predictions' / variant / (row['dialogue_id'] + '.json')) for row in records]
            common.save(RUN / 'exports' / (variant + '.json'), rows)
    common.save(RUN / ('offline_status.json' if offline else 'inference_status.json'), {
        'model': ALGORITHM.MODEL, 'endpoint': TOKEN_PLAN, 'dialogues': len(records),
        'full_baseline_replay_exact': len(records), 'completed': counts, 'errors': errors,
        'single_pass_gap_prompt_changes': ['two separate agents → one earlier extraction pass',
                                          'BOTH candidate lists → the supplied candidate list'],
    })
    if errors and not offline:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--workers', type=int, default=10)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    infer(args.limit, args.workers, args.offline)
