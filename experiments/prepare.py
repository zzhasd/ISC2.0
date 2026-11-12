"""Prepare a fixed, investigator-annotated pilot before model evaluation."""
from pathlib import Path
import collections
import hashlib
import io
import json
import random
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'

def write(name, obj):
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

def load_original():
    outer = zipfile.ZipFile(DATA / 'dailydialog_original.zip')
    rows = []
    for split in ['train', 'validation', 'test']:
        archive = zipfile.ZipFile(io.BytesIO(outer.read(f'EMNLP_dataset/{split}.zip')))
        text = archive.read(f'{split}/dialogues_{split}.txt').decode('utf-8')
        for i, line in enumerate(text.splitlines()):
            rows.append(dict(id=f'{split}_{i}', split=split,
                             turns=[s.strip() for s in line.split('__eou__') if s.strip()]))
    return rows

# id, proposition about B, full-dialogue truth, A-only support, domain,
# full evidence turn (1-based), A evidence turn(s), annotation rationale.
# Unknown is not false. Only explicit negation permits a false truth label.
ANNOTATIONS = [
 (7,'B has a headache.','true','unknown','health',[2],[], 'A identifies influenza but never specifies headache.'),
 (34,'B is looking for a new job.','true','true','employment',[8],[7,9,11], 'Future plans, job advertisements, and an offer to help jointly support job search; indirect.'),
 (107,'B currently has a fever.','true','true','health',[7],[7], 'A explicitly says your fever.'),
 (144,'B has a stomachache.','unknown','unknown','health',[],[], 'The stomachache belongs to A; no evidence about B.'),
 (189,'B has a husband.','true','unknown','relationship',[4,12],[], 'Spouse is mentioned only by B.'),
 (195,'B is preparing to get married.','true','true','relationship',[2,6],[1,5], 'A explicitly refers to your wedding and upcoming marriage.'),
 (219,'B is receiving unemployment benefits.','unknown','unknown','finance',[],[], 'Benefits belong to A, not B; B is the service representative.'),
 (244,'B has a wife.','true','unknown','relationship',[2],[], 'Buying earrings and being called sir do not establish marriage.'),
 (248,'B is pregnant.','unknown','unknown','health',[],[], 'Pregnancy concerns an absent columnist, not B.'),
 (258,'B has a rare blood disease.','unknown','unknown','health',[],[], 'The disease belongs to a local girl in a news story.'),
 (269,'B has a wife.','true','true','relationship',[4],[11], 'A explicitly says your wife.'),
 (283,'B has an upset stomach.','true','unknown','health',[2],[], 'A offers medication but does not specify an upset stomach.'),
 (303,'B has a cold.','true','true','health',[7],[7], 'A explicitly states the diagnosis in the dialogue world.'),
 (449,'B has a headache.','true','unknown','health',[2],[], 'A observes illness without specifying the symptom.'),
 (475,'B has a son.','true','unknown','family',[4],[], 'The answer identifying a son is hidden.'),
 (484,'B has a wife.','true','unknown','relationship',[2],[], 'Booking a double room does not establish marriage.'),
 (506,'B has anemia.','true','true','health',[5],[5], 'A explicitly says you are anemic; no independent clinical truth is asserted.'),
 (530,'B has a daughter.','true','unknown','family',[2],[], 'A uses she/her but does not establish the parental relationship.'),
 (546,'B is preparing to get married.','true','true','relationship',[2],[1,3], 'Bride-to-be and maid of honor provide presuppositional evidence.'),
 (671,'B is married.','true','true','relationship',[2,12],[1,5,7,11], 'A refers to B wedding and husband.'),
 (692,'B has a daughter who is ill.','true','unknown','family',[2],[], 'The patient and relationship are absent from A turns.'),
 (699,'B is preparing to get married.','true','true','relationship',[2],[1,3,5,11], 'A checks a report and subsequently congratulates and discusses wedding preparations.'),
 (713,'B has a wife.','true','unknown','relationship',[2,6],[], 'A clothing compliment does not establish a spouse.'),
 (725,'B is married.','unknown','unknown','relationship',[],[], 'The married person is B brother, not B; absence is not a negative label.'),
 (728,'B is separating from a spouse.','unknown','unknown','relationship',[],[], 'The separating couple is Mary and Tom, not B.'),
 (807,'B has a daughter who recently got married.','true','true','family',[8],[7], 'A explicitly refers to your daughter and reports her recent marriage.'),
 (827,'B is pregnant.','unknown','unknown','health',[],[], 'Pregnancy belongs to A; no evidence about B.'),
 (836,'B is allergic to cats.','true','true','health',[12],[13], 'A explicitly says your cat allergy.'),
 (838,'B is a doctor.','true','true','employment',[2,4],[1], 'The question presupposes B is a doctor; B confirms in full dialogue.'),
 (851,'B has a wife.','true','true','relationship',[8],[7], 'A asks whether B discussed it with your wife.'),
 (913,'B has children.','true','unknown','family',[6],[], 'A only says that is terrific after the hidden disclosure.'),
 (924,'B is currently married.','false','unknown','relationship',[4],[], 'B explicitly says not married yet; A-only engagement is suggestive but not conclusive.'),
 (951,'B is pregnant.','unknown','unknown','health',[],[], 'The pregnant person is B wife; never infer B pregnancy.'),
 (952,'B has been drinking alcohol.','true','true','health',[2,4],[1], 'A says your drinking and B acknowledges it.'),
 (968,'B is married.','unknown','unknown','relationship',[],[], 'The marriage question concerns B boss, not B.'),
]

