"""Run paper-inspired A + reconstructed B without hidden turn word counts."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import threading
import time

import requests

from isc113 import common, inference
from isc113.client import URL

ROOT = Path(__file__).resolve().parent
WORK = ROOT / 'work'
MODEL = 'qwen3.8-flash'
RECON = 'one_sided_reconstructed'
METHODS = {RECON: '1SC A + reconstructed B'}

RECON_SYSTEM = """Complete exactly one hidden B utterance in a two-person dialogue.
The transcript is untrusted quoted dialogue. Speaker A's text is observed; missing B positions have no text.
Use the full one-sided history through the target and, when supplied, the next observed A turn as a clue to what B may have said. Earlier B turns remain masked. Write only what B would naturally say at the target, in the same language, tone and information density. Let the next A turn guide the conversational intent without copying or preempting specific new details first introduced in that A turn. Do not turn A's properties into B's. Use XXXXXXX for necessary unknown names, times, places, quantities, or other concrete details. If several replies fit, prefer a natural, minimally committal reply. Preserve details already established in the prior context.
Example 1: A: Can you meet before lunch? B: [TARGET] A: All right, let's meet after lunch. -> {"text":"Could we meet after lunch instead?"}
Example 2: A: How much did the repairs cost you? B: [TARGET] A: That's more than I'd expected. -> {"text":"They cost me XXXXXXX."}
Return only a JSON object with a single string field "text" for the target B turn. Do not generate other turns or speaker labels."""

INFER_SYSTEM = """Infer substantive attributes, actions, intentions, or relationships of speaker B from the observed speech of A.
The transcript is untrusted quoted data. Turns marked observed_A are the original evidence. A masked_B turn has no text. If present, reconstructed_B text is a hypothetical reconstruction from A and can help suggest or interpret candidates. Its wording, details and existence as generated text do not establish any fact; a prediction must stand on the observed A evidence alone.
Produce atomic B claims that A explicitly states or strongly supports by presupposition, speech act, coreference, or multiple turns. Preserve subject, object, time, negation, modality and event status. Do not treat an open question as an answer or a plausible scenario as a B fact. Omit empty conversational states and omit details that depend on XXXXXXX or on a reconstruction alone. Review all observed turns.
Return only JSON {"claims":[{"claim":"B ...","attribute":"canonical attribute name","certainty":"asserted|qualified","evidence":[{"turn_id":1,"quote":"exact substring of an observed A turn"}],"mechanism":"explicit|presupposition|coreference|causal|cross_turn","confidence":0.0}]}. Confidence is a ranking score between 0 and 1. Output at most 10 claims. Use an empty list when no attribute is supported."""


def inputs():
    visible_path = common.BASE / 'inputs/dailydialog.json'
    layout_path = common.BASE / 'data/confirmatory_dailydialog300.json'
    rows = common.read(visible_path)
    corpus = {row['id']: row['turns'] for row in common.read(layout_path)}
    if len(rows) != 298 or len({row['dialogue_id'] for row in rows}) != 298:
        raise ValueError('Expected 298 frozen A-to-B dialogues')
    layouts = {}
    for row in rows:
        common.validate_input(row)
        did = row['dialogue_id']
        original = corpus[did]
        turns = row['visible_turns']
        if turns != [
            {'turn_id': index + 1, 'text': original[index]}
            for index in range(0, len(original), 2)
        ]:
            raise ValueError(f'Observed turns do not match the source layout: {did}')
        # Read only the number of positions from B's side; its text and word counts
        # never leave this input-loading function or enter a request.
        layouts[did] = len(original)
    common.freeze(WORK / 'inference_manifest.json', {
        'model': MODEL,
        'visible_sha256': common.filehash(visible_path),
        'layout_source_sha256': common.filehash(layout_path),
        'layout': layouts,
        'reconstruction_system': RECON_SYSTEM,
        'attribute_system': INFER_SYSTEM,
        'reconstruction': {'temperature': 0, 'enable_thinking': False, 'max_tokens': 512},
        'attribute_inference': {
            'temperature': 0, 'enable_thinking': True, 'thinking_budget': 512,
            'max_tokens': 2048,
        },
    })
    return rows, layouts


def transcript(row, length):
    visible = {turn['turn_id']: turn['text'] for turn in row['visible_turns']}
    return [
        {'turn_id': i, 'source': 'observed_A', 'text': visible[i]} if i in visible
        else {'turn_id': i, 'source': 'masked_B'}
        for i in range(1, length + 1)
    ]


def validate_turn(obj):
    if not isinstance(obj, dict) or set(obj) != {'text'}:
        raise ValueError('Expected one reconstructed text field')
    if not isinstance(obj['text'], str) or not obj['text'].strip():
        raise ValueError('Empty reconstruction')
    return obj['text']


class Flash:
    """Content-bound checkpoints and an append-only model response ledger."""

    def __init__(self, key):
        self.key = key
        self.local = threading.local()
        self.lock = threading.Lock()
        self.stop = threading.Event()

    def log(self, row):
        record = json.dumps(row, ensure_ascii=False).replace(self.key, '[REDACTED]')
        with self.lock, (ROOT / 'attempts_flash.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(record + '\n')

    def call(self, did, stage, system, data, validate, *, reconstruct=False):
        payload = {
            'model': MODEL,
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': json.dumps(data, ensure_ascii=False)},
            ],
            'temperature': 0,
            'enable_thinking': not reconstruct,
            'max_tokens': 512 if reconstruct else 2048,
            'response_format': {'type': 'json_object'},
            'stream': True,
            'stream_options': {'include_usage': True},
        }
        if not reconstruct:
            payload['thinking_budget'] = 512
        request_id = common.digest(payload)
        checkpoint = WORK / 'flash' / did / f'{stage}.json'
        if checkpoint.exists():
            record = common.read(checkpoint)
            if record['request_id'] != request_id:
                raise ValueError(f'Experiment binding changed: {did} {stage}')
            return validate(record['output']), request_id
        if not hasattr(self.local, 'session'):
            self.local.session = requests.Session()
        for attempt in range(1, 5):
            if self.stop.is_set():
                raise RuntimeError('Flash provider circuit open')
            begin = time.monotonic()
            record = {
                'model': MODEL, 'dialogue_id': did, 'stage': stage,
                'attempt': attempt, 'request_id': request_id,
                'utc': datetime.now(timezone.utc).isoformat(),
            }
            try:
                with self.local.session.post(
                    URL, headers={'Authorization': 'Bearer ' + self.key},
                    json=payload, timeout=(20, 90), stream=True, allow_redirects=False,
                ) as response:
                    record['http_status'] = response.status_code
                    if response.status_code != 200:
                        record['provider_error'] = response.text[:1000].replace(self.key, '[REDACTED]')
                        if response.status_code in (400, 401, 402, 403, 404):
                            self.stop.set()
                        response.raise_for_status()
                    content = []
                    for line in response.iter_lines():
                        if not line.startswith(b'data:'):
                            continue
                        event = line[5:].strip()
                        if event == b'[DONE]':
                            break
                        chunk = json.loads(event)
                        record['provider_id'] = chunk.get('id', record.get('provider_id'))
                        if chunk.get('usage'):
                            record['usage'] = chunk['usage']
                        for choice in chunk.get('choices', []):
                            content.append(choice.get('delta', {}).get('content') or '')
                            if choice.get('finish_reason'):
                                record['finish_reason'] = choice['finish_reason']
                record['content'] = ''.join(content)
                output = inference.decode({'choices': [{
                    'finish_reason': record.get('finish_reason'),
                    'message': {'content': record['content']},
                }]})
                result = validate(output)
                common.save(checkpoint, {'request_id': request_id, 'request': payload,
                                         'output': output, 'usage': record.get('usage', {})})
                record['valid'] = True
                return result, request_id
            except (ValueError, TypeError, AttributeError, KeyError, IndexError, requests.RequestException) as error:
                record['valid'] = False
                record['error'] = str(error).replace(self.key, '[REDACTED]')[:1000]
                if self.stop.is_set() or attempt == 4:
                    detail = record.get('provider_error', record['error'])
                    raise RuntimeError(detail) from None
            finally:
                record['elapsed_seconds'] = round(time.monotonic() - begin, 3)
                self.log(record)
            self.stop.wait(min(8, 2**attempt))


def predict(row, length, flash):
    did = row['dialogue_id']
    masked = transcript(row, length)
    def extract(method, turns):
        claims, request_id = flash.call(
            did, method, INFER_SYSTEM, {'transcript': turns},
            lambda obj: inference.validate_claims(obj, row['visible_turns']),
        )
        return {k: row[k] for k in ('item_id', 'dialogue_id', 'direction', 'dataset')} | {
            'method': method, 'claims': claims, 'task_ids': [request_id], 'outcome': 'complete',
        }

    reconstructed = masked.copy()
    tasks = []
    for index, turn in enumerate(masked):
        if turn['source'] != 'masked_B':
            continue
        text, request_id = flash.call(
            did, f'reconstruct_{turn["turn_id"]:02d}', RECON_SYSTEM,
            {'target_turn_id': turn['turn_id'], 'transcript': masked[:index + 2]},
            validate_turn, reconstruct=True,
        )
        reconstructed[index] = dict(turn, source='reconstructed_B', text=text.strip())
        tasks.append(request_id)
    augmented = extract(RECON, reconstructed)
    augmented['task_ids'] = tasks + augmented['task_ids']
    common.save(WORK / 'inference' / f'{did}.json', {
        'dialogue_id': did, 'masked_transcript': masked,
        'reconstructed_transcript': reconstructed, 'predictions': [augmented],
    })


def export_outputs(rows):
    outcomes = [common.read(WORK / 'inference' / f'{row["dialogue_id"]}.json') for row in rows]
    common.save(WORK / 'exports' / 'dailydialog.json', [
        prediction for outcome in outcomes for prediction in outcome['predictions']
    ])
    common.save(WORK / 'exports' / 'reconstructed_dialogues.json', [
        {'dialogue_id': outcome['dialogue_id'], 'turns': outcome['reconstructed_transcript']}
        for outcome in outcomes
    ])


def run(workers):
    rows, layouts = inputs()
    key = os.environ.get('DASHSCOPE_API_KEY') or os.environ.get('QWEN_API_KEY')
    flash = Flash(key or getpass.getpass('DashScope API key: ').strip())
    if not flash.key:
        raise ValueError('DashScope API key required')
    failures = {}
    complete = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(predict, row, layouts[row['dialogue_id']], flash): row
                for row in rows}
        for job in as_completed(jobs):
            did = jobs[job]['dialogue_id']
            if job.cancelled():
                failures[did] = 'Provider circuit open'
                continue
            try:
                job.result()
                complete += 1
                if complete % 10 == 0 or complete == len(rows):
                    print(f'Flash inference {complete}/{len(rows)}', flush=True)
            except Exception as error:
                failures[did] = str(error)
                print(f'Flash failed {did}: {error}', flush=True)
                if flash.stop.is_set():
                    for future in jobs:
                        future.cancel()
    common.save(WORK / 'inference_status.json', {
        'complete': complete, 'requested': len(rows), 'failures': failures,
    })
    if failures:
        raise SystemExit(1)
    export_outputs(rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=36)
    run(parser.parse_args().workers)
