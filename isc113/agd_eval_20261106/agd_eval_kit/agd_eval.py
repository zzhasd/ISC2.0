#!/usr/bin/env python3
# AGD-Eval starter v1.0 | Python 3.10+ | pip install openai
# No network calls during prepare/score. All judge calls require --stage ...
import argparse, csv, hashlib, json, os, random, re, statistics, time, zipfile
from collections import Counter, defaultdict
from pathlib import Path

MODEL_DEFAULT = 'qwen3.8-max-0902'  # version-locked; use qwen3.8-max if snapshot unavailable
BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
METHODS = {
 'direct_thinking':'Direct Thinking',
 'dual_without_verifier':'Dual Without Verifier',
 'evidence_adaptive_v3':'Evidence-Adaptive v3',
 'elara_evidence_lattice_v1':'ELARA v1',
 'elara_v2_evidence_calibrated_dual_route':'ELARA v2',
 'prism_scoped_evidence_v1':'PRISM',
}
PATHS = ['main/exports/dailydialog.json',
 'evidence_adaptive_v3_append/exports/dailydialog.json',
 'elara_append_v1/exports/dailydialog.json',
 'elara_v2_append/exports/dailydialog.json',
 'prism_enhanced_v11/exports/dailydialog.json']
LEVELS = {'E1','E2','E3','E4','CONTRADICTED','NOT_B','UNCERTAIN'}
VALID = {'E1','E2'}

def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def dump(path,obj):
 p=Path(path);p.parent.mkdir(parents=True, exist_ok=True)
 tmp=p.with_suffix(p.suffix+'.tmp')
 tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(p)
def stable_hash(obj): return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def clean_claim(s): return ' '.join(s.lower().strip().rstrip('.').split())
def path_for(work,stage,did): return Path(work)/'judgments'/stage/(did+'.json')

def prepare(args):
 inp=read(args.inputs); refs=read(args.refs)
 ids=[x['dialogue_id'] for x in inp]
 if len(ids)!=len(set(ids)): raise ValueError('duplicate dialogue IDs in inputs')
 dialogues={x['dialogue_id']:{'visible_turns':x['visible_turns'],'predictions':[], 'references':[], 'direction':x['direction']} for x in inp}
 for r in refs:
  d=dialogues[r['dialogue_id']]
  for i,c in enumerate(r['claims']):
   d['references'].append({'id':c['claim_id'],'claim':c['claim'],'old_level':c['evidence_level'],
                           'old_category':c.get('category'),'old_mechanism':c.get('mechanism')})
 with zipfile.ZipFile(args.runs) as z:
  for name in PATHS:
   for r in json.loads(z.read(name)):
    if r['method'] not in METHODS:continue
    d=dialogues[r['dialogue_id']]
    for i,c in enumerate(r['claims']):
     d['predictions'].append({'id':r['method']+':'+str(i),'algorithm':r['method'],
       'claim':c['claim'],'evidence':c.get('evidence',[]),'confidence':c.get('confidence')})
 for did,d in dialogues.items():
  if len({p['algorithm'] for p in d['predictions']})>6: raise ValueError('invalid methods')
  assert all(int(x['turn_id'])%2==1 for x in d['visible_turns']),did
  pc={};
  for p in d['predictions']:
   key=clean_claim(p['claim']);cid='p_'+stable_hash({'did':did,'text':key})[:14]
   p['candidate_id']=cid
   if cid not in pc:pc[cid]={'id':cid,'claim':p['claim'], 'evidence':p['evidence']}
  d['pred_candidates']=sorted(pc.values(),key=lambda x:x['id'])
  d['gold_candidates']=[{'id':'g_'+c['id'],'claim':c['claim']} for c in d['references']]
 total=Counter(p['algorithm'] for d in dialogues.values() for p in d['predictions'])
 if len(dialogues)!=298 or sum(total.values())!=7868: print('NOTE: nonoriginal dataset size detected',len(dialogues),sum(total.values()))
 work=Path(args.out);work.mkdir(parents=True,exist_ok=True)
 dump(work/'data.json',{'dialogues':dialogues,'methods':METHODS,'inputs_hash':stable_hash(inp),'refs_hash':stable_hash(refs),'prediction_counts':dict(total),'model':args.model})
 print('PREPARED',len(dialogues),'dialogues',sum(total.values()),'predictions; counts:',dict(total))