def tokenize(text):
    return re.findall(r"\b\w+\b", text.lower())

def prepare_natural(rows):
    indexed = {r['id']: r for r in rows}
    result = []
    for idx, claim, truth, support, domain, full_ev, a_ev, rationale in ANNOTATIONS:
        row = indexed[f'test_{idx}']
        a = row['turns'][::2]
        shuffled = a.copy()
        random.Random(1000 + idx).shuffle(shuffled)
        if shuffled == a and len(a) > 1:
            shuffled = a[1:] + a[:1]
        result.append(dict(
            id=row['id'], group=row['id'], dataset='dailydialog', domain=domain,
            claim=claim, truth=truth, support=support,
            full_evidence_turns=full_ev, a_evidence_turns=a_ev,
            annotation_rationale=rationale, annotation_status='single-investigator provisional; no independent IAA',
            conditions={
                'prior':'No dialogue is available.',
                'full':'\n'.join(f'{"A" if i%2==0 else "B"}: {t}' for i,t in enumerate(row['turns'])),
                'a_only':'\n'.join('A: '+t for t in a),
                'shuffled':'\n'.join('A: '+t for t in shuffled),
                'word_bag':'Unordered words from A (order discarded): '+' '.join(sorted(tokenize(' '.join(a)))),
            }))
    return result

DOMAINS = [
 ('health','has diabetes','has asthma'),
 ('health','has a headache','has a fever'),
 ('finance','has a bank loan','has credit card debt'),
 ('employment','is unemployed','is retired'),
 ('relationship','is married','is divorced'),
 ('family','has a son','has a daughter'),
]

