"""Check request boundaries and report the completed AGD append."""
from collections import Counter
import csv
import json

from isc113 import common
from .infer import INFER_SYSTEM, MODEL, RECON, RECON_SYSTEM, ROOT, WORK, inputs, transcript

OUT = WORK / 'results'
METRICS = {
    'P_raw': 'P_raw',
    'R_full': 'R_full',
    'R_E1_full': 'E1 Recall',
    'R_E2_full': 'E2 Recall',
    'slot_coverage': 'Slot Coverage',
    'useful_yield': 'Useful Yield',
}


def csv_rows(name):
    with (OUT / name).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(name, rows, fields=None):
    if fields is None:
        fields = list(rows[0])
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def verify_inference():
    rows, layouts = inputs()
    exports = {row['dialogue_id']: row for row in common.read(WORK / 'exports/dailydialog.json')}
    transcripts = {row['dialogue_id']: row['turns'] for row in
                   common.read(WORK / 'exports/reconstructed_dialogues.json')}
    reconstructed = 0

    def checkpoint(did, stage, expected_payload, system):
        record = common.read(WORK / 'flash' / did / f'{stage}.json')
        request = record['request']
        expected_messages = [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': json.dumps(expected_payload, ensure_ascii=False)},
        ]
        if request['messages'] != expected_messages or request['model'] != MODEL:
            raise ValueError(f'Unexpected input in Flash request: {did} {stage}')
        if record['request_id'] != common.digest(request):
            raise ValueError(f'Flash request hash mismatch: {did} {stage}')
        return record

    for row in rows:
        did = row['dialogue_id']
        result = common.read(WORK / 'inference' / f'{did}.json')
        masked = transcript(row, layouts[did])
        rebuilt = masked.copy()
        tasks = []
        for index, turn in enumerate(masked):
            if turn['source'] != 'masked_B':
                continue
            record = checkpoint(did, f'reconstruct_{turn["turn_id"]:02d}', {
                'target_turn_id': turn['turn_id'], 'transcript': masked[:index + 2],
            }, RECON_SYSTEM)
            rebuilt[index] = dict(turn, source='reconstructed_B', text=record['output']['text'].strip())
            tasks.append(record['request_id'])
            reconstructed += 1
        attribute = checkpoint(did, RECON, {'transcript': rebuilt}, INFER_SYSTEM)
        prediction, = result['predictions']
        if (result['masked_transcript'] != masked or result['reconstructed_transcript'] != rebuilt
                or transcripts[did] != rebuilt
                or prediction != exports[did] or prediction['method'] != RECON
                or prediction['claims'] != attribute['output']['claims']
                or prediction['task_ids'] != tasks + [attribute['request_id']]):
            raise ValueError(f'Inference output differs from its requests: {did}')
    return reconstructed


def verify_judge_requests(base):
    from .evaluate import agd, append

    for stage, keys, system, budget in (
        ('append_pred', {'visible_turns', 'candidates'}, agd.SUPPORT_SYSTEM, 4096),
        ('append_coverage', {'visible_turns', 'atoms', 'frozen_facts'}, append.MATCH_SYSTEM, 8192),
    ):
        for path in (WORK / 'calls' / stage).glob('*/*.json'):
            binding = common.read(path)['binding']
            payload = binding['payload']
            if (set(payload) != keys or payload['visible_turns'] != base['dialogues'][path.parent.name]['visible_turns']
                    or binding['system'] != system or binding['model'] != agd.MODEL_DEFAULT
                    or binding['thinking_budget'] != budget or binding['temperature'] != 0):
                raise ValueError(f'Unexpected Max scoring request: {path}')


