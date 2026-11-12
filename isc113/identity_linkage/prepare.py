"""Pinned public-source census and reproducible, globally dialogue-disjoint sampling."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import random
from pathlib import Path
import zipfile
import json
import requests
from .core import HERE, digest, freeze, load, sanitize, save

COMMIT = '28d0b6b3865b29cabc26c230a2db37cdf315e937'
SOURCE_URL = f'https://api.github.com/repos/nu-dialogue/real-persona-chat/zipball/{COMMIT}'


def read_corpus(archive):
    records = []
    with zipfile.ZipFile(archive) as z:
        for name in sorted(z.namelist()):
            if '/real_persona_chat/dialogues/' in name and name.endswith('.json'):
                obj = json.loads(z.read(name))
                obj['_reported_dialogue_id'] = obj['dialogue_id']
                obj['dialogue_id'] = Path(name).stem
                speakers = obj['interlocutors']
                if len(speakers) != 2 or len(set(speakers)) != 2:
                    raise ValueError('Non-dyadic dialogue')
                if {u['interlocutor_id'] for u in obj['utterances']} != set(speakers):
                    raise ValueError('Speaker mismatch')
                records.append(obj)
    if not records or len({r['dialogue_id'] for r in records}) != len(records):
        raise ValueError('Empty corpus or duplicate IDs')
    return records


def make_index(records):
    index = defaultdict(lambda: defaultdict(list))
    seen = set()
    duplicate_ids = []
    for r in records:
        # Reject exact duplicate transcript content even when its source ID differs.
        a, b = r['interlocutors']
        transcript = [(r['interlocutors'].index(u['interlocutor_id']), u['text']) for u in r['utterances']]
        key = digest(transcript)
        if key in seen:
            duplicate_ids.append(r['dialogue_id'])
            continue
        seen.add(key)
        index[a][b].append(r)
        index[b][a].append(r)
    return index, duplicate_ids


def capacities(index, used):
    return {a: {b: [r for r in rs if r['dialogue_id'] not in used] for b, rs in partners.items()
                if any(r['dialogue_id'] not in used for r in rs)} for a, partners in index.items()}


def sample_same(index, used, k, rng):
    available = capacities(index, used)
    candidates = [a for a, ps in available.items() if len(ps) >= k and sum(map(len, ps.values())) >= 10]
    rng.shuffle(candidates)
    for a in candidates:
        partners = list(available[a])
        for _ in range(500):
            bs = rng.sample(partners, k)
            if sum(len(available[a][b]) for b in bs) < 10:
                continue
            pools = {b: rng.sample(available[a][b], len(available[a][b])) for b in bs}
            selection = [(a, b, pools[b].pop()) for b in bs]
            while len(selection) < 10:
                b = rng.choice([b for b in bs if pools[b]])
                selection.append((a, b, pools[b].pop()))
            rng.shuffle(selection)
            return selection
    raise ValueError(f'No Same-A group found for K={k}; search is bounded, not a proof of infeasibility')


def sample_different(index, used, k, rng):
    available = capacities(index, used)
    speakers = list(available)
    for _ in range(20000):
        bs = rng.sample(speakers, k)
        neighbors = {b: [a for a in available[b] if a not in bs] for b in bs}
        if any(not neighbors[b] for b in bs):
            continue
        slots = list(bs)
        for _ in range(10-k):
            candidates = [b for b in bs if slots.count(b) < len(neighbors[b])]
            if not candidates:
                break
            slots.append(rng.choice(candidates))
        if len(slots) != 10:
            continue
        for ns in neighbors.values():
            rng.shuffle(ns)
        # Bipartite matching ensures ten distinct A's and exact chosen B multiplicities.
        owner = {}
        def augment(slot, visited):
            for a in neighbors[slots[slot]]:
                if a in visited:
                    continue
                visited.add(a)
                if a not in owner or augment(owner[a], visited):
                    owner[a] = slot
                    return True
            return False
        if not all(augment(i, set()) for i in range(10)):
            continue
        result = [(a, slots[i], rng.choice(available[a][slots[i]])) for a, i in owner.items()]
        rng.shuffle(result)
        return result
    raise ValueError(f'No Different-A group found for K={k}; bounded randomized search exhausted')


def prepare(out, groups_per_k=1, seed=20261106, archive=None):
    if groups_per_k < 1:
        raise ValueError('groups_per_k must be positive')
    archive = Path(archive) if archive else HERE/'data/real-persona-chat.zip'
    if not archive.exists():
        r = requests.get(SOURCE_URL, timeout=180)
        r.raise_for_status()
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(r.content)
    records = read_corpus(archive)
    index, duplicates = make_index(records)
    degrees = [len(ps) for ps in index.values()]
    pairs = {tuple(sorted((a,b))): len(rs) for a,ps in index.items() for b,rs in ps.items()}
    census = dict(source_url=SOURCE_URL, source_commit=COMMIT,
                  archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                  dialogues=len(records), speakers=len(index), unique_pairs=len(pairs),
                  duplicate_reported_dialogue_ids={str(i):n for i,n in Counter(r['_reported_dialogue_id'] for r in records).items() if n>1},
                  source_identity='archive dialogue filename (reported dialogue_id is not unique)',
                  pair_dialogues_min=min(pairs.values()), pair_dialogues_max=max(pairs.values()),
                  pair_dialogues_mean=sum(pairs.values())/len(pairs),
                  partner_degree_histogram=dict(sorted(Counter(degrees).items())),
                  speakers_with_at_least_10_partners=sum(d>=10 for d in degrees),
                  same_a_k1_eligible_pairs=sum(v>=10 for v in pairs.values()),
                  exact_duplicate_transcript_ids=duplicates,
                  note='Eligibility counts are not maximum numbers of disjoint test groups.')
    rng = random.Random(seed)
    used = set()
    visible, answers = [], []
    all_speakers = sorted(index)
    for rep in range(groups_per_k):
        for setting in ('same_a','different_a'):
            for k in range(1,11):
                selection = (sample_same if setting=='same_a' else sample_different)(index,used,k,rng)
                gid = f'{setting}_k{k:02d}_r{rep+1:03d}'
                inputs, gold = [], []
                for pos,(a,b,r) in enumerate(selection,1):
                    if r['dialogue_id'] in used:
                        raise ValueError('Dialogue reused')
                    used.add(r['dialogue_id'])
                    local = f'D{pos}'
                    # Keep only the selected A's text. Local numbering removes B turn-gap metadata.
                    texts = [sanitize(u['text'],all_speakers) for u in r['utterances'] if u['interlocutor_id']==a]
                    inputs.append(dict(dialogue=local, visible_turns=[dict(turn_id=i,text=t) for i,t in enumerate(texts,1)]))
                    gold.append(dict(dialogue=local,source_dialogue_id=r['dialogue_id'],a_id=a,b_id=b))
                assert len({g['b_id'] for g in gold}) == k
                if setting=='different_a':
                    assert len({g['a_id'] for g in gold})==10
                    assert not {g['a_id'] for g in gold} & {g['b_id'] for g in gold}
                else:
                    assert len({g['a_id'] for g in gold})==1
                # Random opaque ID ensures K is NEVER present in inference inputs/task names.
                opaque = hashlib.sha256(f'{seed}:{gid}'.encode()).hexdigest()[:20]
                visible.append(dict(group_id=opaque,setting=setting,dialogues=inputs))
                answers.append(dict(group_id=opaque,setting=setting,true_k=k,stratum=gid,answers=gold))
    freeze(out/'census.json',census)
    freeze(out/'inputs.json',visible)
    freeze(out/'gold.json',answers)
    freeze(out/'sampling.json',dict(seed=seed,groups_per_k=groups_per_k,groups=len(visible),
                                  unique_source_dialogues=len(used),source_commit=COMMIT,
                                  input_digest=digest(visible),gold_digest=digest(answers),
                                  selection='bounded seeded random exact-K sampling; random nonuniform multiplicities',
                                  global_dialogue_disjoint=True,different_a_ab_disjoint=True))
    print(json.dumps(dict(groups=len(visible),dialogues=len(used),census=census),ensure_ascii=True),flush=True)


if __name__=='__main__':
    from pathlib import Path
    p=argparse.ArgumentParser()
    p.add_argument('--out',type=Path,default=HERE/'runs/pilot')
    p.add_argument('--groups-per-k',type=int,default=1)
    p.add_argument('--seed',type=int,default=20261106)
    p.add_argument('--archive',type=Path)
    args=p.parse_args()
    prepare(args.out,args.groups_per_k,args.seed,args.archive)