def synth_pair(mechanism, p, q, y, style):
    """Two balanced worlds differ in binding, with exactly the same word counts."""
    # y=True assigns proposition p to B. q is explicitly mutually assigned to C;
    # p is explicitly denied for B when y=False, rather than inferred from q.
    own, other = (p,q) if y else (q,p)
    if mechanism == 'confirmation':
        t = [f'A: I recorded the descriptions "{p}" and "{q}" for you and Casey in that order. Is that right?',
             'A: '+('Yes, that assignment is correct. No, the reverse assignment is incorrect.' if y else
                      'No, that assignment is incorrect. Yes, the reverse assignment is correct.'),
             'A: Only one assignment is true, and each person has only the assigned property.']
        narrative = f'B {own}; Casey {other}. B does not {other.split(" ",1)[1] if other.startswith("has ") else other}.'
        # Avoid ungrammatical does not is/has by use of explicit propositions below.
    elif mechanism == 'reference':
        first, second = ('you','Casey') if y else ('Casey','you')
        t = [f'A: I am recording two people in order: {first}, then {second}.',
             f'A: The first person {p}; the second person {q}.',
             'A: Only the first person has the first property; the second person does not.']
    elif mechanism == 'correction':
        old, new = ('Casey','you') if y else ('you','Casey')
        t = [f'A: I wrote the description "{p}" next to {old}.',
             f'A: That was incorrect: replace {old} with {new}.',
             f'A: I initially left {new} out of the old assignment.',
             f'A: The corrected person {p}; the other person does not.',
             f'A: The other person {q}.']
    elif mechanism == 'cross_turn':
        first, second = ('you','Casey') if y else ('Casey','you')
        t = [f'A: Your file and Casey\'s file use the names {first} for file one and {second} for file two.',
             f'A: File one says the person {p}.',
             f'A: File two says the person {q}, and does not have the property listed in file one.']
    else:
        raise ValueError(mechanism)
    # Matched pair has identical tokens, including both Yes and No in confirmation.
    # Two narrative surface forms are fixed in advance; they preserve holder and polarity.
    negative_p = ('does not have '+p[4:]) if p.startswith('has ') else ('is not '+p[3:])
    if style == 0:
        narrative = f'B {p}. Casey {q}.' if y else f'B {q}. B {negative_p}. Casey {p}.'
    else:
        narrative = f'The property assigned to B is: {p}. The property assigned to Casey is: {q}.' if y else f'The property assigned to B is: {q}. It is false that B {p}. The property assigned to Casey is: {p}.'
    return '\n'.join(t), narrative

def prepare_controlled():
    result=[]
    for m in ['confirmation','reference','correction','cross_turn']:
        for d,(domain,p,q) in enumerate(DOMAINS):
            group=f'{m}_{d}'
            texts=[]
            for y in [False,True]:
                text,narrative=synth_pair(m,p,q,y,d%2)
                texts.append(text)
                turns=text.splitlines()
                shuffled=turns.copy(); random.Random(700+d).shuffle(shuffled)
                result.append(dict(id=f'{group}_{int(y)}',group=group,dataset='controlled',
                    mechanism=m,domain=domain,claim=f'B {p}.',truth='true' if y else 'false',
                    support='true' if y else 'false',
                    conditions={'a_only':text,'narrative':narrative,
                                'word_bag':'Unordered words from A (order discarded): '+' '.join(sorted(tokenize(text))),
                                'shuffled':'\n'.join(shuffled)},
                    annotation_status='constructed truth; not naturally sampled'))
            assert collections.Counter(tokenize(texts[0])) == collections.Counter(tokenize(texts[1])), group
    return result

def main():
    rows=load_original()
    (DATA/'dailydialog.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    natural=prepare_natural(rows); controlled=prepare_controlled()
    write('natural_pilot.json', natural); write('controlled_pilot.json', controlled)
    manifest={'seed':20261031,'natural_items':len(natural),'natural_truth':dict(collections.Counter(r['truth'] for r in natural)),
              'natural_support':dict(collections.Counter(r['support'] for r in natural)),
              'controlled_items':len(controlled),'controlled_groups':len(controlled)//2,
              'files':{name:hashlib.sha256((DATA/name).read_bytes()).hexdigest() for name in ['natural_pilot.json','controlled_pilot.json']}}
    write('manifest.json',manifest)
    print(json.dumps(manifest,indent=2))

if __name__=='__main__': main()