def attribution(base):
    from .evaluate import agd

    outside, slots, uncertain = [], [], []
    counts = Counter()
    for did, d in base['dialogues'].items():
        pred = {x['id']: x for x in agd.read(agd.path_for(WORK, 'pred', did))['items']}
        pool = agd.read(agd.path_for(WORK, 'pool', did))['facts']
        mapped = {member['atom_id'] for fact in pool for member in fact['members']}
        decisions = {x['atom_id']: x for x in agd.read(WORK / 'coverage' / f'{did}.json')['assignments']}
        new = {candidate['id'] for candidate in d['append_candidates']}
        active = set()
        predictions = [p for p in d['predictions'] if p['algorithm'] == RECON]
        counts['zero_output_dialogues'] += int(not predictions)
        for p in predictions:
            item = pred[p['candidate_id']]
            counts['new_judgment_predictions' if item['id'] in new else 'reused_judgment_predictions'] += 1
            for index, atom in enumerate(item['atoms']):
                aid = item['id'] + '::' + str(index)
                detail = {
                    'dialogue_id': did, 'prediction_id': p['id'], 'prediction': p['claim'],
                    'atom_id': aid, 'atom_claim': atom['text'], 'label': atom['label'],
                    'turn_ids': json.dumps(atom['turn_ids']), 'human_decision': '',
                }
                if atom['label'] in agd.VALID:
                    counts['grounded_atom_occurrences'] += 1
                    if aid in mapped:
                        active.add(aid)
                    else:
                        outside.append(dict(detail, reason=decisions[aid]['reason']))
                elif atom['label'] == 'UNCERTAIN':
                    uncertain.append(dict(detail, reason=atom['reason']))
        for fact in pool:
            covered = {sid for member in fact['members'] if member['atom_id'] in active
                       for sid in member['slot_ids']}
            for slot in fact['slots']:
                slots.append({
                    'dialogue_id': did, 'fact_id': fact['id'], 'canonical_claim': fact['canonical_claim'],
                    'slot_id': slot['id'], 'name': slot['name'], 'value': slot['value'],
                    'core': int(slot['core']), 'required': int(slot['required']),
                    'weight': slot['weight'], 'hit': int(slot['id'] in covered),
                })
    fields = ['dialogue_id', 'prediction_id', 'prediction', 'atom_id', 'atom_claim',
              'label', 'turn_ids', 'human_decision', 'reason']
    write_csv('outside_pool_grounded_atoms.csv', outside, fields)
    write_csv('human_review_queue.csv', uncertain, fields)
    write_csv('per_slot_append.csv', slots)
    if len(slots) != 3985 or sum(row['weight'] for row in slots) != 6352:
        raise ValueError('Slot report differs from frozen denominators')
    return dict(counts, outside_grounded_atom_occurrences=len(outside), uncertain_atom_occurrences=len(uncertain))


def model_usage():
    usage = {}
    for filename in ('attempts_flash.jsonl', 'attempts.jsonl'):
        for row in common.jsonlines(ROOT / filename):
            stage = row['stage']
            group = (
                'reconstruction' if stage.startswith('reconstruct_')
                else 'attribute_inference' if stage == RECON
                else 'stopped_a_only_pilot' if stage == 'one_sided_direct_matched'
                else stage
            )
            count = usage.setdefault(group, Counter())
            count['logged_attempts'] += 1
            count['valid_attempts'] += int(row.get('valid', False))
            count['attempts_without_usage'] += int(not row.get('usage'))
            for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                count[key] += (row.get('usage') or {}).get(key, 0)
    return {stage: dict(values) for stage, values in usage.items()}


