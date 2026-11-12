"""Combine post-hoc machine screening and separately fixed assistant review.
Never rewrites extraction, linkage predictions, gold, or original scores.
"""
from collections import Counter
import csv
import hashlib
import json
import re
from .core import digest, load, save
from .subject_audit import OUT, PILOT, STRICT, validate


def write_csv(path,rows):
    if not rows:return
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def summarize():
    cases=load(OUT/'cases.json')
    manifest=load(OUT/'manifest.json')
    assert digest(cases)==manifest['input_digest']
    assert hashlib.sha256((PILOT/'inputs.json').read_bytes()).hexdigest()==manifest['source_inputs_sha256']
    for name,sha in manifest['source_attribute_sha256'].items():
        assert hashlib.sha256((PILOT/'attributes'/name).read_bytes()).hexdigest()==sha
    gold={g['group_id']:g for g in load(PILOT/'gold.json')}
    review=load(OUT/'assistant_review_conservative_v2.json')
    reviewed={(r['case_id'],r['claim_id']):r for r in review['rows']}
    originals={}
    rows=[];reason_mentions=[];missing=[]
    for case in cases:
        cid=case['case_id'];meta=gold[case['group_id']]
        source=load(PILOT/'attributes'/f'{cid}.json')
        original_claims=source['prediction']['claims']
        originals[cid]=source
        judges={a['candidate_id']:a['auditor'] for a in source['audit']['candidates']}
        path=OUT/'decisions'/f'{cid}.json'
        if not path.exists():missing.append(cid);continue
        decisions=load(path)
        validate(dict(decisions=decisions['decisions']),case)
        by_id={d['claim_id']:d for d in decisions['decisions']}
        for index,c in enumerate(case['candidates']):
            d=by_id[c['claim_id']];orig=original_claims[index]
            origjudge=judges[orig['candidate_id']]
            claim_flag=d['claim_label'] in STRICT
            attr_flag=d['attribute_label'] in STRICT
            r=reviewed.get((cid,c['claim_id']))
            row=dict(case_id=cid,group_id=case['group_id'],setting=meta['setting'],true_k=meta['true_k'],dialogue=case['dialogue'],
                     claim_id=c['claim_id'],original_candidate_id=orig['candidate_id'],claim=c['claim'],attribute=c['attribute'],
                     original_verdict=orig['audit_verdict'],original_evidence_level=orig['audited_evidence_level'],
                     original_sources='|'.join(orig['sources']),original_audit_reason=origjudge['reason'],
                     machine_claim_label=d['claim_label'],machine_attribute_label=d['attribute_label'],
                     machine_strict_flag=claim_flag or attr_flag,
                     machine_a_to_b='A_TO_B' in {d['claim_label'],d['attribute_label']},
                     machine_turn_id=d['turn_id'],machine_quote=d['quote'],machine_reason=d['reason'],
                     assistant_reviewed=r is not None,
                     assistant_confirmed_strict=(r['strict_transfer_confirmed'] if r else ''),
                     assistant_claim_label=(r['review'].get('claim_label','') if r else ''),
                     assistant_attribute_label=(r['review'].get('attribute_label','') if r else ''),
                     assistant_turn_id=(r['review'].get('turn_id','') if r else ''),
                     assistant_quote=(r['review'].get('quote','') if r else ''),
                     assistant_reason=(r['review'].get('reason',r['review'].get('note','')) if r else ''))
            rows.append(row)
            # This string pattern documents explicit role wording, not semantic correctness.
            matches=re.findall(r"\bB(?:'s|’s)\s+(?:turn\s+\d+|(?:response|reply|statement)\s+(?:in|at)\s+turn\s+\d+)",origjudge['reason'],flags=re.I)
            if matches:reason_mentions.append(dict(case_id=cid,claim_id=c['claim_id'],matches=matches,reason=origjudge['reason']))
    if missing:raise ValueError('Incomplete screening: '+str(missing))
    assert len(rows)==3195
    def counts(sub):
        strict=[r for r in sub if r['machine_strict_flag']]
        a2b=[r for r in sub if r['machine_a_to_b']]
        return dict(claims=len(sub),dialogues=len({r['case_id'] for r in sub}),groups=len({r['group_id'] for r in sub}),
                    strict_flagged_claims=len(strict),strict_flagged_dialogues=len({r['case_id'] for r in strict}),strict_flagged_groups=len({r['group_id'] for r in strict}),
                    a_to_b_flagged_claims=len(a2b),a_to_b_flagged_dialogues=len({r['case_id'] for r in a2b}),
                    strict_flagged_original_supported=sum(r['original_verdict']=='supported' for r in strict),
                    strict_flagged_original_supported_e1_e2=sum(r['original_verdict']=='supported' and r['original_evidence_level'] in ('E1','E2') for r in strict),
                    strict_flagged_original_levels=dict(Counter(r['original_evidence_level'] for r in strict)),
                    strict_claim_field=sum(r['machine_claim_label'] in STRICT for r in sub),
                    strict_attribute_field=sum(r['machine_attribute_label'] in STRICT for r in sub),
                    strict_attribute_only=sum(r['machine_claim_label'] not in STRICT and r['machine_attribute_label'] in STRICT for r in sub),
                    claim_label_counts=dict(Counter(r['machine_claim_label'] for r in sub)),
                    attribute_label_counts=dict(Counter(r['machine_attribute_label'] for r in sub)))
    confirmed=[r for r in rows if r['assistant_confirmed_strict'] is True]
    sampled=[r for r in rows if r['assistant_reviewed']]
    confirmed_a2b=[r for r in confirmed if 'A_TO_B' in {r['assistant_claim_label'],r['assistant_attribute_label']}]
    manual=dict(sampled_dialogues=len({r['case_id'] for r in sampled}),sampled_claims=len(sampled),
                confirmed_strict_claims=len(confirmed),confirmed_strict_dialogues=len({r['case_id'] for r in confirmed}),
                confirmed_a_to_b_claims=len(confirmed_a2b),confirmed_a_to_b_dialogues=len({r['case_id'] for r in confirmed_a2b}),
                confirmed_original_supported=sum(r['original_verdict']=='supported' for r in confirmed),
                confirmed_original_supported_e1_e2=sum(r['original_verdict']=='supported' and r['original_evidence_level'] in ('E1','E2') for r in confirmed),
                confirmed_original_levels=dict(Counter(r['original_evidence_level'] for r in confirmed)),
                confirmed_detected_by_screening=sum(r['machine_strict_flag'] for r in confirmed),
                screening_flagged_but_not_assistant_confirmed=sum(r['machine_strict_flag'] and not r['assistant_confirmed_strict'] for r in sampled),
                not_human_gold=True,not_confirmed_does_not_mean_correct=True)
    all_flagged={(r['case_id'],r['claim_id']) for r in rows if r['machine_strict_flag']}
    confirmed_keys={(r['case_id'],r['claim_id']) for r in confirmed}
    links=[]
    for meta in gold.values():
        p=load(PILOT/'predictions'/f"{meta['group_id']}_elara.json")
        for link in p['prediction']['merge_evidence']:
            refs={(meta['group_id']+'_'+ref['dialogue'],ref['claim_id']) for ref in link['references']}
            links.append(dict(group_id=meta['group_id'],setting=meta['setting'],true_k=meta['true_k'],left=link['left'],right=link['right'],
                              machine_flagged_references=[list(x) for x in sorted(refs & all_flagged)],
                              assistant_confirmed_references=[list(x) for x in sorted(refs & confirmed_keys)],
                              reason=link['reason']))
    summary=dict(automatic_screening_complete=True,automatic_screening=counts(rows),
                 by_setting={s:counts([r for r in rows if r['setting']==s]) for s in ('same_a','different_a')},
                 by_setting_k={f'{s}/K={k}':counts([r for r in rows if r['setting']==s and r['true_k']==k]) for s in ('same_a','different_a') for k in range(1,11)},
                 assistant_review=manual,
                 assistant_review_by_setting={s:dict(sampled_claims=sum(r['setting']==s for r in sampled),
                                                   confirmed_strict_claims=sum(r['setting']==s for r in confirmed),
                                                   confirmed_strict_dialogues=len({r['case_id'] for r in confirmed if r['setting']==s}),
                                                   confirmed_a_to_b_claims=sum(r['setting']==s for r in confirmed_a2b)) for s in ('same_a','different_a')},
                 old_audit_literal_b_turn_mentions=len(reason_mentions),
                 linkage_merge_edges=len(links),linkage_edges_with_machine_flagged_reference=sum(bool(l['machine_flagged_references']) for l in links),
                 linkage_edges_with_assistant_confirmed_reference=sum(bool(l['assistant_confirmed_references']) for l in links),
                 original_inputs_and_extractions_unchanged=True,
                 caveats=['All full-corpus flags are Qwen judgments, not human gold.',
                          'The assistant reviewed 20 randomly chosen dialogues, one per group, before reading automatic labels.',
                          'Assistant labels are conservative lower-bound confirmations in that sample, not human annotations.',
                          'Counts are original output rows; semantic duplicates are counted separately.',
                          'No extrapolated exact full-corpus error rate and no causal claim about clustering performance.',
                          'Primary audit uses only A-only text; hidden B utterances/persona were not used.'])
    save(OUT/'summary.json',summary)
    write_csv(OUT/'all_claims_screening.csv',rows)
    write_csv(OUT/'assistant_review_349.csv',sampled)
    write_csv(OUT/'assistant_confirmed_errors.csv',confirmed)
    save(OUT/'original_audit_role_wording.json',reason_mentions)
    save(OUT/'linkage_evidence_overlap.json',links)
    save(OUT/'all_claims_screening.json',rows)
    write_report(summary,rows,confirmed)
    save(OUT/'status.json',dict(total=200,complete=200,failures=[],schema_format_recovery=load(OUT/'format_recovery.json') if (OUT/'format_recovery.json').exists() else None))
    print(json.dumps(dict(automatic=summary['automatic_screening'],assistant_review=manual,by_setting=summary['by_setting'],
                         old_audit_role_wording=len(reason_mentions),link_edges=len(links),link_edges_with_screened_error=summary['linkage_edges_with_machine_flagged_reference'],
                         link_edges_with_assistant_error=summary['linkage_edges_with_assistant_confirmed_reference']),ensure_ascii=False))


