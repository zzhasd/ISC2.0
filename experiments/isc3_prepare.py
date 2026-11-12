"""Freeze worlds, one-target requests, ablations and dependent inference plans."""
import argparse
import collections
import copy
import hashlib
import random
from isc3_common import *
from revision_prepare import DOMAINS, controlled_text, neg

def support_set(row):
    m = row['mechanism']; style = int(row['template_family'].rsplit('_', 1)[1])
    # Minimal sufficient set for BOTH explicit positive and exclusive negative.
    if m == 'confirmation': return [1, 2, 3]
    if m == 'reference': return [1, 2, 3]
    if m == 'cross_turn': return [1, 2, 3, 4]
    if m == 'correction': return [1, 2, 5]
    if m == 'presupposition': return [1, 3] if style in (0, 2) else [1, 2, 4]
    raise ValueError(m)

def property_support(row):
    """Sufficient support for the assigned positive; negative also needs exclusivity."""
    m = row['mechanism']; style = int(row['template_family'].rsplit('_', 1)[1])
    y = row['truth'] == 'true'
    if m in ('confirmation', 'reference'): return [1, 2]
    if m == 'cross_turn': return [1, 2 if y else 3]
    if m == 'correction': return [1, 2] if y else [1, 2, 3, 5]
    if m == 'presupposition': return [1] if style in (0, 2) else [1 if y else 2]
    raise ValueError(m)

ZH_PROPERTIES = [
 ('患有糖尿病','患有哮喘'),('现在头痛','现在发烧'),('有银行贷款','有信用卡债务'),
 ('目前失业','已经退休'),('已婚','已经离婚'),('有一个儿子','有一个女儿'),
 ('对猫过敏','对花生过敏'),('目前怀孕','正在接受生育治疗'),('吸烟','饮酒'),
 ('有房贷','有学生贷款'),('是一名护士','是一名教师'),('有一个兄弟','有一个姐妹')]

def chinese_turns(row):
    p, q = ZH_PROPERTIES[row['lexical_assignment']]
    y = row['truth'] == 'true'; first, second = ('你','凯西') if y else ('凯西','你')
    exclusive = f'我们说的这两个人各自恰好符合“{p}”和“{q}”中的一项，都不符合另一项。'
    m = row['mechanism']
    if m == 'confirmation':
        yn, ny = ('是','否') if y else ('否','是')
        return [f'我的草稿将“{p}”记在你名下，将“{q}”记在凯西名下。这份草稿正确吗？',
                f'你对保留草稿的回答是“{yn}”，对调换两人的回答是“{ny}”。', exclusive]
    if m == 'reference': return [f'我按顺序说的两个人是{first}，然后是{second}。', f'前者{p}，后者{q}。', exclusive]
    if m == 'cross_turn': return [f'一号档案属于{first}，二号档案属于{second}。', f'一号档案记录的那个人{p}。',f'二号档案记录的那个人{q}。',exclusive]
    if m == 'correction':
        old, new = ('凯西','你') if y else ('你','凯西')
        return [f'我把“{p}”记在了{old}名下。', f'那是错误记录，把{old}改为{new}。',f'剩下的另一个人{q}。', f'原草稿遗漏了{new}。',exclusive]
    if m == 'presupposition': return [f'我们需要为{first}“{p}”以及{second}“{q}”这两件事安排处理。','我说的都是现在已存在的事实，不是假设。',exclusive]
    raise ValueError(m)

def controlled_case(row):
    di = row['lexical_assignment']; _, p, q, _, _ = DOMAINS[di]
    y = row['truth'] == 'true'; text = row['conditions']['a_only']
    turns = [{'turn': i+1, 'speaker': 'A', 'text': t.removeprefix('A: ')} for i,t in enumerate(text.splitlines())]
    private = 'true' if (di + int(row['template_family'].rsplit('_',1)[1])) % 2 == 0 else 'false'
    # Hidden truth is independent of opposite assignment; counter-world flips it.
    ids = ['property_p','property_q','iguana','sailboat']
    catalogue = [{'id': i, 'claim': c} for i,c in zip(ids,[f'B {p}.',f'B {q}.','B owns a pet iguana.','B owns a sailboat.'])]
    truths = [row['truth'], 'false' if y else 'true', private, 'unknown']
    m=row['mechanism']; style=int(row['template_family'].rsplit('_',1)[1]); n=len(turns)
    if m in ('confirmation','reference'):
        ps=[1,2] if y else [1,2,n]; qs=[1,2,n] if y else [1,2]
    elif m=='cross_turn':
        ps=[1,2] if y else [1,3,n]; qs=[1,2,n] if y else [1,3]
    elif m=='correction':
        ps=[1,2] if y else [1,2,n]; qs=[1,2,n] if y else [1,2,3]
    else:
        pos=[1] if style in (0,2) else [1 if y else 2]
        ps=pos if y else pos+[n]; qs=pos+[n] if y else pos
    supports = [ps, qs, [], []]
    facts = [{'id':i, 'truth':v, 'a_support':v if j<2 else 'unknown',
              'support_turns':s, 'domain':row['domain'] if j<2 else 'unobserved_control'}
             for j,(i,v,s) in enumerate(zip(ids,truths,supports))]
    split = 'calibration' if di < 4 and not row['template_family'].endswith('_3') else 'test'
    return {'case_id':row['id'], 'dataset':'controlled','group':row['group'],
            'template_family':row['template_family'], 'lexical_assignment':di,
            'mechanism':row['mechanism'],'domain':row['domain'],'split':split,
            'catalogue':catalogue,'visible_A':turns,'facts':facts,
            'full_world':{'B_properties':[p if y else q], 'Casey_properties':[q if y else p],
                          'B_owns_iguana':private=='true', 'B_owns_sailboat':None},
            'counter_world':{'identical_A':True,'B_owns_iguana':private!='true'}}

