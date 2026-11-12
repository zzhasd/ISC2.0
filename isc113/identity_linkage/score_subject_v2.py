"""Deterministic validation/aggregation of native Sol high agent judgments."""
import argparse
from collections import Counter
import hashlib
from itertools import combinations
import json
from pathlib import Path
from .core import load, save, freeze, digest, SOURCE, HERE
from .profile_subject_v2 import OUT, admission, hashes


def compound_relation(relations):
    # Support of a conjunction requires ALL its conjuncts, while refuting one
    # conjunct refutes the conjunction. Mixed requires evidence for BOTH sides.
    support=all(r in ('supported','mixed') for r in relations)
    negative=any(r in ('contradicted','mixed') for r in relations)
    return 'mixed' if support and negative else 'supported' if support else 'contradicted' if negative else 'insufficient'


def summary(relations):
    c=Counter(relations);n=len(relations);covered=n-c['insufficient'];credit=c['supported']+.5*c['mixed']
    return dict(counts={k:c[k] for k in ('supported','contradicted','mixed','insufficient')},n=n,coverage=covered/n if n else 0,
                full_denominator_support_score=100*credit/n if n else None,
                conditional_consistency_score=100*credit/covered if covered else None)


def validate_judgment(obj,atoms,inputs,condition,traits):
    if obj.get('judge_model')!='gpt-6.1-sol' or obj.get('reasoning_effort')!='high' or obj.get('condition')!=condition:raise ValueError('Wrong scoring model/condition metadata')
    expected={a['atom_id']:p['archive_id'] for p in atoms['items'] for a in p['atoms']}
    ds=obj.get('judgments')
    if not isinstance(ds,list) or len(ds)!=len(expected) or {d.get('atom_id') for d in ds}!=set(expected):raise ValueError('Each archive atom exactly once')
    source={(d['dialogue'],t['turn_id']):t['text'] for d in inputs['dialogues'] for t in d['visible_turns']}
    bytrait={t['trait_id']:t for t in traits['traits']}
    quality_blocked={q.get('trait_id') for q in obj.get('trait_quality_issues',[])}
    for d in ds:
        if d.get('archive_id')!=expected[d['atom_id']]:raise ValueError('Wrong parent archive item')
        rel=d.get('relation')
        if rel not in ('supported','contradicted','mixed','insufficient'):raise ValueError('Unknown relation')
        if not isinstance(d.get('reason'),str) or not d['reason'].strip():raise ValueError('Missing reason')
        sp=d.get('support_references');cp=d.get('contradiction_references');ts=d.get('trait_refs')
        if not all(isinstance(x,list) for x in (sp,cp,ts)):raise ValueError('Missing reference arrays')
        if rel in ('supported','mixed') and not sp:raise ValueError('Missing actual support')
        if rel in ('contradicted','mixed') and not cp:raise ValueError('Missing actual counterevidence')
        if rel=='supported' and cp or rel=='contradicted' and sp:raise ValueError('Inconsistent reference polarity')
        if rel=='insufficient' and (sp or cp):raise ValueError('Insufficient cannot assert actual support/counterevidence')
        for r in sp+cp:
            if type(r.get('turn_id')) is not int or not isinstance(r.get('quote'),str) or not r['quote'].strip():raise ValueError('Bad quote')
            text=source.get((r.get('dialogue'),r['turn_id']))
            if text is None or r['quote'] not in text:raise ValueError('Invented/marked quote')
        if condition=='direct':
            if ts:raise ValueError('Direct must not use intermediate traits')
        else:
            if rel!='insufficient' and not ts:raise ValueError('ELARA cannot mine raw text to bypass traits')
            if any(t not in bytrait for t in ts):raise ValueError('Unknown trait')
            if rel!='insufficient' and set(ts)&quality_blocked:raise ValueError('Known quality failure cannot contribute to score')
            allowed={r['dialogue'] for t in ts for r in bytrait[t]['references']}
            if any(r['dialogue'] not in allowed for r in sp+cp):raise ValueError('Evidence from unrelated trait source')
    if not isinstance(obj.get('trait_quality_issues'),list) or not isinstance(obj.get('limitations'),str):raise ValueError('Missing quality findings')
    if condition=='direct' and obj['trait_quality_issues']:raise ValueError('Direct cannot generate trait audit')
    for issue in obj['trait_quality_issues']:
        if issue.get('trait_id') not in bytrait:raise ValueError('Unknown problem trait')
        for r in issue.get('references',[]):
            if not isinstance(r.get('quote'),str) or not r['quote'].strip() or r['quote'] not in source.get((r.get('dialogue'),r.get('turn_id')),''):raise ValueError('Bad issue citation')
    return obj


