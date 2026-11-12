"""Offline, reproducible audit of the sixteen frozen methods; no API calls."""
import csv
import json
from collections import Counter
from pathlib import Path
from .common import BASE, read, save, digest, filehash
from .evaluation import reference_map, score_item
from .statistics import four_metrics, matching

SOURCES = [
    ('main', 'results/prompts_v2/matches'),
    ('efcr_append_v1', 'results/efcr_append_v1/matches'),
    ('evidence_adaptive_v1_append', 'results/evidence_adaptive_v1_append/matches'),
    ('evidence_adaptive_v2_corrected', 'results/evidence_adaptive_v2_corrected/matches'),
    ('evidence_adaptive_v3_append', 'results/evidence_adaptive_v3_append/matches'),
    ('efcr_append_v2', 'results/efcr_append_v2/matches'),
    ('evidence_adaptive_v4_append', 'results/evidence_adaptive_v4_append/matches'),
    ('evidence_adaptive_v5_append', 'results/evidence_adaptive_v5_append/matches'),
    ('elara_append_v1', 'runs/elara_append_v1/evaluation/matches'),
    ('elara_v2_append', 'runs/elara_v2_append/evaluation/matches'),
    ('elara_v3_append', 'runs/elara_v3_append/evaluation/matches'),
]
NAMES = dict(zip([
    'direct_thinking','direct_multisample_verifier','route1_only','route2_only',
    'dual_without_verifier','dual_with_verifier','evidence_counterfactual_repair',
    'evidence_adaptive_v1','evidence_adaptive_v2','evidence_adaptive_v3',
    'evidence_counterfactual_repair_v2','evidence_adaptive_v4','evidence_adaptive_v5',
    'elara_evidence_lattice_v1','elara_v2_evidence_calibrated_dual_route',
    'elara_v3_relation_preserving_mechanism_adjudication'], [
    'Direct thinking','Direct multisample verifier','Route 1','Route 2',
    'Dual without verifier','Dual with verifier','EFCR v1','Evidence-Adaptive v1',
    'Evidence-Adaptive v2','Evidence-Adaptive v3','EFCR v2','Evidence-Adaptive v4',
    'Evidence-Adaptive v5','ELARA v1','ELARA v2','ELARA v3']))