def cases():
    rows = read(ROOT/'data/revision/controlled_v2.json')
    mechanisms = ['confirmation','reference','correction','cross_turn','presupposition']
    chosen = [r for r in rows if int(r['template_family'].rsplit('_',1)[1]) ==
              (r['lexical_assignment']+mechanisms.index(r['mechanism']))%4]
    result = [controlled_case(r) for r in chosen]
    inventory = read(ROOT/'data/stage2/inventory.json')
    gold = collections.defaultdict(list)
    for f in read(ROOT/'data/stage2/gold.json'): gold[(f['dialogue_id'],f['target_source_speaker'])].append(f)
    for d in read(ROOT/'data/stage2/dialogues.json'):
        for hidden in [0,1]:
            original = [i+1 for i in range(len(d['turns'])) if i%2 != hidden]
            local = {n:i+1 for i,n in enumerate(original)}
            facts = [{'id':f['attribute'],'truth':f['truth'],'a_support':f['a_support'],
                      'support_turns':[local[n] for n in f['a_evidence_turns']],
                      'domain':f['domain'],'sensitive_to_annotation_policy':f['sensitive_to_annotation_policy']}
                     for f in gold[(d['id'],hidden)]]
            split = 'calibration' if int(hashlib.sha256(d['id'].encode()).hexdigest()[:8],16)%4==0 else 'test'
            result.append({'case_id':f"{d['id']}_target{hidden}",'dataset':'natural','group':d['id'],
                           'template_family':d['id'],'domain':'natural','split':split,'arm':d['arm'],
                           'catalogue':inventory,'facts':facts,'hidden':hidden,'original_turns':original,
                           'visible_A':[{'turn':j+1,'speaker':'A','text':d['turns'][n-1]} for j,n in enumerate(original)]})
    freeze(DATA/'cases.json', result)
    return result

def initial():
    cs = cases(); requests=[]; bindings=[]
    def add(c, method, system, turns=None, condition='full', **meta):
        visible = c['visible_A'] if turns is None else turns
        content={'visible_A':visible}
        if method not in ('recon_one_generate','recon_multi_generate','open_generate'): content['catalogue']=c['catalogue']
        cap = 3200 if len(c['catalogue'])>4 else 1600
        if method=='recon_multi_generate': cap=2400
        if method=='open_generate':cap=1800
        t=make_task(system,content,method,c['case_id'],condition,cap)
        # Empty/prior and duplicate subsets may be identical: one charge, many bindings.
        bindings.append({'task_id':t['task_id'],'case_id':c['case_id'],'method':method,
                         'condition':condition,'visible_turns':[v['turn'] for v in visible],**meta})
        requests.append(t)
    originals={r['id']:r for r in read(ROOT/'data/revision/controlled_v2.json')}
    e3_groups=set()
    for c in cs:
        for method,system in [('direct',DIRECT),('graph',GRAPH),('recon_one_generate',RECON),
                              ('recon_multi_generate',MULTI),('open_generate',OPEN)]: add(c,method,system)
        n=len(c['visible_A'])
        for k in range(n):
            for method,system in [('direct',DIRECT),('graph',GRAPH)]:
                add(c,method,system,c['visible_A'][:k],condition=f'prefix_{k}',k=k)
        if c['dataset']!='controlled':continue
        # Forty worlds, twenty independent opposite pairs for expensive evidence subsets.
        if c['lexical_assignment'] in (0,4,8,9):
            e3_groups.add(c['group'])
            subsets=[]
            for j in range(n):
                subsets.append((f'single_{j+1}',[c['visible_A'][j]]))
                subsets.append((f'delete_{j+1}',[v for v in c['visible_A'] if v['turn']!=j+1]))
            count=max(1,n//2)
            chosen=random.Random(SEED+int(digest(c['group'])[:8],16)).sample(range(n),count)
            subsets.append(('random_half',[v for j,v in enumerate(c['visible_A']) if j in chosen]))
            for cond,visible in subsets:
                for method,system in [('direct',DIRECT),('graph',GRAPH)]:add(c,method,system,visible,condition=cond)
        if c['split']=='test':
            row=originals[c['case_id']]
            # Same truth and propositions, different observed holder: A instead of Casey.
            holder=[{**v,'text':v['text'].replace("Casey's",'my').replace('Casey','me')} for v in c['visible_A']]
            di=c['lexical_assignment'];m=c['mechanism'];style=(int(c['template_family'].rsplit('_',1)[1])+1)%4
            alt=originals[f'{m}_{di}_{style}_{int(row["truth"]=="true")}']
            altturns=[{'turn':j+1,'speaker':'A','text':t.removeprefix('A: ')} for j,t in enumerate(alt['conditions']['a_only'].splitlines())]
            zh=[{'turn':j+1,'speaker':'A','text':t} for j,t in enumerate(chinese_turns(row))]
            for cond,visible in [('holder_A',holder),('template_ood',altturns),('chinese',zh)]:
                for method,system in [('direct',DIRECT),('graph',GRAPH)]:add(c,method,system,visible,condition=cond)
    unique={t['task_id']:t for t in requests}
    plan=list(unique.values());random.Random(SEED).shuffle(plan)
    freeze(OUT/'initial/requests.json',plan);freeze(DATA/'bindings_initial.json',bindings)
    manifest={'cases':len(cs),'by_dataset':dict(collections.Counter(c['dataset'] for c in cs)),
              'splits':dict(collections.Counter((c['dataset']+'_'+c['split']) for c in cs)),
              'e3_groups':len(e3_groups),'initial_unique_requests':len(plan),'bindings':len(bindings),
              'case_sha256':digest(cs),'protocol_sha256':hashlib.sha256((ROOT/'ISC3_PROTOCOL.md').read_bytes()).hexdigest(),
              'inputs':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
                        ['data/revision/controlled_v2.json','data/stage2/gold.json','data/stage2/dialogues.json']},
              'scripts':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.glob('experiments/isc3_*.py')}}
    freeze(DATA/'manifest_initial.json',manifest)
    print({k:v for k,v in manifest.items() if k not in ('inputs','scripts')})

