"""Offline semantic-review packets and frozen-reference comparison; never imported by inference."""
import collections
import csv
import hashlib
import statistics

from isc112.io import review_key
from isc112.statistics import bootstrap_mean, bootstrap_ratio, maximum_match
from .runner import DATA, OUT, ROOT, ARM, read, save, freeze, sha, verify_frozen, lines, validate, chosen


def review():
    predictions = read(OUT / 'predictions.json')
    assert len(predictions) == 112 and len({p['dialogue_id'] for p in predictions}) == 112, 'Complete the 112-dialogue run before freezing review packets'
    if (OUT/'review_manifest.json').exists():
        manifest=read(OUT/'review_manifest.json')
        assert manifest['predictions_sha256']==sha(predictions),'Frozen review input changed'
        queue=read(OUT/'review_queue.json')
        assert manifest['queue_sha256']==sha(queue)
        assert manifest['reference_sha256']==hashlib.sha256((ROOT/'data/isc112/reference.json').read_bytes()).hexdigest()
        # Keep the original queue even if more reviewed variants became available.
        return {'final_dialogues':len(predictions),'fact_occurrences':len(read(OUT/'review_bindings.json')),
            'new_reviews':len(queue),'reused_reviews':len(read(OUT/'review_reused.json')),'packets':len(manifest['packets']),'frozen_queue_reused':True}
    old = {r['review_id']: r for r in read(ROOT / 'data/isc112/e3/reviews.json')}
    for p in globals().get('EXTRA_REVIEW_FILES', []):
        old.update({r['review_id']: r for r in read(p)})
    for folder in [OUT / 'review_early'] + globals().get('EXTRA_REVIEW_DIRS', []):
        for p in sorted(folder.glob('decisions_*.json')):
            old.update({r['review_id']: r for r in read(p)})
    entries = {}; reused = {}; bindings = []
    for p in predictions:
        for n, f in enumerate(p['facts']):
            rid = review_key(p['dialogue_id'], f, 'e3')
            if rid in old and f['evidence_turns'] in old[rid].get('evidence_variants', []):
                reused[rid] = old[rid]
            else:
                row = entries.setdefault(rid, {'review_id': rid, 'dialogue_id': p['dialogue_id'], 'claim': f['claim'],
                        'time': f['time'], 'evidence_variants': [], 'model_origin': f.get('origin', 'revision')})
                if f['evidence_turns'] not in row['evidence_variants']: row['evidence_variants'].append(f['evidence_turns'])
            bindings.append({'review_id': rid, 'dialogue_id': p['dialogue_id'], 'fact_index': n})
    # If any occurrence has a new evidence variant, review the claim once with all
    # variants rather than placing the same key in both reused and new sets.
    for rid in set(entries) & set(reused):
        for ev in reused[rid].get('evidence_variants', []):
            if ev not in entries[rid]['evidence_variants']: entries[rid]['evidence_variants'].append(ev)
        del reused[rid]
    queue = sorted(entries.values(), key=lambda r: (r['dialogue_id'], r['claim'], r['time']))
    for n, q in enumerate(queue): q['index'] = n
    freeze(OUT / 'review_queue.json', queue); freeze(OUT / 'review_reused.json', list(reused.values()))
    freeze(OUT / 'review_bindings.json', bindings)
    ds = {d['id']: d for d in read(ROOT / 'data/isc112/dialogues.json')}
    refs = {r['dialogue_id']: r['facts'] for r in read(ROOT / 'data/isc112/reference.json')}
    ids = sorted({r['dialogue_id'] for r in queue})
    packets = []
    for start in range(0, len(ids), 7):
        selected = ids[start:start+7]; number = len(packets) + 1
        packet = []
        for did in selected:
            packet.append({'dialogue_id': did, 'full_AB': [{'turn': i+1, 'speaker': 'A' if i % 2 == 0 else 'B', 'text': t} for i, t in enumerate(ds[did]['turns'])],
                'frozen_references': [{'id': f['id'], 'claim': f['claim'], 'A_supported': bool(f['A_support_sets'])} for f in refs[did]],
                'review_rows': [q for q in queue if q['dialogue_id'] == did]})
        freeze(OUT / f'review_packets/packet_{number:02d}.json', packet)
        packets.append({'packet': number, 'dialogues': selected, 'rows': sum(len(d['review_rows']) for d in packet), 'sha256': sha(packet)})
    freeze(OUT / 'review_manifest.json', {'predictions_sha256': sha(predictions), 'queue_sha256': sha(queue), 'packets': packets,
        'reference_sha256': hashlib.sha256((ROOT / 'data/isc112/reference.json').read_bytes()).hexdigest(),
        'reviewer': 'current conversational assistant reads A+B and frozen references; method author; not independent human gold'})
    return {'final_dialogues': len(predictions), 'fact_occurrences': len(bindings), 'new_reviews': len(queue), 'reused_reviews': len(reused), 'packets': len(packets)}