SUPPORT_SYSTEM='''你是 A-only 隐式/显式事实审核专家。原始预测中的 target、hidden partner、对话另一方均指 B；visible speaker 指 A。你的唯一任务是判断 A 单侧是否足以支持关于 B 的候选事实；不看 B 隐藏发言，不能猜测 B 的真实回答。严格输出 JSON。
定义：E1=A 直接陈述/明确称呼/明确断言 B 的属性。E2=A 的预设、语用行为、指代或多轮证据足够强地支持的保守推断；不要求形式逻辑绝对必然，但不能仅是常见猜测。E3=相关但证据不够，例如开放问题、条件句未兑现、身份未定、时态/数量/角色过强。E4=毫无相关线索。CONTRADICTED=A 证据否定该断言。NOT_B=不是关于 B 的属性事实。UNCERTAIN=必须人工复核的边界案例。
先将候选中相互独立的 B 谓词拆成 atoms；不要把同一事件的时间、对象、程度和否定等必要限定条件随意拆成独立不完整事实。如果联合事实只有部分支持，可输出一条有据的核心事实以及一条未被支持的额外断言，不能把复合断言整体算完全正确。每个 atom 的 text 必须是完整可独立判断的 B 命题。
从全部 A 可见轮次寻找证据，不必拘泥于候选自引证据。turn_ids 必须属于给定 A 轮次，若 E1/E2 则至少一个；若 E4/NOT_B 则可空。引用存在不代表支持充分。禁止把请求当完成、可能当已然、问题当肯定、A 的身份当 B 的身份、A 的行为当 B 的行为。尤其仔细判断角色、对象、时间、数量、否定、条件、职业与事件状态。拒绝空洞属性（例如 B 正在某个对话中）。
只输出 {"items":[{"id":"候选ID","atoms":[{"text":"完整原子命题","label":"E1|E2|E3|E4|CONTRADICTED|NOT_B|UNCERTAIN","turn_ids":[1],"mechanism":"explicit|presupposition|cross_turn|coreference|speech_act|event_state|weak|none","reason":"<=40字简短依据"}]}]}。即便不是 B 属性，也必须有一个 NOT_B atom。不得漏掉、重复任何候选 ID。'''
SWEEP_SYSTEM='''你是独立的 A-only 信息发现审核员。只能看 A 发言，不看任何算法预测或旧金标准。尽可能全面但保守地发现由 A 直接明示(E1)或强隐式支持(E2)的、与 B 有关的可验证属性。逐轮扫描并整合跨轮证据。不要把开放疑问当事实；不要从服务业常识过度推断具体职业；不要把 A 的行为写成 B 的行为；不要生成仅仅属于场景的空洞陈述。保留时间、数量、否定和事件状态。多个独立关系分开，同一关系的限定条件在同一命题。输出 JSON {"claims":[{"claim":"B ...","turn_ids":[1],"proposed_level":"E1|E2","mechanism":"explicit|presupposition|cross_turn|coreference|speech_act|event_state"}]}。没有有效事实就空数组。'''
POOL_SYSTEM='''你是 A-only 规范事实库和信息覆盖审核员。输入都是另一轮审核已经确认 E1/E2 的完整原子命题；它们可能有重复、宽泛形式及互补细节。只看 A 发言及这些命题，不能看算法名称、旧金标准来源，也不能引用 B 发言。输出 JSON。
目标：将关于同一 B 实体、同一事件、同一关系的命题合并为一个最有信息量且 A 侧确实支持的规范事实；把不同关系（例如姓名/职业/拥有物）分开。同一事件的时间、对象、程度、状态放进 slots，不要产生新的无证据字段。事件不同不能因同属一类而合并。语义上部分覆盖但未完整恢复的命题可以加入同一 fact，只标记它确实覆盖的字段。严格不能因为宽泛预测便给它未提到的具体 slot。
每个 fact 要有 canonical_claim、level(E1|E2)、slots(至少一个 core/required)，members(引用所有被分配的 atom_id，且声明每条 atom 覆盖哪些 slot_ids)。core=true 表示主体-谓词-关键对象的核心判断；required=true 表示完整恢复金标准/事实需覆盖的字段。每个 slot.weight 取1或2，核心可设2，其他1。所有输入 atom 必须恰好分配一次；不得发明 atom_id；不准把原本 E2 细节提升为 E1。若同一 fact 同时含 E1/E2 证据，level 按整个最完整命题的支持机制选择。
只输出 {"facts":[{"id":"f1","canonical_claim":"B ...","level":"E1|E2","slots":[{"id":"s1","name":"role|relation|object|time|state|...","value":"...","core":true,"required":true,"weight":2}],"members":[{"atom_id":"...","slot_ids":["s1"]}]}]}。'''