def dependent():
    cs={c['case_id']:c for c in read(DATA/'cases.json')}
    raw=raw_index(OUT/'initial'); plan=[];bindings=[];errors=[]
    first={t['task_id']:t for t in read(OUT/'initial/requests.json')}
    for b in read(DATA/'bindings_initial.json'):
        method=b['method'];c=cs[b['case_id']];t=first[b['task_id']]
        if method not in ('direct','graph','recon_one_generate','recon_multi_generate','open_generate'):continue
        if method=='direct' and b['condition']!='full':continue
        try:
            obj=decode(raw[t['task_id']]);content=read_content(t)
            visible=content['visible_A'];catalogue=c['catalogue']
            if method in ('direct','graph'):validate_facts(obj,catalogue,visible)
            if method=='direct': system=SELFCHECK;dest='direct_review';content['draft']=obj
            elif method=='graph':system=VERIFY;dest='recover';content['draft']=obj
            elif method in ('recon_one_generate','recon_multi_generate'):
                hs=obj['hypotheses'];expected=1 if method=='recon_one_generate' else 3
                if not isinstance(hs,list) or len(hs)!=expected:raise ValueError('Wrong reconstruction hypothesis count')
                for h in hs:
                    if not isinstance(h.get('replies'),list):raise ValueError('Missing replies')
                    if any(not isinstance(r.get('text'),str) or r.get('after_turn') not in b['visible_turns'] for r in h['replies']):raise ValueError('Invalid reconstruction turn/text')
                system=EXTRACT;dest='recon_one' if expected==1 else 'recon_multi';content['hypothetical_B']=hs
                content['catalogue']=catalogue
            else:
                claims=obj['claims']
                if not isinstance(claims,list) or len(claims)>8:raise ValueError('Invalid open claim list')
                for claim in claims:
                    if not isinstance(claim.get('text'),str) or claim.get('holder')!='B':raise ValueError('Invalid open claim')
                    if not isinstance(claim.get('confidence'),(float,int)) or not 0<=claim['confidence']<=1:raise ValueError('Invalid open confidence')
                    if any(i not in b['visible_turns'] for i in claim.get('evidence_turns',[])):raise ValueError('Invalid open evidence')
                system=NORMALIZE;dest='open';content={'claims':claims,'catalogue':catalogue}
            nt=make_task(system,content,dest,c['case_id'],b['condition'],3200 if len(catalogue)>4 else 1600,source_task_id=t['task_id'])
            plan.append(nt);bindings.append({**b,'method':dest,'task_id':nt['task_id'],'source_task_id':t['task_id']})
        except (KeyError,ValueError,TypeError) as exc:errors.append({'case_id':b['case_id'],'task_id':t['task_id'],'error':str(exc)})
    freeze(OUT/'dependent/requests.json',list({t['task_id']:t for t in plan}.values()))
    freeze(DATA/'bindings_dependent.json',bindings);save(OUT/'dependent/source_errors.json',errors)
    print({'dependent_unique_requests':len({t['task_id'] for t in plan}),'bindings':len(bindings),'source_errors':len(errors)})

def read_content(t):
    import json
    return json.loads(t['payload']['messages'][1]['content'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['initial','dependent']);args=p.parse_args()
    {'initial':initial,'dependent':dependent}[args.stage]()
