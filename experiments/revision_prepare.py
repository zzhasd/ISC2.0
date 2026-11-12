"""Freeze expanded controlled, natural and repeat requests, without API calls."""
import copy
import collections
import hashlib
import json
import random
import re
from revision_api import ROOT, OUT, MODEL, read, save, freeze, digest
from run_api import SYSTEM as PROB_SYSTEM
from stage2_run import SYSTEM as CATALOGUE_SYSTEM

DOMAINS=[
 ('health','has diabetes','has asthma','diabetes','asthma'),
 ('health','has a headache','has a fever','headache','fever'),
 ('finance','has a bank loan','has credit card debt','bank loan','credit card debt'),
 ('employment','is unemployed','is retired','unemployment','retirement'),
 ('relationship','is married','is divorced','marriage','divorce'),
 ('family','has a son','has a daughter','son','daughter'),
 ('health','has a cat allergy','has a peanut allergy','cat allergy','peanut allergy'),
 ('health','is pregnant','is receiving fertility treatment','pregnancy','fertility treatment'),
 ('health','smokes tobacco','drinks alcohol','tobacco use','alcohol use'),
 ('finance','has mortgage debt','has student debt','mortgage debt','student debt'),
 ('employment','is a nurse','is a teacher','nursing job','teaching job'),
 ('family','has a brother','has a sister','brother','sister'),
]
MECHANISMS=['confirmation','reference','correction','cross_turn','presupposition']
def tokens(t): return re.findall(r'\b\w+\b',t.lower())
def neg(p):
    if p.startswith('has '): return 'does not have '+p[4:]
    if p.startswith('is '): return 'is not '+p[3:]
    if p.startswith('smokes '): return 'does not smoke '+p[7:]
    if p.startswith('drinks '): return 'does not drink '+p[7:]
    raise ValueError(p)

def controlled_text(mech,p,q,np,nq,y,style):
    first,second=('you','Casey') if y else ('Casey','you')
    # Every text explicitly defines the task's exclusive assignment; this is a
    # constructed reasoning test, not a medical or population assumption.
    exclusive='A: These two people each have exactly one of the two listed properties; neither has the other property.'
    if mech=='confirmation':
        initial=[f'A: I listed you and Casey as the people who respectively {p} and {q}.',
                 f'A: My draft says that you {p} and Casey {q}.',
                 f'A: In my note, the assignments for you and Casey are "{p}" and "{q}" in that order.',
                 f'A: I paired "{p}" with you and "{q}" with Casey in the provisional record.'][style]
        ok,bad=('Yes','No') if y else ('No','Yes')
        response=[f'A: {ok}, the draft is correct. {bad}, reversing the two people is correct.',
                  f'A: {ok}, keep the assignment. {bad}, swap the assignment.',
                  f'A: {ok} to the initial record; {bad} to the reversed record.',
                  f'A: Your confirmation was {ok} for the draft and {bad} for its reversal.'][style]
        t=[initial,response,exclusive]
    elif mech=='reference':
        t=[[f'A: In the ordered list I mean {first}, then {second}.',f'A: The first person {p}; the second person {q}.'],
           [f'A: I assigned the names {first} and {second} to entries one and two.',f'A: Entry one says the person {p}; entry two says the person {q}.'],
           [f'A: I will mention two people in sequence: {first}, followed by {second}.',f'A: The former {p}, whereas the latter {q}.'],
           [f'A: The upper and lower rows belong to {first} and {second}, respectively.',f'A: The upper row describes someone who {p}; the lower row describes someone who {q}.']][style]+[exclusive]
    elif mech=='correction':
        old,new=('Casey','you') if y else ('you','Casey')
        t=[[f'A: I attached "{p}" to {old}.',f'A: That was a mistake; change {old} to {new}.',f'A: The other person {q}.'],
           [f'A: My initial note links {old} with "{p}".',f'A: Please correct the name from {old} to {new}.',f'A: Whoever is not named in the corrected note {q}.'],
           [f'A: I first wrote that {old} would be the person who {p}.',f'A: I retract that identification: {new}, rather than {old}, is the intended person.',f'A: The remaining person {q}.'],
           [f'A: The old entry for "{p}" names {old}.',f'A: Replace {old} by {new} in that entry.',f'A: The person left over {q}.']][style]+[exclusive]
        t.insert(-1, f'A: The provisional record had omitted {new}.')
    elif mech=='cross_turn':
        t=[[f'A: File one is for {first}; file two is for {second}.',f'A: File one records someone who {p}.',f'A: File two records someone who {q}.'],
           [f'A: The red folder belongs to {first}; the blue folder belongs to {second}.',f'A: The red folder says its owner {p}.',f'A: The blue folder says its owner {q}.'],
           [f'A: I use code X for {first} and code Y for {second}.',f'A: Code X is linked to "{p}".',f'A: Code Y is linked to "{q}".'],
           [f'A: The Monday appointment is for {first}, and the Tuesday appointment is for {second}.',f'A: The Monday visitor {p}.',f'A: The Tuesday visitor {q}.']][style]+[exclusive]
    elif mech=='presupposition':
        possessive1,possessive2=('your',"Casey's") if y else ("Casey's",'your')
        t=[[f'A: We should make arrangements for {possessive1} {np} and {possessive2} {nq}.',
            'A: I am discussing existing facts, not hypothetical possibilities.'],
           [f'A: The meeting must take account of {possessive1} {np}.',f'A: We also need to accommodate {possessive2} {nq}.',
            'A: These are present circumstances, not hypothetical examples.'],
           [f'A: I have already made space in the plan for {possessive1} {np} and for {possessive2} {nq}.',
            'A: Neither of these present circumstances is in dispute.'],
           [f'A: The paperwork about {possessive1} {np} is ready.',f'A: The documents about {possessive2} {nq} are ready too.',
            'A: Both sets of documents concern existing personal circumstances.']][style]+[exclusive]
    else: raise ValueError(mech)
    own,other=(p,q) if y else (q,p)
    narrative=f'B {own}. B {neg(other)}. Casey {other}. Casey {neg(own)}. Each person has exactly one of these two properties.'
    return t,narrative