def record_batch(number, decisions, folder='review_packets', output_dir=None):
    assert folder in {'review_packets', 'review_early'}
    directory = output_dir or OUT
    packet = read(directory / f'{folder}/packet_{number:02d}.json')
    rows = [r for d in packet for r in d['review_rows']]
    assert set(decisions) == {r['index'] for r in rows}, {'missing': {r['index'] for r in rows} - set(decisions)}
    out = []
    for r in rows:
        x = decisions[r['index']]
        assert x['rationale'].strip() and type(x['A_grounded']) is bool
        out.append({**r, **x, 'reviewer': 'current conversational assistant reads A+B; frozen reference; not independent human gold'})
    freeze(directory / f'{folder}/decisions_{number:02d}.json', out)
    return len(out)


def early():
    """Seven completed dialogues per immutable packet, while remaining API calls run."""
    if not (OUT / 'dependent/requests.json').exists(): return {'waiting': 'candidate phase'}
    assigned = set(); existing = sorted((OUT / 'review_early').glob('packet_*.json'))
    for p in existing: assigned.update(d['dialogue_id'] for d in read(p))
    rows = lines(OUT / 'dependent/api_raw.jsonl'); available = {}
    for t in read(OUT / 'dependent/requests.json'):
        if t['dialogue_id'] in assigned: continue
        r = chosen(t, rows)
        if r: available[t['dialogue_id']] = validate(t, r)
    if len(available) < 7: return {'available_unassigned': len(available)}
    ids = sorted(available)[:7]
    ds = {d['id']: d for d in read(ROOT / 'data/isc112/dialogues.json')}
    refs = {r['dialogue_id']: r['facts'] for r in read(ROOT / 'data/isc112/reference.json')}
    packet = []; number = len(existing) + 1; index = 0
    for did in ids:
        entries = {}
        for f in available[did]['facts']:
            rid = review_key(did, f, 'e3')
            q = entries.setdefault(rid, {'review_id': rid, 'dialogue_id': did, 'claim': f['claim'],
                'time': f['time'], 'model_origin': f['origin'], 'evidence_variants': []})
            if f['evidence_turns'] not in q['evidence_variants']: q['evidence_variants'].append(f['evidence_turns'])
        qq = sorted(entries.values(), key=lambda r: (r['claim'], r['time']))
        for q in qq: q['index'] = index; index += 1
        packet.append({'dialogue_id': did,
            'full_AB': [{'turn': i+1, 'speaker': 'A' if i % 2 == 0 else 'B', 'text': t} for i, t in enumerate(ds[did]['turns'])],
            'frozen_references': [{'id': f['id'], 'claim': f['claim'], 'A_supported': bool(f['A_support_sets'])} for f in refs[did]],
            'review_rows': qq})
    freeze(OUT / f'review_early/packet_{number:02d}.json', packet)
    return {'packet': number, 'dialogues': ids, 'rows': index, 'folder': 'review_early'}


