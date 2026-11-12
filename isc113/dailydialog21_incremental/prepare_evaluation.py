"""Prepare blinded offline Sol packets, never call an evaluation API."""
import argparse
import hashlib
import importlib.util
import json
import shutil
import os
import tempfile
from datetime import datetime,timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('agd',HERE.parent/'agd_eval_20261106/agd_eval.py')
agd=importlib.util.module_from_spec(spec);spec.loader.exec_module(agd)

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def temporary_json(p,o):
    p.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix=p.name+'.',suffix='.tmp',dir=p.parent)
    with os.fdopen(fd,'w',encoding='utf-8') as f:
        json.dump(o,f,ensure_ascii=False,indent=2)
    return Path(name)

def dump_atomic(p,o):
    temp=temporary_json(p,o)
    try:os.replace(temp,p)
    finally:
        if temp.exists():temp.unlink()

def freeze(p,o):
    if p.exists():
        assert read(p)==o, f'Frozen packet differs: {p}'
        return
    temp=temporary_json(p,o)
    try:
        try:os.link(temp,p)
        except FileExistsError:assert read(p)==o, f'Frozen packet differs: {p}'
    finally:temp.unlink()

def scoring_input_fingerprint():
    """Bind statistics to the actual predictions, judgments and identity maps."""
    paths=[HERE/'data/prefix_inputs.json',HERE/'agd_eval/private_source_mapping.json']
    for folder in ('inference/direct_thinking','inference/elara_v1',
                   'agd_eval/judgments/support','agd_eval/judgments/pool','alignment/judgments'):
        paths.extend(sorted((HERE/folder).glob('*.json')))
    return agd.stable_hash({str(p.relative_to(HERE)).replace('\\','/'):agd.stable_hash(read(p)) for p in paths})

def pool_level_findings(pool,atoms):
    """An E1 full fact cannot inherit a required field supported only at E2."""
    by={a['atom_id']:a for a in atoms};findings=[]
    for fact in pool['facts']:
        if fact['level']!='E1':continue
        required={s['id'] for s in fact['slots'] if s['required']}
        explicit={sid for m in fact['members'] if by[m['atom_id']]['level']=='E1' for sid in m['slot_ids']}
        missing=required-explicit
        if missing:findings.append({'fact_id':fact['id'],'required_slots_without_e1_member':sorted(missing)})
    return findings

def prepare_support(available=False,dialogue_ids=None):
    prefixes=read(HERE/'data/prefix_inputs.json')
    # Entire independent sweep must precede any exposure to predictor hypotheses.
    for p in prefixes:
        f=HERE/'agd_eval/judgments/sweep'/(p['prefix_id']+'.json')
        assert f.exists(), f'Independent Sweep incomplete: {p["prefix_id"]}'
        agd.validate_sweep(read(f),p['visible_turns'])
    index_path=HERE/'agd_eval/private_source_mapping.json'
    index=read(index_path) if index_path.exists() else {}
    prepared=0
    for p in prefixes:
        if dialogue_ids and p['dialogue_id'] not in dialogue_ids:continue
        pid=p['prefix_id']; candidates={};predictions=[];sweep_ids=[]
        missing=[a for a in ('direct_thinking','elara_v1') if not(HERE/'inference'/a/(pid+'.json')).exists()]
        missing += [a for a in ('direct_thinking','elara_v1') if (HERE/'inference'/a/(pid+'.json')).exists()
                    and 'claims' not in read(HERE/'inference'/a/(pid+'.json'))]
        if missing:
            if available:continue
            raise AssertionError(f'Inference incomplete: {pid}: {missing}')
        def candidate(text):
            normalized=agd.clean_claim(text)
            cid='c_'+hashlib.sha256((pid+'\n'+normalized).encode()).hexdigest()[:16]
            if cid not in candidates:candidates[cid]={'id':cid,'claim':text}
            return cid
        for a in ('direct_thinking','elara_v1'):
            output=read(HERE/'inference'/a/(pid+'.json'))
            for n,c in enumerate(output['claims']):
                predictions.append({'id':f'{a}:{n}','algorithm':a,'claim':c['claim'],
                                    'candidate_id':candidate(c['claim'])})
        sweep=read(HERE/'agd_eval/judgments/sweep'/(pid+'.json'))
        for c in sweep['claims']:sweep_ids.append(candidate(c['claim']))
        ordered=sorted(candidates.values(),key=lambda c:c['id'])
        payload={'prefix_id':pid,'visible_turns':p['visible_turns'],
                 'batches':[ordered[i:i+12] for i in range(0,len(ordered),12)]}
        freeze(HERE/'agd_eval/packets/support'/(pid+'.json'),payload)
        if not ordered:
            freeze(HERE/'agd_eval/judgments/support'/(pid+'.json'),
                   {'items':[],'_meta':{'stage':'support','deterministic_empty_input':True}})
        entry={'predictions':predictions,'sweep_candidate_ids':sweep_ids,'candidates':ordered,
               'support_input_sha256':agd.stable_hash(payload)}
        if pid in index:assert index[pid]==entry, 'Frozen source mapping changed'
        index[pid]=entry;prepared+=1
        freeze(HERE/'agd_eval/judgments/gold'/(pid+'.json'),{'items':[],'not_applicable':True})
    dump_atomic(index_path,index)
    print(f'Prepared {prepared}/341 blinded Support packets, <=12 candidates per batch.')

