"""Run ELARA v1.1 inference on the 298 frozen ISC113 A-only dialogues.

Install requests and tqdm, then use QWEN_API_KEY or DASHSCOPE_API_KEY.
Repeat with the same run ID and scope to resume saved work.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import getpass
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import types

from tqdm import tqdm

HERE = Path(__file__).resolve().parent
ALGORITHM_PATH = HERE / 'ELARA-v1.1.py'
PACKAGE = '_isc113_elara_v1_1'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(HERE)]
sys.modules.setdefault(PACKAGE, package)

common = importlib.import_module(f'{PACKAGE}.common')
clientmod = importlib.import_module(f'{PACKAGE}.client')
spec = importlib.util.spec_from_file_location(f'{PACKAGE}.algorithm', ALGORITHM_PATH)
algorithm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(algorithm)

SCOPE_COUNT = 298
ORIGINAL_ALGORITHM_SHA256 = 'c7335b87573021325170a6998409e9589e6b06fee5ba3124f10f6b5d4c5022c5'
SCHEMA_KEYS = {'turns', 'hypotheses', 'claims', 'decisions'}
RETRY_INSTRUCTIONS = """
FORMAT REPAIR: Output one complete JSON object matching the schema above.
Exclude markdown, explanations and examples outside the object. Claims must
begin with B followed by a verb, or with B's followed by a possessed noun.
Omit A-only claims. Keep each original quote verbatim, including punctuation.
In act tagging, use [] if no unique literal trigger can be identified. Split
adjacent clauses if needed to isolate an unambiguous additive marker. Preserve
all original IDs and enumerated labels.
"""


def decode_response(body):
    """Recover exactly one complete task object from a finished wrapped reply."""
    try:
        return base_decode(body)
    except json.JSONDecodeError:
        content = body['choices'][0]['message']['content']
        decoder = json.JSONDecoder()
        matches = []
        for match in re.finditer(r'\{\s*"(?:turns|hypotheses|claims|decisions)"\s*:', content):
            try:
                obj, _ = decoder.raw_decode(content, match.start())
            except json.JSONDecodeError:
                continue
            if len(obj) == 1 and set(obj) <= SCHEMA_KEYS and isinstance(next(iter(obj.values())), list):
                matches.append(obj)
        if len(matches) == 1:
            return matches[0]
        raise


# The private package keeps this decoder local to the v1.1 runner.
base_decode = importlib.import_module(f'{PACKAGE}.inference').decode
clientmod.decode = decode_response


class DialogueClient:
    """Reuse the shared Client ledger and reopen only exhausted request budgets."""

    def __init__(self, client, recovery, retry_interrupted=False):
        self.client = client
        self.recovery = recovery
        self.task_ids = []
        self.replayed_responses = []
        self.retry_interrupted = retry_interrupted
        self.retried_interrupted_attempts = []

    @staticmethod
    def task_id(name, payload):
        return common.digest({'logical_name': name, 'payload': payload})

    def call(self, name, payload, validate):
        primary = self.task_id(name, payload)
        prefix = name + '/recovery_'
        repair = dict(payload, messages=[
            dict(payload['messages'][0], content=payload['messages'][0]['content'] + RETRY_INSTRUCTIONS),
            *payload['messages'][1:],
        ])
        with self.client.lock:
            history = [
                row for row in self.client.rows
                if row['logical_name'] == name or row['logical_name'].startswith(prefix)
            ]
        matches = {name: {primary}}
        last_round = 0
        for row in history:
            logical = row['logical_name']
            if logical != name and logical not in matches:
                index = int(logical.removeprefix(prefix))
                last_round = max(last_round, index)
                matches[logical] = {self.task_id(logical, p) for p in (payload, repair)}
        history = [row for row in history if row['task_id'] in matches[row['logical_name']]]
        self.task_ids.extend(dict.fromkeys(row['task_id'] for row in history))

        # Prefer previously valid replies so downstream cache keys stay stable.
        done = [row for row in history if row['event'] == 'complete']
        for row in sorted(done, key=lambda row: not row.get('valid')):
            if row.get('http_status') != 200:
                continue
            try:
                result = validate(decode_response(row['body']))
            except (ValueError, TypeError, KeyError, IndexError, AttributeError):
                continue
            if not row.get('valid'):
                self.replayed_responses.append({
                    'task_id': row['task_id'], 'attempt_id': row['attempt_id'],
                    'logical_name': row['logical_name'], 'previous_error': row.get('error'),
                })
            return result, row['task_id']

        started = {row['attempt_id'] for row in history if row['event'] == 'start'}
        interrupted = started - {row['attempt_id'] for row in done}
        if interrupted:
            if not (self.recovery and self.retry_interrupted):
                raise RuntimeError('Unresolved in-flight request; audit before retry: ' + name)
            self.retried_interrupted_attempts.extend(sorted(interrupted))
        else:
            self.task_ids.append(primary)
            try:
                return self.client.call(name, payload, validate)
            except RuntimeError as exc:
                if not self.recovery or str(exc) != 'Attempt limit exceeded: ' + name:
                    raise
        retry_name = f'{prefix}{last_round + 1}'
        self.task_ids.append(self.task_id(retry_name, repair))
        return self.client.call(retry_name, repair, validate)


def read_inputs(limit):
    records = common.read(HERE / 'inputs' / 'dailydialog.json')
    if len(records) != SCOPE_COUNT or len({row['item_id'] for row in records}) != SCOPE_COUNT:
        raise ValueError(f'Expected {SCOPE_COUNT} unique frozen A-only dialogues')
    for row in records:
        common.validate_input(row)
    return records[:limit]


def api_key():
    key = os.getenv('QWEN_API_KEY') or os.getenv('DASHSCOPE_API_KEY')
    if not key and sys.stdin.isatty():
        key = getpass.getpass('请输入 Qwen DashScope API Key（输入不显示）：').strip()
    if not key:
        raise RuntimeError('请设置 QWEN_API_KEY 或 DASHSCOPE_API_KEY，或在交互式终端输入。')
    return key


def filename(item):
    return f"{item['dialogue_id']}__A_to_B.json"


def saved_prediction(run, item):
    try:
        rows = common.read(run / 'predictions' / filename(item))
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            return None
        row = rows[0]
        if (
            row.get('method') == algorithm.METHOD
            and all(row.get(key) == item[key] for key in ('item_id', 'dialogue_id', 'direction', 'dataset'))
            and isinstance(row.get('claims'), list)
            and isinstance(row.get('task_ids'), list)
        ):
            return row
    except (OSError, ValueError):
        pass
    return None


def infer(records, run_id, workers, retry_interrupted=False):
    run = common.run_folder(run_id)
    todo = [item for item in records if saved_prediction(run, item) is None]
    print(f'[推理] 共 {len(records)} 段，已完成 {len(records) - len(todo)} 段，待处理 {len(todo)} 段。')
    if not todo:
        return []

    key = api_key()
    client = clientmod.Client(key, run_id=run_id)

    def work(item, recovery):
        dialogue = DialogueClient(client, recovery, retry_interrupted)
        prediction, diagnostics = algorithm.pipeline(dialogue, item)
        task_ids = list(dict.fromkeys(dialogue.task_ids))
        prediction['task_ids'] = task_ids
        diagnostics['api_task_ids'] = task_ids
        prediction['inference_revision'] = algorithm.REVISION
        diagnostics['inference_revision'] = algorithm.REVISION
        diagnostics['replayed_responses'] = dialogue.replayed_responses
        diagnostics['retried_interrupted_attempts'] = dialogue.retried_interrupted_attempts
        common.save(run / 'diagnostics' / filename(item), diagnostics)
        common.save(run / 'predictions' / filename(item), [prediction])

    def wave(items, label, recovery):
        errors = {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            jobs = {pool.submit(work, item, recovery): item['item_id'] for item in items}
            with tqdm(total=len(jobs), desc=label, unit='段') as bar:
                for future in as_completed(jobs):
                    try:
                        future.result()
                    except Exception as exc:
                        errors[jobs[future]] = f'{type(exc).__name__}: {exc}'.replace(key, '[REDACTED]')
                    bar.update()
                    bar.set_postfix(failed=len(errors), refresh=False)
        return errors

    initial = wave(todo, 'ELARA v1.1 推理', recovery=False)
    if not initial:
        return []

    retry = [item for item in todo if item['item_id'] in initial]
    final = wave(retry, 'ELARA v1.1 补跑', recovery=True)
    return [
        {'item_id': item['item_id'], 'initial_error': initial[item['item_id']],
         'error': final[item['item_id']]}
        for item in retry if item['item_id'] in final
    ]


def bind_manifest(run, records):
    manifest = {
        'method': algorithm.METHOD,
        'version': algorithm.VERSION,
        'model': algorithm.MODEL,
        'direction': 'A_to_B',
        'inputs_sha256': common.digest(records),
        'algorithm_sha256': common.filehash(ALGORITHM_PATH),
        'scope_count': len(records),
        'reference_access_during_inference': False,
    }
    path = run / 'method_manifest.json'
    original = dict(manifest, algorithm_sha256=ORIGINAL_ALGORITHM_SHA256)
    if path.exists() and common.read(path) == original:
        common.freeze(run / 'recovery_manifest_v1_1_1.json', {
            **manifest,
            'original_algorithm_sha256': ORIGINAL_ALGORITHM_SHA256,
            'inference_revision': algorithm.REVISION,
        })
    else:
        common.freeze(path, manifest)


def main():
    parser = argparse.ArgumentParser(description='Run ELARA v1.1 inference on frozen ISC113 inputs.')
    parser.add_argument('--run-id', default='elara_v1_1')
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--limit', type=int, metavar='N', help='Smoke test the first N dialogues.')
    parser.add_argument(
        '--retry-interrupted', action='store_true',
        help='After the previous process has stopped, retry requests with unknown billing status.',
    )
    args = parser.parse_args()
    if args.workers < 1 or (args.limit is not None and not 1 <= args.limit <= SCOPE_COUNT):
        parser.error(f'--workers must be positive and --limit must be 1–{SCOPE_COUNT}')
    run = common.run_folder(args.run_id)
    records = read_inputs(args.limit)
    common.freeze(run / 'inputs.json', records)
    bind_manifest(run, records)

    errors = infer(records, args.run_id, args.workers, args.retry_interrupted)
    common.save(run / 'inference_errors.json', errors)
    results = [saved_prediction(run, item) for item in records]
    predictions = [row for row in results if row is not None]
    common.save(run / 'exports' / 'dailydialog.json', predictions)

    print(f'[完成] 已导出 {len(predictions)}/{len(records)} 段。输出目录为 {run}')
    if len(predictions) != len(records):
        print(f'[未完成] 详见 {run / "inference_errors.json"}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
