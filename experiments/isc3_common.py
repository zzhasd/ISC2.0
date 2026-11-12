"""Shared immutable schemas for the ISC3 pilot. No credentials in files."""
from pathlib import Path
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/isc3'
OUT = ROOT / 'results/isc3'
MODEL = 'qwen3.8-flash'
SEED = 20261031
LABELS = ['true', 'false', 'unknown']

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

def freeze(path, value):
    path = Path(path)
    if path.exists() and read(path) != value:
        raise ValueError(f'Refusing to overwrite frozen artifact: {path}')
    save(path, value)

COMMON = '''Recover facts about the UNSEEN interlocutor B, using only visible A.
A addresses B as you. A, B and third parties are distinct. A's own facts do not belong
to B. Questions and guesses are not automatically facts. Resolve references, explicit
reported acceptance/rejection and corrected assignments. A fact may need multiple turns.
For each catalogue claim return true only if supported, false only if its negation is
supported, otherwise unknown. Unknown is not false. Do not infer unmentioned attributes.
Confidence means probability that your chosen true/false/unknown label is supported by
the supplied text, not probability of guessing the person's real private state.
Return every catalogue id exactly once in JSON {"facts":[{"id":"...",
"label":"true|false|unknown","confidence":0.0,"evidence_turns":[1]}]}.
Use original supplied turn numbers. Unknown normally has no supporting turns.
No real B speech is present. Hypothetical B replies, if supplied, are model guesses and
must not be treated as additional observations. Do not add prose or hidden replies.'''
DIRECT = COMMON
GRAPH = COMMON + '''
First construct a small evidence graph of at most six edges (speaker, entity, reference,
event, correction or assignment links). Then use this graph to decide the catalogue.
Add "edges":[{"source":"...","relation":"...","target":"...","turns":[1]}]
to the JSON. Keep edges short. Do not introduce entities or facts absent from A.'''
VERIFY = COMMON + '''
An earlier graph-based assistant's draft is provided, and may be wrong. Independently
test each proposed fact against three competing hypotheses: true, false, not identifiable.
Check holder, temporal corrections, exact evidence, alternative compatible worlds and
whether each required premise exists. Reject conclusions supported only by generated
content, stereotypes, an obsolete draft, or a third party's facts. Choose unknown if
the alternatives cannot be ruled out. Return the facts schema only, no copied graph.'''
SELFCHECK = COMMON + '''
An earlier direct assistant draft is provided. Re-read A and correct errors in the draft.
Return the facts schema only. Do not assume the draft is evidence.'''
RECON = '''Only A's side of a fictional conversation is observed, addressing unseen B.
Generate one short plausible missing B reply after each visible A turn. Do not copy A
as B. Replies are hypothetical, not observations. Return JSON {"hypotheses":[
{"replies":[{"after_turn":1,"text":"..."}]}]}. Use only one hypothesis.'''
MULTI = RECON.replace('Use only one hypothesis.', '''Use exactly three distinct coherent
hypotheses, including alternative interpretations when evidence is insufficient.
Do not treat arbitrary new private details as established facts.''')
EXTRACT = COMMON + '''
Use all hypothetical reconstructions as possible representations of A's implications.
When hypotheses disagree or agree only on invented detail, use unknown. Evidence must
point to A turns, never to a reconstructed B turn. Return the facts schema only.'''
OPEN = '''Only A's side of a fictional conversation is observed. A addresses unseen B.
Discover at most eight independent atomic facts about B that A actually supports.
Distinguish B from A and third parties. Resolve cross-turn references and corrections.
Do not invent B replies or use stereotypes. Return JSON {"claims":[{"text":"B ...",
"holder":"B","confidence":0.0,"evidence_turns":[1]}]}. Include supported negations.
If nothing is supported return an empty claims list. Use original supplied turn numbers.'''
NORMALIZE = '''Map ONLY the supplied discovered claims to the fixed catalogue. You do
not see A and must not add missing information. Return all catalogue ids in JSON
{"facts":[{"id":"...","label":"true|false|unknown","confidence":0.0,
"evidence_turns":[1],"source_claim_indices":[0]}],"unmatched_claim_indices":[0]}.
True requires an explicit equivalent atomic positive assertion about B; false requires
an explicit equivalent negation. Preserve the source claim confidence and evidence;
unknown has confidence 1 and no evidence. Do not infer a broader fact from an unrelated
or more specific fact unless the implication is logically certain. Index claims from 0.
Assertions about A/third parties cannot establish B facts.'''

def make_task(system, content, method, case_id, condition, cap=1800, **metadata):
    payload = {'model': MODEL, 'temperature': 0, 'enable_thinking': False,
               'max_tokens': cap, 'response_format': {'type': 'json_object'},
               'messages': [{'role': 'system', 'content': system},
                            {'role': 'user', 'content': json.dumps(content, ensure_ascii=False)}]}
    h = digest(payload)
    return {'task_id': h[:24], 'request_sha256': h, 'method': method,
            'case_id': case_id, 'condition': condition, **metadata, 'payload': payload}

def raw_index(directory):
    result = {}
    path = Path(directory) / 'api_raw.jsonl'
    if not path.exists(): return result
    for line in path.read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        if row.get('http_status') == 200: result[row['task_id']] = row
    return result

def decode(row):
    choice = row['body']['choices'][0]
    if choice.get('finish_reason') != 'stop': raise ValueError('Incomplete generation')
    obj = json.loads(choice['message']['content'])
    if not isinstance(obj, dict): raise ValueError('Output must be an object')
    return obj

def validate_facts(obj, catalogue, visible):
    facts = obj['facts']; ids = {a['id'] for a in catalogue}
    if not isinstance(facts, list) or len(facts) != len(ids) or {f['id'] for f in facts} != ids:
        raise ValueError('Missing, duplicated or unexpected catalogue IDs')
    allowed = {v['turn'] for v in visible}
    for f in facts:
        if f.get('label') not in LABELS: raise ValueError('Invalid label')
        c = f.get('confidence')
        if isinstance(c, bool) or not isinstance(c, (float, int)) or not math.isfinite(c) or not 0 <= c <= 1:
            raise ValueError('Invalid confidence')
        ev = f.get('evidence_turns')
        if not isinstance(ev, list) or any(type(i) is not int or i not in allowed for i in ev):
            raise ValueError('Invalid evidence turn')
    return facts
