"""Gold-aware deterministic evaluation, separate from model inference."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import statistics
import hashlib
from .core import HERE, digest, load, metrics, save


def score(folder):
    inputs=load(folder/'inputs.json')
    gold=load(folder/'gold.json')
    sampling=load(folder/'sampling.json')
    manifest=load(folder/'inference_manifest.json')
    if digest(inputs)!=sampling['input_digest'] or digest(gold)!=sampling['gold_digest'] or digest(inputs)!=manifest['inputs_digest']:
        raise ValueError('Input/gold binding mismatch')
    rows=[]
    comparisons=[]
    missing=[]
    for g in gold:
        for method in ('elara','direct'):
            path=folder/'predictions'/f"{g['group_id']}_{method}.json"
            if not path.exists():
                missing.append(dict(group_id=g['group_id'],method=method))
                continue
            r=load(path)
            part=r['prediction']['clusters']
            labels={d:i for i,c in enumerate(part) for d in c}
            if len(labels)!=10 or sum(map(len,part))!=10:
                raise ValueError('Invalid saved partition')
            m=metrics([a['b_id'] for a in g['answers']],[labels[f'D{i}'] for i in range(1,11)])
            rows.append(dict(group_id=g['group_id'],setting=g['setting'],method=method,stratum=g['stratum'],**m))
            anonymous_gold={}
            for a in g['answers']:
                anonymous_gold.setdefault(a['b_id'],[]).append(a['dialogue'])
            comparisons.append(dict(group_id=g['group_id'],setting=g['setting'],method=method,
                                    true_k=m['true_k'],predicted_k=m['predicted_k'],
                                    signed_count_error=m['signed_count_error'],
                                    true_clusters=list(anonymous_gold.values()),predicted_clusters=part,
                                    merge_evidence=r['prediction']['merge_evidence'],
                                    uncertainty=r['prediction']['uncertainty']))
    def aggregate(rs):
        names=['absolute_count_error','signed_count_error','exact_k','exact_partition','pair_f1','ari','bcubed_f1']
        return dict(n=len(rs),**{name:statistics.mean([r[name] for r in rs if r[name] is not None]) if any(r[name] is not None for r in rs) else None for name in names},
                    pair_f1_defined_n=sum(r['pair_f1'] is not None for r in rs),
                    micro_pair_tp=sum(r['pair_tp'] for r in rs),micro_pair_fp=sum(r['pair_fp'] for r in rs),micro_pair_fn=sum(r['pair_fn'] for r in rs))
    summary={}
    byk={}
    for setting in ('same_a','different_a'):
        for method in ('elara','direct'):
            selected=[r for r in rows if r['setting']==setting and r['method']==method]
            summary[setting+'/'+method]=aggregate(selected)
            for k in range(1,11):
                byk[f'{setting}/{method}/K={k}']=aggregate([r for r in selected if r['true_k']==k])
    paired=[]
    for g in gold:
        rs={r['method']:r for r in rows if r['group_id']==g['group_id']}
        if len(rs)==2:
            paired.append(dict(group_id=g['group_id'],setting=g['setting'],true_k=g['true_k'],
                               elara_minus_direct_absolute_error=rs['elara']['absolute_count_error']-rs['direct']['absolute_count_error'],
                               elara_minus_direct_ari=rs['elara']['ari']-rs['direct']['ari']))
    ledger=folder/'attempts.jsonl'
    attempts=[json.loads(s) for s in ledger.read_text(encoding='utf-8').splitlines()] if ledger.exists() else []
    complete=[r for r in attempts if r['event']=='complete']
    usage={name:sum((r.get('body',{}).get('usage') or {}).get(name,0) for r in complete) for name in ('prompt_tokens','completion_tokens','total_tokens')}
    usage.update(completed_attempts=len(complete),valid_attempts=sum(r.get('valid',False) for r in complete),
                 rejected_or_failed_attempts=sum(not r.get('valid',False) for r in complete),
                 unresolved_starts=len({r['attempt_id'] for r in attempts if r['event']=='start'}-{r['attempt_id'] for r in complete}),
                 billing_unknown_attempts=sum(r.get('billing_unknown',False) for r in complete),
                 usage_missing_attempts=sum(not r.get('body',{}).get('usage') for r in complete),
                 wrapper_recovered_attempts=len({r['attempt_id'] for r in attempts if r['event']=='wrapper_recovery'}),
                 note='Returned token totals include invalid/schema-retry responses. Missing usage/unknown billing is NOT zero cost; no monetary estimate.')
    result=dict(complete_experiment=not missing,expected_group_method_outcomes=len(gold)*2,observed_outcomes=len(rows),missing=missing,
                scoring_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                summary=summary,by_k=byk,paired=paired,usage=usage,
                limitations=['Exploratory pilot: one group per K per setting by default; no population-level claim.',
                             'Dialogue-disjoint groups may reuse speakers; groups are not speaker-independent.',
                             'Direct prompt has no attribute-extraction scaffolding; internal reasoning strategy cannot be verified.',
                             'K is not disclosed; exact-K stratification and multiplicities are design choices.',
                             'No learned calibration, prompt tuning against gold, or real-world identity resolution.',
                             'One logical linkage/direct prediction per group, with logged format/transport retries; ELARA uses additional extraction calls.'])
    save(folder/'results.json',result)
    save(folder/'group_metrics.json',rows)
    save(folder/'predictions_vs_gold.json',comparisons)
    if rows:
        with (folder/'group_metrics.csv').open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    lines=['# RealPersonaChat 十对话身份关联实验','',
           f"完整运行：{not missing}；已评分 {len(rows)}/{len(gold)*2} 个组×方法。",'',
           '| 设置 | 方法 | 组数 | 人数 MAE ↓ | 人数准确率 ↑ | 完整聚类准确率 ↑ | ARI ↑ | B³ F1 ↑ |',
           '|---|---|---:|---:|---:|---:|---:|---:|']
    def fmt(x):
        return 'NA' if x is None else f'{x:.3f}'
    for key,m in summary.items():
        setting,method=key.split('/')
        lines.append(f"| {setting} | {method} | {m['n']} | {fmt(m['absolute_count_error'])} | {fmt(m['exact_k'])} | {fmt(m['exact_partition'])} | {fmt(m['ari'])} | {fmt(m['bcubed_f1'])} |")
    lines+=['','人数差定义为预测人数减真实人数；逐组真实 K、预测 K、差值和聚类指标见 group_metrics.csv。',
            'K=10 没有真实同人对；未定义的 pair precision/recall/F1 记 null，ARI 和 B³ 仍可计算。',
            '', '## 每个 K 的结果','', '| 设置 | K | ELARA 预测人数 | Direct 预测人数 | ELARA 绝对误差 | Direct 绝对误差 |', '|---|---:|---|---|---|---|']
    for g in gold:
        rs={r['method']:r for r in rows if r['group_id']==g['group_id']}
        get=lambda method,name: str(rs[method][name]) if method in rs else 'missing'
        lines.append(f"| {g['setting']} | {g['true_k']} | {get('elara','predicted_k')} | {get('direct','predicted_k')} | {get('elara','absolute_count_error')} | {get('direct','absolute_count_error')} |")
    lines+=['','## 解释边界','']+['- '+s for s in result['limitations']]
    lines+=['','## 请求统计','','```json',json.dumps(usage,ensure_ascii=False,indent=2),'```','',
            '结果为封闭语料库中匿名标签的聚类，不恢复任何真实姓名或外部身份。']
    (folder/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(complete_experiment=not missing,summary=summary,usage=usage),ensure_ascii=True),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--folder',type=Path,default=HERE/'runs/pilot')
    score(p.parse_args().folder)