def make_support_batches(did,d,source,batch_size):
 if source=='pred':candidates=d['pred_candidates']
 elif source=='gold':candidates=d['gold_candidates']
 else:
  sw=read(path_for(d['_work'],'sweep',did))['claims']
  candidates=[{'id':'s_'+did+'_'+str(i),'claim':c['claim']} for i,c in enumerate(sw)]
 rr=random.Random(314159+sum(map(ord,did)))
 candidates=candidates[:]; rr.shuffle(candidates)
 return [candidates[i:i+batch_size] for i in range(0,len(candidates),batch_size)]

def validate_support(obj, cands, turns):
 if not isinstance(obj,dict) or not isinstance(obj.get('items'),list):raise ValueError('items missing')
 ids=[c['id'] for c in cands];seen=[x.get('id') for x in obj['items']]
 if len(seen)!=len(ids) or set(seen)!=set(ids):raise ValueError('candidate coverage mismatch')
 allowed={int(t['turn_id']) for t in turns}
 for item in obj['items']:
  if not isinstance(item.get('atoms'),list) or not item['atoms']:raise ValueError('empty atoms')
  for atom in item['atoms']:
   if atom.get('label') not in LEVELS or not isinstance(atom.get('text'),str) or not atom['text'].strip():raise ValueError('invalid atom')
   tid=atom.get('turn_ids',[])
   if not isinstance(tid,list) or any(not isinstance(i,int) or i not in allowed for i in tid):raise ValueError('invalid turn IDs')
   if atom['label'] in VALID and not tid:raise ValueError('supported atom lacks turn_id')
 return obj

def validate_sweep(obj,turns):
 if not isinstance(obj,dict) or not isinstance(obj.get('claims'),list):raise ValueError('claims missing')
 allowed={int(t['turn_id']) for t in turns}
 for c in obj['claims']:
  if not c.get('claim') or c.get('proposed_level') not in VALID:raise ValueError('bad sweep claim')
  if not c.get('turn_ids') or any(i not in allowed for i in c['turn_ids']):raise ValueError('invalid sweep turn_ids')
 return obj

