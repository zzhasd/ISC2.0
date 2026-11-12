"""Independent request-boundary audit for the all-dialogue single-B experiment."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
from .core import load, freeze, digest
from .profile_consistency import DEFAULT, DIRECT, STABLE, ELARA_SCORE, inventories


def verify(folder):
    inputs=load(folder/'inputs.json');archive=load(folder/'archive.json')
    traits=load(folder/'stable_traits.json')['prediction']
    records=inventories(folder,inputs)
    byid={d['dialogue']:d['visible_turns'] for d in inputs['dialogues']}
    rows=[json.loads(s) for s in (folder/'attempts.jsonl').read_text(encoding='utf-8').splitlines()]
    starts={r['attempt_id']:r for r in rows if r['event']=='start'}
    ends={r['attempt_id']:r for r in rows if r['event']=='complete'}
    assert starts.keys()==ends.keys(), 'Unresolved requests'
    counts=Counter();budget=Counter()
    for r in starts.values():
        payload=r['request'];name=r['logical_name'];data=json.loads(payload['messages'][1]['content'])
        assert payload['model']=='qwen3.8-flash' and payload['enable_thinking'] is True
        assert payload['temperature']==0
        prompt=payload['messages'][0]['content']
        if name=='single_b/direct':
            assert data==dict(inputs,archive=archive) and prompt==DIRECT
            phase='direct'
        elif name=='single_b/stable':
            assert data==dict(dialogues=records) and prompt==STABLE
            phase='stable'
        elif name=='single_b/elara_score':
            assert data==dict(traits=traits,archive=archive) and prompt==ELARA_SCORE
            phase='elara_score'
        else:
            match=re.fullmatch(r'realpersonachat/single_b_(D\d+)/A_to_B/elara/(explicit|implicit|gap_scan|audit_\d+)',name)
            assert match, 'Unexpected request name'
            assert data['visible_turns']==byid[match[1]] and data['target']=='hidden B, unseen partner'
            assert set(data)<= {'visible_turns','target','candidates','existing_claims'}, 'Unexpected v1 fields'
            phase='elara_extraction'
        assert payload['thinking_budget']==(512 if phase=='elara_extraction' else 2048)
        assert payload['max_tokens']==(4096 if phase=='elara_extraction' else 12000)
        counts[phase]+=1;budget[phase]+=payload['max_tokens']
    assert set(counts)=={'direct','stable','elara_score','elara_extraction'}
    unknown=[r['attempt_id'] for r in ends.values() if r.get('billing_unknown')]
    # Check credential patterns without exposing matching values.
    leaked=[]
    for p in folder.rglob('*'):
        if p.is_file() and p.suffix in ('.py','.json','.jsonl','.md'):
            if re.search(r'sk-[A-Za-z0-9_.-]{20,}',p.read_text(encoding='utf-8')):leaked.append(str(p))
    assert not leaked, 'Credential-like data found in artifacts'
    out=dict(passed=True,exact_request_input_projection=True,all_llm_qwen38_flash_thinking=True,
             no_archive_in_extraction_or_synthesis=True,all_requests_resolved=True,
             credential_scan_passed=True,request_counts=dict(counts),
             unknown_billing_attempt_ids=unknown,
             billing_note='Returned usage is observable token usage only; transport failures can have unknown costs. No price/cost is inferred.',
             requests_digest=digest(list(starts.values())))
    freeze(folder/'request_verification.json',out)
    print(json.dumps(out,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,default=DEFAULT);verify(p.parse_args().folder)