def verify(folder):
    inputs=load(folder/'inputs.json');manifest=load(folder/'manifest.json');design=load(folder/'design.json')
    assert manifest['inputs_digest']==digest(inputs) and manifest['code_sha256']==hashes()
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==design['original_algorithm_sha256'], 'Original algorithm changed'
    assert SOURCE.read_bytes()==(HERE/'runs/single_b_profile_20261106/source_snapshot/new_algorithm.py').read_bytes(), 'Original differs from previous experiment snapshot'
    assert inputs==load(HERE/'runs/single_b_profile_20261106/inputs.json')
    rows=[json.loads(s) for s in (folder/'attempts.jsonl').read_text(encoding='utf-8').splitlines()]
    starts={r['attempt_id']:r for r in rows if r['event']=='start'};ends={r['attempt_id']:r for r in rows if r['event']=='complete'}
    assert starts.keys()==ends.keys(),'Unresolved requests'
    counts=Counter();usage=Counter()
    expected_turns={d['dialogue']:[dict(t,speaker='A',text='A says: '+t['text']) for t in d['visible_turns']] for d in inputs['dialogues']}
    for r in starts.values():
        p=r['request'];assert p['model']=='qwen3.8-flash' and p['enable_thinking'] is True and p['temperature']==0
        data=json.loads(p['messages'][1]['content'])
        def no_archive(x):
            if isinstance(x,dict):
                assert not ({'archive','atoms','archive_id','persona','judgments'} & set(x)), 'Archive/scoring leaked into Qwen'
                for v in x.values():no_archive(v)
            elif isinstance(x,list):
                for v in x:no_archive(v)
        no_archive(data)
        if '/elara/' in r['logical_name']:
            did=r['logical_name'].split('subject_v2_')[1].split('/')[0]
            assert data['visible_turns']==expected_turns[did];phase='extraction'
        elif '/gate_' in r['logical_name']:
            did=data['dialogue'];assert data['visible_turns']==expected_turns[did];phase='subject_stability_gate'
        else:
            phase=r['logical_name'].split('/')[1].split('_')[0]
            for d in data.get('dialogues',[]):assert d['visible_turns']==expected_turns[d['dialogue']]
        counts[phase]+=1
    for r in ends.values():
        for k,v in r.get('body',{}).get('usage',{}).items():
            if isinstance(v,(float,int)):usage[k]+=v
    proposed=load(folder/'proposed_traits.json')['prediction']['traits'];final=load(folder/'stable_traits.json')['traits']
    allowed={}
    original_count=retained_count=0
    for d in inputs['dialogues']:
        gate=load(folder/'gates'/f"{d['dialogue']}.json");passed={x['candidate_id'] for x in gate['decisions'] if admission(x)}
        original_count+=len(load(folder/'attributes'/f"{d['dialogue']}.json")['prediction']['claims']);retained_count+=len(gate['accepted'])
        assert all(c['candidate_id'] in passed and c['certainty']=='asserted' for c in gate['accepted'])
        allowed[d['dialogue']]={c['candidate_id'] for c in gate['accepted']}
    for t in proposed:
        assert all(r['claim_id'] in allowed[r['dialogue']] for r in t['references'])
    good={d['candidate_id'] for d in load(folder/'final_gate.json')['decisions'] if admission(d)}
    conflicts=load(folder/'conflicts.json');blocked=set(conflicts['quarantined_ids']);dup=set(conflicts['equivalent_duplicate_ids'])
    checked=[t for t in proposed if t['trait_id'] in good]
    pairs={tuple(sorted((p['left'],p['right']))) for p in conflicts['pairs']}
    assert pairs=={tuple(sorted((a['trait_id'],b['trait_id']))) for a,b in combinations(checked,2)}
    assert {t['trait_id'] for t in final}==good-blocked-dup
    return dict(passed=True,input_unchanged=True,original_algorithm_unchanged=True,all_A_turns_labeled=True,no_Qwen_archive_or_scoring=True,request_counts=dict(counts),requests=len(starts),returned_usage=dict(usage),unknown_billing_attempts=sum(bool(r.get('billing_unknown')) for r in ends.values()),v2_extraction_candidates=original_count,after_subject_stability_gate=retained_count,proposed_traits=len(proposed),after_final_gate=len(checked),conflict_quarantine=len(blocked),final_traits=len(final),final_pair_coverage_complete=True)


