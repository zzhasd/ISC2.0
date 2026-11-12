"""Check observation boundaries, frozen sources, complete coverage and review packets."""
import collections
import csv
import hashlib
import json
import re
from revision_api import ROOT,OUT,read,save,freeze
from revision_prepare import tokens
from stage2_prepare import norm

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def create_review_csv(path,fields,rows):
    if path.exists():return # never erase a human's completed review on audit reruns
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
def main():
    originals=[ROOT/'data/natural_pilot.json',ROOT/'data/controlled_pilot.json',ROOT/'data/stage2/dialogues.json',ROOT/'data/stage2/gold.json',
        ROOT/'results/api_raw.jsonl',ROOT/'results/requests.json',ROOT/'results/summary.json',ROOT/'results/stage2/api_raw.jsonl',ROOT/'results/stage2/requests.json',ROOT/'results/stage2/summary.json']
    frozen=OUT/'original_preservation_hashes.json'
    snapshot={str(p.relative_to(ROOT)):sha(p) for p in originals}
    if frozen.exists():assert read(frozen)==snapshot,'Original historical data/result was modified'
    else:save(frozen,snapshot)
    for new,old in [('stage1','results/requests.json'),('singletons','results/singletons_requests.json'),('stage2','results/stage2/requests.json')]:
        a=read(OUT/new/'requests.json');b=read(ROOT/old)
        assert len(a)==len(b)
        for x,y in zip(a,b):
            p=json.loads(json.dumps(x['payload']));p['model']=y['payload']['model']
            assert p==y['payload'],'Rerun changed a field other than model'
    all_data=[json.loads(x) for x in (ROOT/'data/dailydialog.jsonl').read_text(encoding='utf-8').splitlines()]
    oldids={r['id'] for r in read(ROOT/'data/natural_pilot.json')}|{r['id'] for r in read(ROOT/'data/stage2/dialogues.json')}
    blocked={norm(r) for r in all_data if r['split']!='test' or r['id'] in oldids}
    ds=read(ROOT/'data/revision/dialogues.json');byid={d['id']:d for d in ds}
    assert len({norm(d) for d in ds})==len(ds) and not any(norm(d) in blocked for d in ds)
    inventory=read(ROOT/'data/stage2/inventory.json')
    for t in read(OUT/'natural/requests.json'):
        c=json.loads(t['payload']['messages'][1]['content'])
        assert c['catalogue']==inventory
        assert set(c)=={'targets','catalogue','transcript'}
        if t['condition']=='a_only':
            d=byid[t['dialogue_id']];s=t['target_source_speaker']
            visible=[text for i,text in enumerate(d['turns']) if i%2!=s]
            assert c['transcript']==[{'turn':i+1,'speaker':'A','text':text} for i,text in enumerate(visible)]
            assert c['targets']==['B']
    rows=read(ROOT/'data/revision/controlled.json');groups=collections.defaultdict(list)
    for r in rows:groups[r['group']].append(r)
    assert len(groups)==240
    for pair in groups.values():
        assert len(pair)==2 and pair[0]['truth']!=pair[1]['truth']
        assert collections.Counter(tokens(pair[0]['conditions']['a_only']))==collections.Counter(tokens(pair[1]['conditions']['a_only']))
        assert pair[0]['conditions']['word_bag']==pair[1]['conditions']['word_bag']
    indexed={r['id']:r for r in rows}
    for t in read(OUT/'controlled/requests.json'):
        batch=list(t['mapping'].values());assert len({x['group'] for x in batch})==len(batch)
        content=json.loads(t['payload']['messages'][1]['content'])
        assert all(set(x)=={'id','proposition','text'} for x in content['items'])
        assert all(re.fullmatch('[0-9a-f]{12}',x['id']) for x in content['items'])
    v2=read(ROOT/'data/revision/controlled_v2.json')
    assert len(v2)==len(rows)
    for a,b in zip(rows,v2):
        assert {k:v for k,v in a.items() if k!='conditions'}=={k:v for k,v in b.items() if k!='conditions'}
        if a['mechanism']!='confirmation':assert a==b,'V2 changed a non-confirmation item'
    pairs_v2=collections.defaultdict(list)
    for r in v2:pairs_v2[r['group']].append(r)
    for pair in pairs_v2.values():
        assert collections.Counter(tokens(pair[0]['conditions']['a_only']))==collections.Counter(tokens(pair[1]['conditions']['a_only']))
        assert pair[0]['conditions']['word_bag']==pair[1]['conditions']['word_bag']
    for name in ['defense_reconstruction','defense_summary']:
        p=OUT/name/'requests.json'
        if not p.exists():continue
        originals2={(t['dialogue_id'],t['target_source_speaker']):json.loads(t['payload']['messages'][1]['content'])['transcript'] for t in read(OUT/'stage2/requests.json') if t['condition']=='a_only'}
        for t in read(p):
            c=json.loads(t['payload']['messages'][1]['content'])
            assert c['visible_A']==originals2[(t['dialogue_id'],t['target_source_speaker'])]
            assert set(c)<= {'visible_A','reconstructed_B'}
    for judge_name in ['defense_judge','defense_judge_v2']:
      judge_plan=OUT/judge_name/'requests.json'
      if judge_plan.exists():
        for t in read(judge_plan):
            c=json.loads(t['payload']['messages'][1]['content'])
            assert set(c)=={'visible_A','summary','catalogue'}
            assert c['catalogue']==inventory
            assert c['visible_A']==originals2[(t['dialogue_id'],t['target_source_speaker'])]
    counts={};tokens_total=read(OUT/'probe.json')['body']['usage']['total_tokens'];errors=[];models=set();attempts=1;unreturned=[]
    for planpath in OUT.glob('*/requests.json'):
        name=planpath.parent.name;plan=read(planpath);rawpath=planpath.parent/'api_raw.jsonl'
        assert len({t['task_id'] for t in plan})==len(plan),'Duplicate frozen task IDs'
        raw=[json.loads(x) for x in rawpath.read_text(encoding='utf-8').splitlines()] if rawpath.exists() else []
        successes=[r for r in raw if r.get('http_status')==200]
        planned={t['task_id'] for t in plan}
        assert all(r['task_id'] in planned for r in raw)
        assert len({r['task_id'] for r in successes})==len(successes),'Duplicate successful requests'
        counts[name]={'planned':len(plan),'recorded_attempts':len(raw),'successful':len(successes),
                      'missing_tasks':len(planned-{r['task_id'] for r in successes})}
        attempts_file=planpath.parent/'attempts.jsonl'
        submitted=[json.loads(x) for x in attempts_file.read_text(encoding='utf-8').splitlines()] if attempts_file.exists() else []
        logged={r.get('attempt_id') for r in raw}
        unlogged=[a for a in submitted if a['attempt_id'] not in logged]
        counts[name]['unreturned_attempts']=len(unlogged)
        unreturned.extend({'plan':name,**a} for a in unlogged)
        attempts+=len(raw)
        for r in raw:
            tokens_total+=r.get('body',{}).get('usage',{}).get('total_tokens',0)
            if r.get('body',{}).get('model'):models.add(r['body']['model'])
            if r.get('http_status')!=200:errors.append({'plan':name,'task':r['task_id'],'error':r.get('error'), 'http':r.get('http_status')})
    result={'original_hashes_unchanged':True,'rerun_only_model_changed':True,'new_unique_dialogues':len(ds),
        'new_gold_decisions':len(read(ROOT/'data/revision/gold.json')),'controlled_pairs':len(groups),
        'one_sided_observation_boundary_passed':True,'identical_controlled_pair_word_bags':True,
        'requests':counts,'recorded_attempts_including_probe':attempts,'recorded_tokens_including_probe':tokens_total,
        'returned_models':sorted(models),'transport_or_http_failures':errors,
        'unreturned_attempts':unreturned,'max_attempts_per_task':max((r.get('attempt_number_for_task',1) for p in OUT.glob('*/api_raw.jsonl') for r in map(json.loads,p.read_text(encoding='utf-8').splitlines())),default=0),
        'all_plans_complete':all(c['missing_tasks']==0 for c in counts.values()),
        'scientific_limitations':['AI provisional labels; no independent human agreement','Unknown truth is not false',
            'Hand-authored template/naturalness confounding remains','Same-model summary judge is a utility proxy','Real-world prevalence and novelty unestablished']}
    save(OUT/'audit.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))

def review_packets():
    directory=OUT/'human_review';directory.mkdir(exist_ok=True)
    gold=read(ROOT/'data/revision/gold.json');ds={d['id']:d for d in read(ROOT/'data/revision/dialogues.json')}
    fields=['dialogue_id','target_source_speaker','attribute','truth','a_support','full_evidence_turns','a_evidence_turns','truth_basis','sensitive_to_annotation_policy','dialogue_note','human1_truth','human2_truth','human1_A_support','human2_A_support','adjudication']
    create_review_csv(directory/'natural_annotations.csv',fields,gold)
    packet=['# 新增自然对话的人工复核材料','','现有标签均为 Codex AI 暂定；两名人工审核栏尚未填写。请分开判定事实、持有者、可见证据与具体程度。unknown 不等于 false。','']
    for d in ds.values():
        packet += [f'## {d["id"]} / {d["arm"]}','']+[f'{i+1}. S{i%2}: {t}' for i,t in enumerate(d['turns'])]+['']
        for r in gold:
            if r['dialogue_id']==d['id'] and r['truth']!='unknown':
                packet.append(f'- S{r["target_source_speaker"]} / {r["attribute"]}: {r["truth"]}; A support {r["a_support"]}; full {r["full_evidence_turns"]}; A {r["a_evidence_turns"]}; {r["truth_basis"]}')
        packet.append('')
    (directory/'natural_transcripts.md').write_text('\n'.join(packet),encoding='utf-8')
    controlled=read(ROOT/'data/revision/controlled.json')
    fields=['id','mechanism','lexical_assignment','truth','a_only','narrative','human_naturalness','human_semantic_equivalence','human_holder','human_note']
    create_review_csv(directory/'controlled_quality.csv',fields,[{**{k:r[k] for k in ['id','mechanism','lexical_assignment','truth']},'a_only':r['conditions']['a_only'],'narrative':r['conditions']['narrative']} for r in controlled])
    controlled_v2=read(ROOT/'data/revision/controlled_v2.json')
    fields=['id','mechanism','a_only','narrative','human1_naturalness','human2_naturalness','human1_semantic_equivalence','human2_semantic_equivalence','human_holder','human_note']
    create_review_csv(directory/'controlled_v2_quality.csv',fields,[{'id':r['id'],'mechanism':r['mechanism'],'a_only':r['conditions']['a_only'],'narrative':r['conditions']['narrative']} for r in controlled_v2])
    inv=read(ROOT/'data/stage2/inventory.json');blind_a=[];blind_full=[]
    for d in ds.values():
        for s in [0,1]:
            opaque=hashlib.sha256(f'{d["id"]}|{s}|human'.encode()).hexdigest()[:12]
            blind_a.append({'id':opaque,'target':'B','transcript':[{'turn':i+1,'speaker':'A','text':t} for i,t in enumerate(text for j,text in enumerate(d['turns']) if j%2!=s)]})
            blind_full.append({'id':opaque,'target':f'S{s}','transcript':[{'turn':i+1,'speaker':f'S{i%2}','text':t} for i,t in enumerate(d['turns'])]})
    save(directory/'a_only_blind.json',{'catalogue':inv,'items':blind_a})
    save(directory/'full_truth_blind.json',{'catalogue':inv,'items':blind_full})
    blind_template=directory/'blind_annotations.csv'
    if not blind_template.exists():
        fields=['id','attribute','human1_truth','human2_truth','human1_A_support','human2_A_support','human1_holder','human2_holder','human1_evidence','human2_evidence','human1_specificity','human2_specificity','adjudication']
        with blind_template.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
            for view in blind_a:
                for a in inv:w.writerow({'id':view['id'],'attribute':a['id']})
    instructions='''# 人工审核说明

本目录没有完成任何独立人工标注。不要将 AI 标签或模型评分复制进人工栏。

请两名标注员分别独立完成 `blind_annotations.csv` 中自己的栏位：

1. 先只阅读 `a_only_blind.json`，判定 A 的可见证据是否足以支持/否定关于 B 的目录命题；填写 true / false / unknown、持有者、证据、可支持的具体程度。
2. 完成第一遍后再阅读 `full_truth_blind.json`，针对指定 S0/S1 判定完整对话设定中的事实。unknown 不是 false；问题、第三人事实和泛化场景不能自动移给目标。
3. 两位标注员完成前不互看、不查看现有 AI 标签或攻击输出；之后再仲裁。`natural_annotations.csv` 和带标签对话材料只用于仲裁。
4. 受控质量使用 `controlled_v2_quality.csv`，分别评价自然度、语义等价和属性持有者。首版有已知构造缺陷，另行保留。
5. 摘要人工复核先使用不含方法名的 `summary_review_blind.csv`，仲裁再看 `summary_review.csv`，模型评分不等于人工评分。

填写后运行 `python experiments/revision_annotation_agreement.py`。程序只计算双人已实际填写的行，不填补空白，不把 AI 标签当作第二个标注员。保存的 agreement status 在全空时明确报告 pending。
'''
    (directory/'README.md').write_text(instructions,encoding='utf-8')

if __name__=='__main__':review_packets();main()