def report(base):
    from .evaluate import SNAPSHOT, append

    reconstructed = verify_inference()
    verify_judge_requests(base)
    summary = common.read(OUT / 'summary.json')
    baseline_summary = common.read(SNAPSHOT / 'summary.json')
    dialogues = csv_rows('per_dialogue.csv')
    original_rows = [row for row in dialogues if row['algorithm'] in baseline_summary]
    with (SNAPSHOT / 'per_dialogue.csv').open(encoding='utf-8-sig', newline='') as stream:
        if original_rows != list(csv.DictReader(stream)):
            raise ValueError('Historical per-dialogue scores changed')
    counts = {name: Counter() for name in base['methods']}
    for row in dialogues:
        counts[row['algorithm']].update({
            key: int(value) for key, value in row.items() if key not in ('dialogue_id', 'algorithm')
        })
    metrics = []
    aggregate = []
    for method, name in base['methods'].items():
        values = summary[method]
        counts_for_method = dict(counts[method])
        if method in baseline_summary and counts_for_method != baseline_summary[method]['counts']:
            raise ValueError(f'Historical aggregate counts changed: {method}')
        values['counts'] = counts_for_method
        if (values['n_dialogues'], values['denom_pool'], values['denom_E1'], values['denom_E2']) != (298, 1630, 511, 1119):
            raise ValueError(f'Wrong fact denominator: {method}')
        metrics.append({
            'algorithm': name, **{key: values[key] for key in METRICS},
            'raw_predictions': values['raw_predictions'], 'grounded_raw': values['grounded_raw'],
            'P_atom': values['P_atom'], 'R_core': values['R_core'],
            'R_full_CI95_low': values['R_full_CI95_dialogue_bootstrap'][0],
            'R_full_CI95_high': values['R_full_CI95_dialogue_bootstrap'][1],
        })
        aggregate.append({'algorithm': name, **counts_for_method})
    prediction_rows = csv_rows('per_prediction.csv')
    if (len(dialogues) != 298 * 7 or len(csv_rows('per_fact.csv')) != 1630 * 7
            or Counter(row['algorithm'] for row in prediction_rows) != base['prediction_counts']):
        raise ValueError('Incomplete score tables')
    diagnostics = attribution(base)
    diagnostics['ungrounded_predictions_by_label'] = dict(Counter(
        label for row in prediction_rows if row['algorithm'] == RECON and row['all_grounded'] == '0'
        for label in sorted(set(row['labels'].split('|')) - {'E1', 'E2'})
    ))
    usage = model_usage()
    append.verify_sources()
    common.save(OUT / 'summary.json', summary)
    common.save(OUT / 'append_diagnostics.json', diagnostics)
    common.save(OUT / 'model_usage.json', usage)
    common.save(OUT / 'delivery_checks.json', {
        'dialogues': 298, 'methods': 7, 'new_methods': 1, 'reconstructed_B_turns': reconstructed,
        'facts': 1630, 'slots': 3985, 'slot_weight': 6352, 'E1': 511, 'E2': 1119,
        'original_facts_slots_and_members_verified': True, 'historical_scores_identical': True,
        'hidden_turn_text_and_word_counts_excluded': True, 'judge_observed_A_only': True,
        'human_calibrated': False,
    })
    write_csv('combined_metrics.csv', metrics)
    write_csv('aggregate_counts.csv', aggregate)
    write_report(metrics, summary[RECON], reconstructed, diagnostics, usage)


