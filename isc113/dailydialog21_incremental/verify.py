"""Audit complete artifacts and replay frozen inference entirely offline."""
import hashlib
import argparse
import json
from pathlib import Path
from collections import Counter
from prepare_evaluation import read,agd,HERE,scoring_input_fingerprint,pool_level_findings
from run_inference import safe_item,direct,elara,prompts,common,Transport

def verify_review_progress():
    """Verify existing semantic artifacts without filling missing judgments."""
    support_count=ready_count=pool_count=0
    source_mapping=read(HERE/'agd_eval/private_source_mapping.json')
    pending=[];level_findings=[]
    for target in sorted((HERE/'agd_eval/judgments/support').glob('*.json')):
        pid=target.stem;support=read(target)
        packet=read(HERE/'agd_eval/packets/support'/target.name)
        assert agd.stable_hash(packet)==source_mapping[pid]['support_input_sha256'],'Blinded packet changed since source preparation'
        candidates=[c for batch in packet['batches'] for c in batch]
        assert candidates==source_mapping[pid]['candidates'],'Candidate-to-source mapping changed'
        agd.validate_support(support,candidates,packet['visible_turns']);support_count+=1
        sizes=[len(batch) for batch in packet['batches']]
        meta=support.get('_meta',{})
        if not candidates:
            assert meta.get('deterministic_empty_input') and not support['items']
        else:
            assert meta['model']=='gpt-6.1-sol' and meta['reasoning_effort']=='high'
            assert meta['input_sha256']==agd.stable_hash(packet)
            if meta.get('reviewed_batch_sizes')!=sizes:
                pending.append(pid);continue
            for i,batch in enumerate(packet['batches']):
                receipt=read(HERE/'agd_eval/batch_reviews/support'/pid/f'{i:03d}.json')
                items=[x for x in support['items'] if x['id'] in {c['id'] for c in batch}]
                assert receipt['batch_size']==len(batch)<=12
                assert receipt['input_sha256']==agd.stable_hash({'visible_turns':packet['visible_turns'],'candidates':batch})
                assert receipt['reviewed_items_sha256']==agd.stable_hash(items),'Support changed after batch review'
        ready_count+=1
        pool_target=HERE/'agd_eval/judgments/pool'/target.name
        if not pool_target.exists():continue
        pool=read(pool_target);pool_packet=read(HERE/'agd_eval/packets/pool'/target.name)
        expected=[{'atom_id':f'{item["id"]}::{i}','claim':a['text'],'turn_ids':a['turn_ids'],'level':a['label']}
                  for item in support['items'] for i,a in enumerate(item['atoms']) if a['label'] in agd.VALID]
        assert pool_packet['atoms']==expected
        agd.validate_pool(pool,expected)
        level_findings.extend(dict(prefix_id=pid,**f) for f in pool_level_findings(pool,expected))
        if expected:
            assert pool['_meta']['model']=='gpt-6.1-sol' and pool['_meta']['reasoning_effort']=='high'
            assert pool['_meta']['input_sha256']==agd.stable_hash(pool_packet)
        else:assert pool.get('_meta',{}).get('deterministic_empty_input')
        for f in pool['facts']:
            assert f['members'],'Fact without any input member'
            covered={s for m in f['members'] for s in m['slot_ids']}
            assert covered=={s['id'] for s in f['slots']},'Invented uncovered slot'
            assert all(s['required'] and s['weight']==(2 if s['core'] else 1) for s in f['slots'])
        pool_count+=1
    alignment_count=0
    for target in sorted((HERE/'alignment/judgments').glob('*.json')):
        obj=read(target);did=target.stem;assert obj['dialogue_id']==did
        packet=read(HERE/'alignment/packets'/target.name)
        assert obj['_meta']['model']=='gpt-6.1-sol' and obj['_meta']['reasoning_effort']=='high'
        assert obj['_meta']['input_sha256']==agd.stable_hash(packet)
        assert obj['_meta'].get('identity_only_no_support_backfill') is True
        assert len(packet['prefixes'])==11
        assert {p['prefix_k'] for p in packet['prefixes']}==set(range(1,12))
        defined={f['id'] for f in obj['unified_facts']}
        assert len(defined)==len(obj['unified_facts'])
        assert all(uid.startswith(did+'::') for uid in defined)
        expected={(p['prefix_id'],f['id']) for p in packet['prefixes'] for f in p['facts']}
        actual=[(m['prefix_id'],m['fact_id']) for m in obj['mapping']]
        assert len(actual)==len(set(actual)) and set(actual)==expected
        assert {m['unified_fact_id'] for m in obj['mapping']}==defined
        for p in packet['prefixes']:
            pool=read(HERE/'agd_eval/judgments/pool'/(p['prefix_id']+'.json'))
            assert p['facts']==[{k:v for k,v in f.items() if k!='members'} for f in pool['facts']]
            mapped=[m['unified_fact_id'] for m in obj['mapping'] if m['prefix_id']==p['prefix_id']]
            assert len(mapped)==len(set(mapped)), 'Two local facts collapsed within one prefix; Pool needs review'
        alignment_count+=1
    summary={'overall_evaluation_complete':False,'support_files_validated':support_count,
             'support_prefixes_with_verified_batch_receipts':ready_count,
             'pool_files_validated':pool_count,'pending_batch_metadata':pending,
             'missing_support_prefixes':341-support_count,'missing_pools':341-pool_count,
             'complete_dialogue_alignments_validated':alignment_count,
             'pool_level_policy_findings_count':len(level_findings)}
    agd.dump(HERE/'agd_eval/quality_findings/pool_levels.json',level_findings)
    agd.dump(HERE/'results/review_progress_verification.json',summary)
    print(json.dumps(summary,indent=2));return summary

