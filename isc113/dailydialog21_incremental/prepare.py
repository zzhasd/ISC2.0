"""Freeze the exact length-21 dataset; keep hidden turns outside inference inputs."""
import collections
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=2)
    if path.exists():
        assert json.loads(path.read_text(encoding='utf-8')) == obj, f'Frozen file changed: {path}'
    else:
        path.write_text(text, encoding='utf-8')

def main():
    source = ROOT / 'data/dailydialog.jsonl'
    records = [json.loads(s) for s in source.read_text(encoding='utf-8').splitlines() if s.strip()]
    selected = [r for r in records if len(r['turns']) == 21]
    assert len(records) == 13118 and len(selected) == 31
    assert collections.Counter(r['split'] for r in selected) == {'train':27,'validation':2,'test':2}
    prefixes = []
    for r in selected:
        visible = [{'turn_id':i+1,'text':t} for i,t in enumerate(r['turns']) if i % 2 == 0]
        for k in range(1, 12):
            prefixes.append(dict(prefix_id=f"{r['id']}__k{k:02d}", dialogue_id=r['id'],
                                 prefix_k=k, split=r['split'], direction='A_to_B',
                                 visible_turns=visible[:k]))
    assert len({p['prefix_id'] for p in prefixes}) == 341
    for r in selected:
        ps = [p for p in prefixes if p['dialogue_id'] == r['id']]
        for k,p in enumerate(ps, 1):
            assert [t['turn_id'] for t in p['visible_turns']] == list(range(1,2*k,2))
            if k>1: assert ps[k-2]['visible_turns'] == p['visible_turns'][:-1]
        assert [t['text'] for t in ps[-1]['visible_turns']] == r['turns'][::2]
    save(HERE/'data/selected_dialogues.json', selected)
    save(HERE/'data/prefix_inputs.json', prefixes)
    save(HERE/'data/prefix_manifest.json', {
        'source_file':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'source_count':len(records),'dialogue_count':31,'prefix_count':341,
        'splits':dict(collections.Counter(r['split'] for r in selected)),
        'prefix_ids':[p['prefix_id'] for p in prefixes], 'all_invariants_passed':True})
    snapshot = HERE/'source_snapshot'
    snapshot.mkdir(exist_ok=True)
    hashes = {}
    for name in ['new_algorithm.py','inference.py','prompts.py','common.py']:
        data=(HERE.parent/name).read_bytes()
        path=snapshot/name
        if path.exists(): assert path.read_bytes()==data
        else: path.write_bytes(data)
        hashes[name]=hashlib.sha256(data).hexdigest()
    save(HERE/'experiment_manifest.json', {
        'protocol':'DailyDialog length-21 incremental / AGD-EVAL 2026-11-06',
        'hypotheses':['H1 within-length evidence accumulation','H2 widening ELARA advantage','H3 E2 marginal discoveries'],
        'predictor_requested':'qwen3.8-flash','predictor_fallback_allowed':False,
        'judge':{'model':'gpt-6.1-sol','reasoning_effort':'high','mode':'Codex evaluation subagent','qwen_judge_forbidden':True},
        'direct':{'temperature':0,'thinking_budget':512,'max_tokens':2048,'claim_limit':10},
        'elara':{'original_source':'ISC113/new_algorithm.py','temperature':0,'thinking_budget':512,
                 'generation_passes':['explicit','implicit','gap_scan'],'max_tokens_per_call':4096,
                 'audit_batch_size':8,'prompt_claim_limit_per_pass':16,'validation_limit_per_pass':18,
                 'final_claim_limit':None,'internal_auditor_is_part_of_predictor':True},
        'gold':None,'new_vs_gold':'not_applicable','support_batch_size':12,
        'slots':{'all_required':True,'core_weight':2,'other_weight':1},
        'bootstrap':{'unit':'paired whole dialogue','replicates':2000,'seed':20261106},
        'human_calibration_complete':False,'source_sha256':hashes,
        'adaptations':['original qwen3.8-flash predictor preserved per user correction',
                       'Sol high evaluator replaces original Qwen evaluator',
                       'references=[]; no old-gold novelty metrics',
                       'cross-prefix identity alignment cannot backfill evidence']})
    print('Frozen 31 dialogues / 341 A-only prefixes; all invariants passed.')

if __name__ == '__main__': main()