def prepare_pool(available=False,dialogue_ids=None):
    prefixes=read(HERE/'data/prefix_inputs.json')
    private=read(HERE/'agd_eval/private_source_mapping.json')
    for p in prefixes:
        if dialogue_ids and p['dialogue_id'] not in dialogue_ids:continue
        pid=p['prefix_id']
        if available and pid not in private:continue
        data=private[pid]
        target=HERE/'agd_eval/judgments/support'/(pid+'.json')
        if not target.exists() and available:continue
        support=read(target)
        support_packet=read(HERE/'agd_eval/packets/support'/(pid+'.json'))
        expected_batches=[len(batch) for batch in support_packet['batches']]
        if expected_batches and support.get('_meta',{}).get('reviewed_batch_sizes')!=expected_batches:
            if available:continue
            raise AssertionError(f'Explicit <=12-candidate batch review incomplete: {pid}')
        agd.validate_support(support,data['candidates'],p['visible_turns'])
        atoms=[]
        for item in support['items']:
            for i,a in enumerate(item['atoms']):
                if a['label'] in agd.VALID:
                    atoms.append({'atom_id':f'{item["id"]}::{i}','claim':a['text'],
                                  'turn_ids':a['turn_ids'],'level':a['label']})
        freeze(HERE/'agd_eval/packets/pool'/(pid+'.json'),
               {'prefix_id':pid,'visible_turns':p['visible_turns'],'atoms':atoms})
        if not atoms:
            freeze(HERE/'agd_eval/judgments/pool'/(pid+'.json'),
                   {'facts':[],'_meta':{'stage':'pool','deterministic_empty_input':True}})
    print('Prepared blinded Pool packets; only validated E1/E2 atoms admitted.')

def prepare_alignment(available=False,dialogue_ids=None):
    prefixes=read(HERE/'data/prefix_inputs.json');by={}
    for p in prefixes:
        if dialogue_ids and p['dialogue_id'] not in dialogue_ids:continue
        pid=p['prefix_id']
        if available and not (HERE/'agd_eval/judgments/pool'/(pid+'.json')).exists():continue
        packet=read(HERE/'agd_eval/packets/pool'/(pid+'.json'))
        result=read(HERE/'agd_eval/judgments/pool'/(pid+'.json'))
        agd.validate_pool(result,packet['atoms'])
        by.setdefault(p['dialogue_id'],[]).append({'prefix_id':pid,'prefix_k':p['prefix_k'],
                   'facts':[{k:v for k,v in f.items() if k!='members'} for f in result['facts']]})
    prepared=0
    for did,ps in by.items():
        if available and len(ps)!=11:continue
        freeze(HERE/'alignment/packets'/(did+'.json'),{'dialogue_id':did,'prefixes':ps,
               'policy':'Align identity only. Never backfill support, slots, or hits to earlier prefixes.'})
        prepared+=1
    print(f'Prepared {prepared} identity-only alignment packets in the requested scope.')