def validate_pool(obj, atoms):
 fs=obj.get('facts') if isinstance(obj,dict) else None
 if not isinstance(fs,list):raise ValueError('facts missing')
 if not atoms and fs:raise ValueError('no input atoms but pool contains facts')
 ids={x['atom_id'] for x in atoms}; seen=[]; fidset=set()
 for f in fs:
  if f.get('level') not in VALID or not f.get('canonical_claim') or f.get('id') in fidset:raise ValueError('bad fact')
  fidset.add(f['id']);slots=f.get('slots')
  if not isinstance(slots,list) or not slots or not any(s.get('core') is True for s in slots):raise ValueError('bad slots')
  sids=[s['id'] for s in slots]
  if len(set(sids))!=len(sids):raise ValueError('duplicate slots')
  for s in slots:
   if not isinstance(s.get('weight'),int) or s['weight'] not in [1,2] or not isinstance(s.get('required'),bool) or not isinstance(s.get('core'),bool):raise ValueError('slot schema error')
  for m in f.get('members',[]):
   if m.get('atom_id') not in ids or not m.get('slot_ids') or not set(m['slot_ids']).issubset(sids):raise ValueError('bad member')
   seen.append(m['atom_id'])
 if len(seen)!=len(ids) or set(seen)!=ids:raise ValueError(f'atom coverage mismatch: expected {len(ids)}, received {len(seen)}')
 return obj

def model_call(client,sys,payload,validate,max_tokens=12000,model=MODEL_DEFAULT):
 # Server-enforced JSON mode; local structural checks still required.
 messages=[{'role':'system','content':sys},{'role':'user','content':json.dumps(payload,ensure_ascii=False)}]
 last=None
 for attempt in range(3):
  try:
   req=client.chat.completions.create(model=model,messages=messages,temperature=0,
                    max_tokens=max_tokens,response_format={'type':'json_object'}, timeout=240)
   content=req.choices[0].message.content
   output=json.loads(content)
   validate(output)
   usage=req.usage.model_dump() if req.usage else {}
   return output,usage
  except Exception as e:
   last=e
   if attempt<2:time.sleep(2**attempt)
 raise RuntimeError('Qwen failed validation / API after retries: '+repr(last))

def pool_atoms(work,did):
 atoms=[]
 for source in ('pred','gold','sweep_support'):
  p=path_for(work,source,did)
  if not p.exists():raise FileNotFoundError('run support stage before pool: '+str(p))
  for item in read(p)['items']:
   for i,a in enumerate(item['atoms']):
    if a['label'] in VALID:
     atoms.append({'atom_id':item['id']+'::'+str(i), 'claim':a['text'], 'turn_ids':a['turn_ids'], 'level':a['label']})
 return atoms

def judge(args):
 from openai import OpenAI
 data=read(Path(args.work)/'data.json')['dialogues'];client=OpenAI(api_key=os.environ.get('DASHSCOPE_API_KEY') or os.environ.get('QWEN_API_KEY'),base_url=args.base_url)
 if not (os.environ.get('DASHSCOPE_API_KEY') or os.environ.get('QWEN_API_KEY')):raise ValueError('set DASHSCOPE_API_KEY or QWEN_API_KEY')
 done=0
 for did in sorted(data):
  if args.limit and done>=args.limit:break
  d=data[did];d['_work']=args.work
  target=path_for(args.work,args.stage,did)
  if target.exists() and not args.force:continue
  turns=d['visible_turns'];usage=[]
  if args.stage=='sweep':
   inp={'visible_turns':turns}
   obj,u=model_call(client,SWEEP_SYSTEM,inp,lambda o:validate_sweep(o,turns),max_tokens=16000,model=args.model)
   obj['claims']=[dict(c,id='s_'+did+'_'+str(i)) for i,c in enumerate(obj['claims'])]; usage=[u]
  elif args.stage in ('pred','gold','sweep_support'):
   source='sweep' if args.stage=='sweep_support' else args.stage
   batches=make_support_batches(did,d,source,args.batch)
   obj={'items':[]}
   for b in batches:
    payload={'visible_turns':turns,'candidates':b}
    res,u=model_call(client,SUPPORT_SYSTEM,payload,lambda o,b=b:validate_support(o,b,turns),model=args.model)
    obj['items']+=res['items'];usage.append(u)
  elif args.stage=='pool':
   atoms=pool_atoms(args.work,did)
   if not atoms:obj={'facts':[]}
   else:
    inp={'visible_turns':turns,'atoms':atoms}
    obj,u=model_call(client,POOL_SYSTEM,inp,lambda o:validate_pool(o,atoms),max_tokens=30000,model=args.model)
    usage=[u]
  else:raise ValueError('unknown stage')
  obj['_meta']={'model':args.model,'base_url':args.base_url,'stage':args.stage,
                'input_sha256':stable_hash({'visible_turns':turns,'stage':args.stage,'source':d.get('pred_candidates',[]) if args.stage=='pred' else d.get('gold_candidates',[]) if args.stage=='gold' else 'other'}),
                'usage':usage}
  dump(target,obj);done+=1
  if done%10==0: print(args.stage,'completed',done,'(cached files skipped)')
 print('completed new dialogues',done,'stage',args.stage)

