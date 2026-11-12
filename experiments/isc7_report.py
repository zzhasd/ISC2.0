"""Reproducible reporting and frozen-input integrity checks for ISC7."""
import hashlib
import json
from pathlib import Path
from isc4_open import ROOT,read,save,sha,visible
from isc7_run import OUT,DATA,ARMS,records


def main():
    s=read(OUT/'summary.json');m=read(DATA/'manifest.json');ds=read(DATA/'dialogues.json');by={d['id']:d for d in ds}
    plans={p:read(OUT/p/'requests.json') for p in ['initial','dependent']}
    audit=read(OUT/'execution_audit.json');ps=read(OUT/'predictions.json');review=read(OUT/'semantic_review.json')
    checks={'original_32_intact_dialogues':ds==read(ROOT/'data/isc4/dialogues.json'),
        'initial_requests_frozen':sha(plans['initial'])==m['initial_requests_sha256'],
        'reference_frozen':sha(read(DATA/'reference.json'))==m['reference_sha256'],
        'protocol_frozen':hashlib.sha256((ROOT/'ISC7_PROTOCOL.md').read_bytes()).hexdigest()==m['protocol_sha256'],
        'inference_module_frozen':hashlib.sha256((ROOT/'experiments/isc7_module.py').read_bytes()).hexdigest()==m['module_sha256'],
        'runner_frozen':hashlib.sha256((ROOT/'experiments/isc7_run.py').read_bytes()).hexdigest()==m['runner_sha256'],
        'old_sources_unchanged':all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in m['old_source_hashes'].items()),
        'unique_calls_within_256_cap':len(audit)<=256 and len({a['task_id'] for a in audit})==len(audit),
        'all_returned_model_correct':all(a['returned_model']=='qwen3.8-flash' for a in audit),
        'all_http_200':all(a['http_status']==200 for a in audit),
        'phases_complete':all(read(OUT/p/'run_status.json')['complete'] for p in plans),
        'on_responses_have_reasoning':all(a['reasoning_chars']>0 and (a['reasoning_tokens'] or 0)>0 for a in audit if a['arm'].endswith('_on')),
        'off_responses_no_reasoning':all(a['reasoning_chars']==0 for a in audit if a['arm'].endswith('_off'))}
    initial={t['task_id']:t for t in plans['initial']}
    for phase,tasks in plans.items():
        for t in tasks:
            p=t['payload'];content=json.loads(p['messages'][1]['content'])
            assert content['visible_A']==visible(by[t['dialogue_id']])
            assert set(content)==({'visible_A'} if phase=='initial' else {'visible_A','candidates'})
            assert p['enable_thinking']==t['arm'].endswith('_on')
            if p['enable_thinking']:assert p['thinking_budget']==2048
            else:assert 'thinking_budget' not in p
            if phase=='dependent':
                assert len(t['source_task_ids'])==2
                assert {initial[x]['stage'] for x in t['source_task_ids']}=={'global','local'}
                assert all(initial[x]['dialogue_id']==t['dialogue_id'] and initial[x]['arm']==t['arm'] for x in t['source_task_ids'])
    checks['A_only_observation_and_correct_factor']=True
    raw_ids={r['task_id'] for phase in plans for r in records(phase)}
    checks['export_covers_all_recorded_calls']=raw_ids=={r['task_id'] for r in audit}
    reference_ids={f['id'] for d in read(DATA/'reference.json') for f in d['facts']}
    checks['review_reference_ids_exist']=all(set(r['reference_ids']+r['partial_reference_ids'])<=reference_ids for r in review)
    from isc7_analyze import review_key
    checks['all_final_assertions_reviewed']={r['review_id'] for r in review}=={review_key(p['dialogue_id'],f) for p in ps for f in p['facts']}
    assert all(checks.values()),checks
    save(OUT/'final_checks.json',checks)
    n=len(s['common_ids']);den=s['methods'][0]['A_reference_count'];labels={'direct_off':'直接提取，thinking关','direct_on':'直接提取，thinking开','dual_off':'双路＋判别，thinking关','dual_on':'双路＋判别，thinking开'}
    lines=['# ISC7：流程 × thinking 的 2×2 实际实验','',
        '2026-11-01，Asia/Shanghai。原32段完整自然对话的配对开发诊断；未训练权重。所有四组本轮重新调用，未使用历史输出充当基线。','',
        '## 主要发现','',
        '本轮双路＋thinking的严格覆盖最高：41/43（95.3%），直接关闭thinking为28/43（65.1%）。增加13条，其中6条来自医疗高密度对话，其余7条分散在另外6段。这个结果支持把该配置作为高召回候选生成器继续验证，还不能把它当作可靠事实的自动输出器。',
        '', '代价很明显：原始断言从49条增至130条，A依据不足/未决从15条增至56条，占输出断言的比例从30.6%升至43.1%；平均tokens约为基线7.8倍。较高覆盖伴随更宽的输出，不能称为整体准确率达到95.3%。逐项判别仍会接受超出证据的解释。',
        '', '直接开启thinking或单独双路流程，各增加5条覆盖；去掉医疗病例后分别仅净增1条和0条。组合配置相对直接开启、双路关闭各增加8条，去掉医疗病例后分别仍增加6条和7条。两因素交互仅为每段+0.097条，95%探索区间[-0.194, 0.387]跨零，尚不能确认稳定的超加性互补。',
        '', '建议保留直接关闭thinking作低成本对照，将双路＋thinking定位为候选发现阶段；下一步优先检验接纳条件是否能压低无依据输出，在未看过的新对话上比较相同可靠性水平下的覆盖。进一步增加自由推理或重复自我验证，不是本轮已经证明有效的解决办法。',
        '',
        '## 执行与有效性','',
        f"计划256次请求，实际{s['actual_calls']}次，累计{s['actual_tokens']:,} tokens。全部已记录请求HTTP 200，返回模型均为qwen3.8-flash。开启组响应中核实了思考文本与reasoning token用量；关闭组未返回思考文本。",
        '', '直接流程每段1次；双路流程每段两次互不看对方答案的候选提取，再逐项判别1次。on组每次thinking_budget=2048；所有调用temperature=0、max_tokens=4096。每个阶段使用独立上下文，没有传递历史思考文本。',
        '', '双路两次提取都读取完整A，分别关注全局关系和局部细节。确定性程序只检查标签、引用、候选ID与输出接纳条件；语义支持另由当前助手逐条复核。没有人工挑选某次输出或修复后静默重跑。',
        '', '| 组别 | 有效最终结果 | 实际调用 | 实际总tokens（含失败路径） | 返回思考内容的调用 |', '| --- | ---: | ---: | ---: | ---: |']
    for r in s['methods']:lines.append(f"| {labels[r['arm']]} | {r['valid']}/32 | {r['actual_calls_all_planned']} | {r['total_tokens_all_planned']:,} | {r['reasoning_response_calls']} |")
    errors=read(OUT/'validation_errors.json');sources=read(OUT/'dependent/source_errors.json')
    lines+=['','结构失败详情：'+json.dumps(errors,ensure_ascii=False)+'。依赖源失败：'+json.dumps(sources,ensure_ascii=False)+'。失败保留为缺失，不伪装成零事实。','',
        '## 四组共同有效样本的恢复与可靠性','',f'共同有效{n}段；完整参考共{s["methods"][0]["full_reference_count"]}条，其中{den}条暂定A可支持。以下所有组使用相同分母。', '',
        '| 组别 | 严格原子覆盖 | 原一对一覆盖 | 原始断言 | A依据不足/未决 | 范围外 | 源文明确冲突 |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in s['methods']:
        lines.append(f"| {labels[r['arm']]} | {r['atomic_coverage']}/{den}（{r['atomic_coverage']/den:.1%}） | {r['legacy_strict']}/{den} | {r['raw_claims']} | {r['A_unsupported_or_uncertain']} | {r['out_of_scope']} | {r['source_contradicted']} |")
    lines+=['', '原子覆盖对复合句中的独立属性分别审核，同一参考去重。混合句可以保留有依据的独立原子，同时将额外无依据内容记入问题断言；带错误时间/剂量的同一谓词不能删掉限定后冒充严格命中。原一对一列更接近历史口径，但受每行容纳几个事实影响。',
        '', 'A依据不足/未决、范围外与源文冲突列可能重叠，不能相加。没有A依据不等于隐藏源文必假；较粗部分匹配和参考外新发现也不当作严格参考命中。原始断言和支持行含冗余，不能用它们直接表示去重信息量。',
        '', '## 配对效应与交互','', '| 对比 | 净增加参考数 | 每段平均增加 | 探索性95%区间 | 去掉医疗病例后的每段增量 |', '| --- | ---: | ---: | --- | ---: |']
    effect_labels={'thinking_in_direct':'直接：开−关','thinking_in_dual':'双路：开−关','pipeline_without_thinking':'关：双路−直接','pipeline_with_thinking':'开：双路−直接','interaction':'交互：(双路开−关)−(直接开−关)'}
    for e in s['effects']:
        b=e['per_dialogue'];w=e['without_medical']
        lines.append(f"| {effect_labels[e['name']]} | {e['net_reference_count']:+d} | {b['mean']:+.3f} | [{b['low']:.3f}, {b['high']:.3f}] | {w['mean']:+.3f} |")
    lines+=['', '区间按对话聚类bootstrap（3000次固定种子）。同时检查多个对比，没有作确认性多重检验；不把单个区间排除零解释为总体泛化已证明。排除确认式问句/身份锚定争议标签的结果保存在summary.json。',
        '', '## 实际计算成本','', '| 组别 | 平均tokens/段 | 其中思考tokens | 调用耗时合计/秒 | 估算并行关键路径/秒 |', '| --- | ---: | ---: | ---: | ---: |']
    for r in s['methods']:
        lines.append(f"| {labels[r['arm']]} | {r['mean_total_tokens']:.0f} | {r['mean_reasoning_tokens']:.0f} | {r['mean_latency_sum']:.2f} | {r['mean_latency_critical_path']:.2f} |")
    lines+=['', '思考token是completion tokens中的子集，不再加到total tokens中。关闭模式未提供reasoning_tokens时，根据无思考文本和关闭设置作0显示。关键路径按max(全局,局部)+判别估算，未包括批量调度等待，并非在线实测端到端延迟。三次调用流程和thinking开启都增加预算，不能将收益全部归因于算法结构。',
        '', '## 解释边界与复现','',
        '原32段及其错误已用于设计，参考和复核由同一看过完整A+B的助手完成。没有独立人类gold、封存新样本或多随机种子重复。该实验只能诊断当前预算和提示下的收益/成本，不能得出云端Qwen全部thinking设置的结论。下一步若选择某配置，需冻结它后再用从未观察的新对话评价。',
        '', '审计记录：完成统计时发现此前243条审核快照早于最终导出，导致完整性检查停止。该快照及其清单保留为semantic_review_partial_243*；补齐到341条时，原243条判断逐字未改。冻结条件已增加原始响应与导出记录一致性检查；本次统计使用全部341条审核，未重新调用模型。',
        '', '协议ISC7_PROTOCOL.md；实现experiments/isc7_module.py与isc7_run.py；完整请求/响应、候选、审核、统计均保存在results/isc7。凭证只用于运行时认证，不写入这些产物。',
        '', '```powershell','python experiments/isc7_run.py export','python experiments/isc7_analyze.py prepare','python experiments/isc7_adjudicate.py','python experiments/isc7_analyze.py analyze','python experiments/isc7_report.py','python -m unittest discover -s experiments -p test_isc7.py -v','```','']
    (OUT/'实验报告.md').write_text('\n'.join(lines),encoding='utf-8')
    save(OUT/'final_manifest.json',{'status':'completed exploratory 2x2','summary_sha256':sha(s),'checks_sha256':sha(checks),'review_sha256':sha(review),'inference_manifest':m})
    print({'checks_passed':len(checks),'report_written':True})


if __name__=='__main__':main()