def early_predictions():
    """Incremental review of saved complete predictions, with exact prior review reuse."""
    predictions = read(OUT / 'predictions.json')
    old = {r['review_id']: r for r in read(ROOT / 'data/isc112/e3/reviews.json')}
    for p in globals().get('EXTRA_REVIEW_FILES', []): old.update({r['review_id']:r for r in read(p)})
    existing = sorted((OUT / 'review_early').glob('packet_*.json')); assigned = set()
    for p in existing: assigned.update(d['dialogue_id'] for d in read(p))
    pending = {}
    for p in predictions:
        did=p['dialogue_id']
        if did in assigned:continue
        entries={}
        for f in p['facts']:
            rid=review_key(did,f,'e3')
            if rid in old and f['evidence_turns'] in old[rid].get('evidence_variants',[]):continue
            q=entries.setdefault(rid,{'review_id':rid,'dialogue_id':did,'claim':f['claim'],'time':f['time'],
                'model_origin':f.get('origin','revision'),'evidence_variants':[]})
            if f['evidence_turns'] not in q['evidence_variants']:q['evidence_variants'].append(f['evidence_turns'])
        if entries:pending[did]=sorted(entries.values(),key=lambda r:(r['claim'],r['time']))
    if len(pending)<7 and len(predictions)<112:return {'available_unassigned':len(pending),'completed_dialogues':len(predictions)}
    ids=sorted(pending)[:7]
    if not ids:return {'available_unassigned':0,'completed_dialogues':len(predictions)}
    ds={d['id']:d for d in read(ROOT/'data/isc112/dialogues.json')};refs={r['dialogue_id']:r['facts'] for r in read(ROOT/'data/isc112/reference.json')}
    packet=[];index=0
    for did in ids:
        qq=pending[did]
        for q in qq:q['index']=index;index+=1
        packet.append({'dialogue_id':did,'full_AB':[{'turn':i+1,'speaker':'A' if i%2==0 else 'B','text':t} for i,t in enumerate(ds[did]['turns'])],
            'frozen_references':[{'id':f['id'],'claim':f['claim'],'A_supported':bool(f['A_support_sets'])} for f in refs[did]],'review_rows':qq})
    number=len(existing)+1;freeze(OUT/f'review_early/packet_{number:02d}.json',packet)
    return {'packet':number,'dialogues':ids,'new_review_rows':index}


def decision(kind, refs=(), reason='', ground=True, source='consistent', canonical=None, core=None):
    if isinstance(refs, str): refs = [refs]
    x = {'verdict': kind, 'reference_ids': [] if kind == 'partial' else list(refs),
         'partial_reference_ids': list(refs) if kind == 'partial' else [], 'A_grounded': ground,
         'source_status': source, 'rationale': reason, 'conjunctive_atoms': len(refs) > 1}
    if canonical: x['canonical_id'] = canonical
    if core is not None: x['grounded_reference_ids'] = list(core)
    return x


def reviewed():
    manifest = read(OUT / 'review_manifest.json')
    assert sha(read(OUT / 'predictions.json')) == manifest['predictions_sha256']
    rows = list(read(OUT / 'review_reused.json'))
    for packet in manifest['packets']:
        rows += read(OUT / f'review_packets/decisions_{packet["packet"]:02d}.json')
    result = {r['review_id']: r for r in rows}
    assert len(result) == len(rows)
    assert set(result) == {r['review_id'] for r in read(OUT / 'review_bindings.json')}
    return result