def divide(a,b):return a/b if b else None

def score(args):
 data=read(Path(args.work)/'data.json');rows=[];p_rows=[];f_rows=[];invalid=[]
 for did,d in sorted(data['dialogues'].items()):
  files=[path_for(args.work,s,did) for s in ('pred','gold','sweep','sweep_support','pool')]
  if any(not p.exists() for p in files):
   if args.allow_incomplete:continue
   raise FileNotFoundError('Incomplete stage for '+did+' : '+', '.join(str(p) for p in files if not p.exists()))
  pred=read(files[0]);gold=read(files[1]);sw=read(files[3]);pool=read(files[4])
  candidates={x['id']:x for x in pred['items']}
  for s in ('gold','sweep_support'):
   for x in read(path_for(args.work,s,did))['items']:
    candidates[x['id']]=x
  if set(x['id'] for x in d['pred_candidates'])!=set(x['id'] for x in pred['items']): raise ValueError('missing candidate assessments '+did)
  fact_by_atom={}
  for f in pool['facts']:
   for m in f['members']:
    fact_by_atom[m['atom_id']]=(f,m)
  total_alg={m:[] for m in METHODS}
  for p in d['predictions']:total_alg[p['algorithm']].append(p)
  for alg,raws in total_alg.items():
   if not raws:continue
   correct_raw=correct_atoms=total_atoms=0; unsupported_unit_norm=set();all_raw_norm=set();semantic_redundant_valid=0;seen_fact_slots=set()
   alg_atom_ids=set()
   for p in raws:
    c=candidates[p['candidate_id']];atoms=c['atoms'];truth=[x['label'] in VALID for x in atoms]
    total_atoms+=len(atoms);correct_atoms+=sum(truth)
    raw_valid=bool(atoms) and all(truth)
    correct_raw+=int(raw_valid)
    all_raw_norm.add(clean_claim(p['claim']))
    this_fact_slots=set()
    for i,a in enumerate(atoms):
     aid=p['candidate_id']+'::'+str(i)
     if a['label'] in VALID:
      alg_atom_ids.add(aid)
      if aid not in fact_by_atom:raise ValueError('supported prediction atom missing from pool: '+aid)
      fact,member=fact_by_atom[aid]
      this_fact_slots.update((fact['id'],sid) for sid in member['slot_ids'])
     else:unsupported_unit_norm.add(clean_claim(a['text']))
    if raw_valid and not (this_fact_slots - seen_fact_slots):semantic_redundant_valid+=1
    seen_fact_slots.update(this_fact_slots)
    p_rows.append({'dialogue_id':did,'algorithm':alg,'prediction_id':p['id'],'claim':p['claim'],
        'all_grounded':int(raw_valid),'grounded_atoms':sum(truth),'all_atoms':len(atoms),
        'labels':'|'.join(a['label'] for a in atoms)})
   full=core=partial_weight=all_weight=0
   e_full=Counter();e_core=Counter();e_den=Counter();unique_grounded=set();new_facts=0
   for f in pool['facts']:
    fid=f['id'];level=f['level'];e_den[level]+=1
    covered=set()
    for m in f['members']:
     if m['atom_id'] in alg_atom_ids:covered.update(m['slot_ids'])
    essential={s['id'] for s in f['slots'] if s['required']}
    cores={s['id'] for s in f['slots'] if s['core']}
    full_hit=bool(essential) and essential.issubset(covered)
    core_hit=bool(cores) and cores.issubset(covered)
    full+=int(full_hit);core+=int(core_hit)
    e_full[level]+=int(full_hit);e_core[level]+=int(core_hit)
    all_weight+=sum(s['weight'] for s in f['slots'] if s['required'])
    partial_weight+=sum(s['weight'] for s in f['slots'] if s['required'] and s['id'] in covered)
    if core_hit: unique_grounded.add(fid)
    is_novel=not any(m['atom_id'].startswith('g_') for m in f['members'])
    new_facts+=int(core_hit and is_novel)
    f_rows.append({'dialogue_id':did,'algorithm':alg,'fact_id':did+'::'+fid,'canonical_claim':f['canonical_claim'],
                    'level':level,'core_hit':int(core_hit),'full_hit':int(full_hit),
                    'slot_weight_hit':sum(s['weight'] for s in f['slots'] if s['required'] and s['id'] in covered),
                    'slot_weight_total':sum(s['weight'] for s in f['slots'] if s['required']),
                    'new_vs_gold':int(is_novel)})
   rows.append({'dialogue_id':did,'algorithm':alg,'raw_count':len(raws),'raw_grounded':correct_raw,
     'atom_count':total_atoms,'atom_grounded':correct_atoms,'raw_text_unique':len(all_raw_norm),
     'invalid_unique_text_approx':len(unsupported_unit_norm),
     'semantic_redundant_valid':semantic_redundant_valid,
     'unique_core_found':len(unique_grounded),'valid_novel_core_found':new_facts,
     'pool_total':len(pool['facts']),'pool_full':full,'pool_core':core,
     'slot_weight_hit':partial_weight,'slot_weight_total':all_weight,
     'E1_total':e_den['E1'],'E1_full':e_full['E1'],'E1_core':e_core['E1'],
     'E2_total':e_den['E2'],'E2_full':e_full['E2'],'E2_core':e_core['E2']})
 out=Path(args.work)/'results';out.mkdir(exist_ok=True)
 for fn,dat in [('per_dialogue.csv',rows),('per_prediction.csv',p_rows),('per_fact.csv',f_rows)]:
  with (out/fn).open('w',newline='',encoding='utf-8-sig') as file:
   if dat:
    w=csv.DictWriter(file,fieldnames=dat[0].keys());w.writeheader();w.writerows(dat)
 def metrics(rr):
  s=Counter()
  for r in rr:
   for k,v in r.items():
    if k not in ('dialogue_id','algorithm'):s[k]+=v
  pg=divide(s['raw_grounded'],s['raw_count'])
  pa=divide(s['atom_grounded'],s['atom_count'])
  rg=divide(s['pool_full'],s['pool_total']);rc=divide(s['pool_core'],s['pool_total'])
  macro= (divide(s['E1_full'],s['E1_total'])+divide(s['E2_full'],s['E2_total']))/2 if s['E1_total'] and s['E2_total'] else None
  # This unique precision is a conservative approximation because invalid semantic synonyms are not merged.
  pu=divide(s['unique_core_found'],s['unique_core_found']+s['invalid_unique_text_approx'])
  return {'n_dialogues':len(rr),'raw_predictions':s['raw_count'],'grounded_raw':s['raw_grounded'],
    'P_raw':pg,'P_atom':pa,'P_unique_approx':pu,
    'R_full':rg,'R_core':rc,'R_E1_full':divide(s['E1_full'],s['E1_total']),
    'R_E2_full':divide(s['E2_full'],s['E2_total']),'R_E1_E2_macro':macro,
    'slot_coverage':divide(s['slot_weight_hit'],s['slot_weight_total']),
    'F1_raw_full':divide(2*pg*rg,pg+rg) if pg is not None and rg is not None else None,
    'valid_novel_core_found':s['valid_novel_core_found'],
    'valid_novel_per_100_dialogues':divide(100*s['valid_novel_core_found'],len(rr)),
    'unsupported_raw_rate':divide(s['raw_count']-s['raw_grounded'],s['raw_count']),
    'exact_text_repetition_rate':divide(s['raw_count']-s['raw_text_unique'],s['raw_count']),
    'valid_raw_per_100_dialogues':divide(100*s['raw_grounded'],len(rr)),
    'unique_core_per_100_dialogues':divide(100*s['unique_core_found'],len(rr)),
    'useful_yield':divide(s['unique_core_found'],s['raw_count']),
    'semantic_redundant_valid_rate':divide(s['semantic_redundant_valid'],s['raw_count']),
    'denom_pool':s['pool_total'],'denom_E1':s['E1_total'],'denom_E2':s['E2_total'],
    'note':'P_unique_approx not primary; exact-text invalid dedup only. F1 is raw-precision/pooled-recall hybrid.'}
 names=sorted({r['algorithm'] for r in rows})
 summary={m:metrics([r for r in rows if r['algorithm']==m]) for m in names}
 # Paired cluster bootstrap over dialogues. All six methods must be evaluated on same dialogue set.
 dset=sorted({r['dialogue_id'] for r in rows})
 matrix={(r['dialogue_id'],r['algorithm']):r for r in rows}
 if len(names)==len(METHODS) and all((did,m) in matrix for did in dset for m in names):
  rr=random.Random(20261106);B=args.bootstraps
  cis=defaultdict(list); diffs=defaultdict(list)
  for _ in range(B):
   sample=[dset[rr.randrange(len(dset))] for _ in dset]
   samp={m:metrics([matrix[(did,m)] for did in sample]) for m in names}
   for m in names:cis[m].append(samp[m]['R_full'])
   for j,a in enumerate(names):
    for b in names[j+1:]:diffs[(a,b)].append(samp[a]['R_full']-samp[b]['R_full'])
  def ci(v):
   vv=sorted(v);return [vv[int(.025*(len(vv)-1))],vv[int(.975*(len(vv)-1))]]
  for m in names:summary[m]['R_full_CI95_dialogue_bootstrap']=ci(cis[m])
  dump(out/'paired_differences_CI95.json',{a+' - '+b:ci(v) for (a,b),v in diffs.items()})
 dump(out/'summary.json',summary)
 print('SCORING COMPLETE:',len(dset),'dialogues;',len(rows),'algorithm-dialogue rows')
 def fmt(x):return f'{x:.3f}' if x is not None else 'NA'
 for m in names:print(f'{m:45s} P_raw={fmt(summary[m]["P_raw"])} R_full={fmt(summary[m]["R_full"])} R_E1={fmt(summary[m]["R_E1_full"])} R_E2={fmt(summary[m]["R_E2_full"])}')

if __name__=='__main__':
 p=argparse.ArgumentParser(description='AGD-Eval: Qwen judge + deterministic metrics')
 sp=p.add_subparsers(dest='cmd',required=True)
 a=sp.add_parser('prepare');a.add_argument('--runs',required=True);a.add_argument('--inputs',required=True);a.add_argument('--refs',required=True);a.add_argument('--out',required=True);a.add_argument('--model',default=MODEL_DEFAULT);a.set_defaults(func=prepare)
 a=sp.add_parser('judge');a.add_argument('--work',required=True);a.add_argument('--stage',required=True,choices=['sweep','pred','gold','sweep_support','pool']);a.add_argument('--model',default=MODEL_DEFAULT);a.add_argument('--base-url',default=BASE_URL);a.add_argument('--batch',type=int,default=12);a.add_argument('--limit',type=int);a.add_argument('--force',action='store_true');a.set_defaults(func=judge)
 a=sp.add_parser('score');a.add_argument('--work',required=True);a.add_argument('--allow-incomplete',action='store_true');a.add_argument('--bootstraps',type=int,default=2000);a.set_defaults(func=score)
 args=p.parse_args();args.func(args)