def payload(system,content,cap=2200,temp=0):
    return {'model':MODEL,'temperature':temp,'enable_thinking':False,'max_tokens':cap,
            'response_format':{'type':'json_object'},'messages':[{'role':'system','content':system},
            {'role':'user','content':json.dumps(content,ensure_ascii=False)}]}
def task(p,**meta):
    h=digest(p)
    return {'task_id':h[:16]+'_r'+str(meta.get('trial',0)), 'request_sha256':h,**meta,'payload':p}

def controlled(version=1):
    rows=[]
    for m in MECHANISMS:
        for di,(domain,p,q,np,nq) in enumerate(DOMAINS):
            for style in range(4):
                pair=[]
                for y in [False,True]:
                    turns,narrative=controlled_text(m,p,q,np,nq,y,style)
                    if version==2 and m=='confirmation':
                        initial=[
                            f'A: In my draft, the descriptions "{p}" and "{q}" belong to you and Casey in that order. Is this draft correct?',
                            f'A: My draft links you with the property "{p}" and Casey with "{q}". Should the draft stand?',
                            f'A: I proposed the assignment "{p}" to you and "{q}" to Casey. Was this proposal accepted?',
                            f'A: I initially matched you to "{p}" and Casey to "{q}". Which assignment did you confirm?'][style]
                        yes,no=('yes','no') if y else ('no','yes')
                        accept,reject=('accepted','rejected') if y else ('rejected','accepted')
                        confirm,deny=('confirmed','denied') if y else ('denied','confirmed')
                        response=[
                            f'A: You answered {yes} to keeping the draft and {no} to reversing it.',
                            f'A: Your answer was {yes} for retaining this assignment and {no} for swapping the two people.',
                            f'A: You {accept} the original and {reject} the reversal.',
                            f'A: You {confirm} the initial assignment and {deny} its reversal.'][style]
                        turns=[initial,response,turns[-1]]
                    rng=random.Random(f'{m}|{di}|{style}'); shuffled=turns.copy();rng.shuffle(shuffled)
                    row={'id':f'{m}_{di}_{style}_{int(y)}','group':f'{m}_{di}_{style}',
                         'template_family':f'{m}_{style}','lexical_assignment':di,'dataset':'expanded_controlled',
                         'mechanism':m,'domain':domain,'claim':f'B {p}.','truth':'true' if y else 'false',
                         'support':'true' if y else 'false','conditions':{'a_only':'\n'.join(turns),
                         'narrative':narrative,'shuffled':'\n'.join(shuffled),
                         'word_bag':'Unordered words from A (order discarded): '+' '.join(sorted(tokens(' '.join(turns))))}}
                    pair.append(row); rows.append(row)
                assert collections.Counter(tokens(pair[0]['conditions']['a_only']))==collections.Counter(tokens(pair[1]['conditions']['a_only']))
                assert pair[0]['conditions']['word_bag']==pair[1]['conditions']['word_bag']
                assert collections.Counter(tokens(pair[0]['conditions']['narrative']))==collections.Counter(tokens(pair[1]['conditions']['narrative']))
    assert len(rows)==480
    data_name='controlled.json' if version==1 else 'controlled_v2.json'
    out_name='controlled' if version==1 else 'controlled_v2'
    freeze(ROOT/'data/revision'/data_name,rows)
    rng=random.Random(20261101); plan=[]
    for cond in ['a_only','narrative','shuffled','word_bag']:
        halves=[[],[]]
        grouped=collections.defaultdict(list)
        for r in rows: grouped[r['group']].append(r)
        for pair in grouped.values():
            pair=pair.copy();rng.shuffle(pair)
            for i,r in enumerate(pair): halves[i].append(r)
        for block in halves:
            rng.shuffle(block)
            for start in range(0,len(block),6):
                batch=block[start:start+6];mapping={};items=[]
                assert len({r['group'] for r in batch})==len(batch)
                for r in batch:
                    opaque=hashlib.sha256((r['id']+'|'+cond+'|opaque').encode()).hexdigest()[:12]
                    mapping[opaque]={'item_id':r['id'],'group':r['group']}
                    items.append({'id':opaque,'proposition':r['claim'],'text':r['conditions'][cond]})
                plan.append(task(payload(PROB_SYSTEM,{'items':items},4000),condition=cond,
                                 dataset='expanded_controlled',mapping=mapping))
    rng.shuffle(plan);freeze(OUT/out_name/'requests.json',plan)
    return rows