def analyze():
    verify_frozen(); reviews = reviewed()
    ps = {p['dialogue_id']: p for p in read(OUT / 'predictions.json')}
    ds = read(ROOT / 'data/isc112/dialogues.json')
    refs = {r['dialogue_id']: r['facts'] for r in read(ROOT / 'data/isc112/reference.json')}
    costs = collections.defaultdict(list)
    for r in read(OUT / 'cost_ledger.json'): costs[r['dialogue_id']].append(r)
    baseline = [r for r in read(ROOT / 'results/isc112/e3/dialogue_scores.json') if r['arm'] == 'dual_on']
    base = {r['dialogue_id']: r for r in baseline}; rows = []
    assert len(ps) == 112 and set(ps) == set(base)
    for d in ds:
        did = d['id']; p = ps[did]; support = {f['id'] for f in refs[did] if f['A_support_sets']}
        atoms = set(); edges = []; unsupported = scope = conflict = grounded = 0; discoveries = set()
        for f in p['facts']:
            r = reviews[review_key(did, f, 'e3')]
            assert set(r['reference_ids'] + r['partial_reference_ids']) <= {f['id'] for f in refs[did]}
            assert len(r['reference_ids']) <= 1 or r.get('conjunctive_atoms') is True
            exact = [i for i in r['reference_ids'] if i in support and r['A_grounded'] is True]
            core = r.get('grounded_reference_ids', exact)
            assert set(core) <= set(r['reference_ids'])
            atoms.update(i for i in core if i in support); edges.append(exact)
            unsupported += r['A_grounded'] is not True; scope += r['verdict'] == 'out_of_scope'
            conflict += r['source_status'] == 'contradicted'
            grounded += r['A_grounded'] is True and r['source_status'] == 'consistent' and r['verdict'] != 'out_of_scope'
            if r['verdict'] == 'supported_new': discoveries.add(r.get('canonical_id', r['review_id']))
        rows.append({'dialogue_id': did, 'arm': ARM, 'A_reference_count': len(support), 'atomic_coverage': len(atoms),
            'one_to_one_coverage': len(maximum_match(edges)), 'atomic_ids': sorted(atoms), 'raw_claims': len(p['facts']),
            'hypotheses': len(p['hypotheses']), 'unsupported_or_uncertain': unsupported, 'out_of_scope': scope,
            'source_contradicted': conflict, 'grounded_in_scope_raw': grounded, 'supported_new': len(discoveries),
            'additions_accepted': sum(f.get('origin', 'addition' if str(f.get('id','')).startswith('a') else 'candidate') == 'addition' for f in p['facts']), 'actual_calls': len(costs[did]),
            'total_tokens': sum(r.get('total_tokens') or 0 for r in costs[did])})
    metrics = ['A_reference_count', 'atomic_coverage', 'one_to_one_coverage', 'raw_claims', 'hypotheses',
               'unsupported_or_uncertain', 'out_of_scope', 'source_contradicted', 'grounded_in_scope_raw', 'supported_new', 'actual_calls', 'total_tokens']
    def summary(rr, label):
        return {'method': label, 'dialogues': len(rr), **{k: sum(r[k] for r in rr) for k in metrics},
                'coverage': bootstrap_ratio([r['atomic_coverage'] for r in rr], [r['A_reference_count'] for r in rr]),
                'unsupported_fraction': bootstrap_ratio([r['unsupported_or_uncertain'] for r in rr], [r['raw_claims'] for r in rr]),
                'mean_tokens': statistics.mean(r['total_tokens'] for r in rr)}
    new = summary(rows, ARM); old = summary(baseline, 'original_dual_on')
    differences = [r['atomic_coverage'] - base[r['dialogue_id']]['atomic_coverage'] for r in rows]
    largest = max(refs, key=lambda d: sum(bool(f['A_support_sets']) for f in refs[d]))
    result = {'methods': [old, new], 'net_reference_gain': sum(differences), 'paired_gain': bootstrap_mean(differences),
        'without_high_density': bootstrap_mean([v for r, v in zip(rows, differences) if r['dialogue_id'] != largest]),
        'excluded_dialogue': largest, 'improved_dialogues': sum(v > 0 for v in differences),
        'tied_dialogues': sum(v == 0 for v in differences), 'worsened_dialogues': sum(v < 0 for v in differences),
        'coverage_target_met': new['atomic_coverage'] > old['atomic_coverage'],
        'unsupported_target_met': new['unsupported_fraction']['estimate'] <= old['unsupported_fraction']['estimate'],
        'joint_target_met': new['atomic_coverage'] > old['atomic_coverage'] and new['unsupported_fraction']['estimate'] <= old['unsupported_fraction']['estimate'],
        'added_reference_ids': sorted(set().union(*(set(r['atomic_ids']) for r in rows)) - set().union(*(set(r['atomic_ids']) for r in baseline))),
        'lost_reference_ids': sorted(set().union(*(set(r['atomic_ids']) for r in baseline)) - set().union(*(set(r['atomic_ids']) for r in rows))),
        'new_fact_occurrences': sum(len(p['facts']) for p in ps.values()), 'review_count': len(reviews),
        'setting': 'same 112 previously inspected development dialogues; current assistant source-aware provisional review; no independent held-out confirmation'}
    raw_out = globals().get('RAW_OUT', OUT)
    raw = sum((lines(p) for p in globals().get('RAW_FILES', [raw_out / 'initial/api_raw.jsonl', raw_out / 'dependent/api_raw.jsonl'])), [])
    result['execution'] = {'planned_logical_calls': 336, 'actual_calls': len(raw),
        'first_attempt_valid': sum(r['attempt'] == 1 and r['valid'] for r in raw),
        'invalid_attempts': sum(not r['valid'] for r in raw),
        'http_status_counts': dict(collections.Counter(str(r.get('http_status')) for r in raw)),
        'validation_errors': dict(collections.Counter(r.get('validation_error') for r in raw if not r['valid']))}
    save(OUT / 'semantic_review.json', list(reviews.values())); save(OUT / 'dialogue_scores.json', rows); save(OUT / 'summary.json', result)
    with (OUT / 'dialogue_scores.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    return {k: result[k] for k in ['net_reference_gain', 'paired_gain', 'coverage_target_met', 'unsupported_target_met', 'joint_target_met']}


def check():
    verify_frozen()
    starts = []; rows = []; tasks = []
    for phase in ['initial', 'dependent']:
        tasks += read(OUT / phase / 'requests.json'); starts += lines(OUT / phase / 'attempt_starts.jsonl'); rows += lines(OUT / phase / 'api_raw.jsonl')
    assert len(tasks) == 336 and len({t['task_id'] for t in tasks}) == 336
    assert {s['attempt_id'] for s in starts} == {r['attempt_id'] for r in rows} and len(starts) == len(rows)
    cap = read(DATA / 'recovery_manifest.json')['max_total_attempts'] if (DATA / 'recovery_manifest.json').exists() else 4
    assert all(sum(r['task_id'] == t['task_id'] for r in rows) <= cap for t in tasks)
    aa = {d['id']: d['visible_A'] for d in read(DATA / 'visible_A.json')}
    for t in tasks:
        u = __import__('json').loads(t['payload']['messages'][1]['content'])
        assert set(u) == ({'visible_A', 'candidates'} if t['stage'] == 'judge' else {'visible_A'})
        assert u['visible_A'] == aa[t['dialogue_id']]
        assert t['request_sha256'] == sha(t['payload'])
        r = chosen(t, rows); assert r is not None; validate(t, r)
        assert r['body']['model'] == 'qwen3.8-flash'
        assert r['body']['choices'][0]['message'].get('reasoning_content'), 'Thinking not observed'
    assert len(read(OUT / 'predictions.json')) == 112
    assert len(read(OUT / 'cost_ledger.json')) == len(rows)
    result = {'original_files_unchanged': True, 'same_112_dialogues': True, 'A_only_payloads': True,
              '336_logical_requests': True, 'first_valid_selection': True, 'thinking_observed': True,
              'all_attempts_accounted': True, 'valid_finals': 112, 'actual_calls': len(rows), 'total_attempt_cap': cap}
    if (OUT / 'review_manifest.json').exists(): result['all_final_facts_reviewed'] = bool(reviewed())
    save(OUT / 'final_checks.json', result)
    return result


def report():
    from .publication import build
    return build()
