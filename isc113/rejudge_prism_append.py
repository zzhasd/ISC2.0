#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Append PRISM as a SIXTH ISC113 experiment, WITHOUT changing 5 frozen runs.

Place ``PRISM.py`` and this file next to original ISC113:
    common.py, client.py, rejudge_njl_five.py, prompts-v2.py,
    inputs/dailydialog.json, references/dailydialog_human_adjudicated_588.json

Recommended commands (from the ISC113 source directory):
    python -m pip install requests tqdm
    export QWEN_API_KEY=...                   # Windows: set QWEN_API_KEY=...
    python rejudge_prism_append.py --mode all
    python rejudge_prism_append.py --mode infer --limit 3 --run-id prism_smoke
    python rejudge_prism_append.py --mode judge

The ONLY JUDGE prompt is imported from rejudge_njl_five.load_match_prompt
(prompts-v2.py). Judge payload/validation/score/attempt persistence are
reused EXACTLY from rejudge_njl_five.py. Only the NEW method is inferred and
rejudged. Original five runs/results are NEVER rewritten.

Data leakage protection: inference path imports no references or match scores;
judge only starts AFTER the independent 298-input prediction export is frozen.
The five baseline scores may be compared by supplying --baseline-results,
but they are NEVER provided to PRISM inference or to the judge.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import getpass
import hashlib
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import sys
import threading
import types
from typing import Any

HERE = Path(__file__).resolve().parent
LABEL = 'prism_v1'
DISPLAY = 'PRISM v1 (Scoped Evidence)'
RUN_ID_DEFAULT = 'prism_matched_v11'
JUDGE_DIR_DEFAULT = 'runs/njl_prism_matched_v11_qwen38max_prompts_v2'

# "matched" aligns per-call thinking with the 512-token baseline and the
# Evidence-Adaptive v3 generation/review output ceiling (3072); its global
# semantic clustering request uses up to 8192, analogous to a longer verifier.
# There is no single all-five inference max_tokens: methods have varied caps.
INFERENCE_PROFILES = {
    'matched': {'thinking_budget': 512, 'generation_max_tokens': 3072,
                'review_max_tokens': 3072, 'cluster_max_tokens': 8192},
    'enhanced': {'thinking_budget': 2048, 'generation_max_tokens': 8192,
                 'review_max_tokens': 8192, 'cluster_max_tokens': 12288},
}

# This import is intentionally safe: no input/reference files read on import.
import rejudge_njl_five as judge


def algorithm_and_project():
    """Make sibling files behave as the original ISC113 package does."""
    pkg_name = '_prism_project'
    if pkg_name not in sys.modules:
        pkg = types.ModuleType(pkg_name)
        pkg.__path__ = [str(HERE)]
        pkg.__package__ = pkg_name
        sys.modules[pkg_name] = pkg
    common = importlib.import_module(pkg_name + '.common')
    client_module = importlib.import_module(pkg_name + '.client')
    path = HERE / 'PRISM.py'
    if not path.is_file():
        raise FileNotFoundError(f'未找到 PRISM 独立算法: {path}')
    spec = importlib.util.spec_from_file_location(pkg_name + '.prism', path)
    if spec is None or spec.loader is None:
        raise RuntimeError('PRISM.py 无法导入')
    if spec.name in sys.modules:
        alg = sys.modules[spec.name]
    else:
        alg = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = alg
        spec.loader.exec_module(alg)
    return common, client_module, alg


def key_from_user() -> str:
    key = os.getenv('QWEN_API_KEY') or os.getenv('DASHSCOPE_API_KEY')
    if not key and sys.stdin.isatty():
        key = getpass.getpass('请输入 Qwen DashScope API Key（不会回显）：').strip()
    if not key:
        raise RuntimeError('缺少 QWEN_API_KEY / DASHSCOPE_API_KEY')
    return key


