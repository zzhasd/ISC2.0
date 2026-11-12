"""Read-only source audit: existential coverage of fixed 588-reference inventory.

Run from repository root: python -B -m isc113.audit_ever_grounded_coverage
Writes only a new audit directory, never calls an API or changes old results.
"""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from .common import BASE, ROOT, digest, read, save, filehash

OUT = BASE / 'results/ever_grounded_coverage_audit'


def main():
    refpath = BASE / 'references/dailydialog_human_adjudicated_588.json'
    records = read(refpath)
    refs = {c['claim_id']: dict(c, dialogue_id=p['dialogue_id'])
            for p in records for c in p['claims']}
    target = {k: r for k, r in refs.items() if r['evidence_level'] in ('E1', 'E2')}
    assert len(refs) == 588
    assert Counter(r['evidence_level'] for r in target.values()) == {'E1': 136, 'E2': 126}
    dids = {p['dialogue_id'] for p in records}
    roots = [BASE, ROOT / 'isc113 - 副本']
    predictions = defaultdict(lambda: dict(methods=set(), files=set()))
    source_hashes = {str(refpath.relative_to(ROOT)): filehash(refpath)}
    prediction_sources = {}
    for root in roots:
        # Legacy and final reference claim IDs have exactly the same text.
        for old in (root / 'references').glob('dailydialog*.json'):
            obj = read(old)
            if not isinstance(obj, list):
                continue
            oldrefs = {c['claim_id']: c['claim'] for p in obj if isinstance(p, dict)
                       for c in p.get('claims', []) if 'claim_id' in c}
            assert all(oldrefs[k] == refs[k]['claim'] for k in oldrefs.keys() & refs.keys()), old
        candidates = set(root.glob('runs/*/exports/dailydialog.json'))
        candidates.update(p for p in (root / 'runs').rglob('*.json') if 'predictions' in p.parts)
        for path in sorted(candidates):
            obj = read(path)
            items = obj if isinstance(obj, list) else [obj]
            n = 0
            methods = set()
            for p in items:
                if not isinstance(p, dict) or p.get('dialogue_id') not in dids:
                    continue
                if p.get('direction') != 'A_to_B' or p.get('dataset') != 'dailydialog':
                    continue
                for c in p.get('claims', []):
                    if not isinstance(c.get('claim'), str):
                        continue
                    key = (p['dialogue_id'], digest(c['claim']))
                    entry = predictions[key]
                    entry['claim'] = c['claim']
                    entry['methods'].add(p['method'])
                    entry['files'].add(str(path.relative_to(ROOT)))
                    methods.add(p['method'])
                    n += 1
            if n:
                rel = str(path.relative_to(ROOT))
                source_hashes[rel] = filehash(path)
                prediction_sources[rel] = dict(claim_occurrences=n, methods=sorted(methods))

    edges = defaultdict(list)
    judged = set()
    families = defaultdict(lambda: dict(files=0, rows=0, hit_ids=set(), strict_ids=set()))
    skipped = Counter()
    for root in roots:
        paths = sorted(p for p in root.rglob('*.json') if 'matches' in p.parts)
        for path in paths:
            suffix = '__A_to_B'
            if not path.stem.endswith(suffix):
                continue
            did = path.stem[:-len(suffix)]
            if did not in dids:
                continue
            obj = read(path)
            if not isinstance(obj, dict) or not isinstance(obj.get('matches'), list):
                continue
            rel = str(path.relative_to(ROOT))
            folder = str(path.parent.relative_to(ROOT))
            family = families[folder]
            family['files'] += 1
            source_hashes[rel] = filehash(path)
            for m in obj['matches']:
                key = (did, m['prediction_id'])
                if key not in predictions:
                    skipped['match_rows_without_saved_final_prediction'] += 1
                    continue
                judged.add(key)
                family['rows'] += 1
                relation = m['relation']
                assert relation in ('equivalent', 'broader', 'narrower', 'none')
                for rid in m['reference_ids']:
                    if rid not in target:
                        continue
                    assert target[rid]['dialogue_id'] == did
                    entry = dict(relation=relation, prediction=predictions[key]['claim'],
                                 prediction_id=key[1], methods=sorted(predictions[key]['methods']),
                                 match_file=rel, evaluation_model=obj.get('evaluation_model'))
                    edges[rid].append(entry)
                    if relation == 'equivalent':
                        family['strict_ids'].add(rid)
                    if relation in ('equivalent', 'broader'):
                        family['hit_ids'].add(rid)

    # Exact reference strings present even in incomplete, unjudged final outputs
    # are independently sufficient for existential strict coverage.
    for rid, r in target.items():
        key = (r['dialogue_id'], digest(r['claim']))
        if key in predictions:
            edges[rid].append(dict(relation='equivalent', prediction=r['claim'],
                                   prediction_id=key[1], methods=sorted(predictions[key]['methods']),
                                   match_file=None, evidence='exact reference text in saved final output'))

    inputs = {p['dialogue_id']: p for p in read(BASE / 'inputs/dailydialog.json')}
    details = []
    for rid, r in target.items():
        ee = edges[rid]
        strict = any(e['relation'] == 'equivalent' for e in ee)
        loose = any(e['relation'] in ('equivalent', 'broader') for e in ee)
        narrow = any(e['relation'] == 'narrower' for e in ee)
        pending = [dict(prediction=p['claim'], methods=sorted(p['methods']), files=sorted(p['files']))
                   for key, p in predictions.items() if key[0] == r['dialogue_id'] and key not in judged]
        details.append(dict(claim_id=rid, dialogue_id=r['dialogue_id'], level=r['evidence_level'],
                            reference=r['claim'], strict_ever_hit=strict, loose_ever_hit=loose,
                            any_directional_edge=strict or loose or narrow,
                            relation_counts=dict(Counter(e['relation'] for e in ee)),
                            evidence=r.get('evidence', []), visible_turns=inputs[r['dialogue_id']]['visible_turns'],
                            matching_edges=ee, unjudged_predictions_in_dialogue=pending))
    counts = {}
    for level in ('E1', 'E2'):
        rr = [r for r in details if r['level'] == level]
        counts[level] = dict(total=len(rr), strict_ever_hit=sum(r['strict_ever_hit'] for r in rr),
                             strict_never_hit=sum(not r['strict_ever_hit'] for r in rr),
                             loose_ever_hit=sum(r['loose_ever_hit'] for r in rr),
                             loose_never_hit=sum(not r['loose_ever_hit'] for r in rr),
                             no_directional_edge=sum(not r['any_directional_edge'] for r in rr))
    family_summary = {}
    for name, f in families.items():
        family_summary[name] = dict(files=f['files'], rows=f['rows'],
                                   strict_hits_by_level=dict(Counter(target[r]['evidence_level'] for r in f['strict_ids'])),
                                   loose_hits_by_level=dict(Counter(target[r]['evidence_level'] for r in f['hit_ids'])))
    summary = dict(reference_sha256=filehash(refpath), counts=counts,
                   unique_saved_final_predictions=len(predictions), predictions_with_any_cached_judgment=len(judged),
                   unjudged_unique_predictions=len(set(predictions)-judged),
                   methods=sorted({m for p in predictions.values() for m in p['methods']}),
                   prediction_files=len(prediction_sources), matching_files=sum(f['files'] for f in families.values()),
                   match_families=family_summary, skipped=dict(skipped), new_api_calls=0,
                   scope='Same dialogue and A_to_B; saved final predictions only, including incomplete runs. '
                         'Existential union of every saved cache, plus exact reference-text predictions. '
                         'No raw failed attempts or intermediate candidates. No one-to-one matching reduction. '
                         'Cached non-hits do not prove semantic absence, especially for unjudged predictions.')
    OUT.mkdir(parents=True, exist_ok=True)
    save(OUT / 'summary.json', summary)
    save(OUT / 'reference_coverage.json', details)
    save(OUT / 'strict_never_hit.json', [r for r in details if not r['strict_ever_hit']])
    save(OUT / 'loose_never_hit.json', [r for r in details if not r['loose_ever_hit']])
    save(OUT / 'source_hashes.json', source_hashes)
    save(OUT / 'prediction_sources.json', prediction_sources)
    fields = ['claim_id', 'dialogue_id', 'level', 'reference', 'strict_ever_hit', 'loose_ever_hit', 'any_directional_edge']
    with (OUT / 'reference_coverage.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: r[k] for k in fields} for r in details)
    lines = ['# 历次最终预测的 E1/E2 覆盖并集审计', '',
             '固定 588 参考库；E1 136 条，E2 126 条。仅检查相同对话的 A→B 最终输出。',
             '严格=equivalent；宽松=equivalent+broader。任一算法任一缓存命中过即算曾命中；原始失败响应和中间候选不算最终输出。',
             '“未命中”表示已有缓存和精确同文检查未发现命中，不等于人工确认所有预测均无语义对应。', '',
             '| 等级 | 总数 | 严格曾命中 | 严格从未命中 | 宽松曾命中 | 宽松从未命中 | 连 narrower 边也没有 |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for level, c in counts.items():
        lines.append(f"| {level} | {c['total']} | {c['strict_ever_hit']} | {c['strict_never_hit']} | {c['loose_ever_hit']} | {c['loose_never_hit']} | {c['no_directional_edge']} |")
    lines += ['', f"扫描 {len(summary['methods'])} 个方法、{summary['matching_files']} 个匹配文件；"
              f"去重后 {len(predictions)} 条对话内预测，其中 {summary['unjudged_unique_predictions']} 条没有任何已存语义判断。", '',
              '## 宽松仍从未命中的属性', '', '| 等级 | 参考 ID | 参考属性 |', '|---|---|---|']
    for r in details:
        if not r['loose_ever_hit']:
            lines.append(f"| {r['level']} | {r['claim_id']} | {r['reference'].replace('|', '/')} |")
    lines += ['', '## 严格从未命中的全部属性', '', '| 等级 | 参考 ID | 参考属性 | 对话内未评价预测数 |', '|---|---|---|---:|']
    for r in details:
        if not r['strict_ever_hit']:
            lines.append(f"| {r['level']} | {r['claim_id']} | {r['reference'].replace('|', '/')} | {len(r['unjudged_predictions_in_dialogue'])} |")
    lines += ['', '## 对宽松未命中项的文本检查', '',
              '- train_2859_A_to_B_a1_1：参考是想今晚去音乐会；多个算法输出已同意/接受今晚去音乐会，部分缓存判为 narrower。因此是原计分规则下未命中，不能称完全未提到音乐会。',
              '- train_3954_A_to_B_a2_1：参考同时包含喜欢自然景色和希望增加亲近自然的时间；已有输出描述一同出游、受益于自然景色或出游不频繁，未有缓存 equivalent/broader 命中该完整参考。',
              '- train_447_A_to_B_a2_1：参考为 upset and angry；已有输出主要为 worried/anxious 和 finger-pointing。原可见证据明确有 worried，但没有直接写 angry，建议另行复核参考 E2 标注；本审计不修改参考或历史判断。', '',
              '142 条独特最终预测尚无任何已存评价，主要来自未完成的追加运行；上述三个宽松未命中对话没有此类未评价预测。',
              '上述条目按原始参考 ID 计数，不合并参考库中的近义或复合命题。']
    (OUT / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'match_families'}, ensure_ascii=True, indent=2))
    print('\nLOOSE NEVER HIT:')
    for r in details:
        if not r['loose_ever_hit']:
            print(r['level'], r['claim_id'], r['reference'], 'pending=', len(r['unjudged_predictions_in_dialogue']))


if __name__ == '__main__':
    main()
