"""Offline PRISM enhanced v1.1 rescore: python -B -m isc113.rescore_prism_third_policy."""
import csv
import io
import json
from collections import Counter

from . import rejudge_njl_five as judge
from .rescore_njl_third_policy import COUNTS, RULES, filter_matches


def main():
    source = judge.HERE / 'runs/njl_prism_enhanced_v11_qwen38max_prompts_v2'
    out = source / 'third_policy'
    manifest = judge.read_json(source / 'manifest.json')
    export = judge.HERE / manifest['input_export']
    reference = judge.HERE / manifest['reference_file']
    assert judge.sha_bytes(export.read_bytes()) == manifest['export_sha256']
    assert judge.sha_bytes(reference.read_bytes()) == manifest['reference_sha256']
    prompt, prompt_hash = judge.load_match_prompt()
    assert prompt_hash == manifest['prompt_file_sha256']
    assert judge.sha_obj(prompt) == manifest['matcher_prompt_sha256']
    records = judge.read_json(export)
    refs = {(r['dialogue_id'], r['direction']): r['claims'] for r in judge.read_json(reference)}
    assert len(records) == len(refs) == 298
    assert {(r['dialogue_id'], r['direction']) for r in records} == set(refs)
    assert all(r['method'] == manifest['method'] and r['dataset'] == manifest['dataset']
               and r['direction'] == manifest['direction'] for r in records)
    assert all(r['truth'] == 'true' and r.get('review_status', 'reviewed') == 'reviewed'
               for gold in refs.values() for r in gold)
    old = judge.read_json(source / 'scores' / manifest['label'] / 'summary.json')
    rows, replay, hashes = [], {'strict': [], 'loose': []}, {}
    for original in sorted(records, key=lambda r: r['dialogue_id']):
        did, direction = original['dialogue_id'], original['direction']
        gold = refs[(did, direction)]
        unique = {judge.sha_obj(c['claim']): c['claim'] for c in original['claims']}
        predictions = [{'prediction_id': h, 'claim': text} for h, text in sorted(unique.items())]
        references = [{'claim_id': r['claim_id'], 'claim': r['claim']} for r in gold]
        content = dict(predictions=predictions, reference=references,
                       subject_mapping=judge.SUBJECT_MAPPING, persona_reference_rule=judge.PERSONA_RULE,
                       matcher_prompt_sha256=judge.sha_obj(prompt))
        payload = {k: manifest[k] for k in (
            'model', 'temperature', 'enable_thinking', 'thinking_budget', 'max_tokens')}
        payload['messages'] = [{'role': 'system', 'content': prompt},
                               {'role': 'user', 'content': json.dumps(content, ensure_ascii=False)}]
        binding = judge.sha_obj(dict(payload=payload, endpoint=manifest['endpoint'],
                                     version=manifest['matching_version'], method=manifest['label'],
                                     dialogue_id=did, direction=direction))
        task = judge.Task(manifest['label'], manifest['algorithm'], did, direction,
                          tuple(predictions), tuple(references), payload, binding)
        matches = judge.cached_matches(source, task)
        assert matches is not None, f'Missing evaluation: {did}'
        path = judge.cache_path(source, task)
        hashes[path.relative_to(source).as_posix()] = judge.sha_bytes(path.read_bytes())
        filtered = filter_matches(matches, gold)
        row = judge.score_input(original, gold, filtered, ('equivalent',))
        for level in ('E1', 'E2'):
            part = judge.score_input(original, [r for r in gold if r['evidence_level'] == level],
                                     filtered, ('equivalent',))
            row[level.lower() + '_hits'] = part['recovered_reference_attributes']
        rows.append(row)
        for policy, accepted in (('strict', ('equivalent',)), ('loose', ('equivalent', 'broader'))):
            base = judge.score_input(original, gold, matches, accepted)
            replay[policy].append(base)
            for k in ('correct_output_assertions', 'recovered_reference_attributes',
                      'recovered_grounded_reference_attributes'):
                assert base[k] <= row[k] if policy == 'strict' else row[k] <= base[k]
    for policy in replay:
        for k in COUNTS:
            assert sum(r[k] for r in replay[policy]) == old[policy][k], (policy, k)
    sums = {k: sum(r[k] for r in rows) for k in COUNTS}
    assert (sums['output_assertions'], sums['true_reference_attributes'],
            sums['grounded_reference_attributes']) == (996, 588, 262)
    sums.update(algorithm=manifest['label'], name='PRISM enhanced v1.1', single_sided_inputs=len(rows),
                precision=sums['correct_output_assertions'] / sums['output_assertions'],
                recall=sums['recovered_reference_attributes'] / sums['true_reference_attributes'],
                grounded_recall=sums['recovered_grounded_reference_attributes'] / sums['grounded_reference_attributes'])
    levels = dict(sorted(Counter(r['evidence_level'] for gold in refs.values() for r in gold).items()))
    for level in ('E1', 'E2'):
        hits = sum(r[level.lower() + '_hits'] for r in rows)
        sums.update({level.lower() + '_hits': hits, level.lower() + '_reference': levels[level],
                     level.lower() + '_recall': hits / levels[level]})
    judge.atomic_json(out / 'scores' / manifest['label'] / 'per_input.json', rows)
    judge.atomic_json(out / 'prism_third_policy.json', dict(
        complete=True, accepted_relations_by_reference_level=RULES, reference_level_counts=levels,
        source_manifest_sha256=judge.sha_obj(manifest), source_match_sha256=hashes,
        new_api_calls=0, verification='Both historical policies reproduced exactly; strict <= third <= loose per input',
        methods={manifest['label']: sums}))
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=list(sums))
    writer.writeheader()
    writer.writerow(sums)
    (out / 'prism_third_policy.csv').write_text(buffer.getvalue(), encoding='utf-8-sig')
    report = '\n'.join([
        '# PRISM enhanced v1.1 第三种计算口径', '',
        '复用 qwen3.8-max 已完成的评价结果，无新增 API 请求。',
        'E1/E3/E4 仅 equivalent；E2 接受 equivalent + broader。按匹配参考的证据等级筛选。',
        'Precision 保留全部原始输出；Recall/Grounded Recall 分别使用全参考/E1E2 独立最大一对一匹配。', '',
        '| 算法 | Precision | Recall | Grounded Recall |', '|---|---:|---:|---:|',
        f"| PRISM enhanced v1.1 | {sums['precision']:.4%} | {sums['recall']:.4%} | {sums['grounded_recall']:.4%} |", '',
        f"- 正确输出 / 全部输出：{sums['correct_output_assertions']}/996。",
        f"- 恢复参考 / 全部参考：{sums['recovered_reference_attributes']}/588。",
        f"- 恢复有据参考 / E1E2 参考：{sums['recovered_grounded_reference_attributes']}/262。",
        '- 覆盖固定 298 段 A→B 对话；已复现原严格/宽松全部计数，逐对话验证新口径位于二者之间。',
        '- 冻结预测、参考、提示词哈希及全部匹配缓存绑定均已核验；原始文件保留。', '',
        'E1/E2 分级召回另见 CSV/JSON，分别独立做最大一对一匹配，不能直接相加代替联合匹配。', ''])
    (out / 'REPORT.md').write_text(report, encoding='utf-8')
    print(json.dumps(sums, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
