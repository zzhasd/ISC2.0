"""Rejudge frozen predictions with prompts-v2, preserving historical artifacts.

python -B -m isc113.evaluate_prompts_v2 --workers 12
Credentials are read only from QWEN_API_KEY / DASHSCOPE_API_KEY.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import importlib.util
import os

from .common import BASE, digest, filehash, read, save
from .client import Client, URL
from .evaluation import (predictions, reference_map, _prediction_inventory,
                         _reference_inventory, validate_matches, cost_map, score_item)
from .inference import METHODS, payload, decode
from .statistics import four_metrics

OUTPUT = BASE / 'results/prompts_v2'


def load_prompt():
    spec = importlib.util.spec_from_file_location('isc113_prompts_v2', BASE / 'prompts-v2.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not isinstance(module.MATCH, str) or not module.MATCH.strip():
        raise ValueError('Missing MATCH prompt')
    return module.MATCH


def validate_v2(obj, pp, rr):
    # Preserve the historical parser contract. Prompt conformance is audited
    # separately; it must not silently change first-response selection.
    return validate_matches(obj, pp, rr)


def replay_recorded():
    """Select first original-schema-valid complete response, without new calls.

    Early transport validation was overstrict about directional ID counts.
    Replaying every task with the historical parser avoids selectively keeping
    later responses for those tasks. Raw logs and validity flags stay intact.
    """
    from .common import jsonlines
    from .recover_evaluations import terminal_matches
    ps, refs, jobs = prepare()
    raw = jsonlines(BASE / 'runs/prompts_v2_evaluation/attempts.jsonl')
    recovered, missing, deviations = [], [], []
    for j in jobs:
        if not j['pp'] or not j['rr']:
            continue
        name = 'prompts_v2/' + j['dialogue_id'] + '/' + j['binding']
        attempts = [r for r in raw if r['event'] == 'complete' and r['logical_name'] == name]
        selected = None
        for r in attempts:
            if r.get('http_status') != 200:
                continue
            try:
                ms = validate_v2(decode(r['body']), j['pp'], j['rr'])
                selected = (r, ms, 'original_parser')
                break
            except (ValueError, KeyError, TypeError):
                pass
        if selected is None and len(attempts) >= 3:
            for r in attempts:
                if r.get('http_status') != 200:
                    continue
                try:
                    ms = validate_v2(terminal_matches(r['body']), j['pp'], j['rr'])
                    selected = (r, ms, 'terminal_complete_JSON_recovery')
                    break
                except (ValueError, KeyError, TypeError):
                    pass
        if selected is None:
            missing.append(j['dialogue_id'])
            continue
        r, ms, parser = selected
        for m in ms:
            if (m['relation'] in ('broader', 'narrower') and len(m['reference_ids']) != 1
                    or m['relation'] == 'none' and m['reference_ids']):
                deviations.append(dict(dialogue_id=j['dialogue_id'], **m))
        save(path_for(j), dict(binding=j['binding'], matches=ms, task_id=r['task_id'],
                              attempt_id=r['attempt_id'], evaluation_model='qwen3.8-flash',
                              selection='first complete response valid under historical schema',
                              parser=parser, raw_validity_flag_unchanged=True))
        recovered.append(dict(dialogue_id=j['dialogue_id'], attempt_id=r['attempt_id'], parser=parser))
    save(OUTPUT / 'parser_replay_audit.json', dict(selected=recovered, missing=missing,
         prompt_contract_deviations=deviations, new_api_calls=0,
         note='Historical validate_matches used for every task; raw attempt validity flags preserved.'))
    if missing or any(cached(j) is None for j in jobs):
        raise RuntimeError('Missing evaluations after replay: ' + str(missing))
    result = summarize(ps, refs, jobs)
    if (OUTPUT / 'status.json').exists():
        save(OUTPUT / 'transport_status_before_replay.json', read(OUTPUT / 'status.json'))
    save(OUTPUT / 'status.json', dict(complete=True, matched_dialogues=len(jobs), missing=[],
                                    parser_replay='parser_replay_audit.json'))
    return result


def prepare():
    ps = predictions('dailydialog')
    refs = reference_map('dailydialog')
    expected_counts = dict(zip(METHODS, [952, 1379, 651, 1087, 1695, 1255]))
    assert Counter(p['method'] for p in ps) == Counter({m: 298 for m in METHODS})
    assert {m: sum(len(p['claims']) for p in ps if p['method'] == m) for m in METHODS} == expected_counts
    assert len(refs) == 298
    assert sum(len(r) for r in refs.values()) == 588
    assert sum(r['evidence_level'] in ('E1', 'E2') for rs in refs.values() for r in rs) == 262
    groups = {}
    for p in ps:
        k = (p['dialogue_id'], p['direction'])
        assert k in refs
        groups.setdefault(k, []).append(p)
    prompt = load_prompt()
    jobs = []
    for (did, direction), arms in sorted(groups.items()):
        pp = _prediction_inventory(arms)
        rr = _reference_inventory(refs[(did, direction)])
        content = {
            'predictions': pp, 'reference': rr,
            'subject_mapping': {'hidden partner / target': 'original B', 'visible speaker / observer': 'original A'},
            'persona_reference_rule': 'In persona references I/my refer to the hidden target, never the observer.',
            'matcher_prompt_sha256': digest(prompt),
        }
        request = payload(prompt, content, 4096)
        binding = digest({'request': request, 'endpoint': URL, 'adapter_version': 1})
        jobs.append(dict(dialogue_id=did, direction=direction, pp=pp, rr=rr,
                         request=request, binding=binding))
    manifest = dict(predictions_sha256=filehash(BASE / 'runs/main/exports/dailydialog.json'),
                    reference_sha256=filehash(BASE / 'references/dailydialog_human_adjudicated_588.json'),
                    prompt_sha256=filehash(BASE / 'prompts-v2.py'), matcher_prompt_sha256=digest(prompt),
                    endpoint=URL, model='qwen3.8-flash', temperature=0,
                    enable_thinking=True, thinking_budget=512, max_tokens=4096,
                    input_count=298, prediction_counts=expected_counts, references=588,
                    grounded_references=262, inference_rerun=False,
                    token_source='historical inference attempts; semantic evaluation excluded',
                    directional_relation_policy='prediction perspective; broader means reference entails prediction',
                    jobs_digest=digest(jobs))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUTPUT / 'manifest.json'
    if manifest_path.exists() and read(manifest_path) != manifest:
        raise ValueError('Evaluation inputs/config changed: use a separate output directory')
    save(manifest_path, manifest)
    return ps, refs, jobs


def path_for(job):
    return OUTPUT / 'matches' / (job['dialogue_id'] + '__' + job['direction'] + '.json')


def cached(job):
    p = path_for(job)
    if not p.exists():
        return None
    obj = read(p)
    if obj['binding'] != job['binding']:
        raise ValueError('Stale v2 cache: ' + str(p))
    return validate_v2(obj, job['pp'], job['rr'])


def run(workers=12, limit=None):
    ps, refs, jobs = prepare()
    selected = jobs if limit is None else [j for j in jobs if j['pp'] and j['rr']][:limit]
    requires_api = any(cached(j) is None and j['pp'] and j['rr'] for j in selected)
    client = Client(os.environ.get('QWEN_API_KEY') or os.environ.get('DASHSCOPE_API_KEY'),
                    run_id='prompts_v2_evaluation') if requires_api else None

    def work(j):
        if cached(j) is not None:
            return 'cached'
        if not j['pp']:
            ms, tid = [], None
        elif not j['rr']:
            ms = [dict(prediction_id=p['prediction_id'], reference_ids=[], relation='none') for p in j['pp']]
            tid = None
        else:
            ms, tid = client.call('prompts_v2/' + j['dialogue_id'] + '/' + j['binding'],
                                  j['request'], lambda obj: validate_v2(obj, j['pp'], j['rr']))
        save(path_for(j), dict(binding=j['binding'], matches=ms, task_id=tid,
                              evaluation_model='qwen3.8-flash', deterministic_empty=tid is None))
        return 'complete'

    counts, errors = Counter(), []
    # A single actual evaluation also verifies authentication before fanout.
    pending = list(selected)
    first = next((j for j in pending if j['pp'] and j['rr'] and cached(j) is None), None)
    if first:
        try:
            counts[work(first)] += 1
            pending.remove(first)
            print('First live evaluation succeeded.', flush=True)
        except Exception as e:
            save(OUTPUT / 'status.json', dict(complete=False, counts=dict(counts), errors=[dict(dialogue_id=first['dialogue_id'], error=str(e))]))
            raise
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fs = {pool.submit(work, j): j for j in pending}
        for f in as_completed(fs):
            j = fs[f]
            try:
                counts[f.result()] += 1
            except Exception as e:
                errors.append(dict(dialogue_id=j['dialogue_id'], error=str(e)))
            n = sum(counts.values()) + len(errors)
            if n % 20 == 0:
                print(dict(finished=n, selected=len(selected), counts=dict(counts), errors=len(errors)), flush=True)
    all_done = all(cached(j) is not None for j in jobs)
    save(OUTPUT / 'status.json', dict(complete=all_done, counts=dict(counts), errors=errors))
    if errors:
        raise RuntimeError('Incomplete matching: see results/prompts_v2/status.json')
    if all_done:
        return summarize(ps, refs, jobs)
    return dict(complete=False, counts=dict(counts))


def summarize(ps, refs, jobs):
    costs = cost_map()
    matched = {(j['dialogue_id'], j['direction']): cached(j) for j in jobs}
    assert all(ms is not None for ms in matched.values())
    result = {}
    for policy, accepted in [('equivalent_only', ('equivalent',)),
                             ('broader_counted_as_hit', ('equivalent', 'broader'))]:
        rows = [score_item(p, refs[(p['dialogue_id'], p['direction'])],
                           matched[(p['dialogue_id'], p['direction'])], costs,
                           accepted_relations=accepted) for p in ps]
        assert len(rows) == 1788 and not any(r['missing_usage_attempts'] for r in rows)
        table = [dict(method=m, **four_metrics([r for r in rows if r['method'] == m])) for m in METHODS]
        assert all(r['true_reference_attributes'] == 588 and r['grounded_reference_attributes'] == 262
                   and r['single_sided_inputs'] == 298 for r in table)
        folder = OUTPUT / policy
        save(folder / 'per_input.json', rows)
        save(folder / 'four_metrics.json', table)
        result[policy] = table
    lines = ['# prompts-v2 重新语义评价结果', '',
             '固定六算法 7,019 条预测，298 段 A→B；参考 588 条，其中 E1/E2 为 262 条。', '',
             '模型 qwen3.8-flash，temperature=0，enable_thinking=true，thinking_budget=512，max_tokens=4096。',
             'Precision 按原始输出计数；Recall 和 Grounded Recall 采用最大一对一匹配。',
             '平均 token 为原算法实际推断成本/298，不包含本轮语义评价成本。', '',
             'broader 指参考蕴含预测；宽松表的 Grounded Recall 继承匹配参考的 E1/E2 等级。', '']
    audit_path = OUTPUT / 'parser_replay_audit.json'
    if audit_path.exists():
        audit = read(audit_path)
        lines += ['沿用旧评价器 validate_matches，对每条请求选择首个符合旧结构的完整响应；不改写语义判断。',
                  f"提示词格式偏离共 {len(audit['prompt_contract_deviations'])} 项，详见 parser_replay_audit.json。原始响应与原校验标记均保留。", '']
    for policy, table in result.items():
        lines += ['## ' + policy, '', '| 算法 | Precision | Recall | Grounded Recall | 平均 token |',
                  '|---|---:|---:|---:|---:|']
        for r in table:
            lines.append(f"| {r['method']} | {r['precision']:.4%} | {r['recall']:.4%} | {r['grounded_recall']:.4%} | {r['mean_tokens']:.6f} |")
        lines += ['', '| 算法 | 正确输出/输出 | 恢复参考/588 | 恢复有据参考/262 |', '|---|---:|---:|---:|']
        for r in table:
            lines.append(f"| {r['method']} | {r['correct_output_assertions']}/{r['output_assertions']} | {r['recovered_reference_attributes']}/588 | {r['recovered_grounded_reference_attributes']}/262 |")
        lines.append('')
    (OUTPUT / 'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    save(OUTPUT / 'four_metrics_both_policies.json', result)
    print('Complete: ' + str(OUTPUT / 'REPORT.md'), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--workers', type=int, default=12)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--replay-recorded', action='store_true')
    args = parser.parse_args()
    if args.replay_recorded:
        print(replay_recorded())
    elif args.prepare_only:
        _, _, jobs = prepare()
        print(dict(dialogues=len(jobs), api_dialogues=sum(bool(j['pp'] and j['rr']) for j in jobs)))
    else:
        print(run(args.workers, args.limit))