def write_report(s,rows,confirmed):
    a=s['automatic_screening'];r=s['assistant_review']
    pct=lambda n,d:f'{n/d:.1%}' if d else 'NA'
    lines=['# 主体归属专项审计','',
           '结论：本次输出中存在跨测试组的反复主体误归，不能视为两个孤立例子。全量自动筛查和助手逐条复核应分别看待。原始预测、人数误差和聚类指标均未更改。','',
           '## 固定随机样本逐条复核（主结论）','',
           f"在每个测试组均匀抽一段，共 {r['sampled_dialogues']} 段、{r['sampled_claims']} 条；由本助手逐条阅读全部 A 侧上下文、claim 和 attribute，复核时未查看自动筛查标签。",'',
           f"- 保守确认主体/说话行为误归 {r['confirmed_strict_claims']}/{r['sampled_claims']}（{pct(r['confirmed_strict_claims'],r['sampled_claims'])}），涉及 {r['confirmed_strict_dialogues']}/20 段（{pct(r['confirmed_strict_dialogues'],20)}）。",
           f"- 其中直接 A→B 信息转移 {r['confirmed_a_to_b_claims']}/{r['sampled_claims']}（{pct(r['confirmed_a_to_b_claims'],r['sampled_claims'])}），涉及 {r['confirmed_a_to_b_dialogues']}/20 段。",
           f"- 确认误归中，原审核判 supported 的有 {r['confirmed_original_supported']} 条，其中 supported 且 E1/E2 的有 {r['confirmed_original_supported_e1_e2']} 条。",'',
           '这不是人工金标。未确认错误的条目不保证正确，可能仍有问题无答案、泛化过度、模态错误或主体歧义。18.6% 是这 349 条的保守确认比例，不是全量 3,195 条的精确错误率。按原始输出条目计数，近义重复条目仍分别计数；对话级结果可以补充判断是否反复出现。','',
           '此处的错误判断是：可见证据实际描述 A，却据此给 B 赋予相应事实，或把 A 的说话行为写成 B 的行为。它不等于断言 B 在现实中绝对不符合该事实；偶合为真不能补足 A-only 推断的证据。','',
           '| 设置 | 样本条目 | 确认误归条目 | 涉及对话（每设置抽十段） | A→B 条目 |','|---|---:|---:|---:|---:|']
    for setting,m in s['assistant_review_by_setting'].items():
        lines.append(f"| {setting} | {m['sampled_claims']} | {m['confirmed_strict_claims']} | {m['confirmed_strict_dialogues']}/10 | {m['confirmed_a_to_b_claims']} |")
    lines+=['','## 全量自动筛查（模型标签，不等于确认错误率）','',
            '模型为 qwen3.8-flash thinking，采用专门主体规则；不提供原 E1–E4 标签、审核理由、B 发言、persona 或真实 B 身份。claim 和 attribute 分开判定。严格误归只包括 A_TO_B、THIRD_TO_B 和 SPEAKER_REVERSAL；一般事实个体化、主体歧义及其他支持不足分列。','',
            f"- 全量 {a['claims']} 条、{a['dialogues']} 段、{a['groups']} 组均完成筛查。",
            f"- 严格类别标记 {a['strict_flagged_claims']}/{a['claims']}（{pct(a['strict_flagged_claims'],a['claims'])}），涉及 {a['strict_flagged_dialogues']}/200 段和 {a['strict_flagged_groups']}/20 组。",
            f"- A→B 标记 {a['a_to_b_flagged_claims']} 条，涉及 {a['a_to_b_flagged_dialogues']} 段。",
            f"- 标记严格误归中，原 supported+E1/E2 的有 {a['strict_flagged_original_supported_e1_e2']} 条。",
            f"- 只在短 attribute 字段触发严格标记、claim 未触发的有 {a['strict_attribute_only']} 条。",'',
            '| 设置 | 总条目 | 严格类别标记 | 涉及对话 | A→B 标记 |','|---|---:|---:|---:|---:|']
    for setting,m in s['by_setting'].items():
        lines.append(f"| {setting} | {m['claims']} | {m['strict_flagged_claims']} | {m['strict_flagged_dialogues']}/100 | {m['a_to_b_flagged_claims']} |")
    lines+=['',f"样本中助手确认的 {r['confirmed_strict_claims']} 条里，筛查器标记了 {r['confirmed_detected_by_screening']} 条；另外有 {r['screening_flagged_but_not_assistant_confirmed']} 条筛查标记未被助手保守确认，不能把这些未确认条目直接叫作错误或把筛查比例当真值。",'',
            '筛查器与原抽取器是同系列同模型，错误可能相关；这次是独立提示词复审，不是独立人工或跨模型验证。一段对话六次未满足输出 schema，保留失败响应后按七条候选分两批补齐；规则、完整 A 上下文及模型参数未改，增加了 ID/schema 提醒。','',
            '## 你指出的两例','']
    targets=[('c6ba18dda2b437d2bc6d_D1','c4'),('df73a6571cfbbfaf67c1_D1','c5')]
    for cid,claim_id in targets:
        row=next(r for r in rows if r['case_id']==cid and r['claim_id']==claim_id)
        lines += [f"### {row['setting']}、K={row['true_k']}、{row['dialogue']}、{claim_id}",'',f"claim：{row['claim']}",'',f"attribute：{row['attribute']}",'',f"原审核：{row['original_evidence_level']} / {row['original_verdict']}",'',f"本次机器筛查：claim={row['machine_claim_label']}，attribute={row['machine_attribute_label']}；{row['machine_reason']}",'']
    lines+=['烤红薯例的原 claim 实际为“B 提到或赞同香味好”，短 attribute 则直接写 B 欣赏香味。可见文本中后半句是 A 的喜好自述，前半句附和不足以建立 B 的这项具体喜好。大阪例是 A 的位置回答；原审核把 ですよ 强行解释为 A 确认 B 的位置，随后 A 想去参观别处也不能逆推大阪就是 B 的位置。',
            '专项筛查仍将大阪例判作 NO_SUBJECT_TRANSFER，重复了原审核的错误解释。它没有见过原审核理由，因此这进一步显示同模型的角色偏差和漏报风险；983 条只能称机器筛查标记，不能当成确证错误数。',
            '在样本复核和全部机器标签固定之后，仅对这两个既知例子另查完整 A+B 原记录作旁证：大阪前一条确实是 B 问 A“お住まいって関西ではないですよね？”，A 才回答“関西ですよ。大阪です。”；烤红薯例中，B 随后也说“いい香りしますよねー。”，说明 B 可能同样欣赏香味，但这条隐藏 B 发言不是 ELARA 当时可见的证据。旁证保存在 secondary_full_context_examples.json，未送入机器筛查、未用于随机样本标签或修改统计。','',
            '## 随机样本中的其他明确例子','',
            '| 设置/K/对话 | A 的原话 | 被归给 B 的内容 | 原审核 |','|---|---|---|---|']
    example_keys=[('36a0f7906df78c6204f8_D6','c4'),('8f3f6d0e2bc20c97f8d7_D5','c8'),('7f22565852d990bd9564_D2','c1'),('df73a6571cfbbfaf67c1_D5','c8'),('f948b39b8a6a8a0ca243_D2','c11'),('24de896ada0d15bf853a_D8','c10'),('6d0b9fc8db9f687d1397_D6','c14')]
    for cid,claim_id in example_keys:
        x=next(r for r in confirmed if r['case_id']==cid and r['claim_id']==claim_id)
        lines.append(f"| {x['setting']}/K={x['true_k']}/{x['dialogue']} | {x['assistant_quote']} | {x['claim']} | {x['original_evidence_level']}/{x['original_verdict']} |")
    lines+=['','## 机制与结果解释','',
            '可复核的模式包括：日语零主语的自述/回答被当成 B 的属性；自家亲属和持有物的领属关系被搬给 B；把 はい、ですよね、そうですね 等附和词升级为某个具体 B 事实；claim 的限定表述在 attribute 中变成更强的属性；原审核同样接受了这些主体转换。',
            f"原审核理由中有 {s['old_audit_literal_b_turn_mentions']} 条匹配到明确的 B’s turn N 或 B’s response in turn N 字样；实际所有可见行都是 A。这是角色表述混乱的附加证据，但不等于这些最终事实一定全部错误，逐条保留在 original_audit_role_wording.json。",'',
            f"原关联输出共 {s['linkage_merge_edges']} 条合并证据边，其中 {s['linkage_edges_with_machine_flagged_reference']} 条引用了自动筛查标记属性，{s['linkage_edges_with_assistant_confirmed_reference']} 条引用了本随机样本中助手确认的误归属性。未被作为合并理由引用的属性也可能影响拆分判断，因此不能由这个交集完整衡量影响。",'',
            '本次审计足以说明属性库存在反复的主体污染，不能把原实验结果仅解释为身份关联模块能力不足。它尚未证明主体污染是聚类失败的唯一原因或主要原因，也没有通过过滤重跑证明可以改善指标。本次不改变 ELARA v1、原预测或原评分。','',
            '## 文件与复现','',
            '- all_claims_screening.csv / .json：全量自动标签、原判定、引用与两字段标签。',
            '- assistant_review_349.csv：固定随机样本的全部条目；assistant_confirmed_errors.csv：65 条保守确认条目。',
            '- assistant_review_conservative_v2.json：冻结复核结果，含两个边界条目的保守排除说明；初版笔记另保留。',
            '- review_sample.json、review_packet_1..4.txt：抽样 seed、清单及不含自动标签的原文阅读包。',
            '- attempts.jsonl、decisions/、manifest.json、format_recovery.json：请求原始记录、冻结数据哈希与格式恢复记录。',
            '- secondary_full_context_examples.json：统计固定后，仅针对两个用户已指出例子的完整对话旁证。',
            '- 运行 python -B -m isc113.identity_linkage.subject_audit_report 可离线重算本报告。']
    (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':summarize()
