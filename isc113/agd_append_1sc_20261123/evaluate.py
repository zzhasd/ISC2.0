"""Append one method to the immutable AGD scoring view."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import copy
import getpass
import hashlib
import os
from pathlib import Path
import shutil
import sys
import time

from isc113 import common
from .infer import METHODS, RECON, ROOT, WORK

BASE = ROOT.parent / 'agd_eval_20261106'
PRECEDENT = ROOT.parent / 'agd_append_elara_v1_1_20261123'
STAGES = ('sweep', 'pred', 'gold', 'sweep_support', 'pool')
SNAPSHOT = WORK / 'frozen' / 'baseline'

# Reuse the existing AGD append protocol and transport, with isolated outputs.
sys.path.insert(0, str(PRECEDENT))
import append_eval as append
import agd_eval as agd
import judge_transport as transport

append.ROOT = WORK
append.WORK = WORK
transport.ROOT = ROOT
transport.WORK = WORK


def prepare():
    base = BASE / 'scored_eval'
    data = agd.read(base / 'data.json')
    agd.METHODS = data['methods'] | METHODS
    agd_prompt = agd.read(BASE / 'judge_prompt_manifest.json')
    if hashlib.sha256(agd.SUPPORT_SYSTEM.encode()).hexdigest() != agd_prompt['systems_sha256']['SUPPORT_SYSTEM']:
        raise ValueError('Support rubric differs from the frozen AGD evaluation')
    sources = {
        base / 'data.json': SNAPSHOT / 'data.json',
        base / 'results/summary.json': SNAPSHOT / 'summary.json',
        base / 'results/per_dialogue.csv': SNAPSHOT / 'per_dialogue.csv',
        BASE / 'judge_prompt_manifest.json': None,
        BASE / 'protocol_manifest.json': None,
        BASE / 'agd_eval.py': None,
        PRECEDENT / 'agd_eval.py': None,
        PRECEDENT / 'append_eval.py': None,
        PRECEDENT / 'judge_transport.py': None,
    }
    for did in data['dialogues']:
        for stage in STAGES:
            relative = Path('judgments') / stage / f'{did}.json'
            sources[base / relative] = SNAPSHOT / relative
    manifest = {str(src.resolve()): common.filehash(src) for src in sources}
    common.freeze(WORK / 'source_manifest.json', manifest)
    for src, dest in sources.items():
        if dest is None:
            continue
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        if common.filehash(dest) != manifest[str(src.resolve())]:
            raise ValueError(f'Frozen snapshot mismatch: {dest}')
    levels = Counter()
    slots = Counter()
    for did in data['dialogues']:
        for fact in agd.read(agd.path_for(SNAPSHOT, 'pool', did))['facts']:
            levels[fact['level']] += 1
            slots['count'] += len(fact['slots'])
            slots['required_weight'] += sum(s['weight'] for s in fact['slots'] if s['required'])
    if len(data['dialogues']) != 298 or levels != {'E1': 511, 'E2': 1119} or slots != {
        'count': 3985, 'required_weight': 6352,
    }:
        raise ValueError(f'Unexpected frozen pool: {levels}, {slots}')
    common.freeze(WORK / 'evaluation_manifest.json', {
        'method': RECON, 'model': transport.MODEL, 'dialogues': 298,
        'temperature': 0, 'support_batch_size': 12,
        'support_thinking_budget': 4096, 'coverage_thinking_budget': 8192,
        'support_system_sha256': agd_prompt['systems_sha256']['SUPPORT_SYSTEM'],
        'coverage_system': append.MATCH_SYSTEM,
        'facts': dict(levels), 'slots': dict(slots),
        'paired_bootstrap_seed': 20261106, 'paired_bootstrap_replicates': 2000,
    })
    return data


def append_predictions(did, baseline, outcome):
    prediction, = [row for row in outcome['predictions'] if row['method'] == RECON]
    if prediction['dialogue_id'] != did or prediction['direction'] != 'A_to_B' or prediction['outcome'] != 'complete':
        raise ValueError(f'Invalid inference artifact: {did}')
    observed = [
        {'turn_id': turn['turn_id'], 'text': turn['text']}
        for turn in outcome['reconstructed_transcript'] if turn['source'] == 'observed_A'
    ]
    if observed != baseline['visible_turns']:
        raise ValueError(f'Inference A differs from the official A-only view: {did}')
    d = copy.deepcopy(baseline)
    known = {agd.clean_claim(c['claim']): c['id'] for c in d['pred_candidates']}
    new = {}
    predictions = []
    for index, claim in enumerate(prediction['claims']):
        text = claim['claim']
        normalized = agd.clean_claim(text)
        cid = 'p_' + agd.stable_hash({'did': did, 'text': normalized})[:14]
        if normalized in known:
            if known[normalized] != cid:
                raise ValueError(f'Candidate ID mismatch: {did}')
        else:
            new.setdefault(cid, {'id': cid, 'claim': text})
        predictions.append({
            'id': f'{RECON}:{index}', 'algorithm': RECON, 'claim': text, 'candidate_id': cid,
        })
    d['append_candidates'] = sorted(new.values(), key=lambda c: c['id'])
    d['append_prediction_ids'] = [p['id'] for p in predictions]
    d['predictions'].extend(predictions)
    d['pred_candidates'].extend(d['append_candidates'])
    common.freeze(WORK / 'bindings' / f'{did}.json', {
        'prediction_sha256': common.digest(prediction),
        'appended_candidate_sha256': common.digest(d['append_candidates']),
    })
    return d


def evaluate_dialogue(did, original):
    data = append_predictions(did, original, common.read(WORK / 'inference' / f'{did}.json'))
    append.process(did, data)


def judge(base, workers, follow):
    key = os.environ.get('DASHSCOPE_API_KEY') or os.environ.get('QWEN_API_KEY')
    os.environ['DASHSCOPE_API_KEY'] = key or getpass.getpass('DashScope API key: ').strip()
    if not os.environ['DASHSCOPE_API_KEY']:
        raise ValueError('DashScope API key required')
    rows = base['dialogues']
    pending = set(rows)
    done = 0
    failures = {}
    jobs = {}
    last_progress = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        while pending or jobs:
            if not transport.STOP.is_set():
                ready = [did for did in sorted(pending) if (WORK / 'inference' / f'{did}.json').exists()]
                if ready:
                    last_progress = time.monotonic()
                for did in ready:
                    pending.remove(did)
                    jobs[executor.submit(evaluate_dialogue, did, rows[did])] = did
            for future in list(jobs):
                if not future.done():
                    continue
                did = jobs.pop(future)
                try:
                    future.result()
                    done += 1
                    if done % 10 == 0 or done == len(rows):
                        print(f'Max evaluation {done}/{len(rows)}', flush=True)
                except Exception as error:
                    failures[did] = str(error)
                    print(f'Max failed {did}: {error}', flush=True)
            if transport.STOP.is_set():
                for future in jobs:
                    future.cancel()
                break
            if pending and not jobs and (not follow or time.monotonic() - last_progress > 900):
                break
            if pending or jobs:
                time.sleep(2)
    common.save(WORK / 'evaluation_status.json', {
        'complete': done, 'requested': len(rows), 'missing_inference': sorted(pending),
        'failures': failures,
    })
    if failures or done != len(rows):
        raise SystemExit(1)


def score(base):
    predictions = common.read(WORK / 'exports/dailydialog.json')
    if len(predictions) != 298 or {p['dialogue_id'] for p in predictions} != set(base['dialogues']):
        raise ValueError('Exactly 298 complete A+B inference exports are required')
    for did, original in base['dialogues'].items():
        outcome = common.read(WORK / 'inference' / f'{did}.json')
        base['dialogues'][did] = append_predictions(did, original, outcome)
        if not (WORK / 'complete' / f'{did}.json').exists():
            raise ValueError(f'Incomplete append evaluation: {did}')
        original_pred = agd.read(agd.path_for(SNAPSHOT, 'pred', did))['items']
        appended_pred = agd.read(agd.path_for(WORK, 'pred', did))['items']
        if appended_pred[:len(original_pred)] != original_pred:
            raise ValueError(f'Original judgments changed: {did}')
        for stage in ('sweep', 'gold', 'sweep_support'):
            if common.filehash(agd.path_for(SNAPSHOT, stage, did)) != common.filehash(agd.path_for(WORK, stage, did)):
                raise ValueError(f'Original {stage} changed: {did}')
    base['methods'].update(METHODS)
    base['prediction_counts'][RECON] = sum(len(row['claims']) for row in predictions)
    common.save(WORK / 'data.json', base)
    # The shared scorer checks unchanged facts/fields/member prefixes and
    # verifies every published metric for the original six algorithms.
    append.score()
    from .report import report
    report(base)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('judge', 'score'))
    parser.add_argument('--workers', type=int, default=24)
    parser.add_argument('--follow', action='store_true')
    args = parser.parse_args()
    base = prepare()
    if args.action == 'judge':
        judge(base, args.workers, args.follow)
    else:
        score(base)


if __name__ == '__main__':
    main()