def main(inference_only=False):
    prefixes=read(HERE/'data/prefix_inputs.json');manifest=read(HERE/'experiment_manifest.json')
    for name,expected in manifest['source_sha256'].items():
        assert hashlib.sha256((HERE/'source_snapshot'/name).read_bytes()).hexdigest()==expected
    for name,expected in read(HERE/'transport_manifest.json').items():
        assert hashlib.sha256((HERE/'source_snapshot/transport'/name).read_bytes()).hexdigest()==expected
    rows=[]
    for ledger in (HERE/'inference').glob('api*/attempts.jsonl'):
        rows.extend(json.loads(s) for s in ledger.read_text(encoding='utf-8').splitlines() if s.strip())
    starts=[r for r in rows if r['event']=='start'];completed=[r for r in rows if r['event']=='complete']
    assert {r['attempt_id'] for r in starts}=={r['attempt_id'] for r in completed},'Live/unresolved requests remain'
    valid={r['task_id']:r for r in completed if r.get('valid')}
    request_by_id={r['task_id']:r for r in starts}
    pmap={p['prefix_id']:p for p in prefixes}
    for start in starts:
        req=start['request'];pid=start['logical_name'].split('/')[1]
        assert pid in pmap and req['model']=='qwen3.8-flash'
        assert req['temperature']==0 and req['enable_thinking'] and req['thinking_budget']==512
        payload=json.loads(req['messages'][1]['content'])
        assert payload['visible_turns']==pmap[pid]['visible_turns'],'Request leakage or wrong prefix'
    counts=Counter();replayed=0;used_all=set()
    class Replay:
        def __init__(self,ids):self.ids=ids;self.used=[]
        def call(self,name,payload,validate):
            matches=[tid for tid in self.ids if request_by_id[tid]['logical_name']==name and request_by_id[tid]['request']==payload]
            assert len(matches)==1, f'Cannot replay request: {name}'
            tid=matches[0];self.used.append(tid)
            return Transport.parse(valid[tid]['body'],validate),tid
    for p in prefixes:
        for algorithm in ('direct_thinking','elara_v1'):
            output=read(HERE/'inference'/algorithm/(p['prefix_id']+'.json'))
            assert output['input_sha256']==common.digest(safe_item(p)) and output['model']=='qwen3.8-flash'
            replay=Replay(output['task_ids']);item=safe_item(p)
            if algorithm=='direct_thinking':
                claims,_=replay.call(item['item_id']+'/direct',direct.payload(prompts.DIRECT,{'visible_turns':item['visible_turns'],'target':'hidden partner'}),lambda o:direct.validate_claims(o,item['visible_turns']))
            else:
                native,diagnostics=elara.pipeline(replay,item);claims=native['claims']
                assert diagnostics==read(HERE/'inference/diagnostics'/(p['prefix_id']+'.json'))
            assert claims==output['claims'],'Saved predictions differ from original algorithm replay'
            assert replay.used==output['task_ids']
            used_all.update(output['task_ids'])
            counts[algorithm]+=1;replayed+=1
    assert used_all==set(valid),'Successful API calls are missing from prediction provenance'
    frozen_sweep=read(HERE/'agd_eval/sweep_manifest.json')
    assert len(frozen_sweep['files'])==341
    for name,expected in frozen_sweep['files'].items():
        assert hashlib.sha256((HERE/'agd_eval/judgments/sweep'/name).read_bytes()).hexdigest()==expected,'Independent Sweep was modified after freezing'
    inference_summary={'inference_complete':True,'evaluation_complete':False,
             'offline_replayed_predictions':replayed,'counts':dict(counts),
             'api_attempts':len(completed),'valid_logical_requests':len(valid),
             'duplicate_valid_completions':len([r for r in completed if r.get('valid')])-len(valid),
             'api_failure_count':sum(not r.get('valid',False) for r in completed),
             'charged_tokens_reported':sum(r.get('body',{}).get('usage',{}).get('total_tokens',0) for r in completed),
             'all_request_prefix_boundaries_verified':True,'independent_sweep_hashes_unchanged':True}
    if inference_only:
        agd.dump(HERE/'results/inference_verification.json',inference_summary)
        print(json.dumps(inference_summary,indent=2));return
    review=verify_review_progress()
    assert review['support_prefixes_with_verified_batch_receipts']==341 and review['pool_files_validated']==341
    assert review['complete_dialogue_alignments_validated']==31
    assert review['pool_level_policy_findings_count']==0,'Unresolved E1/E2 field-level policy findings'
    for p in prefixes:
        pid=p['prefix_id'];turns=p['visible_turns']
        sweep=read(HERE/'agd_eval/judgments/sweep'/(pid+'.json'))
        agd.validate_sweep(sweep,turns)
        assert sweep['_meta']['model']=='gpt-6.1-sol' and sweep['_meta']['reasoning_effort']=='high'
        assert sweep['_meta']['input_sha256']==agd.stable_hash({'visible_turns':turns})
        support=read(HERE/'agd_eval/judgments/support'/(pid+'.json'))
        packet=read(HERE/'agd_eval/packets/support'/(pid+'.json'))
        candidates=[c for batch in packet['batches'] for c in batch]
        assert all(len(batch)<=12 for batch in packet['batches'])
        agd.validate_support(support,candidates,turns)
        expected_atoms=[{'atom_id':f'{item["id"]}::{i}','claim':a['text'],'turn_ids':a['turn_ids'],'level':a['label']}
                        for item in support['items'] for i,a in enumerate(item['atoms']) if a['label'] in agd.VALID]
        pool=read(HERE/'agd_eval/judgments/pool'/(pid+'.json'))
        atoms=read(HERE/'agd_eval/packets/pool'/(pid+'.json'))['atoms']
        assert atoms==expected_atoms,'Pool packet does not match the actual supported atoms'
        agd.validate_pool(pool,atoms)
        for stage,obj in (('support',support),('pool',pool)):
            if not obj.get('_meta',{}).get('deterministic_empty_input'):
                assert obj['_meta']['model']=='gpt-6.1-sol' and obj['_meta']['reasoning_effort']=='high'
                assert obj['_meta']['input_sha256']==agd.stable_hash(read(HERE/'agd_eval/packets'/stage/(pid+'.json')))
        if candidates:
            assert support['_meta']['reviewed_batch_sizes']==[len(b) for b in packet['batches']]
    for did in {p['dialogue_id'] for p in prefixes}:
        aligned=read(HERE/'alignment/judgments'/(did+'.json'))
        assert aligned['_meta']['model']=='gpt-6.1-sol' and aligned['_meta']['reasoning_effort']=='high'
        assert aligned['_meta']['input_sha256']==agd.stable_hash(read(HERE/'alignment/packets'/(did+'.json')))
    import csv
    with (HERE/'results/prefix_metrics.csv').open(encoding='utf-8-sig',newline='') as f:metrics=list(csv.DictReader(f))
    assert len(metrics)==682
    assert len({(r['dialogue_id'],r['prefix_k'],r['algorithm']) for r in metrics})==682
    for a in ('direct_thinking','elara_v1'):
        for did in {p['dialogue_id'] for p in prefixes}:
            rr=sorted((r for r in metrics if r['algorithm']==a and r['dialogue_id']==did),key=lambda r:int(r['prefix_k']))
            assert [int(r['prefix_k']) for r in rr]==list(range(1,12))
            total=0
            for r in rr:
                total+=int(r['first_new_count']);assert total==int(r['ever_found_count'])
                assert int(r['unique_core_count'])<=int(r['pool_count'])
    assert len(list((HERE/'figures').glob('figure*.png')))==4
    assert read(HERE/'results/scoring_status.json')['input_fingerprint']==scoring_input_fingerprint(),'Statistics are stale after a judgment revision'
    summary={'complete':True,'offline_replayed_predictions':replayed,'counts':dict(counts),
             'api_attempts':len(completed),'valid_logical_requests':len(valid),
             'duplicate_valid_completions':len([r for r in completed if r.get('valid')])-len(valid),
             'api_failure_count':sum(not r.get('valid',False) for r in completed),
             'charged_tokens_reported':sum(r.get('body',{}).get('usage',{}).get('total_tokens',0) for r in completed),
             'all_request_prefix_boundaries_verified':True,'all_scoring_rows_verified':True}
    agd.dump(HERE/'results/verification.json',summary)
    stale=HERE/'results/evaluation_revision_required.json'
    if stale.exists():stale.unlink()
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inference-only',action='store_true')
    parser.add_argument('--review-progress',action='store_true')
    args=parser.parse_args()
    if args.review_progress:verify_review_progress()
    else:main(args.inference_only)