def natural():
    ds=read(ROOT/'data/revision/dialogues.json');inv=read(ROOT/'data/stage2/inventory.json');plan=[]
    for d in ds:
        for hidden in [0,1]:
            visible=[t for i,t in enumerate(d['turns']) if i%2!=hidden]
            a=[{'turn':i+1,'speaker':'A','text':t} for i,t in enumerate(visible)]
            full=[{'turn':i+1,'speaker':f'S{i%2}','text':t} for i,t in enumerate(d['turns'])]
            for cond,trans,target in [('a_only',a,'B'),('full',full,f'S{hidden}')]:
                plan.append(task(payload(CATALOGUE_SYSTEM,{'targets':[target],'catalogue':inv,'transcript':trans}),
                            condition=cond,dialogue_id=d['id'],arm=d['arm'],target_source_speaker=hidden))
    plan.append(task(payload(CATALOGUE_SYSTEM,{'targets':['B'],'catalogue':inv,'transcript':[]}),condition='prior'))
    random.Random(20261101).shuffle(plan);freeze(OUT/'natural/requests.json',plan)

def repeats():
    originals=[t for t in read(OUT/'stage2/requests.json') if t['condition']=='a_only']
    chosen=random.Random(20261101).sample(originals,24);plan=[]
    for original in chosen:
        for temp,trials in [(0,[1]),(.7,[1,2,3])]:
            for trial in trials:
                p=copy.deepcopy(original['payload']);p['temperature']=temp
                plan.append(task(p,condition='repeat_t0' if temp==0 else 'repeat_t07',trial=trial,
                                 dialogue_id=original['dialogue_id'],target_source_speaker=original['target_source_speaker'],
                                 arm=original['arm'],reference_task_id=original['task_id']))
    freeze(OUT/'repeats/requests.json',plan)

if __name__=='__main__':
    controlled(); natural(); repeats()
    print(json.dumps({n:len(read(OUT/n/'requests.json')) for n in ['controlled','natural','repeats']}))
