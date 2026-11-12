"""Create one canonical, cohort-free input snapshot from accepted audited results."""
import json
from .io import ROOT, DATA, read, save, file_hash, digest

SOURCES = {
    'reference.json': 'data/merged112/reference.json',
    'e1_e2/predictions.json': 'results/recovery112/isc4/predictions.json',
    'e1_e2/reviews.json': 'results/recovery112/isc4/assistant_semantic_review.json',
    'e3/predictions.json': 'results/recovery112/isc7/predictions.json',
    'e3/reviews.json': 'results/recovery112/isc7/semantic_review.json',
    'e3/cost_ledger.json': 'results/recovery112/isc7/execution_audit.json',
    'selection_bindings.json': 'results/recovery112/selection_bindings.json',
}

def prepare():
    if (DATA / 'manifest.json').exists():
        manifest = read(DATA / 'manifest.json')
        assert all(file_hash(ROOT / p) == h for p, h in manifest['source_hashes'].items()), 'Frozen source changed; create a versioned snapshot instead of silently replacing accepted inputs.'
        return check()
    ds = read(ROOT / 'data/merged112/dialogues.json')
    clean = [{'id': d['id'], 'split': d['split'], 'turns': d['turns']} for d in ds]
    assert len(clean) == len({d['id'] for d in clean}) == 112
    save(DATA / 'dialogues.json', clean)
    hashes = {'data/merged112/dialogues.json': file_hash(ROOT / 'data/merged112/dialogues.json')}
    for target, source in SOURCES.items():
        save(DATA / target, read(ROOT / source)); hashes[source] = file_hash(ROOT / source)
    historical = read(ROOT / 'results/recovery112/original_tasks.json')
    additions_path = ROOT / 'results/recovery112/attempt_results.jsonl'
    additions = [json.loads(s) for s in additions_path.read_text(encoding='utf-8').splitlines()]
    prefix_calls = [e['original_response'] for e in historical if e['kind'] == 'isc4'] + [r for r in additions if r['kind'] == 'isc4']
    ledger = []
    for r in prefix_calls:
        usage = r.get('body', {}).get('usage', {})
        ledger.append({k: r.get(k) for k in ['task_id', 'attempt_id', 'dialogue_id', 'k', 'K', 'http_status', 'elapsed_seconds']} |
                      {'total_tokens': usage.get('total_tokens'), 'prompt_tokens': usage.get('prompt_tokens'), 'completion_tokens': usage.get('completion_tokens')})
    save(DATA / 'e1_e2/cost_ledger.json', ledger)
    prompts = {}
    for e in historical:
        t = e['task']; stage = 'direct_prefix' if e['kind'] == 'isc4' else t['stage']
        if stage not in prompts:
            p = t['payload']
            prompts[stage] = {'system': p['messages'][0]['content'], 'model': p['model'],
                             'temperature': p['temperature'], 'max_tokens': p['max_tokens'],
                             'response_format': p['response_format']}
    save(DATA / 'prompts.json', prompts)
    hashes['results/recovery112/original_tasks.json'] = file_hash(ROOT / 'results/recovery112/original_tasks.json')
    hashes[str(additions_path.relative_to(ROOT))] = file_hash(additions_path)
    inputs = {str(p.relative_to(DATA)): file_hash(p) for p in DATA.rglob('*.json') if p.name != 'manifest.json'}
    save(DATA / 'manifest.json', {'dialogues': 112, 'dialogues_sha256': digest(clean), 'input_hashes': inputs,
        'source_hashes': hashes, 'sample_policy': 'One unified 112-dialogue analysis cohort; source acquisition batches are audit provenance only.',
        'reference_status': 'Frozen provisional same-assistant AI reference and review, not independent human gold',
        'selection_policy': 'Original valid results retained; first structurally valid authorized recovery response selected.',
        'new_api_calls_in_this_refactor': 0})
    return check()

def check():
    from .io import review_key
    manifest = read(DATA / 'manifest.json')
    assert all(file_hash(DATA / p) == h for p, h in manifest['input_hashes'].items())
    ds = read(DATA / 'dialogues.json'); by = {d['id']: d for d in ds}
    assert len(by) == 112 and all(set(d) == {'id', 'split', 'turns'} for d in ds)
    source = {r['id']: r for r in map(json.loads, (ROOT / 'data/dailydialog.jsonl').read_text(encoding='utf-8').splitlines())}
    assert all(d['turns'] == source[d['id']]['turns'] for d in ds)
    refs = read(DATA / 'reference.json'); refids = {f['id'] for r in refs for f in r['facts']}
    assert {r['dialogue_id'] for r in refs} == set(by) and len(refids) == 329
    assert sum(bool(f['A_support_sets']) for r in refs for f in r['facts']) == 138
    for r in refs:
        for f in r['facts']:
            assert all(e['quote'] == by[r['dialogue_id']]['turns'][e['turn'] - 1] for e in f['full_evidence'])
    for exp in ['e1_e2', 'e3']:
        ps = read(DATA / exp / 'predictions.json'); reviews = read(DATA / exp / 'reviews.json')
        assert len({p['task_id'] for p in ps}) == len(ps)
        expected = {review_key(p['dialogue_id'], f, exp) for p in ps for f in p['facts']}
        assert expected == {r['review_id'] for r in reviews} and len(reviews) == len(expected)
        assert all(set(r['reference_ids']) <= refids for r in reviews)
        if exp == 'e1_e2':
            actual = {(p['dialogue_id'], p['k']) for p in ps}
            wanted = {(d['id'], k) for d in ds for k in range(1, (len(d['turns']) + 1) // 2 + 1)} | {('shared_prior', 0)}
            assert actual == wanted and len(ps) == 459
            assert next(p for p in ps if p['dialogue_id'] == 'shared_prior')['facts'] == []
        else:
            assert {(p['dialogue_id'], p['arm']) for p in ps} == {(d, a) for d in by for a in ['direct_off', 'direct_on', 'dual_off', 'dual_on']}
    return {'dialogues': 112, 'full_reference_facts': 329, 'A_supported_reference_facts': 138,
            'valid_prefix_results_including_prior': 459, 'valid_factorial_results': 448, 'canonical_inputs_valid': True}
