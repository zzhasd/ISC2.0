import csv,json,hashlib
from pathlib import Path
from collections import Counter,defaultdict
import agd_eval as a

ROOT=Path(__file__).resolve().parent;W=ROOT/'scored_eval';OUT=W/'results'
def csvwrite(name,rows):
    if not rows:return
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def main():
    data=a.read(W/'data.json');summary=a.read(OUT/'summary.json')
    dr=list(csv.DictReader((OUT/'per_dialogue.csv').open(encoding='utf-8-sig')))
    totals={m:Counter() for m in a.METHODS}
    for r in dr:
        for k,v in r.items():
            if k not in ('dialogue_id','algorithm'):totals[r['algorithm']][k]+=int(v)
    mainrows=[]
    for m,name in a.METHODS.items():
        r=summary[m];s=totals[m]
        r['counts']=dict(s)
        mainrows.append(dict(algorithm=name,P_raw=r['P_raw'],R_full=r['R_full'],R_E1=r['R_E1_full'],R_E2=r['R_E2_full'],slot_coverage=r['slot_coverage'],useful_yield=r['useful_yield'],P_atom=r['P_atom'],R_core=r['R_core'],F1=r['F1_raw_full'],novel_per_100=r['valid_novel_per_100_dialogues'],duplicate_rate=r['semantic_redundant_valid_rate'],precision_at_least_90=int(r['P_raw']>=.9),CI95_low=r['R_full_CI95_dialogue_bootstrap'][0],CI95_high=r['R_full_CI95_dialogue_bootstrap'][1]))
    a.dump(OUT/'summary.json',summary);csvwrite('six_algorithm_metrics.csv',mainrows)
    csvwrite('aggregate_counts.csv',[dict(algorithm=a.METHODS[m],**dict(s)) for m,s in totals.items()])
    pairs=a.read(OUT/'paired_differences_CI95.json')
    csvwrite('paired_differences_CI95.csv',[dict(comparison=k,delta_R_full_CI95_low=v[0],delta_R_full_CI95_high=v[1],interval_excludes_zero=int(v[0]>0 or v[1]<0),multiple_comparisons_adjusted=0) for k,v in pairs.items()])
    reviews=[];transitions=Counter();diag={m:Counter() for m in a.METHODS};slots=[]
    for did,d in data['dialogues'].items():
        pred=a.read(a.path_for(W,'pred',did));gold=a.read(a.path_for(W,'gold',did));pool=a.read(a.path_for(W,'pool',did))
        pc={x['id']:x for x in pred['items']};gc={x['id']:x for x in gold['items']}
        for ref in d['references']:
            item=gc['g_'+ref['id']];new='|'.join(x['label'] for x in item['atoms']);transitions[(ref['old_level'],new)]+=1
            if any(x['label']!=ref['old_level'] for x in item['atoms']):
                reviews.append(dict(dialogue_id=did,source='reference_change',id=item['id'],claim=ref['claim'],old_level=ref['old_level'],new_labels=new,atoms=json.dumps(item['atoms'],ensure_ascii=False),human_decision='',human_notes=''))
        for source in ['pred','gold','sweep_support']:
            for item in a.read(a.path_for(W,source,did))['items']:
                if any(x['label']=='UNCERTAIN' for x in item['atoms']):reviews.append(dict(dialogue_id=did,source='UNCERTAIN',id=item['id'],claim='',old_level='',new_labels='|'.join(x['label'] for x in item['atoms']),atoms=json.dumps(item['atoms'],ensure_ascii=False),human_decision='',human_notes=''))
        for m in a.METHODS:
            raws=[p for p in d['predictions'] if p['algorithm']==m]
            aids={p['candidate_id']+'::'+str(i) for p in raws for i,x in enumerate(pc[p['candidate_id']]['atoms']) if x['label'] in a.VALID}
            for f in pool['facts']:
                covered={sid for member in f['members'] if member['atom_id'] in aids for sid in member['slot_ids']}
                core={s['id'] for s in f['slots'] if s['core']};corehit=core.issubset(covered)
                if not corehit:diag[m]['missing_core_facts']+=1
                for s in f['slots']:
                    slots.append(dict(dialogue_id=did,algorithm=m,fact_id=f['id'],slot_id=s['id'],name=s['name'],value=s['value'],core=int(s['core']),required=int(s['required']),weight=s['weight'],judge_required=int(s.get('judge_required',s['required'])),judge_weight=s.get('judge_weight',s['weight']),hit=int(s['id'] in covered)))
                    if corehit and s['required'] and s['id'] not in covered:diag[m]['missing_slot_'+s['name']]+=1
            for p in raws:
                for atom in pc[p['candidate_id']]['atoms']:
                    if atom['label'] not in a.VALID:diag[m]['atom_label_'+atom['label']]+=1
            diag[m]['grounded_redundant_predictions']=totals[m]['semantic_redundant_valid']
    csvwrite('per_slot.csv',slots);csvwrite('human_review_queue.csv',reviews)
    csvwrite('reference_label_transitions.csv',[dict(old_level=k[0],new_labels=k[1],count=v) for k,v in sorted(transitions.items())])
    allkeys=sorted({k for c in diag.values() for k in c})
    csvwrite('diagnostics.csv',[dict(error_type=k,**{a.METHODS[m]:diag[m][k] for m in a.METHODS}) for k in allkeys])
    usage=Counter();attempts=0;valid=0;unknown_billing=0
    for line in (ROOT/'attempts.jsonl').read_text(encoding='utf8').splitlines():
        row=json.loads(line);attempts+=1;valid+=bool(row.get('valid'))
        unknown_billing+=int('usage' not in row)
        for key in ['prompt_tokens','completion_tokens','total_tokens']:usage[key]+=row.get('usage',{}).get(key,0)
    a.dump(OUT/'evaluation_usage.json',dict(attempts=attempts,valid_attempts=valid,attempts_without_returned_usage=unknown_billing,tokens=dict(usage),probe_usage={'prompt_tokens':751,'completion_tokens':812,'total_tokens':1563},interrupted_pilot_requests='Additional pilot requests were in flight during two process interruptions; billing is unknown.',note='Evaluation only, including pilots and retries with returned usage. Monetary fee not inferred.'))
    hashes=a.read(ROOT/'source_manifest.json');changes=[]
    for rel,h in hashes.items():
        p=ROOT.parent/rel
        if hashlib.sha256(p.read_bytes()).hexdigest()!=h:changes.append(rel)
    assert not changes,changes
    a.dump(OUT/'verification.json',dict(original_inputs_unchanged=True,dialogues=len(data['dialogues']),predictions=sum(data['prediction_counts'].values()),all_methods_shared_denominator=len(set(x['denom_pool'] for x in summary.values()))==1,human_review_complete=False,human_queue_rows=len(reviews)))
    text=['# AGD-Eval 六算法自动评价','',f'冻结 298 段 A-only 对话、7,868 条原始预测（6,915 条去重文本）、588 条旧参考。评价模型 `{a.MODEL_DEFAULT}`。','', '本表为自动审核结果，人工校准尚未完成。UNCERTAIN 按未证实处理，并进入复核队列。所有比例均由 Python 汇总分子分母后计算。','', '|算法|P_raw|R_full|E1 Recall|E2 Recall|Slot Coverage|Useful Yield|','|---|---:|---:|---:|---:|---:|---:|']
    for r in mainrows:text.append('|'+r['algorithm']+'|'+'|'.join(f'{r[k]:.2%}' if r[k] is not None else 'NA' for k in ['P_raw','R_full','R_E1','R_E2','slot_coverage','useful_yield'])+'|')
    eligible=[r for r in mainrows if r['precision_at_least_90']]
    text+=['', ('P_raw ≥ 90% 的算法：'+', '.join(r['algorithm'] for r in eligible)) if eligible else '没有算法达到预先指定的 P_raw ≥ 90% 要求。不能据此报告 Recall@90% Precision，也未使用测试审核标签筛选输出。', '', 'R_full 的 95% 区间及两两差值采用对话配对 bootstrap，2,000 次，种子 20261106。区间只描述对话采样不确定性，不涵盖模型裁定误差。共享池召回率是池内召回率，仍可能遗漏所有来源共同未发现的事实。', '', '原参考外新发现：旧参考已通过审核的原子命题共同覆盖不了该事实核心。重复率：完全有据且在原输出顺序中没有新增任何事实字段的预测数 / 原始预测数。F1 为原始预测准确率和共享池完整召回率的混合指标。', '', '失误诊断中 missing_core 为事实数，missing_slot 为缺失字段数，atom_label 为原始输出加权的原子断言数。不同类别可重叠。事件状态错误与 E2 证据不足未另行调用模型分类，不能仅凭 E3 标签精确推断原因。', '', '判定请求仅包含 A 可见话轮和盲化候选。未向模型发送算法身份、旧标签、旧理由、隐藏 B 话语或历史匹配结果。原始输入哈希复核通过，既有实验数据未修改。', '', '文件：six_algorithm_metrics.csv 主表；aggregate_counts.csv 分子分母；per_prediction.csv、per_fact.csv、per_slot.csv 明细；human_review_queue.csv 人工队列；evaluation_usage.json 评价费用的 token 记录。']
    text+=['','字段完整度规则在产生任何正式分数前统一确定：全部规范事实字段均 required=true，核心字段权重 2，其余字段权重 1。原模型可选标志和权重保留在 judge_required / judge_weight 中，原始模型文件保留在 final_eval。','', '先导检查使用三段对话后收紧了空泛对话状态与弱推测边界，并重新审核全部 298 段。先导结果不混入正式分数。配对差值区间未做多重比较校正，不能将其视为对所有比较同时控制的显著性结论。']
    (OUT/'REPORT.md').write_text('\n'.join(text),encoding='utf8')
    print('\n'.join(text[:16]))

if __name__=='__main__':main()
