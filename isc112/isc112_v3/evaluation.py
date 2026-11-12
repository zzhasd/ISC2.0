"""Shared frozen scoring, explicit semantic review, and full-cost V3 comparison."""
import hashlib
import json
from isc112_v2 import evaluation as shared
from isc112_v2.runner import ROOT, read, save, freeze, lines, sha
from .run import OUT, DATA, verify, valid, chosen, blocked


def configure(mode):
    shared.OUT = OUT / mode; shared.ARM = mode
    shared.EXTRA_REVIEW_DIRS = []
    shared.EXTRA_REVIEW_FILES = [ROOT / 'results/isc112_v22/semantic_review.json']
    if mode == 'retain_union' and (OUT / 'refined/semantic_review.json').exists():
        shared.EXTRA_REVIEW_FILES += [OUT / 'refined/semantic_review.json']
    if mode in {'guarded','guarded_v2'}:shared.EXTRA_REVIEW_FILES += [OUT/'retain_union/semantic_review.json',OUT/'refined/semantic_review.json']
    shared.RAW_FILES = [OUT / 'api_raw.jsonl']


def review(mode):
    configure(mode); return shared.review()


def early(mode):
    configure(mode);return shared.early_predictions()


def analyze(mode):
    configure(mode); return shared.analyze()


def reuse(mode):
    """Bind already actually-reviewed identical assertions to a second output mode."""
    configure(mode)
    source=OUT/'refined/semantic_review.json'
    known={r['review_id']:r for r in read(source)}
    manifest=read(OUT/mode/'review_manifest.json');count=0
    fields=['verdict','reference_ids','partial_reference_ids','A_grounded','source_status','rationale',
            'conjunctive_atoms','canonical_id','grounded_reference_ids']
    for meta in manifest['packets']:
        packet=read(OUT/mode/f'review_packets/packet_{meta["packet"]:02d}.json');dec={}
        for d in packet:
            for q in d['review_rows']:
                assert q['review_id'] in known,'New semantic claim still needs actual review'
                old=known[q['review_id']]
                assert q['dialogue_id']==old['dialogue_id'] and q['claim']==old['claim'] and q['time']==old['time']
                assert all(ev in old['evidence_variants'] for ev in q['evidence_variants']),'New evidence variant needs review'
                dec[q['index']]={k:old[k] for k in fields if k in old}
                dec[q['index']].update(reuse_source=str(source.relative_to(ROOT)),
                    reuse_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        count+=shared.record_batch(meta['packet'],dec)
    return {'exact_already_reviewed_claims_reused':count,'source':str(source)}


def check(mode):
    verify(); tasks = read(OUT / 'requests.json'); raw = lines(OUT / 'api_raw.jsonl'); starts = lines(OUT / 'attempt_starts.jsonl')
    assert len(tasks) == 112 and len({t['task_id'] for t in tasks}) == 112
    assert len(raw) == len(starts) and {r['attempt_id'] for r in raw} == {s['attempt_id'] for s in starts}
    selections = {s['task_id']: s for s in read(OUT / 'selection_bindings.json')}
    aa = {d['id']: d['visible_A'] for d in read(DATA / 'visible_A.json')}
    baseline = {p['dialogue_id']:p for p in read(DATA / 'baseline_predictions.json')}
    ref = {p['dialogue_id']:p for p in read(OUT / 'refined/predictions.json')}
    union = {p['dialogue_id']:p for p in read(OUT / 'retain_union/predictions.json')}
    assert len(ref) == len(union) == 112
    for t in tasks:
        u = json.loads(t['payload']['messages'][1]['content'])
        assert set(u) == {'visible_A','prior_items'} and u['visible_A'] == aa[t['dialogue_id']]
        expected = [{k:f[k] for k in ['claim','time','evidence_turns']} | {'id':f'b{i+1}'} for i,f in enumerate(baseline[t['dialogue_id']]['facts'])]
        assert u['prior_items'] == expected and t['request_sha256'] == sha(t['payload'])
        r = chosen(t,raw)
        if r is None:
            assert blocked(t,raw) and selections[t['task_id']]['selection']=='explicit_provider_blocked_baseline_fallback'
            assert ref[t['dialogue_id']]['outcome']=='provider_blocked_baseline_fallback'
            final=baseline[t['dialogue_id']]
        else:
            assert r['attempt_id'] == selections[t['task_id']]['attempt_id']
            assert r['body']['model'] == 'qwen3.8-flash' and r['body']['choices'][0]['message'].get('reasoning_content')
            final = valid(t,r)
        assert all(ref[t['dialogue_id']][k] == final[k] for k in ['facts','items','hypotheses','excluded'])
        assert sum(r['task_id'] == t['task_id'] for r in raw) <= 4
        norm=lambda f:(' '.join(f['claim'].lower().split()),' '.join(f['time'].lower().split()))
        assert {norm(f) for f in baseline[t['dialogue_id']]['facts']} <= {norm(f) for f in union[t['dialogue_id']]['facts']}
    configure(mode); reviews = shared.reviewed()
    if mode in {'guarded','guarded_v2'}:
        if mode=='guarded':from .guarded import combine
        else:from .guarded_v2 import combine
        m=read(DATA/f'{mode}_manifest.json')
        assert m['code_sha256']==hashlib.sha256((ROOT/f'isc112_v3/{mode}.py').read_bytes()).hexdigest()
        protocol='ISC112_V3_GUARDED_PROTOCOL.md' if mode=='guarded' else 'ISC112_V3_GUARDED_V2_PROTOCOL.md'
        assert m['protocol_sha256']==hashlib.sha256((ROOT/protocol).read_bytes()).hexdigest()
        if mode=='guarded_v2':assert m['parent_code_sha256']==hashlib.sha256((ROOT/'isc112_v3/guarded.py').read_bytes()).hexdigest()
        guarded={p['dialogue_id']:p for p in read(OUT/mode/'predictions.json')}
        assert m['refined_sha256']==sha(read(OUT/'refined/predictions.json'))
        for did,p in ref.items():
            computed,_=combine(baseline[did],p,aa[did]);assert guarded[did]==computed
    result={'original_files_unchanged':True,'same_112_dialogues':True,'A_only_with_A_derived_cache':True,
        'first_valid_selection':True,'all_new_facts_reviewed':True,'thinking_observed':True,
        'retain_union_preserves_baseline':True,'new_actual_calls':len(raw),'pipeline_actual_calls':336+len(raw),'review_count':len(reviews),
        'explicit_baseline_fallbacks':sum(p['outcome']=='provider_blocked_baseline_fallback' for p in ref.values())}
    save(OUT / mode / 'final_checks.json',result);return result


def report(mode):
    from .publication import build
    return build()