def report(folder):
    verification=verify(folder);inputs=load(folder/'inputs.json');atoms=load(folder/'archive_atoms.json');traits=load(folder/'stable_traits.json')
    results={};details={}
    for method in ('elara','direct'):
        obj=validate_judgment(load(folder/f'judgment_{method}_sol.json'),atoms,inputs,method,traits)
        byatom={d['atom_id']:d for d in obj['judgments']};parents=[]
        for p in atoms['items']:
            rels=[byatom[a['atom_id']]['relation'] for a in p['atoms']]
            parents.append(dict(archive_id=p['archive_id'],statement=p['statement'],relation=compound_relation(rels),partly_supported=any(r in ('supported','mixed') for r in rels) and not all(r in ('supported','mixed') for r in rels)))
        results[method]=dict(atomic=summary([d['relation'] for d in obj['judgments']]),whole_archive=summary([p['relation'] for p in parents]),partially_supported_items=sum(p['partly_supported'] for p in parents),trait_quality_issues=len(obj['trait_quality_issues']))
        details[method]=dict(parents=parents,atomic_judgments=obj['judgments'])
    quality=load(folder/'judgment_elara_sol.json')['trait_quality_issues']
    blocked={q['trait_id'] for q in quality}
    vetted=[t for t in traits['traits'] if t['trait_id'] not in blocked]
    freeze(folder/'validated_stable_traits.json',dict(traits=vetted,quarantined_ids=sorted(blocked),quality_issues=quality,validation_model='gpt-6.1-sol',reasoning_effort='high',policy='Whole problematic trait excluded; no rewriting or replacing a rejected trait with a weaker fact during scoring',raw_Qwen_traits_file='stable_traits.json'))
    verification['Sol_quality_quarantined_traits']=len(blocked)
    verification['validated_stable_traits']=len(vetted)
    out=dict(verification=verification,judge_model='gpt-6.1-sol',reasoning_effort='high',results=results,posthoc_improvement=True,old_scores_not_comparable=True,notes='Direct scoring model changed by user request; extraction and direct use different compute. Single B, not an identity accuracy evaluation. Sol judgments are model annotations, not human gold.')
    freeze(folder/'results.json',out);freeze(folder/'judgments_by_granularity.json',details)
    freeze(folder/'verification.json',verification)
    lines=['# 主体与稳定性约束改进实验','', '同一个 B=HS，全部20段、300条A发言。显式A says标记，不虚构B轮次。原算法和上一轮结果保留。','',f"候选数 {verification['v2_extraction_candidates']} → 主体/蕴含/稳定性准入后 {verification['after_subject_stability_gate']} → 合并提案 {verification['proposed_traits']} → Qwen复核后 {verification['final_traits']} → Sol质量复核隔离 {len(blocked)} 条，最终可用特征 {len(vetted)} 条。",'', '全部Qwen调用只用于抽取、准入核验、合并与冲突检测，不接触档案。档案拆分、ELARA语义评分和direct直接分析使用原生 gpt-6.1-sol / high 子代理。问题特征整条隔离，不在评分时改写成较弱的正确命题补分。最终可用特征见 validated_stable_traits.json，原始Qwen输出保留于 stable_traits.json。','', '| 条件 | 原子支持/矛盾/混合/不足 | 原子覆盖率 | 原子支持分 | 完整档案支持/矛盾/混合/不足 | 完整档案支持分 |','|---|---|---:|---:|---|---:|']
    for method,r in results.items():
        a=r['atomic'];b=r['whole_archive'];fmt=lambda x:'/'.join(str(x['counts'][k]) for k in ('supported','contradicted','mixed','insufficient'))
        lines.append(f"| {method} | {fmt(a)} | {a['coverage']:.1%} | {a['full_denominator_support_score']:.2f} | {fmt(b)} | {b['full_denominator_support_score']:.2f} |")
    lines+=['','支持分=100×(支持+0.5×混合)/该粒度全部条目，证据不足不是矛盾。完整复合档案必须全部原子得到支持；部分支持单列，不能当作整体支持。所有分数均为模型证据判断的代码汇总，不能称作身份识别准确率。','','本轮是针对已观察错误的事后改进，且direct评分模型由Qwen改为Sol，不能与上一轮55/30直接比较，也不能用同一个B证明泛化提升。未做人工金标准或统计显著性检验。','','## 按档案条目核对','']
    for method,data in details.items():
        lines+=['',f'### {method}','']
        for p in data['parents']:lines.append(f"- {p['archive_id']}：{p['relation']}，部分支持={p['partly_supported']}。{p['statement']}")
    lines+=['','## 质量与来源','',f"Sol报告的ELARA特征质量问题数：{results['elara']['trait_quality_issues']}。见 judgment_elara_sol.json；全部逐原子理由与原文引用在两个 judgment_*_sol.json。",'', '稳定特征及其来源见 stable_traits.json；每条候选准入/拒绝见 gates/；最终独立核验见 final_gate.json；全量配对兼容性与隔离记录见 conflicts.json。', '',f"Qwen请求尝试 {verification['requests']} 次；返回usage：{verification['returned_usage']}；计费未知传输失败 {verification['unknown_billing_attempts']} 次。不估算费用。",'', 'verification.json核验输入、说话人标记、无档案泄漏、原算法未改、所有最终引用均来自准入项、完整配对检查和排除不确定/冲突。引用和结构验证不保证模型语义判断完全正确。']
    (folder/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,default=OUT);report(p.parse_args().folder)
