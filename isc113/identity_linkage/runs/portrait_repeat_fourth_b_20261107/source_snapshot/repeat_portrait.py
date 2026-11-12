"""Independent new-B replication; reuse unchanged extraction and portrait algorithms."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import random
import zipfile
from .core import HERE, digest, freeze, load, sanitize, save
from .prepare import read_corpus
from .api import Client
from . import elara_subject_v2 as algorithm
from . import portrait_summary as portraits
from .score_portrait_summary import aggregate, validate_score, export_portraits, SCORES

OUT = HERE/'runs/portrait_repeat_new_b_20261107'
SEED = 2026110603


def hashes():
    names = ['repeat_portrait.py','elara_subject_v2.py','portrait_summary.py','api.py','core.py','prepare.py','score_portrait_summary.py','PORTRAIT_SUMMARY_JUDGE.md']
    return {n: hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in names}


def prepare(folder):
    archive = HERE/'data/real-persona-chat.zip'
    records = read_corpus(archive)
    index = defaultdict(list)
    for r in records:
        for b in r['interlocutors']: index[b].append(r)
    old = load(HERE/'runs/single_b_profile_v2/selection.json')['selected_b']
    eligible = sorted(b for b, rr in index.items() if b != old and 10 <= len(rr) <= 20 and len({s for r in rr for s in r['interlocutors'] if s != b}) >= 2)
    b = random.Random(SEED).choice(eligible)
    selected = sorted(index[b], key=lambda r:r['dialogue_id'])
    speakers = sorted(index)
    partners = sorted({s for r in selected for s in r['interlocutors'] if s != b})
    dialogues=[]; provenance=[]
    for i,r in enumerate(selected,1):
        a = next(s for s in r['interlocutors'] if s != b)
        turns = [dict(turn_id=j,text=sanitize(u['text'],speakers)) for j,u in enumerate([u for u in r['utterances'] if u['interlocutor_id']==a],1)]
        dialogues.append(dict(dialogue=f'D{i}',partner=f'A{partners.index(a)+1}',visible_turns=turns))
        provenance.append(dict(dialogue=f'D{i}',source=r['dialogue_id'],a_id=a,b_id=b))
    with zipfile.ZipFile(archive) as z:
        name=next(n for n in z.namelist() if n.endswith('/real_persona_chat/interlocutors.json'))
        profile=json.loads(z.read(name))[b]
    freeze(folder/'inputs.json',dict(dialogues=dialogues))
    freeze(folder/'archive_for_judges.json',[dict(archive_id=f'P{i}',statement=sanitize(s,speakers)) for i,s in enumerate(profile['persona'],1)])
    freeze(folder/'selection.json',dict(seed=SEED,eligible=eligible,excluded_previous_b=old,selected_b=b,provenance=provenance,corpus_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),all_source_dialogues_included=True,duplicates_removed=False,rule='Same sorted 10..20 ALL-conversation / >=2-partner eligibility and same seed as previous experiment; exclude old B before sampling; no persona/outcome selection'))
    freeze(folder/'design.json',dict(independent_repeat=True,user_authorized_new_extraction_for_new_b=True,attribute_count='natural output, not forced to old 209',extraction='unchanged elara_subject_v2.pipeline; no downstream admission gates',summary='unchanged TOP except actual input count and partner labels',direct='unchanged DIRECT except actual partner labels',generation='qwen3.8-flash thinking_budget=2048 max_tokens=20000 temperature=0',extraction_budget='unchanged 512/4096',scoring='unchanged PORTRAIT_SUMMARY_JUDGE.md; independent gpt-6.1-sol/high agents',inputs_digest=digest(dict(dialogues=dialogues)),code_sha256=hashes()))
    for n in hashes():
        dest=folder/'source_snapshot'/n;dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists(): assert dest.read_bytes()==(HERE/n).read_bytes()
        else: dest.write_bytes((HERE/n).read_bytes())
    print(json.dumps(dict(b=b,dialogues=len(dialogues),partners=len(partners),turns=sum(len(d['visible_turns']) for d in dialogues)),ensure_ascii=False),flush=True)


def extract(folder,workers):
    inputs=load(folder/'inputs.json')
    assert hashes()==load(folder/'design.json')['code_sha256']
    client=Client(os.getenv('QWEN_API_KEY') or os.getenv('DASHSCOPE_API_KEY'),folder)
    def one(d):
        did=d['dialogue'];oid='subject_v2_'+did
        item=dict(item_id=f'realpersonachat/{oid}/A_to_B',dialogue_id=oid,dataset='realpersonachat',direction='A_to_B',visible_turns=d['visible_turns'])
        pred,audit=algorithm.pipeline(client,item)
        freeze(folder/'attributes'/f'{did}.json',dict(prediction=pred,audit=audit))
        print(f"{did}: {len(pred['claims'])} attributes",flush=True)
    errors=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fs={pool.submit(one,d):d['dialogue'] for d in inputs['dialogues']}
        for f in as_completed(fs):
            try:f.result()
            except Exception as e:errors.append(dict(dialogue=fs[f],error=str(e)));print(errors[-1],flush=True)
    save(folder/'extraction_status.json',dict(complete=not errors,errors=errors))
    if errors:raise RuntimeError('Extraction incomplete; inspect ledger')
    records=[]
    for d in inputs['dialogues']:
        for c in load(folder/'attributes'/f"{d['dialogue']}.json")['prediction']['claims']:
            records.append(dict(source_id=f"{d['dialogue']}/{c['candidate_id']}",dialogue=d['dialogue'],partner=d['partner'],claim=c))
    freeze(folder/'attributes_all.json',records)
    freeze(folder/'deduplicated.json',portraits.deduplicate(records))
    print(f"TOTAL {len(records)} -> {len(portraits.deduplicate(records))} exact strings",flush=True)


def prompts(folder):
    n=len(load(folder/'attributes_all.json'))
    labels='/'.join(sorted({d['partner'] for d in load(folder/'inputs.json')['dialogues']}))
    top=portraits.TOP.replace('209',str(n)).replace('A1/A2/A3',labels)
    direct=portraits.DIRECT.replace('A1/A2/A3',labels)
    return top,direct


def generate(folder):
    assert hashes()==load(folder/'design.json')['code_sha256']
    inputs=load(folder/'inputs.json');unique=load(folder/'deduplicated.json')
    top,direct=prompts(folder)
    marked=dict(dialogues=[dict(d,visible_turns=[dict(t,speaker='A',text='A says: '+t['text']) for t in d['visible_turns']]) for d in inputs['dialogues']])
    tasks={'summary':portraits.request(top,dict(unique_attributes=unique)),'direct':portraits.request(direct,marked)}
    freeze(folder/'generation_manifest.json',dict(code_sha256=hashes(),inputs_digest=digest(inputs),unique_digest=digest(unique),requests=tasks,archive_access=False,atomic_proposition_access=False,new_generation=True))
    client=Client(os.getenv('QWEN_API_KEY') or os.getenv('DASHSCOPE_API_KEY'),folder)
    def one(method):
        obj,tid=client.call('portrait_repeat_new_b_20261107/'+method,tasks[method],lambda x:portraits.validate_portraits(x,method,inputs,unique))
        freeze(folder/f'{method}_raw.json',dict(prediction=obj,task_id=tid))
        freeze(folder/f'{method}_portraits.json',portraits.materialize(obj,unique) if method=='summary' else obj)
        export_portraits(folder,method)
        print(f"{method}: {len(obj['portraits'])} portraits",flush=True)
    errors=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        fs={pool.submit(one,m):m for m in tasks}
        for f in as_completed(fs):
            try:f.result()
            except Exception as e:errors.append(dict(method=fs[f],error=str(e)));print(errors[-1],flush=True)
    save(folder/'generation_status.json',dict(complete=not errors,errors=errors))
    if errors:raise RuntimeError('Generation incomplete; inspect ledger')
    portraits.packets(folder)
    freeze(folder/'fidelity_full_source_packet.json',dict(generation_instruction=top,portraits=load(folder/'summary_portraits.json')['portraits']))


def audit(folder):
    design=load(folder/'design.json');selection=load(folder/'selection.json')
    assert hashes()==design['code_sha256']
    assert selection['selected_b'] != selection['excluded_previous_b']
    # Reconstruct all A-only inputs from every source record for the selected B.
    corpus=read_corpus(HERE/'data/real-persona-chat.zip')
    selected=sorted([r for r in corpus if selection['selected_b'] in r['interlocutors']],key=lambda r:r['dialogue_id'])
    assert [r['dialogue_id'] for r in selected]==[p['source'] for p in selection['provenance']]
    speakers=sorted({s for r in corpus for s in r['interlocutors']})
    inputs=load(folder/'inputs.json')
    for r,p,d in zip(selected,selection['provenance'],inputs['dialogues'],strict=True):
        assert p['a_id'] != selection['selected_b']
        expected=[dict(turn_id=j,text=sanitize(u['text'],speakers)) for j,u in enumerate([u for u in r['utterances'] if u['interlocutor_id']==p['a_id']],1)]
        assert d['visible_turns']==expected
    assert digest(inputs)==design['inputs_digest']
    records=load(folder/'attributes_all.json');unique=load(folder/'deduplicated.json')
    originals=[dict(source_id=f"{d['dialogue']}/{c['candidate_id']}",dialogue=d['dialogue'],partner=d['partner'],claim=c) for d in inputs['dialogues'] for c in load(folder/'attributes'/f"{d['dialogue']}.json")['prediction']['claims']]
    assert records==originals and unique==portraits.deduplicate(records)
    for method in ('summary','direct'):
        raw=load(folder/f'{method}_raw.json')['prediction']
        portraits.validate_portraits(raw,method,inputs,unique)
        assert load(folder/f'{method}_portraits.json')==(portraits.materialize(raw,unique) if method=='summary' else raw)
    rows=[json.loads(s) for s in (folder/'attempts.jsonl').read_text(encoding='utf-8').splitlines()]
    starts={r['attempt_id']:r for r in rows if r['event']=='start'};ends={r['attempt_id']:r for r in rows if r['event']=='complete'}
    assert starts.keys()==ends.keys()
    manifest=load(folder/'generation_manifest.json');counts=Counter();usage=Counter()
    top,direct=prompts(folder)
    marked=dict(dialogues=[dict(d,visible_turns=[dict(t,speaker='A',text='A says: '+t['text']) for t in d['visible_turns']]) for d in inputs['dialogues']])
    expected={'summary':portraits.request(top,dict(unique_attributes=unique)),'direct':portraits.request(direct,marked)}
    assert manifest['requests']==expected and manifest['code_sha256']==hashes()
    assert manifest['inputs_digest']==digest(inputs) and manifest['unique_digest']==digest(unique)
    for r in starts.values():
        q=r['request'];assert q['model']=='qwen3.8-flash' and q['enable_thinking'] and q['temperature']==0
        if r['logical_name'].startswith('portrait_repeat_new_b_20261107/'):
            method=r['logical_name'].rsplit('/',1)[-1];assert q==expected[method];counts[method]+=1
        else:
            assert '/elara/' in r['logical_name'] and q['thinking_budget']==512 and q['max_tokens']==4096
            did=r['logical_name'].split('/')[1].removeprefix('subject_v2_')
            d=next(d for d in inputs['dialogues'] if d['dialogue']==did)
            data=json.loads(q['messages'][1]['content'])
            assert set(data)<= {'visible_turns','target','existing_claims','candidates'}
            assert data['visible_turns']==[dict(t,speaker='A',text='A says: '+t['text']) for t in d['visible_turns']]
            stage=r['logical_name'].rsplit('/',1)[-1]
            prompt=algorithm.AUDIT if stage.startswith('audit_') else dict(explicit=algorithm.EXPLICIT,implicit=algorithm.IMPLICIT,gap_scan=algorithm.GAP_SCAN)[stage]
            assert q['messages'][0]['content']==prompt
            counts['extraction']+=1
    for r in ends.values():
        for k,v in r.get('body',{}).get('usage',{}).items():
            if isinstance(v,(int,float)):usage[k]+=v
    return dict(passed=True,new_b=selection['selected_b'],all_A_only_sources_verified=True,attributes=len(records),unique_strings=len(unique),all_records_preserved=True,no_archive_or_atoms_in_generation=True,direct_no_extraction_prompt_or_input=True,algorithm_and_config_unchanged_except_count_partner_metadata=True,request_attempts=dict(counts),returned_usage=dict(usage),unknown_billing_attempts=sum(bool(r.get('billing_unknown')) for r in ends.values()))


def report(folder):
    verification=audit(folder);results={};items={}
    for method in ('summary','direct'):
        packet=load(folder/f'judge_{method}_packet.json')
        j=validate_score(load(folder/f'judgment_{method}_sol.json'),packet,method)
        results[method]=dict(portrait_to_archive=aggregate(j['portrait_judgments']),archive_to_portrait=aggregate(j['archive_judgments']))
        items[method]=dict(portraits=[dict(x,score=SCORES[x['relation']]) for x in j['portrait_judgments']],archive=[dict(x,score=SCORES[x['relation']]) for x in j['archive_judgments']],fidelity_checks=j['fidelity_checks'])
    fidelity=None
    if (folder/'fidelity_full_source_sol.json').exists():
        from .score_portrait_summary import validate_full_fidelity
        checks=validate_full_fidelity(load(folder/'fidelity_full_source_sol.json'),load(folder/'summary_portraits.json')['portraits'])
        fidelity=dict(Counter(c['fidelity'] for c in checks))
    freeze(folder/'verification.json',verification)
    freeze(folder/'results.json',dict(verification=verification,results=results,full_input_summary_fidelity=fidelity))
    freeze(folder/'per_item_scores.json',items)
    sel=load(folder/'selection.json');inp=load(folder/'inputs.json')
    lines=['# 新B独立重复实验','',f"B={sel['selected_b']}（排除旧B={sel['excluded_previous_b']}）；全部{len(inp['dialogues'])}段对话，{len({d['partner'] for d in inp['dialogues']})}个A，{sum(len(d['visible_turns']) for d in inp['dialogues'])}条A发言。",'',f"用户已明确换B独立重复，因此重新调用未经修改的改进抽取模块；实际{verification['attributes']}条属性，精确字符串去重为{verification['unique_strings']}条，不强凑旧B的209条。除人数/数量元信息外，沿用前轮算法、提示词、Qwen参数和评分协议。旧实验文件不变。",'','两路Qwen thinking均重新生成且均无自述/原子档案；direct只看完整A原文，没有属性提取提示或中间清单。画像冻结后由两个独立gpt-6.1-sol/high子代理评分。','','| 条件/方向 | 条目数 | 支持/部分/矛盾/混合/未覆盖 | 覆盖率 | 覆盖条件一致性分 | 全条目对齐分 |','|---|---:|---|---:|---:|---:|']
    for m,rr in results.items():
        for direction,r in rr.items():
            counts='/'.join(str(r['counts'][k]) for k in ('supported','partial','contradicted','mixed','not_covered'))
            lines.append(f"| {m}/{direction} | {r['n']} | {counts} | {r['coverage']:.1%} | {r['covered_consistency_score']} | {r['all_item_alignment_score']:.2f} |")
    lines += ['', '固定权重：支持1、部分0.5、混合0.5、矛盾0；未覆盖不是反证。覆盖条件分只以有覆盖项为分母，全条目对齐分以全部条目为分母。比较两组时同时查看共同自述侧结果和粒度差异。','',f'完整生成输入的摘要忠实性独立检查：{fidelity}。附件保全不代表自然语言总结语义无损。','','单个新增B的探索性复验；自述不穷尽真值，不是画像真伪全检、身份准确率或统计显著性。不得按评分回改画像。','','## 全部自述对照','','| ID | B自述原文 | summary | direct |','|---|---|---|---|']
    js={m:{j['archive_id']:j for j in load(folder/f'judgment_{m}_sol.json')['archive_judgments']} for m in ('summary','direct')}
    for a in load(folder/'archive_for_judges.json'):
        pid=a['archive_id'];lines.append(f"| {pid} | {a['statement'].replace('|','／')} | {js['summary'][pid]['relation']} | {js['direct'][pid]['relation']} |")
    lines+=['',f"Qwen请求与usage（不含原生Sol消耗，不推算费用）：{json.dumps(verification,ensure_ascii=False)}"]
    (folder/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(results,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','extract','generate','report','audit']);p.add_argument('--folder',type=Path,default=OUT);p.add_argument('--workers',type=int,default=8);a=p.parse_args()
    if a.command=='extract':extract(a.folder,a.workers)
    elif a.command=='audit':print(json.dumps(audit(a.folder),ensure_ascii=False,indent=2))
    else:globals()[a.command](a.folder)