def write_report(metrics, result, reconstructed, diagnostics, usage):
    def percent(value):
        return '—' if value is None else f'{value:.2%}'

    c = result['counts']
    low, high = result['R_full_CI95_dialogue_bootstrap']
    pilot = usage.get('stopped_a_only_pilot', {})
    lines = [
        '# DailyDialog 逐轮重建与 AGD 追加评价',
        '',
        f'在 298 段冻结对话中，Qwen3.8-Flash 重建了 {reconstructed:,} 个 B 话轮。'
        f'A+B 生成 {result["raw_predictions"]:,} 条属性预测，'
        f'其中 {result["grounded_raw"]:,} 条通过 Qwen3.8-Max 的 A-only 有据审核。',
        '',
        '## 方法',
        '',
        '采用 Ebert 等人论文表 2 中 DailyDialog 无词数设置下的最佳重建条件。'
        '论文该条件使用 Claude-4-Sonnet，本次实验按要求使用 Qwen3.8-Flash。'
        '独立预测每个 B 话轮，输入包括此前完整的 A 单侧历史、历史遮盖位置和紧随其后的 A 话轮。'
        '未知具体信息用 XXXXXXX。末尾 B 无后续 A 时使用已有历史。'
        '完整语料仅用于核对 A 及确定遮盖位置，模型请求未包含真实 B 发言或任何遮盖话轮的词数。',
        '',
        '随后按原顺序合并原始 A 和明确标注为假设的重建 B，再用 Qwen3.8-Flash 提取属性。'
        'Qwen3.8-Max 使用原 AGD 提示词审查较原预测库新增的候选文本，并将有据原子映射到冻结字段。'
        '已有同文候选复用原审核及映射。原 1,630 个事实、3,985 个字段及原映射逐项校验通过。',
        '',
        '## 结果',
        '',
        '| 算法 | ' + ' | '.join(METRICS.values()) + ' |',
        '| ' + ' | '.join(['---'] * (len(METRICS) + 1)) + ' |',
    ]
    for row in metrics:
        lines.append('| ' + row['algorithm'] + ' | ' + ' | '.join(percent(row[key]) for key in METRICS) + ' |')
    lines.extend([
        '',
        f'A+B 完整覆盖 {c["pool_full"]:,}/1,630 个事实，'
        f'E1 为 {c["E1_full"]:,}/511，E2 为 {c["E2_full"]:,}/1,119。'
        f'加权字段覆盖为 {c["slot_weight_hit"]:,}/6,352。'
        f'完整召回率的对话 bootstrap 95% 区间为 {low:.2%}–{high:.2%}（2,000 次）。',
        '',
        f'有据率{"达到" if result["P_raw"] >= .9 else "低于"} AGD 的 90% 门槛。'
        f'未通过的 {result["raw_predictions"] - result["grounded_raw"]} 条预测中，'
        f'{diagnostics["ungrounded_predictions_by_label"].get("E3", 0)} 条含有证据不足的 E3 原子。'
        f'池外有据原子出现 {diagnostics["outside_grounded_atom_occurrences"]} 次，'
        '这些原子保留有据判定。池内召回与字段覆盖的分母保持固定。'
        '六个历史算法指标全部复核一致，可用于描述性参照。'
        '本轮只有一个新条件，无法单独估计重建带来的增益。评价为自动裁定，尚未经人工校准。',
        '',
        '## 用量与复现',
        '',
        f'正式 Flash 重建与推理合计返回 {sum(usage.get(stage, {}).get("total_tokens", 0) for stage in ("reconstruction", "attribute_inference")):,} token。'
        f'Max 评价合计返回 {sum(usage.get(stage, {}).get("total_tokens", 0) for stage in ("append_pred", "append_coverage")):,} token，以上均包含已记录的重试用量。',
        '',
        f'已停止的先期 A-only 对照记录 {pilot.get("logged_attempts", 0)} 次请求，'
        f'服务返回用量 {pilot.get("total_tokens", 0):,} token。'
        '该对照未进入正式评分。停止时仍在途的请求与两次连通性探测没有完整计量。',
        '',
        '在仓库根目录依次运行以下命令。在线步骤从进程环境或终端隐藏输入读取凭据。',
        '',
        '    python -B -m isc113.agd_append_1sc_20261123.infer',
        '    python -B -m isc113.agd_append_1sc_20261123.evaluate judge',
        '    python -B -m isc113.agd_append_1sc_20261123.evaluate score',
        '',
        '[论文原文](https://aclanthology.org/2026.findings-acl.1757/) · '
        '[A+B 重建对话](work/exports/reconstructed_dialogues.json) · '
        '[指标表](work/results/combined_metrics.csv) · [分子分母](work/results/aggregate_counts.csv) · '
        '[逐条预测](work/results/per_prediction.csv) · [字段明细](work/results/per_slot_append.csv) · '
        '[池外有据原子](work/results/outside_pool_grounded_atoms.csv) · [模型用量](work/results/model_usage.json)',
    ])
    (ROOT / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines[:25]))