def refresh_pool(prefix_id,reason,pool_only=False):
    """Archive stale downstream artifacts after an explicitly re-reviewed Support.

    No semantic decisions are generated here. Fresh batch receipts are required.
    Other prefixes' Pool judgments and the immutable Sweep remain untouched.
    """
    prefixes={p['prefix_id']:p for p in read(HERE/'data/prefix_inputs.json')}
    assert prefix_id in prefixes and reason.strip(), 'Known prefix and explicit reason required'
    p=prefixes[prefix_id];did=p['dialogue_id'];name=prefix_id+'.json'
    support=read(HERE/'agd_eval/judgments/support'/name)
    source=read(HERE/'agd_eval/packets/support'/name)
    cands=[c for batch in source['batches'] for c in batch]
    agd.validate_support(support,cands,p['visible_turns'])
    if cands:
        meta=support['_meta']
        assert meta['model']=='gpt-6.1-sol' and meta['reasoning_effort']=='high'
        assert meta['input_sha256']==agd.stable_hash(source)
        assert meta['reviewed_batch_sizes']==list(map(len,source['batches']))
        for i,batch in enumerate(source['batches']):
            receipt=read(HERE/'agd_eval/batch_reviews/support'/prefix_id/f'{i:03d}.json')
            items=[x for x in support['items'] if x['id'] in {c['id'] for c in batch}]
            assert receipt['reviewed_items_sha256']==agd.stable_hash(items),'Finish real batch re-review before refreshing Pool'
    atoms=[{'atom_id':f'{item["id"]}::{i}','claim':a['text'],'turn_ids':a['turn_ids'],'level':a['label']}
           for item in support['items'] for i,a in enumerate(item['atoms']) if a['label'] in agd.VALID]
    packet_path=HERE/'agd_eval/packets/pool'/name
    old=read(packet_path)
    fresh={'prefix_id':prefix_id,'visible_turns':p['visible_turns'],'atoms':atoms}
    judgment_path=HERE/'agd_eval/judgments/pool'/name
    if pool_only:
        assert old==fresh, 'Support input changed; use the normal refresh-pool mode'
        assert judgment_path.exists(), 'No existing Pool judgment to archive for pool-only revision'
    else:assert old!=fresh, 'Pool packet is unchanged; use --pool-only for a semantic Pool revision'
    oldhash=agd.stable_hash(old);newhash=agd.stable_hash(fresh)
    archive_key=oldhash[:16]+'_'+newhash[:16]
    if pool_only:archive_key+='_pool_'+hashlib.sha256(judgment_path.read_bytes()).hexdigest()[:16]
    archive=HERE/'agd_eval/revisions/pool_refresh'/prefix_id/archive_key
    archive.mkdir(parents=True,exist_ok=True)
    artifacts={
        'pool_packet.json':packet_path,
        'pool_judgment.json':judgment_path,
        'alignment_packet.json':HERE/'alignment/packets'/(did+'.json'),
        'alignment_judgment.json':HERE/'alignment/judgments'/(did+'.json')}
    archived={}
    for label,path in artifacts.items():
        if not path.exists():continue
        path.resolve().relative_to(HERE.resolve())
        dest=archive/label
        if dest.exists():assert dest.read_bytes()==path.read_bytes(), 'Revision archive collision'
        else:shutil.copy2(path,dest)
        archived[label]=hashlib.sha256(dest.read_bytes()).hexdigest()
    event={'prefix_id':prefix_id,'dialogue_id':did,'reason':reason,
           'revision_kind':'pool_semantic_review' if pool_only else 'support_atomic_revision',
           'utc':datetime.now(timezone.utc).isoformat(),'old_pool_input_sha256':oldhash,
           'new_pool_input_sha256':newhash,'archived_file_sha256':archived,
           'source_support_sha256':agd.stable_hash(support)}
    freeze(archive/'revision.json',event)
    # Archives exist before invalidating any dependent artifact.
    dump_atomic(packet_path,fresh)
    for label,path in artifacts.items():
        if label!='pool_packet.json' and path.exists():path.unlink()
    dump_atomic(HERE/'results/evaluation_revision_required.json',event)
    if not atoms:
        agd.dump(HERE/'agd_eval/judgments/pool'/name,
                 {'facts':[],'_meta':{'stage':'pool','deterministic_empty_input':True}})
    print('Refreshed Pool packet:',prefix_id,'; archived old downstream artifacts at',archive)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['support','pool','alignment','refresh-pool'])
    parser.add_argument('--available',action='store_true',help='Export complete prefixes while other inference tasks run')
    parser.add_argument('--prefix-id')
    parser.add_argument('--reason')
    parser.add_argument('--dialogue-id',action='append',help='Limit packet preparation to assigned dialogue(s)')
    parser.add_argument('--pool-only',action='store_true',help='Archive an existing Pool judgment for re-review with unchanged Support input')
    args=parser.parse_args()
    if args.stage=='refresh-pool':
        if not args.prefix_id or not args.reason:parser.error('refresh-pool requires --prefix-id and --reason')
        refresh_pool(args.prefix_id,args.reason,args.pool_only)
    else:{'support':prepare_support,'pool':prepare_pool,'alignment':prepare_alignment}[args.stage](args.available,args.dialogue_id)
