"""Offline transport for the designated Sol evaluator. No model/API/semantic rules.

The evaluator authors each decision. This module only displays A-only deltas,
validates their structural schema, and binds persisted results to prefix inputs.
No predictions or hidden/future utterances are opened by this module.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROTOCOL = ROOT.parent / 'agd_eval_20261106' / 'agd_eval.py'
spec = importlib.util.spec_from_file_location('agd_protocol', PROTOCOL)
agd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agd)

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def inputs():
    rows = read(ROOT / 'data' / 'prefix_inputs.json')
    for row in rows:
        assert set(row) <= {'prefix_id','dialogue_id','prefix_k','split','direction','visible_turns'}
        assert all(set(t) <= {'turn_id','text'} for t in row['visible_turns'])
        assert all(t['turn_id'] % 2 == 1 for t in row['visible_turns'])
    return {r['prefix_id']:r for r in rows}

def show(k):
    rows = inputs()
    for row in sorted(rows.values(), key=lambda r:r['prefix_id']):
        if row['prefix_k'] != k:
            continue
        prior_id = f"{row['dialogue_id']}__k{k-1:02d}"
        prior = rows.get(prior_id)
        if prior:
            assert row['visible_turns'][:-1] == prior['visible_turns']
            assert (ROOT/'agd_eval/judgments/sweep'/f'{prior_id}.json').exists(), 'Earlier prefix must be reviewed first'
        print(json.dumps({'prefix_id':row['prefix_id'], 'new_turn':row['visible_turns'][-1]}, ensure_ascii=False))

def publish_sweep(k, decisions, retained):
    """Persist explicit authored decisions. Retention IDs are evaluator decisions,
    never inferred from utterance patterns. Earlier prefix must be immutable.
    """
    rows = inputs()
    expected = {r['dialogue_id'] for r in rows.values() if r['prefix_k']==k}
    assert set(decisions).isdisjoint(retained)
    assert set(decisions) | set(retained) == expected
    targets = []
    for did in sorted(expected):
        pid = f'{did}__k{k:02d}'
        row = rows[pid]
        target = ROOT/'agd_eval/judgments/sweep'/f'{pid}.json'
        assert not target.exists(), f'Immutable judgment exists: {pid}'
        if did in retained:
            assert k > 1
            claims = read(ROOT/'agd_eval/judgments/sweep'/f'{did}__k{k-1:02d}.json')['claims']
            claims = [{key:value for key,value in c.items() if key!='id'} for c in claims]
        else:
            claims = [{'claim':c[0], 'turn_ids':c[1], 'proposed_level':c[2], 'mechanism':c[3]} for c in decisions[did]]
        agd.validate_sweep({'claims':claims}, row['visible_turns'])
        for i,c in enumerate(claims): c['id'] = f's_{pid}_{i}'
        obj = {'claims':claims, '_meta':{'model':'gpt-6.1-sol', 'reasoning_effort':'high',
               'mode':'designated_subagent_semantic_review', 'stage':'sweep',
               'input_sha256':agd.stable_hash({'visible_turns':row['visible_turns']}),
               'prefix_id':pid, 'prefix_k':k, 'independent_from_predictions':True,
               'retention_explicitly_reviewed':did in retained}}
        targets.append((target,obj))
    for target,obj in targets: agd.dump(target,obj)
    print(f'Persisted {len(targets)} reviewed Sweep prefixes at k={k}')

def support_packet(pid):
    return read(ROOT/'agd_eval/packets/support'/f'{pid}.json')

def publish_support_batch(pid, batch_index, decisions):
    """Commit one actually reviewed original batch, then merge complete prefixes.
    Decision indices match show_support's global candidate numbering.
    """
    packet=support_packet(pid);batch=packet['batches'][batch_index]
    start=sum(map(len,packet['batches'][:batch_index]))
    assert len(batch)<=12 and sorted(d[0] for d in decisions)==list(range(start,start+len(batch)))
    items=[]
    for d in decisions:
        c=batch[d[0]-start]
        if len(d)==2:
            atoms=[dict(zip(['text','label','turn_ids','mechanism','reason'],a)) for a in d[1]]
        else:
            _,label,turns,mechanism,reason=d
            atoms=[dict(text=c['claim'],label=label,turn_ids=turns,mechanism=mechanism,reason=reason)]
        items.append({'id':c['id'],'atoms':atoms})
    agd.validate_support({'items':items},batch,packet['visible_turns'])
    partial=ROOT/'agd_eval/reviewed_batches/support'/pid/f'{batch_index:03d}.json'
    assert not partial.exists()
    payload_hash=agd.stable_hash({'visible_turns':packet['visible_turns'],'candidates':batch})
    agd.dump(partial,{'items':items,'batch_index':batch_index,'batch_size':len(batch),'input_sha256':payload_hash,
                      'mode':'separate_original_batch_semantic_review'})
    partials=[partial.parent/f'{i:03d}.json' for i in range(len(packet['batches']))]
    if all(p.exists() for p in partials):
        rs=[read(p) for p in partials]
        obj={'items':[item for r in rs for item in r['items']],
             '_meta':{'model':'gpt-6.1-sol','reasoning_effort':'high','stage':'support',
                'mode':'designated_subagent_semantic_review','prefix_id':pid,'input_sha256':agd.stable_hash(packet),
                'reviewed_batch_sizes':[r['batch_size'] for r in rs],
                'reviewed_batch_input_sha256':[r['input_sha256'] for r in rs]}}
        agd.validate_support(obj,[c for b in packet['batches'] for c in b],packet['visible_turns'])
        target=ROOT/'agd_eval/judgments/support'/f'{pid}.json';assert not target.exists()
        agd.dump(target,obj)
        for i,r in enumerate(rs):
            receipt=ROOT/'agd_eval/batch_reviews/support'/pid/f'{i:03d}.json'
            assert not receipt.exists()
            agd.dump(receipt,{'prefix_id':pid,'batch':i,'mode':r['mode'],'batch_size':r['batch_size'],
                              'input_sha256':r['input_sha256'],'reviewed_items_sha256':agd.stable_hash(r['items'])})
        print('SUPPORT COMPLETE',pid,len(obj['items']))
    else:print('SUPPORT BATCH',pid,batch_index,len(batch))

def revise_support_batch(pid, batch_index, decisions):
    """Persist an explicitly re-reviewed batch, archiving prior support/receipts."""
    packet=support_packet(pid);batch=packet['batches'][batch_index]
    start=sum(map(len,packet['batches'][:batch_index]))
    assert len(batch)<=12 and sorted(d[0] for d in decisions)==list(range(start,start+len(batch)))
    items=[]
    for d in decisions:
        c=batch[d[0]-start]
        if len(d)==2:atoms=[dict(zip(['text','label','turn_ids','mechanism','reason'],a)) for a in d[1]]
        else:
            _,label,turns,mechanism,reason=d
            atoms=[dict(text=c['claim'],label=label,turn_ids=turns,mechanism=mechanism,reason=reason)]
        items.append({'id':c['id'],'atoms':atoms})
    agd.validate_support({'items':items},batch,packet['visible_turns'])
    target=ROOT/'agd_eval/judgments/support'/f'{pid}.json';obj=read(target)
    archive=ROOT/'agd_eval/judgments/support_revisions'/pid/agd.stable_hash(obj)[:16]
    agd.dump(archive/'support.json',obj)
    for old in (ROOT/'agd_eval/batch_reviews/support'/pid).glob('*.json'):
        agd.dump(archive/'batch_reviews'/old.name,read(old))
    replacements={x['id']:x for x in items}
    obj['items']=[replacements.get(x['id'],x) for x in obj['items']]
    agd.validate_support(obj,[c for b in packet['batches'] for c in b],packet['visible_turns'])
    items=[x for x in obj['items'] if x['id'] in replacements]
    receipt=ROOT/'agd_eval/batch_reviews/support'/pid/f'{batch_index:03d}.json'
    old_receipt=read(receipt) if receipt.exists() else None
    agd.dump(receipt,{'prefix_id':pid,'batch':batch_index,'mode':'explicit_semantic_revision',
         'batch_size':len(batch),'input_sha256':agd.stable_hash({'visible_turns':packet['visible_turns'],'candidates':batch}),
         'reviewed_items_sha256':agd.stable_hash(items),'revises_receipt_sha256':agd.stable_hash(old_receipt)})
    receipts=[read(p) for p in sorted(receipt.parent.glob('*.json'))]
    obj['_meta']['batch_review_receipts']=receipts
    obj['_meta']['reviewed_batch_sizes']=[r['batch_size'] for r in receipts]
    obj['_meta']['reviewed_batch_input_sha256']=[r['input_sha256'] for r in receipts]
    obj['_meta']['latest_revision_archive']=str(archive.relative_to(ROOT))
    agd.dump(target,obj);print('REVISED SUPPORT BATCH',pid,batch_index)

def revise_support_batch_retaining(pid, batch_index, changes, retained_indices):
    """Explicit evaluator retention after separately inspecting this exact batch."""
    packet=support_packet(pid);cands=[c for b in packet['batches'] for c in b]
    obj=read(ROOT/'agd_eval/judgments/support'/f'{pid}.json');by={x['id']:x for x in obj['items']}
    assert set(changes).isdisjoint(retained_indices)
    decisions=[[i,atoms] for i,atoms in changes.items()]
    for i in retained_indices:
        decisions.append([i,[[a['text'],a['label'],a['turn_ids'],a['mechanism'],a['reason']] for a in by[cands[i]['id']]['atoms']]])
    revise_support_batch(pid,batch_index,decisions)

def publish_support(pid, decisions, retained=()):
    """Each decision is evaluator-authored: [index,label,turns,mechanism,reason],
    or [index, [[atom_text,label,turns,mechanism,reason], ...]] for atomization.
    Candidate indices are only a compact transport for this exact hashed packet.
    """
    packet=support_packet(pid)
    cands=[c for batch in packet['batches'] for c in batch]
    decisions=list(decisions)
    for i,previous_pid,previous_i in retained:
        previous_packet=support_packet(previous_pid)
        previous_cands=[c for b in previous_packet['batches'] for c in b]
        assert cands[i]['claim']==previous_cands[previous_i]['claim'], 'Retention requires exact unchanged candidate'
        previous_result=read(ROOT/'agd_eval/judgments/support'/f'{previous_pid}.json')
        previous_item=next(x for x in previous_result['items'] if x['id']==previous_cands[previous_i]['id'])
        decisions.append([i,[[a['text'],a['label'],a['turn_ids'],a['mechanism'],a['reason']] for a in previous_item['atoms']]])
    assert sorted(d[0] for d in decisions)==list(range(len(cands)))
    items=[]
    for decision in decisions:
        i=decision[0]
        if len(decision)==2:
            atoms=[dict(zip(['text','label','turn_ids','mechanism','reason'],a)) for a in decision[1]]
        else:
            _,label,turns,mechanism,reason=decision
            atoms=[{'text':cands[i]['claim'],'label':label,'turn_ids':turns,'mechanism':mechanism,'reason':reason}]
        items.append({'id':cands[i]['id'],'atoms':atoms})
    obj={'items':items}
    agd.validate_support(obj,cands,packet['visible_turns'])
    obj['_meta']={'model':'gpt-6.1-sol','reasoning_effort':'high',
                  'stage':'support','mode':'designated_subagent_semantic_review',
                  'prefix_id':pid,'input_sha256':agd.stable_hash(packet),
                  'explicitly_reviewed_retention_indices':[x[0] for x in retained]}
    target=ROOT/'agd_eval/judgments/support'/f'{pid}.json'
    assert not target.exists(), 'Existing reviewed judgment is immutable'
    agd.dump(target,obj)
    print('SUPPORT',pid,len(items),'candidates')

def show_support(pid, batch=0):
    packet=support_packet(pid)
    print(json.dumps({'prefix_id':pid,'visible_turns':packet['visible_turns']},ensure_ascii=False))
    selected=packet['batches'][batch]
    assert len(selected)<=12
    print(f'BATCH {batch+1}/{len(packet["batches"])} SIZE {len(selected)}')
    start=sum(map(len,packet['batches'][:batch]))
    for i,c in enumerate(selected,start): print(f'{i} [{c["id"]}]: {c["claim"]}')

def record_reviewed_batch(pid, batch, mode='posthoc_independent_batch_recheck'):
    """Called only by evaluator after separately reviewing the displayed batch.
    This records that explicit review action; it does not assess any text.
    """
    packet=support_packet(pid)
    candidates=packet['batches'][batch]
    assert len(candidates)<=12
    target=ROOT/'agd_eval/judgments/support'/f'{pid}.json'
    obj=read(target)
    if len(obj['items'])>12 and mode=='posthoc_independent_batch_recheck':
        archive=ROOT/'agd_eval/judgments/support_revisions'/pid/'before_batch_recheck.json'
        if not archive.exists(): agd.dump(archive,obj)
    items=[x for x in obj['items'] if x['id'] in {c['id'] for c in candidates}]
    agd.validate_support({'items':items},candidates,packet['visible_turns'])
    receipt=ROOT/'agd_eval/batch_reviews/support'/pid/f'{batch:03d}.json'
    assert not receipt.exists()
    agd.dump(receipt,{'prefix_id':pid,'batch':batch,'mode':mode,
                     'batch_size':len(candidates),
                     'input_sha256':agd.stable_hash({'visible_turns':packet['visible_turns'],'candidates':candidates}),
                     'reviewed_items_sha256':agd.stable_hash(items)})
    receipts=[read(p) for p in sorted(receipt.parent.glob('*.json'))]
    obj['_meta']['batch_review_receipts']=receipts
    if len(receipts)==len(packet['batches']):
        obj['_meta']['reviewed_batch_sizes']=[r['batch_size'] for r in receipts]
        obj['_meta']['reviewed_batch_input_sha256']=[r['input_sha256'] for r in receipts]
    agd.dump(target,obj)
    print('REVIEWED BATCH',pid,batch,len(candidates))

def pool_packet(pid):return read(ROOT/'agd_eval/packets/pool'/f'{pid}.json')

def show_pool(pid):
    packet=pool_packet(pid)
    print(json.dumps({'prefix_id':pid,'visible_turns':packet['visible_turns']},ensure_ascii=False))
    for i,a in enumerate(packet['atoms']):
        print(f'{i} [{a["atom_id"]}] {a["level"]} {a["turn_ids"]}: {a["claim"]}')

def publish_pool(pid, authored_facts):
    """All fact/slot meanings and member coverage are evaluator-authored."""
    packet=pool_packet(pid);facts=[]
    for fi,(claim,level,slots,members) in enumerate(authored_facts,1):
        facts.append({'id':f'f{fi}','canonical_claim':claim,'level':level,
            'slots':[{'id':sid,'name':name,'value':value,'core':core,'required':True,'weight':2 if core else 1} for sid,name,value,core in slots],
            'members':[{'atom_id':packet['atoms'][i]['atom_id'],'slot_ids':sids} for i,sids in members]})
    obj={'facts':facts};agd.validate_pool(obj,packet['atoms'])
    from prepare_evaluation import pool_level_findings
    assert not pool_level_findings(obj,packet['atoms']), 'Full E1 fact has required fields supported only by E2 members; re-review its level or member coverage'
    for f in facts:
        covered={s for m in f['members'] for s in m['slot_ids']}
        assert covered=={s['id'] for s in f['slots']}
    obj['_meta']={'model':'gpt-6.1-sol','reasoning_effort':'high','stage':'pool',
        'mode':'designated_subagent_semantic_review','prefix_id':pid,'input_sha256':agd.stable_hash(packet)}
    target=ROOT/'agd_eval/judgments/pool'/f'{pid}.json'
    assert not target.exists()
    agd.dump(target,obj);print('POOL',pid,len(facts),'facts')

def publish_alignment(did, identities, assignments):
    packet=read(ROOT/'alignment/packets'/f'{did}.json')
    unified=[{'id':f'{did}::u{i:03d}','canonical_claim':claim} for i,claim in enumerate(identities,1)]
    mapping=[]
    assert len(packet['prefixes'])==11
    for p in packet['prefixes']:
        ids=assignments[p['prefix_k']]
        assert len(ids)==len(p['facts']) and len(ids)==len(set(ids))
        for fact,uid in zip(p['facts'],ids):
            assert 1<=uid<=len(identities)
            mapping.append({'prefix_id':p['prefix_id'],'fact_id':fact['id'],'unified_fact_id':f'{did}::u{uid:03d}'})
    obj={'dialogue_id':did,'unified_facts':unified,'mapping':mapping,
         '_meta':{'model':'gpt-6.1-sol','reasoning_effort':'high','stage':'alignment',
                  'mode':'designated_subagent_semantic_identity_review','input_sha256':agd.stable_hash(packet),
                  'identity_only_no_support_backfill':True}}
    target=ROOT/'alignment/judgments'/f'{did}.json';assert not target.exists()
    agd.dump(target,obj);print('ALIGNED',did,len(unified),'identities',len(mapping),'local facts')

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['show','publish'])
    parser.add_argument('--k',type=int,required=True)
    parser.add_argument('--decisions',type=Path)
    args=parser.parse_args()
    if args.command=='show':show(args.k)
    else:
        batch=read(args.decisions)
        publish_sweep(args.k,batch['decisions'],batch.get('retained',[]))