class ResilientInferenceClient:
    """Use the original Client ledger; recover COMPLETE JSON wrappers only.

    Does not invent missing claims, repair incomplete semantics or resubmit
    an interrupted in-flight request with unknown billing status. A new
    logical request is attempted only after a fully exhausted prior round.
    """
    def __init__(self, base_client, max_rounds: int = 2):
        self.base = base_client
        self.max_rounds = max_rounds

    def _recover(self, name: str, payload: dict, validator):
        # Client uses common.digest with JSON sort_keys=True, ensure_ascii=False
        digest = hashlib.sha256(json.dumps(
            {'logical_name': name, 'payload': payload},
            sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
        with self.base.lock:
            rows = [r for r in self.base.rows if r.get('task_id') == digest and
                    r.get('event') == 'complete' and r.get('http_status') == 200]
        for row in rows:
            body = row.get('body', {})
            try:
                choice = body['choices'][0]
                if choice.get('finish_reason') != 'stop':
                    continue
                content = choice['message'].get('content', '')
                if not isinstance(content, str):
                    continue
                decoder = json.JSONDecoder()
                # Only parse a complete object; validate all required IDs.
                for marker in re.finditer(r'\{', content):
                    try:
                        obj, _ = decoder.raw_decode(content, marker.start())
                        return validator(obj), digest
                    except (ValueError, TypeError, KeyError, AttributeError):
                        pass
            except (TypeError, KeyError, IndexError):
                continue
        return None

    def call(self, logical_name: str, payload: dict, validator):
        for attempt in range(self.max_rounds):
            name = logical_name if attempt == 0 else f'{logical_name}/format_round_{attempt}'
            recovered = self._recover(name, payload, validator)
            if recovered is not None:
                return recovered
            try:
                return self.base.call(name, payload, validator)
            except Exception as err:
                recovered = self._recover(name, payload, validator)
                if recovered is not None:
                    return recovered
                if 'Attempt limit exceeded' not in str(err) or attempt + 1 == self.max_rounds:
                    raise
        raise RuntimeError('Inference format retries exhausted')


def load_inputs(common, limit: int | None = None) -> list[dict]:
    path = HERE / 'inputs' / 'dailydialog.json'
    if not path.is_file():
        raise FileNotFoundError(f'缺失原始冻结的 A-only 输入（ZIP 不包含该文件）：{path}')
    records = common.read(path)
    if len(records) != 298 or len({r['item_id'] for r in records}) != 298:
        raise RuntimeError('需要完整 298 段唯一 A-only 冻结输入')
    for r in records:
        common.validate_input(r)
    return records if limit is None else records[:limit]


def inference_manifest(alg, args) -> dict:
    source = HERE / 'inputs' / 'dailydialog.json'
    if not source.is_file():
        raise FileNotFoundError(f'缺少冻结输入，不能开始推断：{source}')
    return {
        'version': 'prism-inference-freeze-v1',
        'run_id': args.run_id,
        'algorithm_method': alg.METHOD,
        'algorithm_version': alg.VERSION,
        'algorithm_sha256': judge.sha_bytes((HERE / 'PRISM.py').read_bytes()),
        'input_sha256': judge.sha_bytes(source.read_bytes()),
        'model': alg.MODEL,
        'endpoint': args.inference_endpoint or args.endpoint,
        'inference_profile': args.inference_profile,
        'thinking_budget': alg.THINKING_BUDGET,
        'max_tokens': alg.GENERATION_MAX_TOKENS,
        'generation_max_tokens': alg.GENERATION_MAX_TOKENS,
        'review_max_tokens': alg.REVIEW_MAX_TOKENS,
        'cluster_max_tokens': alg.CLUSTER_MAX_TOKENS,
        'generation_temperature': 0,
        'direction': 'A_to_B',
        'dataset': 'dailydialog',
    }


def freeze_inference_manifest(run_folder: Path, alg, args):
    manifest = inference_manifest(alg, args)
    path = run_folder / 'inference_manifest.json'
    if path.is_file():
        if judge.read_json(path) != manifest:
            raise RuntimeError('推断算法/源文件/参数或输入与现有 run-id 不一致；必须使用新 run-id')
    else:
        judge.atomic_json(path, manifest)


def check_judge_provenance(run_folder: Path, alg):
    path = run_folder / 'inference_manifest.json'
    if not path.is_file():
        raise RuntimeError('缺少 PRISM 推断冻结清单，不能证明预测对应哪版算法')
    old = judge.read_json(path)
    if (old.get('algorithm_sha256') != judge.sha_bytes((HERE / 'PRISM.py').read_bytes()) or
        old.get('algorithm_method') != alg.METHOD or
        old.get('model') != alg.MODEL):
        raise RuntimeError('推断冻结清单与当前算法不一致，拒绝错误归因')
    if old.get('algorithm_version') != alg.VERSION:
        raise RuntimeError('推断算法版本不一致')
    input_file = HERE / 'inputs' / 'dailydialog.json'
    if input_file.is_file() and judge.sha_bytes(input_file.read_bytes()) != old.get('input_sha256'):
        raise RuntimeError('冻结 A-only 输入已改变')


def prediction_path(run_folder: Path, item: dict) -> Path:
    return run_folder / 'predictions' / f'{item["dialogue_id"]}__A_to_B.json'


def validated_single_prediction(path: Path, item: dict, method: str) -> dict | None:
    if not path.is_file():
        return None
    rows = judge.read_json(path)
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError(f'预测缓存结构错误，拒绝覆盖：{path}')
    p = rows[0]
    if (p.get('method') != method or
        any(p.get(k) != item[k] for k in ('item_id','dialogue_id','direction','dataset')) or
        not isinstance(p.get('claims'), list)):
        raise ValueError(f'预测缓存方法/身份不匹配：{path}')
    for c in p['claims']:
        if not isinstance(c, dict) or not isinstance(c.get('claim'), str) or not c['claim'].strip():
            raise ValueError(f'预测中的事实非法：{path}')
        cf = c.get('confidence')
        if type(cf) not in (int, float) or not 0 <= cf <= 1:
            raise ValueError(f'预测 confidence 非法：{path}')
        evidence = c.get('evidence')
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f'预测无原文证据：{path}')
        by = {t['turn_id']: t['text'] for t in item['visible_turns']}
        if any(not isinstance(e, dict) or e.get('turn_id') not in by or
               not isinstance(e.get('quote'), str) or not e['quote'].strip() or
               e['quote'] not in by[e['turn_id']] for e in evidence):
            raise ValueError(f'预测证据引用无效：{path}')
    return p


def infer(common, clientmod, alg, records: list[dict], args, run_folder: Path) -> bool:
    # No reference or evaluation files are imported/read by this function.
    pending = [item for item in records if validated_single_prediction(
        prediction_path(run_folder, item), item, alg.METHOD) is None]
    print(f'[PRISM 推断] 目标 {len(records)}；缓存 {len(records)-len(pending)}；待执行 {len(pending)}', flush=True)
    if not pending:
        return True
    key = key_from_user()
    client = ResilientInferenceClient(clientmod.Client(key, run_id=args.run_id), args.inference_retry_rounds)
    stop = threading.Event()
    errors = []
    def run_one(item):
        if stop.is_set():
            return
        prediction, diagnostic = alg.pipeline(client, item)
        if prediction['method'] != alg.METHOD:
            raise ValueError('Wrong algorithm method')
        ppath = prediction_path(run_folder, item)
        # Verify raw prediction with the same constraints before caching.
        # Atomic writes stop half-completed files being taken as successes.
        if not isinstance(prediction.get('claims'), list):
            raise ValueError('Missing output claims')
        for c in prediction['claims']:
            if not c.get('evidence'):
                raise ValueError('PRISM emitted claim without literal evidence')
        judge.atomic_json(run_folder / 'diagnostics' / f'{item["dialogue_id"]}__A_to_B.json', diagnostic)
        judge.atomic_json(ppath, [prediction])
        validated_single_prediction(ppath, item, alg.METHOD)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = {pool.submit(run_one, item): item for item in pending}
        from tqdm import tqdm
        with tqdm(total=len(pending), desc='PRISM 推断', unit='段') as bar:
            for job in as_completed(jobs):
                try:
                    job.result()
                except Exception as exc:
                    errors.append({'item_id': jobs[job]['item_id'], 'error': f'{type(exc).__name__}: {exc}'})
                bar.update(1)
                bar.set_postfix(failed=len(errors))
    judge.atomic_json(run_folder / 'inference_errors.json', errors)
    if errors:
        print(f'[PRISM 推断] 未全部完成（失败 {len(errors)} 段），成功缓存可续跑。', flush=True)
        return False
    return True


def export_freeze(common, alg, records: list[dict], run_folder: Path) -> Path:
    if len(records) != 298:
        raise RuntimeError('不允许把部分 smoke 预测导出为正式 298 对话结果')
    rows = []
    for item in records:
        pred = validated_single_prediction(prediction_path(run_folder, item), item, alg.METHOD)
        if pred is None:
            raise RuntimeError(f'预测缺失：{item["dialogue_id"]}')
        rows.append(pred)
    path = run_folder / 'exports' / 'dailydialog.json'
    # The frozen export is immutable: no silent overwrite of judge inputs.
    if path.is_file():
        if judge.read_json(path) != rows:
            raise RuntimeError('冻结导出被改变，必须另起 run-id，不能混合旧评测缓存')
    else:
        judge.atomic_json(path, rows)
    return path


def prepare_judge_task(args, original: dict, gold: list[dict], prompt: str) -> judge.Task:
    unique = {judge.sha_obj(c['claim']): c['claim'] for c in original['claims']}
    predictions = [{'prediction_id': h, 'claim': text} for h, text in sorted(unique.items())]
    references = [{'claim_id': r['claim_id'], 'claim': r['claim']} for r in gold]
    content = {
        'predictions': predictions, 'reference': references,
        'subject_mapping': judge.SUBJECT_MAPPING,
        'persona_reference_rule': judge.PERSONA_RULE,
        'matcher_prompt_sha256': judge.sha_obj(prompt),
    }
    payload = {
        'model': judge.MODEL, 'temperature': judge.TEMPERATURE,
        'enable_thinking': True, 'thinking_budget': args.thinking_budget,
        'max_tokens': args.max_tokens,
        'messages': [
            {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': json.dumps(content, ensure_ascii=False)},
        ],
    }
    binding = judge.sha_obj({
        'payload': payload, 'endpoint': args.endpoint, 'version': judge.VERSION,
        'method': LABEL, 'dialogue_id': original['dialogue_id'],
        'direction': original['direction'],
    })
    return judge.Task(LABEL, DISPLAY, original['dialogue_id'], original['direction'],
                      tuple(predictions), tuple(references), payload, binding)


def load_frozen_judge_inputs(args, alg, run_folder: Path):
    """No inputs or gold may be read by inference; this is called afterwards."""
    export = run_folder / 'exports' / 'dailydialog.json'
    if not export.is_file():
        raise FileNotFoundError(f'缺少完整冻结导出，请先推断：{export}')
    rows = judge.read_json(export)
    if not isinstance(rows, list) or len(rows) != 298:
        raise RuntimeError('评测必须完整使用 298 段冻结预测')
    by_key = {}
    for row in rows:
        if not isinstance(row, dict) or row.get('dataset') != 'dailydialog' or row.get('direction') != 'A_to_B' or row.get('method') != alg.METHOD:
            raise ValueError('冻结预测身份/方法不正确')
        key = (row['dialogue_id'], row['direction'])
        if key in by_key or not isinstance(row.get('claims'), list):
            raise ValueError('重复/非法的预测组')
        for c in row['claims']:
            if not isinstance(c, dict) or not isinstance(c.get('claim'), str) or not c['claim'].strip():
                raise ValueError('空预测')
            cf = c.get('confidence')
            if type(cf) not in (int, float) or not 0 <= cf <= 1:
                raise ValueError('输出置信度不合法')
        by_key[key] = row
    refpath = HERE / judge.REFERENCE_FILE
    if not refpath.is_file():
        raise FileNotFoundError(f'ZIP 不含人工裁决参考，需从原项目恢复：{refpath}')
    gold_rows = judge.read_json(refpath)
    if not isinstance(gold_rows, list):
        raise ValueError('reference 不为 list')
    refs = {}
    for row in gold_rows:
        if row.get('dataset') != 'dailydialog' or row.get('direction') != 'A_to_B':
            raise ValueError('参考数据集/方向不对')
        key = (row['dialogue_id'], row['direction'])
        if key in refs or not isinstance(row.get('claims'), list):
            raise ValueError('参考重复键/格式错误')
        claim_ids = set()
        for c in row['claims']:
            if c.get('claim_id') in claim_ids or c.get('truth') != 'true' or c.get('evidence_level') not in ('E1','E2','E3','E4') or c.get('review_status', 'reviewed') != 'reviewed':
                raise ValueError('参考未裁决/重复/非法')
            claim_ids.add(c['claim_id'])
        refs[key] = row['claims']
    expected = (298, 588, 262)
    found = (len(refs), sum(len(g) for g in refs.values()),
             sum(c['evidence_level'] in ('E1','E2') for g in refs.values() for c in g))
    if found != expected or set(refs) != set(by_key):
        raise RuntimeError(f'冻结参考或预测不一致：{found} != {expected}')
    prompt, prompt_sha = judge.load_match_prompt()
    tasks = [prepare_judge_task(args, by_key[k], refs[k], prompt) for k in sorted(refs)]
    manifest = {
        'version': 'njl-prism-append-1', 'created_by': 'rejudge_prism_append.py',
        'algorithm': DISPLAY, 'label': LABEL, 'method': alg.METHOD,
        'inference_model': alg.MODEL, 'inference_version': alg.VERSION,
        'inference_file_sha256': judge.sha_bytes((HERE/'PRISM.py').read_bytes()),
        'inference_config': judge.read_json(run_folder / 'inference_manifest.json'),
        'input_export': str(export.relative_to(HERE)),
        'export_sha256': judge.sha_bytes(export.read_bytes()),
        'model': judge.MODEL, 'temperature': judge.TEMPERATURE,
        'enable_thinking': True, 'thinking_budget': args.thinking_budget,
        'max_tokens': args.max_tokens, 'endpoint': args.endpoint,
        'matching_version': judge.VERSION,
        'prompt_file': 'prompts-v2.py', 'prompt_file_sha256': prompt_sha,
        'matcher_prompt_sha256': judge.sha_obj(prompt),
        'reference_file': str(judge.REFERENCE_FILE),
        'reference_sha256': judge.sha_bytes(refpath.read_bytes()),
        'dataset': 'dailydialog', 'direction': 'A_to_B',
        'dialogues_per_method': 298, 'reference_attributes': 588,
        'grounded_reference_attributes': 262,
        'scoring': {'strict_relations': ['equivalent'],
                    'loose_relations': ['equivalent', 'broader'],
                    'precision': 'correct ORIGINAL prediction count / total ORIGINAL count',
                    'recall': 'max bipartite match / 588',
                    'grounded_recall': 'independent max bipartite E1/E2 match / 262'},
    }
    return refs, by_key, tasks, manifest


def baseline_compare(base: Path | None, manifest: dict, summary: dict, out: Path) -> list[str]:
    names = [
        ('Direct Thinking','direct_thinking'),
        ('Dual Without Verifier','dual_without_verifier'),
        ('Evidence-Adaptive v3','evidence_adaptive_v3'),
        ('ELARA v1','elara_v1'),
        ('ELARA v2','elara_v2'),
    ]
    notes = []
    methods = [(DISPLAY, LABEL, summary)]
    if base is not None:
        old_manifest = base / 'manifest.json'
        if not old_manifest.is_file():
            notes.append(f'未找到五算法基线 manifest，跳过比较：{base}')
        else:
            old = judge.read_json(old_manifest)
            required = ('reference_sha256', 'prompt_file_sha256', 'matcher_prompt_sha256',
                        'model', 'temperature', 'thinking_budget', 'max_tokens', 'endpoint')
            mismatched = [key for key in required if old.get(key) != manifest.get(key)]
            if mismatched:
                notes.append(f'基线配置不一致，未混合比较五算法（不同字段：{mismatched}）。'
                             'PRISM 自身评分仍完整保留。')
            else:
                for name, label in names:
                    p = base / 'scores' / label / 'summary.json'
                    if not p.is_file():
                        raise RuntimeError(f'缺少五算法得分：{p}')
                    methods.insert(-1, (name, label, judge.read_json(p)))
                notes.append('五算法比较使用已冻结的历史评分，不重新推理、不重新匹配。')
    compare = {'complete': True, 'methods': {label: scores for _, label, scores in methods},
               'new_manifest_sha256': judge.sha_obj(manifest), 'notes': notes}
    judge.atomic_json(out / 'six_algorithms_compare.json', compare)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['name', 'algorithm', 'policy', 'precision', 'recall', 'grounded_recall',
                     'correct_outputs', 'output_assertions', 'reference_hits', 'grounded_hits'])
    for display, label, scores in methods:
        for policy in ('strict', 'loose'):
            s = scores[policy]
            writer.writerow([display, label, policy, s['precision'], s['recall'],
                             s['grounded_recall'], s['correct_output_assertions'],
                             s['output_assertions'], s['recovered_reference_attributes'],
                             s['recovered_grounded_reference_attributes']])
    (out / 'six_algorithms_compare.csv').write_text('\ufeff' + buffer.getvalue(), encoding='utf-8')
    lines = ['# PRISM 统一 NJL 附加评测（与五算法同口径）', '',
             f'- 推断模型 `{manifest["inference_model"]}`；匹配模型 `{manifest["model"]}`。',
             f'- 固定 298 段 A→B、588 条参考、262 条 E1/E2 参考。',
             f'- 唯一匹配提示词 `{manifest["prompt_file"]}`，SHA256 `{manifest["prompt_file_sha256"]}`。',
             '- 严格等价（equivalent）或宽松（equivalent+broader），不包含 narrower。',
             '- 原始预测条数计入 Precision 分母；Recall/Grounded Recall 使用一对一二分匹配。',
             '- 本结果仅是对固定参考集的模型语义匹配评估，不是开放世界人工核验。', '']
    def pct(value):
        return 'N/A' if value is None else f'{value:.2%}'

    for policy, title in [('strict', '严格'), ('loose', '宽松')]:
        lines.extend([f'## {title}', '', '| 算法 | Precision | Recall | Grounded Recall | 预测条数 |',
                      '|---|---:|---:|---:|---:|'])
        for display, label, scores in methods:
            s = scores[policy]
            lines.append(f'| {display} | {pct(s["precision"])} | {pct(s["recall"])} | '
                         f'{pct(s["grounded_recall"])} | {s["output_assertions"]} |')
        lines.append('')
    lines += ['## 比较约束', ''] + notes
    (out / 'REPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return notes


def rejudge_new_method(args, alg, run_folder: Path, output: Path) -> bool:
    check_judge_provenance(run_folder, alg)
    refs, originals, tasks, manifest = load_frozen_judge_inputs(args, alg, run_folder)
    output.mkdir(parents=True, exist_ok=True)
    with judge.single_process_lock(output):
        mpath = output / 'manifest.json'
        if mpath.is_file():
            if judge.read_json(mpath) != manifest:
                raise RuntimeError('原评测 manifest 与算法/参考/prompt/模型不一致；请新建评测输出目录')
        else:
            judge.atomic_json(mpath, manifest)
        done = judge.count_done(output, tasks)
        print(f'[NJL 追加评测] 冻结输入=298；已评={done}；待评={len(tasks)-done}', flush=True)
        if args.dry_run:
            print('预检查完成，没有产生 API 请求。')
            return False
        if done < len(tasks):
            key = key_from_user()
            stop = threading.Event()
            evaluator = judge.Evaluator(key=key, out=output, args=args, stop=stop)
            errors, _ = judge.execute_method(output, LABEL, DISPLAY, tasks, evaluator,
                                             args.judge_workers, None, stop, phase='initial')
            if stop.is_set():
                raise RuntimeError(f'评测中遇到不可恢复异常：{errors}')
            missing = judge.count_done(output, tasks) < len(tasks)
            if missing:
                rest, _ = judge.execute_method(output, LABEL, DISPLAY, tasks, evaluator,
                                               args.judge_workers, None, stop, phase='final')
                errors += rest
            judge.atomic_json(output / 'new_method_eval_errors.json', errors)
        if judge.count_done(output, tasks) != len(tasks):
            print('存在未完成匹配；保留缓存，重新执行相同命令后才生成完整评分。', flush=True)
            return False
        summary = judge.score_full_method(LABEL, originals, refs, tasks, output)
        base = Path(args.baseline_results)
        if not base.is_absolute():
            base = HERE / base
        if not base.is_dir():
            base = None
        baseline_compare(base, manifest, summary, output)
        print('完成：' + str(output / 'REPORT.md'))
        return True


def main() -> int:
    parser = argparse.ArgumentParser(description='PRISM 新算法推断 + 同 rejudge_njl_five.py 口径的追加评测')
    parser.add_argument('--mode', choices=('all', 'infer', 'judge'), default='all')
    parser.add_argument('--run-id', default=RUN_ID_DEFAULT,
                        help='PRISM 预测 run-id；已有旧 run-id 不应混用')
    parser.add_argument('--workers', type=int, default=6, help='PRISM 推断并发数')
    parser.add_argument('--judge-workers', type=int, default=6, help='同一算法匹配并发数')
    parser.add_argument('--inference-retry-rounds', type=int, default=1,
                        help='原 Client 每轮最多3次；默认1轮以匹配原客户端，失败可另起 run-id 调整')
    parser.add_argument('--inference-profile', choices=tuple(INFERENCE_PROFILES),
                        default='matched', help='matched=原预算512/3072/3072/8192；enhanced=2048/8192/8192/12288')
    parser.add_argument('--inference-thinking-budget', type=int, default=None)
    parser.add_argument('--inference-generation-max-tokens', type=int, default=None)
    parser.add_argument('--inference-review-max-tokens', type=int, default=None)
    parser.add_argument('--inference-cluster-max-tokens', type=int, default=None)
    parser.add_argument('--inference-endpoint', default=None,
                        help='推断使用的完整 Chat Completions HTTP 地址；默认同评测 --endpoint')
    parser.add_argument('--limit', type=int, default=None, help='仅推断前 N 条作 smoke；不能正式评测')
    parser.add_argument('--output-dir', default=JUDGE_DIR_DEFAULT,
                        help='PRISM 独立评测输出目录，绝不覆写五算法基线')
    parser.add_argument('--baseline-results', default='runs/njl_qwen38max_prompts_v2',
                        help='原五算法统一评测目录；无此目录则只汇报 PRISM')
    parser.add_argument('--endpoint', default=judge.DEFAULT_ENDPOINT)
    parser.add_argument('--thinking-budget', type=int, default=8192)
    parser.add_argument('--max-tokens', type=int, default=12288)
    parser.add_argument('--timeout', type=int, default=240)
    parser.add_argument('--max-attempts', type=int, default=5)
    parser.add_argument('--final-retry-attempts', type=int, default=1)
    parser.add_argument('--dry-run', action='store_true', help='judge 模式只检查匹配/配置，不请求模型')
    parser.add_argument('--show-config', action='store_true',
                        help='打印实际两个模型/预算/端点/提示词哈希后退出，不请求模型、不读取私密输入')
    args = parser.parse_args()
    if any(v < 1 for v in (args.workers, args.judge_workers, args.inference_retry_rounds,
                            args.thinking_budget, args.max_tokens, args.timeout,
                            args.max_attempts, args.final_retry_attempts)):
        parser.error('并发、重试、tokens 等参数必须为正数')
    if args.limit is not None and (args.limit < 1 or args.limit > 298):
        parser.error('--limit 范围为 1..298')
    if args.limit is not None and args.mode != 'infer':
        parser.error('--limit 只能在 --mode infer 使用，不得把部分预测计入正式评测')
    if args.dry_run and args.mode != 'judge':
        parser.error('--dry-run 要搭配 --mode judge')

    common, clientmod, alg = algorithm_and_project()
    inference_settings = dict(INFERENCE_PROFILES[args.inference_profile])
    for param in ('thinking_budget', 'generation_max_tokens', 'review_max_tokens',
                  'cluster_max_tokens'):
        override = getattr(args, 'inference_' + param)
        if override is not None:
            if override < 1:
                parser.error(f'--inference-{param.replace("_", "-")} 必须是正整数')
            inference_settings[param] = override
    alg.configure_inference(**inference_settings)
    # Original client.py hardcodes a module-global URL. Setting it here ensures
    # inference and judgement actually use their declared endpoint(s).
    clientmod.URL = args.inference_endpoint or args.endpoint
    if args.show_config:
        prompt, prompt_sha = judge.load_match_prompt()
        snapshot = {
            'inference': {'model': alg.MODEL, 'enable_thinking': True,
                          'temperature': 0, 'profile': args.inference_profile,
                          'endpoint': clientmod.URL, **inference_settings,
                          'max_calls_per_dialogue': 'variable; not equal to the five baselines'},
            'evaluation': {'model': judge.MODEL, 'enable_thinking': True,
                           'temperature': judge.TEMPERATURE,
                           'thinking_budget': args.thinking_budget,
                           'max_tokens': args.max_tokens,
                           'endpoint': args.endpoint,
                           'workers': args.judge_workers,
                           'max_attempts': args.max_attempts,
                           'final_retry_attempts': args.final_retry_attempts,
                           'timeout_seconds': args.timeout,
                           'match_prompt_sha256': prompt_sha},
            'algorithm_file_sha256': judge.sha_bytes((HERE / 'PRISM.py').read_bytes()),
        }
        baseline_manifest = HERE / args.baseline_results / 'manifest.json'
        if baseline_manifest.is_file():
            historic = judge.read_json(baseline_manifest)
            compare_fields = ('model', 'temperature', 'thinking_budget', 'max_tokens', 'endpoint')
            snapshot['historic_judge_config_equal'] = all(
                historic.get(k) == snapshot['evaluation'].get(k) for k in compare_fields
            )
            snapshot['historic_prompt_sha256_equal'] = (
                historic.get('prompt_file_sha256') == prompt_sha
            )
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        return 0
    run_folder = common.run_folder(args.run_id)
    out = Path(args.output_dir)
    if not out.is_absolute():
        out = HERE / out
    if out.resolve() == run_folder.resolve():
        parser.error('评测缓存目录必须与推断 run-id 目录不同')

    if args.mode in ('infer', 'all'):
        with judge.single_process_lock(run_folder):
            records = load_inputs(common, args.limit)
            freeze_inference_manifest(run_folder, alg, args)
            succeeded = infer(common, clientmod, alg, records, args, run_folder)
            if not succeeded:
                return 2
            if args.limit is not None:
                print('Smoke 推断结束：不生成正式冻结导出，不评价，不报告虚假指标。')
                return 0
            frozen = export_freeze(common, alg, records, run_folder)
            print(f'完成冻结：{frozen}', flush=True)
    if args.mode in ('all', 'judge'):
        if not rejudge_new_method(args, alg, run_folder, out):
            return 0 if args.dry_run else 2
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        print(f'[失败，已有缓存保留] {type(e).__name__}: {e}', file=sys.stderr)
        raise SystemExit(2)
