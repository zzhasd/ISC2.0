"""Validate native Sol annotations, audit generation boundaries, and export reports."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from .core import HERE, load, freeze, digest
from .portrait_summary import OUT, SOURCE_RUN, TOP, DIRECT, request, code_hashes, validate_portraits, materialize, deduplicate

RELATIONS=('supported','partial','contradicted','mixed','not_covered')
SCORES=dict(supported=100,partial=50,contradicted=0,mixed=50,not_covered=None)


def aggregate(judgments):
    c=Counter(j['relation'] for j in judgments);n=len(judgments);covered=n-c['not_covered']
    credit=c['supported']+.5*(c['partial']+c['mixed'])
    return dict(counts={k:c[k] for k in RELATIONS},n=n,coverage=covered/n if n else 0,
                covered_consistency_score=100*credit/covered if covered else None,
                all_item_alignment_score=100*credit/n if n else None)


def validate_score(obj,packet,condition):
    if obj.get('judge_model')!='gpt-6.1-sol' or obj.get('reasoning_effort')!='high' or obj.get('condition')!=condition:raise ValueError('Judge metadata mismatch')
    ps={p['portrait_id']:p for p in packet['portraits']};ars={a['archive_id']:a for a in packet['archive']}
    for field,idkey,wanted,refkey,allowed in [('portrait_judgments','portrait_id',ps,'archive_refs',ars),('archive_judgments','archive_id',ars,'portrait_refs',ps)]:
        js=obj.get(field)
        if not isinstance(js,list) or len(js)!=len(wanted) or {j.get(idkey) for j in js}!=set(wanted):raise ValueError('Must cover every '+idkey+' exactly once')
        for j in js:
            if j.get('relation') not in RELATIONS:raise ValueError('Bad relation')
            if not isinstance(j.get('reason'),str) or not j['reason'].strip():raise ValueError('Missing reason')
            refs=j.get(refkey)
            if not isinstance(refs,list) or any(not isinstance(r,str) or r not in allowed for r in refs) or len(refs)!=len(set(refs)):raise ValueError('Invalid counterpart references')
            if j['relation']!='not_covered' and not refs:raise ValueError('Unsupported judgment without counterpart')
            pair=j.get('contradiction_pair')
            if j['relation'] in ('contradicted','mixed'):
                if not isinstance(pair,str) or not pair.strip():raise ValueError('Counterevidence must state actual incompatible propositions')
            elif pair is not None:raise ValueError('Unknown/partial/support is not a contradiction')
    fs=obj.get('fidelity_checks')
    if not isinstance(fs,list) or not isinstance(obj.get('limitations'),str):raise ValueError('Missing fidelity/limitations')
    if condition=='direct':
        if fs:raise ValueError('Direct has no intermediate details to compare')
    else:
        if len(fs)!=len(ps) or {f.get('portrait_id') for f in fs}!=set(ps):raise ValueError('Each summary fidelity once')
        for f in fs:
            if f.get('fidelity') not in ('faithful','lossy','uncertain') or not isinstance(f.get('reason'),str) or not f['reason'].strip():raise ValueError('Invalid fidelity')
            allowed={u['unique_id'] for u in ps[f['portrait_id']]['retained_details']}
            if not isinstance(f.get('detail_refs'),list) or any(r not in allowed for r in f['detail_refs']):raise ValueError('Unknown fidelity detail')
    return obj


def validate_full_fidelity(obj,portraits):
    if obj.get('judge_model')!='gpt-6.1-sol' or obj.get('reasoning_effort')!='high' or obj.get('source_context')!='full_generation_input_including_evidence':raise ValueError('Wrong full-input fidelity metadata')
    ps={p['portrait_id']:p for p in portraits};checks=obj.get('checks')
    if not isinstance(checks,list) or len(checks)!=len(ps) or {c.get('portrait_id') for c in checks}!=set(ps):raise ValueError('Full fidelity must cover all portraits')
    for c in checks:
        if c.get('fidelity') not in ('faithful','lossy','uncertain') or not isinstance(c.get('reason'),str) or not c['reason'].strip():raise ValueError('Invalid full fidelity check')
        allowed={u['unique_id'] for u in ps[c['portrait_id']]['source_details']}
        if not isinstance(c.get('detail_refs'),list) or any(u not in allowed for u in c['detail_refs']):raise ValueError('Unknown full fidelity reference')
    return checks


def audit(folder):
    prep=load(folder/'preparation.json');inputs=load(folder/'inputs.json');records=load(folder/'attributes_209.json');unique=load(folder/'deduplicated.json');manifest=load(folder/'generation_manifest.json')
    assert len(records)==209
    originals=[]
    for d in inputs['dialogues']:
        for c in load(SOURCE_RUN/'attributes'/f"{d['dialogue']}.json")['prediction']['claims']:
            originals.append(dict(source_id=f"{d['dialogue']}/{c['candidate_id']}",dialogue=d['dialogue'],partner=d['partner'],claim=c))
    assert records==originals
    assert digest(records)==prep['records_digest'] and digest(inputs)==prep['inputs_digest'] and digest(unique)==prep['unique_digest']
    assert unique==deduplicate(records)
    for p,h in prep['source_sha256'].items():assert hashlib.sha256((HERE/p).read_bytes()).hexdigest()==h
    assert manifest['code_sha256']==code_hashes() and manifest['inputs_digest']==digest(inputs) and manifest['unique_digest']==digest(unique)
    assert len(unique)==206 and sum(len(u['members']) for u in unique)==209
    for method in ('summary','direct'):
        raw=load(folder/f'{method}_raw.json')['prediction'];validate_portraits(raw,method,inputs,unique)
        assert load(folder/f'{method}_portraits.json')==(materialize(raw,unique) if method=='summary' else raw)
    final=load(folder/'summary_portraits.json')
    flattened=[u for p in final['portraits'] for u in p['source_details']]
    assert sorted(flattened,key=lambda u:u['unique_id'])==unique
    rows=[json.loads(s) for s in (folder/'attempts.jsonl').read_text(encoding='utf-8').splitlines()]
    starts={r['attempt_id']:r for r in rows if r['event']=='start'};ends={r['attempt_id']:r for r in rows if r['event']=='complete'}
    assert starts.keys()==ends.keys()
    direct_data=dict(dialogues=[dict(d,visible_turns=[dict(t,speaker='A',text='A says: '+t['text']) for t in d['visible_turns']]) for d in inputs['dialogues']])
    expected={'summary':request(TOP,dict(unique_attributes=unique)),'direct':request(DIRECT,direct_data)}
    counts=Counter();usage=Counter()
    for r in starts.values():
        method=r['logical_name'].split('/')[-1]
        assert r['logical_name']==f'portrait_summary_20261107/{method}' and method in expected
        assert r['request']==expected[method], 'Actual sent payload differs from exact archive-blind expected request'
        counts[method]+=1
    assert set(counts)=={'summary','direct'}
    for r in ends.values():
        for k,v in r.get('body',{}).get('usage',{}).items():
            if isinstance(v,(int,float)):usage[k]+=v
    leaked=[]
    for p in folder.rglob('*'):
        if p.is_file() and p.suffix in ('.py','.json','.jsonl','.md') and re.search(r'sk-[A-Za-z0-9_.-]{20,}',p.read_text(encoding='utf-8')):leaked.append(str(p))
    assert not leaked
    frozen_semantic=folder/'semantic_judgments_frozen_before_fidelity_supplement.json'
    if frozen_semantic.exists():
        for name,h in load(frozen_semantic).items():assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==h
    if (folder/'fidelity_full_source_packet.json').exists():
        fp=load(folder/'fidelity_full_source_packet.json')
        assert fp['generation_instruction']==TOP and fp['portraits']==final['portraits']
        assert not {'archive','atoms','archive_id'}.intersection(fp)
    return dict(passed=True,original_209_unchanged=True,exact_unique_strings=len(unique),duplicate_records=len(records)-len(unique),all_209_records_preserved_in_portraits=True,qualified_records=sum(r['claim']['certainty']=='qualified' for r in records),no_admission_filter_applied=True,extraction_new_API_calls=0,archive_and_atoms_absent_from_both_generation_requests=True,direct_raw_conversations_only=True,all_Qwen_flash_thinking=True,request_attempts=dict(counts),returned_usage=dict(usage),unknown_billing_attempts=sum(bool(r.get('billing_unknown')) for r in ends.values()),credential_scan_passed=True)


def export_portraits(folder,method):
    obj=load(folder/f'{method}_portraits.json');lines=[f'# {method}：B的画像','',obj['limitations'],'']
    for p in obj['portraits']:
        lines += [f"## {p['portrait_id']}",'',p['statement'],'']
        if method=='summary':
            lines += ['原始细节（全部保留）：','']
            for u in p['source_details']:
                lines.append(f"- {u['unique_id']}：{u['claim']}")
                for m in u['members']:
                    c=m['claim'];lines.append(f"  - {m['source_id']}；attribute={c['attribute']}；certainty={c['certainty']}；confidence={c['confidence']}")
        else:
            for e in p['evidence']:lines.append(f"- {e['dialogue']} / turn {e['turn_id']}：{e['quote']}")
        lines.append('')
    (folder/f'{method}_portraits.md').write_text('\n'.join(lines),encoding='utf-8')


def report(folder):
    verification=audit(folder);results={};fidelity={};per_item={}
    for method in ('summary','direct'):
        packet=load(folder/f'judge_{method}_packet.json');obj=validate_score(load(folder/f'judgment_{method}_sol.json'),packet,method)
        results[method]=dict(portrait_to_archive=aggregate(obj['portrait_judgments']),archive_to_portrait=aggregate(obj['archive_judgments']))
        fidelity[method]=dict(Counter(f['fidelity'] for f in obj['fidelity_checks']))
        portrait_text={p['portrait_id']:p['statement'] for p in packet['portraits']}
        archive_text={a['archive_id']:a['statement'] for a in packet['archive']}
        per_item[method]=dict(portraits=[dict(j,statement=portrait_text[j['portrait_id']],consistency_score=SCORES[j['relation']]) for j in obj['portrait_judgments']],archive=[dict(j,statement=archive_text[j['archive_id']],consistency_score=SCORES[j['relation']]) for j in obj['archive_judgments']],fidelity_checks=obj['fidelity_checks'])
        export_portraits(folder,method)
    limited_fidelity=dict(fidelity['summary']);fidelity_context='claim_attribute_certainty_only'
    if (folder/'fidelity_full_source_sol.json').exists():
        checks=validate_full_fidelity(load(folder/'fidelity_full_source_sol.json'),load(folder/'summary_portraits.json')['portraits'])
        fidelity['summary']=dict(Counter(c['fidelity'] for c in checks));per_item['summary']['full_source_fidelity_checks']=checks
        fidelity_context='full_generation_input_including_evidence'
    out=dict(verification=verification,results=results,summary_text_fidelity=fidelity,fidelity_context=fidelity_context,initial_limited_context_fidelity=limited_fidelity,judging_model='gpt-6.1-sol',judging_reasoning_effort='high',generation_model='qwen3.8-flash',generation_enable_thinking=True,single_B_exploratory=True,not_identity_accuracy=True)
    freeze(folder/'verification.json',verification);freeze(folder/'results.json',out);freeze(folder/'per_item_scores.json',per_item)
    lines=['# 209条固定属性：字符串去重、语义合并与direct画像对照','', '同一个B=HS、20段对话、300条A话语。原209条属性固定复用，包含83条qualified；字符串精确去重后206条。没有重做抽取、没有使用上一轮43条/4条筛选结果，也没有删除任何原属性。','', '两路画像均本次由qwen3.8-flash开启thinking重新生成；都不看B自述或原子命题。画像冻结后，两个独立gpt-6.1-sol/high子代理分别对照B原始10条自述评分，不看另一条件或旧评分。','', '| 条件 / 方向 | 条目数 | 支持/部分/矛盾/混合/未覆盖 | 覆盖率 | 有覆盖条件一致性分 | 全条目对齐分 |','|---|---:|---|---:|---:|---:|']
    for method,rr in results.items():
        for direction,r in rr.items():
            c=r['counts'];labels='/'.join(str(c[k]) for k in RELATIONS);conditional=r['covered_consistency_score']
            lines.append(f"| {method} / {direction} | {r['n']} | {labels} | {r['coverage']:.1%} | {conditional if conditional is not None else 'N/A'} | {r['all_item_alignment_score']:.2f} |")
    lines+=['', '权重：支持1、部分0.5、混合0.5、矛盾0；未覆盖不是矛盾。有覆盖条件分只以非未覆盖条目为分母，全条目分以全部条目为分母。画像数量与粒度不同，两方向必须一起读，不能只用画像均分宣布优劣。','','原209条的claim、attribute、certainty、evidence和审核字段在summary_portraits.json的source_details中原样保留；206条unique_id全部恰好归入一条画像。该结构保全不等于自然语言总结已经无损，Sol另做摘要文字忠实性检查：'+str(fidelity['summary'])+'。','','读取画像：summary_portraits.md、direct_portraits.md。评分逐项理由：judgment_summary_sol.json、judgment_direct_sol.json。自然语言总结有问题时也不回头按评分重生成或删项。','','本实验只测画像与不完整自述的语义对应，不检验全部画像真伪；未被自述覆盖的信息不能据此判假。只有一个B，两个方法计算路径不同，不是身份识别准确率或泛化结论。','',f"Qwen本次请求尝试：{verification['request_attempts']}；返回usage：{verification['returned_usage']}；计费未知传输失败：{verification['unknown_billing_attempts']}。不包含原生Sol消耗，不推算费用。"]
    if fidelity_context=='full_generation_input_including_evidence':lines+=['',f"忠实性补查采用包含原证据的完整生成输入，见 fidelity_full_source_sol.json。首次只看claim/attribute/certainty得到的{limited_fidelity}仍保留于原始judgment_summary_sol.json，不能用来替代完整输入核验。双向自述一致性标签与分数未改，画像未改。"]
    lines+=['','## 相同10条原始自述的并列结果','', '| 自述 | 原文 | summary | direct |','|---|---|---|---|']
    js={m:{j['archive_id']:j for j in load(folder/f'judgment_{m}_sol.json')['archive_judgments']} for m in ('summary','direct')}
    for a in load(folder/'archive_for_judges.json'):
        pid=a['archive_id'];lines.append(f"| {pid} | {a['statement'].replace('|','／')} | {js['summary'][pid]['relation']} | {js['direct'][pid]['relation']} |")
    (folder/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,default=OUT);report(p.parse_args().folder)
