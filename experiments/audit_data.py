from pathlib import Path
import collections
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[1]
rows=[json.loads(line) for line in (ROOT/'data/dailydialog.jsonl').read_text(encoding='utf-8').splitlines()]
natural=json.loads((ROOT/'data/natural_pilot.json').read_text(encoding='utf-8'))
controlled=json.loads((ROOT/'data/controlled_pilot.json').read_text(encoding='utf-8'))

def norm(r):
    return re.sub(r'\W+','', ' '.join(r['turns']).lower())

train={norm(r) for r in rows if r['split']=='train'}
test=[r for r in rows if r['split']=='test']
selected=set(r['id'] for r in natural)
groups=collections.defaultdict(list)
for r in controlled: groups[r['group']].append(r)
pair_word_equal=[];pair_bag_equal=[]
for group,pair in groups.items():
    a,b=pair
    pair_word_equal.append(collections.Counter(re.findall(r'\w+',a['conditions']['a_only'].lower()))==collections.Counter(re.findall(r'\w+',b['conditions']['a_only'].lower())))
    pair_bag_equal.append(a['conditions']['word_bag']==b['conditions']['word_bag'])
result={'split_sizes':dict(collections.Counter(r['split'] for r in rows)),
        'normalized_test_train_exact_overlap_dialogues':sum(norm(r) in train for r in test),
        'selected_normalized_test_train_overlap':[r['id'] for r in test if r['id'] in selected and norm(r) in train],
        'natural_domain_counts':dict(collections.Counter(r['domain'] for r in natural)),
        'natural_support_counts':dict(collections.Counter(r['support'] for r in natural)),
        'controlled_pairs':len(groups),'controlled_exact_word_count_matches':sum(pair_word_equal),
        'controlled_identical_word_bag_matches':sum(pair_bag_equal),
        'sha256':{name:hashlib.sha256((ROOT/'data'/name).read_bytes()).hexdigest() for name in ['natural_pilot.json','controlled_pilot.json']}}
assert all(pair_word_equal) and all(pair_bag_equal)
for r in natural:
    orig=next(x for x in test if x['id']==r['id'])
    assert all(1<=i<=len(orig['turns']) for i in r['full_evidence_turns'])
    assert all(i%2==1 for i in r['a_evidence_turns'])
(ROOT/'results/data_audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
