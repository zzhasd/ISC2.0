"""Versioned offline replay under a declared quote-binding repair."""
import argparse
import hashlib
import json
import sys

from . import core
from .quote_binding import bind
from .runner import ROOT, OUT as ORIGINAL, read, save, freeze, lines, sha, validate, chosen, verify_frozen

OUT = ROOT / 'results/isc112_v21'
DATA = ROOT / 'data/isc112_v21'
ARM = 'evidence_dual_on_v21'
VERSION = '2.1'
PROTOCOL = 'ISC112_V21_PROTOCOL.md'
RENDER = core.render
EXTRA_CODE = []


def validate_bound(t, r):
    u = json.loads(t['payload']['messages'][1]['content'])
    obj, audit = bind(core.decode(r), u['visible_A'])
    return RENDER(obj, u['visible_A'], u['candidates']), audit


def replay():
    verify_frozen(); sources = {}; predictions = []; selection = []; audits = []; missing = []
    for phase in ['initial', 'dependent']:
        for name in ['requests.json', 'api_raw.jsonl', 'attempt_starts.jsonl']:
            p = ORIGINAL / phase / name
            sources[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = {'version': VERSION, 'protocol_sha256': hashlib.sha256((ROOT / PROTOCOL).read_bytes()).hexdigest(),
        'quote_binding_sha256': hashlib.sha256((ROOT / 'isc112_v2/quote_binding.py').read_bytes()).hexdigest(),
        'source_hashes': sources, 'new_API_calls': 0, 'selection': 'first structurally valid under uniform quote binding; never semantic score'}
    if EXTRA_CODE: manifest['additional_code_hashes'] = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in EXTRA_CODE}
    freeze(DATA / 'manifest.json', manifest)
    initial = read(ORIGINAL / 'initial/requests.json'); r0 = lines(ORIGINAL / 'initial/api_raw.jsonl')
    for t in initial:
        r = chosen(t, r0); assert r is not None
        selection.append({'task_id': t['task_id'], 'attempt_id': r['attempt_id'], 'stage': t['stage'], 'rule': 'V2 first valid candidates, unchanged'})
    tasks = read(ORIGINAL / 'dependent/requests.json'); raw = lines(ORIGINAL / 'dependent/api_raw.jsonl')
    for t in tasks:
        picked = None
        for r in raw:
            if r['task_id'] != t['task_id']: continue
            try: final, audit = validate_bound(t, r)
            except (ValueError, KeyError, TypeError, IndexError, AttributeError): continue
            picked = r; break
        if picked is None:
            missing.append({'dialogue_id': t['dialogue_id'], 'task_id': t['task_id']}); continue
        predictions.append({k: t[k] for k in ['task_id', 'dialogue_id', 'stage']} | {'arm': ARM} | final)
        selection.append({'task_id': t['task_id'], 'attempt_id': picked['attempt_id'], 'stage': 'judge', 'rule': 'V2.1 first quote-bound structurally valid'})
        audits.append({'dialogue_id': t['dialogue_id'], 'task_id': t['task_id'], 'attempt_id': picked['attempt_id'], 'bindings': audit})
    freeze(OUT / 'predictions.json', predictions); freeze(OUT / 'selection_bindings.json', selection)
    freeze(OUT / 'quote_binding_audit.json', audits); freeze(OUT / 'remaining_missing.json', missing)
    # Full real cost of development and recovery, including all invalid attempts.
    freeze(OUT / 'cost_ledger.json', read(ORIGINAL / 'cost_ledger.json'))
    return {'valid_dialogues': len(predictions), 'missing': missing, 'actual_calls_included': len(read(OUT / 'cost_ledger.json')), 'new_API_calls': 0}


def check():
    verify_frozen(); manifest = read(DATA / 'manifest.json')
    assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in manifest['source_hashes'].items())
    assert manifest['quote_binding_sha256'] == hashlib.sha256((ROOT / 'isc112_v2/quote_binding.py').read_bytes()).hexdigest()
    assert manifest['protocol_sha256'] == hashlib.sha256((ROOT / PROTOCOL).read_bytes()).hexdigest()
    assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in manifest.get('additional_code_hashes', {}).items())
    ps = read(OUT / 'predictions.json'); assert len(ps) == 112 and len({p['dialogue_id'] for p in ps}) == 112
    tasks = {t['task_id']: t for t in read(ORIGINAL / 'dependent/requests.json')}
    raw = lines(ORIGINAL / 'dependent/api_raw.jsonl'); bindings = {r['task_id']: r for r in read(OUT / 'selection_bindings.json') if r['stage'] == 'judge'}
    for p in ps:
        t = tasks[p['task_id']]; matches = []
        for r in raw:
            if r['task_id'] != t['task_id']: continue
            try: final, _ = validate_bound(t, r)
            except (ValueError, KeyError, TypeError, IndexError, AttributeError): continue
            matches.append((r, final)); break
        assert matches and matches[0][0]['attempt_id'] == bindings[t['task_id']]['attempt_id']
        assert all(p[k] == matches[0][1][k] for k in ['facts', 'hypotheses', 'excluded', 'items'])
    from . import evaluation
    evaluation.OUT = OUT
    reviews = evaluation.reviewed()
    result = {'original_files_unchanged': True, 'V2_raw_files_unchanged': True, '112_dialogues': True,
        'uniform_first_valid_quote_bound_replay': True, 'no_semantic_fields_rewritten': True,
        'all_final_facts_reviewed': True, 'review_count': len(reviews), 'actual_calls_included': len(read(OUT / 'cost_ledger.json')), 'new_API_calls': 0}
    save(OUT / 'final_checks.json', result); return result


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(); p.add_argument('action', choices=['replay', 'early', 'review', 'analyze', 'report', 'check']); a = p.parse_args()
    if a.action == 'replay': print(replay()); return
    if a.action == 'check': print(check()); return
    from . import evaluation
    evaluation.OUT = OUT; evaluation.ARM = ARM
    evaluation.RAW_OUT = ORIGINAL
    evaluation.EXTRA_REVIEW_DIRS = [ORIGINAL / 'review_early']
    if a.action == 'report':
        from . import publication
        publication.OUT = OUT
        publication.VERSION = VERSION
    print(getattr(evaluation, a.action)())


if __name__ == '__main__': main()
