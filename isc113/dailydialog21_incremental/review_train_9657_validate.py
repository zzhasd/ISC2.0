from review_train_9657_common import *
import prepare_evaluation as prep
for k in range(1,12):
 verify(k)
 pid=f'train_9657__k{k:02d}'
 packet=e.pool_packet(pid)
 pool=e.read(e.ROOT/'agd_eval/judgments/pool'/f'{pid}.json')
 e.agd.validate_pool(pool,packet['atoms'])
 assert pool['_meta']['input_sha256']==e.agd.stable_hash(packet)
 assert not prep.pool_level_findings(pool,packet['atoms'])
 assert all(s['required'] and s['weight']==(2 if s['core'] else 1) for f in pool['facts'] for s in f['slots'])
packet=e.read(e.ROOT/'alignment/packets/train_9657.json')
a=e.read(e.ROOT/'alignment/judgments/train_9657.json')
assert a['_meta']['input_sha256']==e.agd.stable_hash(packet)
assert a['_meta']['identity_only_no_support_backfill'] is True
expected={(p['prefix_id'],f['id']) for p in packet['prefixes'] for f in p['facts']}
actual=[(m['prefix_id'],m['fact_id']) for m in a['mapping']]
assert set(actual)==expected and len(actual)==len(expected)
for p in packet['prefixes']:
 vals=[m['unified_fact_id'] for m in a['mapping'] if m['prefix_id']==p['prefix_id']]
 assert len(vals)==len(set(vals))
print('FINAL VERIFIED train_9657: 11 Support, 11 Pool, 12 identities, 81 local facts; no E1 slot elevation findings')