def main():
    refs=reference_map('dailydialog')
    inputs={x['dialogue_id']:x for x in read(BASE/'inputs/dailydialog.json')}
    out=BASE/'results/cover_diagnosis'; tables=[]; missed=[]; empties=[]; provenance={}
    for run, folder in SOURCES:
        path=BASE/'runs'/run/'exports/dailydialog.json'; ps=read(path)
        provenance[str(path.relative_to(BASE))]=filehash(path)
        matches={}
        for p in ps:
            did=p['dialogue_id']
            if did not in matches:
                q=BASE/folder/(did+'__A_to_B.json')
                if q.exists():
                    matches[did]=read(q)['matches'];provenance[str(q.relative_to(BASE))]=filehash(q)
        for method in dict.fromkeys(p['method'] for p in ps):
            subset=[p for p in ps if p['method']==method]
            assert len(subset)==298 and len({p['item_id'] for p in subset})==298
            for policy,accepted in [('strict',('equivalent',)),('lenient',('equivalent','broader'))]:
                rows=[];counts=Counter(); buckets=Counter()
                for p in subset:
                    did=p['dialogue_id'];rr=refs[(did,'A_to_B')]
                    if did not in matches:
                        counts['missing_evaluation_items']+=1
                        continue
                    ms=matches[did]
                    mm={m['prediction_id']:m for m in ms}
                    assert all(digest(c['claim']) in mm for c in p['claims']), (method,did)
                    rows.append(score_item(p,rr,ms,{},accepted_relations=accepted))
                    counts['empty_outputs']+=not p['claims']
                    counts['empty_attribute_fields']+=sum(not str(c.get('attribute','')).strip() for c in p['claims'])
                    counts['empty_claim_fields']+=sum(not str(c.get('claim','')).strip() for c in p['claims'])
                    if not p['claims']:
                        grounded=[r for r in rr if r['evidence_level'] in ('E1','E2')]
                        counts['empty_with_grounded']+=bool(grounded)
                        counts['grounded_in_empty']+=len(grounded)
                        if policy=='strict':empties.append(dict(method=method,dialogue_id=did,reference_count=len(rr),grounded_count=len(grounded),visible_turns=inputs[did]['visible_turns']))
                    eligible={r['claim_id']:r for r in rr if r['evidence_level'] in ('E1','E2')}
                    edges={str(i):{k for k in mm[digest(c['claim'])]['reference_ids'] if k in eligible}
                           if mm[digest(c['claim'])]['relation'] in accepted else set() for i,c in enumerate(p['claims'])}
                    hits=set(matching(edges).values())
                    for c in p['claims']:counts['relation_'+mm[digest(c['claim'])]['relation']]+=1
                    for rid,r in eligible.items():
                        if rid in hits:continue
                        related=[{'claim':c['claim'],**mm[digest(c['claim'])]} for c in p['claims'] if rid in mm[digest(c['claim'])]['reference_ids']]
                        relations={c['relation'] for c in related}
                        bucket=('empty_output' if not p['claims'] else 'one_to_one_competition' if relations & set(accepted)
                                else 'broader_only' if 'broader' in relations else 'narrower_only' if 'narrower' in relations else 'no_cached_semantic_edge')
                        buckets[bucket]+=1
                        missed.append(dict(method=method,policy=policy,dialogue_id=did,claim_id=rid,reference=r['claim'],level=r['evidence_level'],bucket=bucket,
                                           related=related,visible_turns=inputs[did]['visible_turns'],reference_visible_evidence=r.get('evidence',[])))
                metrics=four_metrics(rows)
                # Costs deliberately not reconstructed here; this audit does not report token estimates.
                for k in ('mean_tokens','tokens'):metrics.pop(k,None)
                table=dict(name=NAMES[method],method=method,policy=policy,evaluator='original' if run.startswith('elara') else 'prompts-v2',**metrics,**counts,
                           e1_total=sum(r['e1_reference'] for r in rows),e2_total=sum(r['e2_reference'] for r in rows),
                           e1_hits=sum(r['e1_hits'] for r in rows),e2_hits=sum(r['e2_hits'] for r in rows),
                           e1_missed=sum(r['e1_reference']-r['e1_hits'] for r in rows),e2_missed=sum(r['e2_reference']-r['e2_hits'] for r in rows),miss_buckets=dict(buckets))
                tables.append(table)
    save(out/'summary.json',tables);save(out/'missed_grounded_attributes.json',missed);save(out/'empty_outputs.json',empties)
    save(out/'source_hashes.json',provenance)
    fields=list(dict.fromkeys(k for t in tables for k in t if k!='miss_buckets'))
    with (out/'summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:t.get(k,0) for k in fields} for t in tables)
    lines=['# 十六模块离线统计','', '前十三项使用各自 prompts-v2 历史判断；ELARA 三项使用原 MATCH。跨组数值不能直接排名。', '',
           '| 模块 | P | R | GR | E1 漏/总 | E2 漏/总 | 空输出 | 有据空输出 | 空输出内有据漏检 | broader/narrower |',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for t in tables:
        if t['policy']=='strict':
            lines.append(f"| {t['name'] + ('（296 段）' if t.get('missing_evaluation_items') else '')} | {t['precision']:.2%} | {t['recall']:.2%} | {t['grounded_recall']:.2%} | {t['e1_missed']}/{t['e1_total']} | {t['e2_missed']}/{t['e2_total']} | {t['empty_outputs']} | {t['empty_with_grounded']} | {t['grounded_in_empty']} | {t['relation_broader']}/{t['relation_narrower']} |")
    (out/'TABLE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))

if __name__=='__main__':main()
