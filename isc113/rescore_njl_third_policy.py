"""Offline third-policy scoring of the frozen five-algorithm NJL results.

Run from the workspace: python -B -m isc113.rescore_njl_third_policy
E1/E3/E4: equivalent; E2: equivalent or broader. No API calls.
"""
import csv
import io
from collections import Counter
from types import SimpleNamespace

from .rejudge_njl_five import (
    HERE, METHODS, atomic_json, cache_path, cached_matches, load_inputs,
    load_match_prompt, read_json, score_input, sha_bytes, sha_obj,
)


COUNTS = (
    'output_assertions', 'correct_output_assertions',
    'recovered_reference_attributes', 'true_reference_attributes',
    'recovered_grounded_reference_attributes', 'grounded_reference_attributes',
)
RULES = {level: ['equivalent'] for level in ('E1', 'E2', 'E3', 'E4')}
RULES['E2'] = ['equivalent', 'broader']


def filter_matches(matches, refs):
    """Filter edges by the matched reference's level, not prediction metadata."""
    levels = {r['claim_id']: r['evidence_level'] for r in refs}
    return [dict(m, relation='equivalent', reference_ids=[
        rid for rid in m['reference_ids'] if m['relation'] in RULES[levels[rid]]
    ]) for m in matches]


def main():
    source = HERE / 'runs/njl_qwen38max_prompts_v2'
    out = source / 'third_policy'
    manifest = read_json(source / 'manifest.json')
    args = SimpleNamespace(**{k: manifest[k] for k in (
        'endpoint', 'thinking_budget', 'max_tokens')})
    prompt, prompt_hash = load_match_prompt()
    refs, originals, tasks, rebuilt_manifest = load_inputs(prompt, prompt_hash, args)
    assert rebuilt_manifest == manifest, 'Frozen inputs/config differ from manifest'
    previous = read_json(source / 'five_algorithms_strict_loose.json')
    assert previous['complete'] and previous['manifest_sha256'] == sha_obj(manifest)
    level_counts = dict(sorted(Counter(
        r['evidence_level'] for rs in refs.values() for r in rs).items()))
    result, source_hashes = {}, {}
    for display, label, _, _ in METHODS:
        rows, baselines = [], {'strict': [], 'loose': []}
        for task in tasks[label]:
            key = (task.did, task.direction)
            matches = cached_matches(source, task)
            assert matches is not None, f'Missing matches: {label} {key}'
            path = cache_path(source, task)
            source_hashes[path.relative_to(source).as_posix()] = sha_bytes(path.read_bytes())
            original, gold = originals[label][key], refs[key]
            filtered = filter_matches(matches, gold)
            row = score_input(original, gold, filtered, ('equivalent',))
            # Independent level-specific maximum matchings; these need not add
            # up to the overall matching when one prediction has multiple edges.
            for level in ('E1', 'E2'):
                part = score_input(original, [r for r in gold if r['evidence_level'] == level],
                                   filtered, ('equivalent',))
                row[level.lower() + '_hits'] = part['recovered_reference_attributes']
            rows.append(row)
            for policy, accepted in (('strict', ('equivalent',)),
                                     ('loose', ('equivalent', 'broader'))):
                base = score_input(original, gold, matches, accepted)
                baselines[policy].append(base)
                for count in ('correct_output_assertions', 'recovered_reference_attributes',
                              'recovered_grounded_reference_attributes'):
                    assert (base[count] <= row[count] if policy == 'strict'
                            else row[count] <= base[count])
        sums = {k: sum(r[k] for r in rows) for k in COUNTS}
        assert len(rows) == 298
        assert (sums['true_reference_attributes'], sums['grounded_reference_attributes']) == (588, 262)
        # Replay both historical policies to validate exact scoring compatibility.
        for policy, base_rows in baselines.items():
            for k in COUNTS:
                assert sum(r[k] for r in base_rows) == previous['methods'][label][policy][k], (label, policy, k)
        sums.update(
            algorithm=label, name=display, single_sided_inputs=len(rows),
            precision=sums['correct_output_assertions'] / sums['output_assertions'],
            recall=sums['recovered_reference_attributes'] / sums['true_reference_attributes'],
            grounded_recall=sums['recovered_grounded_reference_attributes'] / sums['grounded_reference_attributes'],
        )
        for level in ('E1', 'E2'):
            hits = sum(r[level.lower() + '_hits'] for r in rows)
            sums.update({level.lower() + '_hits': hits,
                         level.lower() + '_reference': level_counts[level],
                         level.lower() + '_recall': hits / level_counts[level]})
        result[label] = sums
        atomic_json(out / 'scores' / label / 'per_input.json', rows)

    atomic_json(out / 'five_algorithms_third_policy.json', dict(
        complete=True, policy='equivalent_all_levels_plus_broader_E2_only',
        accepted_relations_by_reference_level=RULES, reference_level_counts=level_counts,
        source_manifest_sha256=sha_obj(manifest), source_match_sha256=source_hashes,
        new_api_calls=0, verification='Both historical policies reproduced exactly; strict <= third <= loose per input',
        methods=result))
    fields = ['algorithm', 'name', 'precision', 'recall', 'grounded_recall',
              *COUNTS, 'single_sided_inputs', 'e1_hits', 'e1_reference', 'e1_recall',
              'e2_hits', 'e2_reference', 'e2_recall']
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(result.values())
    (out / 'five_algorithms_third_policy.csv').write_text(buffer.getvalue(), encoding='utf-8-sig')
    lines = ['# 五算法第三种计算口径', '',
             '复用 qwen3.8-max 已完成的评价结果，无新增 API 请求；按匹配参考的证据等级计分。', '',
             '- E1、E3、E4：仅 equivalent；E2：equivalent 或 broader；narrower/none 不计命中。',
             '- Precision：正确原始输出数 / 全部原始输出数，保留重复输出。',
             '- Recall：全部参考最大一对一命中数 / 588。',
             '- Grounded Recall：E1/E2 独立最大一对一命中数 / 262。',
             '- 每个算法均覆盖固定的 298 段 A→B 对话。',
             '- 已复算并精确复现原严格、宽松口径的所有计数；逐对话验证第三种口径位于二者之间。', '',
             '| 算法 | Precision | Recall | Grounded Recall |',
             '|---|---:|---:|---:|']
    for row in result.values():
        lines.append(f"| {row['name']} | {row['precision']:.4%} | {row['recall']:.4%} | {row['grounded_recall']:.4%} |")
    lines += ['', '| 算法 | 正确输出/全部输出 | 恢复参考/588 | 恢复有据参考/262 |', '|---|---:|---:|---:|']
    for row in result.values():
        lines.append(f"| {row['name']} | {row['correct_output_assertions']}/{row['output_assertions']} | {row['recovered_reference_attributes']}/588 | {row['recovered_grounded_reference_attributes']}/262 |")
    lines += ['', 'E1/E2 分级召回另见 CSV/JSON，分别独立做最大一对一匹配；分级命中数不应直接相加替代联合匹配。',
              '原始 matches、attempts、manifest 以及严格/宽松报告均保留。', '']
    (out / 'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
