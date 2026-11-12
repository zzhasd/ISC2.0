#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NJL unified re-evaluation of five FROZEN inference runs.

In the ISC113 project directory:
    python -m pip install requests tqdm
    python rejudge_njl_five.py

Only prompts-v2.py MATCH is ever sent to the judge. No inference reruns,
old semantic-match caches, or prompts.py are used. Algorithms run in fixed
serial order; at most 6 in-flight dialogues per algorithm. Atomic per-dialogue
caches and attempt records allow safe resume with the same command.
"""
from __future__ import annotations

import argparse
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import getpass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import threading
import time
from typing import Any

try:
    import requests
    from tqdm import tqdm
except ImportError as e:
    raise SystemExit(f"缺少依赖 {e}；请执行: python -m pip install requests tqdm")

HERE = Path(__file__).resolve().parent
DEFAULT_ENDPOINT = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'
MODEL = 'qwen3.8-max'
# qwen3.8-max Thinking automatically floors lower temperatures at 0.6.
# Use 0.6 explicitly so the recorded experiment manifest reflects reality.
TEMPERATURE = 0.6
VERSION = 'njl-five-prompts-v2-micro-v1'
DIRECTION = 'A_to_B'
DATASET = 'dailydialog'
REFERENCE_FILE = Path('references/dailydialog_human_adjudicated_588.json')

# (display name, results folder label, frozen export, exact method key)
METHODS = (
    ('Direct thinking', 'direct_thinking', 'runs/main/exports/dailydialog.json', 'direct_thinking'),
    ('Dual (without verifier)', 'dual_without_verifier', 'runs/main/exports/dailydialog.json', 'dual_without_verifier'),
    ('Evidence-Adaptive v3', 'evidence_adaptive_v3', 'runs/evidence_adaptive_v3_append/exports/dailydialog.json', 'evidence_adaptive_v3'),
    ('ELARA v1', 'elara_v1', 'runs/elara_append_v1/exports/dailydialog.json', 'elara_evidence_lattice_v1'),
    ('ELARA v2', 'elara_v2', 'runs/elara_v2_append/exports/dailydialog.json', 'elara_v2_evidence_calibrated_dual_route'),
)
SUBJECT_MAPPING = {'hidden partner / target': 'original B', 'visible speaker / observer': 'original A'}
PERSONA_RULE = 'In persona references I/my refer to the hidden target, never the observer.'


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_obj(value: Any) -> str:
    # Identical hash convention to common.digest in the original ISC113 project.
    return sha_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf-8'))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def atomic_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f'{path.name}.tmp.{os.getpid()}.{threading.get_ident()}')
    try:
        with temp.open('w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def single_process_lock(outdir: Path):
    """Cross-platform process lock; automatically released, even after a crash."""
    lockpath = outdir / '.rejudge.lock'
    lockpath.parent.mkdir(parents=True, exist_ok=True)
    with lockpath.open('a+b') as f:
        f.seek(0, 2)
        if not f.tell():
            f.write(b'0')
            f.flush()
        f.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, IOError) as e:
            raise RuntimeError(f'输出目录正在被另一个评价进程使用：{outdir}') from e
        try:
            yield
        finally:
            if os.name == 'nt':
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def load_match_prompt() -> tuple[str, str]:
    """Hard fail if prompts-v2.py is absent; NEVER fall back to prompts.py."""
    file = HERE / 'prompts-v2.py'
    if not file.is_file():
        raise FileNotFoundError(f'找不到必须使用的 prompts-v2.py: {file}')
    spec = importlib.util.spec_from_file_location('njl_prompts_v2_exclusively', file)
    if spec is None or spec.loader is None:
        raise RuntimeError('无法加载 prompts-v2.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    prompt = getattr(mod, 'MATCH', None)
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError('prompts-v2.py 中缺失有效 MATCH')
    # Extra guard: check the distinctive bidirectional-NLI contract.
    if 'BIDIRECTIONAL NATURAL LANGUAGE INFERENCE' not in prompt or 'broader' not in prompt:
        raise ValueError('prompts-v2.py 的 MATCH 并非预期的 NJL 双向蕴含提示词')
    return prompt, sha_bytes(file.read_bytes())


@dataclass(frozen=True)
class Task:
    algorithm: str
    label: str
    did: str
    direction: str
    predictions: tuple[dict, ...]
    gold: tuple[dict, ...]
    payload: dict
    binding: str


def load_inputs(prompt: str, prompt_file_sha: str, args):
    refpath = HERE / REFERENCE_FILE
    if not refpath.is_file():
        raise FileNotFoundError(f'找不到冻结参考: {refpath}')
    raw_refs = read_json(refpath)
    if not isinstance(raw_refs, list):
        raise ValueError('参考集必须是列表')
    refs = {}
    for row in raw_refs:
        key = (row['dialogue_id'], row['direction'])
        if key in refs or row.get('dataset') != DATASET or key[1] != DIRECTION:
            raise ValueError(f'参考集重复键/方向错误：{key}')
        claims = row['claims']
        if len({r['claim_id'] for r in claims}) != len(claims):
            raise ValueError(f'参考 claim_id 重复：{key}')
        for r in claims:
            if (r.get('truth') != 'true' or r.get('evidence_level') not in ('E1','E2','E3','E4')
                    or r.get('review_status', 'reviewed') != 'reviewed'):
                raise ValueError(f'参考未裁决/标注不合法：{key} {r.get("claim_id")}')
        refs[key] = claims
    reference_count = sum(len(rs) for rs in refs.values())
    grounded_count = sum(r['evidence_level'] in ('E1', 'E2') for rs in refs.values() for r in rs)
    if (len(refs), reference_count, grounded_count) != (298, 588, 262):
        raise ValueError(f'冻结参考数量不符合预期：(段/参考/E1E2)={(len(refs),reference_count,grounded_count)}')

    all_tasks: dict[str, list[Task]] = {}
    original_rows: dict[str, dict[tuple[str, str], dict]] = {}
    export_hashes = {}
    prompt_hash = sha_obj(prompt)
    for display, label, relative, exact_method in METHODS:
        path = HERE / relative
        if not path.is_file():
            raise FileNotFoundError(f'{display} 缺失导出文件：{path}')
        export_hashes[relative] = sha_bytes(path.read_bytes())
        records = read_json(path)
        if not isinstance(records, list):
            raise ValueError(f'{path} 不是预期的列表')
        selected = [p for p in records if p.get('method') == exact_method]
        by_id = {}
        for p in selected:
            key = (p['dialogue_id'], p['direction'])
            if key in by_id or p.get('dataset') != DATASET or key[1] != DIRECTION:
                raise ValueError(f'{display}: 重复键或数据集/方向错误 {key}')
            if not isinstance(p.get('claims'), list):
                raise ValueError(f'{display}: claims 非列表 {key}')
            for c in p['claims']:
                if not isinstance(c, dict) or not isinstance(c.get('claim'), str) or not c['claim'].strip():
                    raise ValueError(f'{display}: 空/非法预测 {key}')
                conf = c.get('confidence')
                if type(conf) not in (int, float) or not 0 <= conf <= 1:
                    raise ValueError(f'{display}: 预测 confidence 不合法 {key}')
            by_id[key] = p
        if set(by_id) != set(refs):
            missing = sorted(set(refs) - set(by_id))[:5]
            extra = sorted(set(by_id) - set(refs))[:5]
            raise ValueError(f'{display}: 预测与参考不完全对应：预测={len(by_id)}, 缺少={missing}, 多出={extra}')
        original_rows[label] = by_id
        tasks = []
        for did, direction in sorted(refs):
            p = by_id[(did, direction)]
            # Exactly the original project's evaluation._prediction_inventory.
            unique = {sha_obj(c['claim']): c['claim'] for c in p['claims']}
            pp = [{'prediction_id': h, 'claim': text} for h, text in sorted(unique.items())]
            rr = [{'claim_id': r['claim_id'], 'claim': r['claim']} for r in refs[(did, direction)]]
            content = {
                'predictions': pp, 'reference': rr,
                'subject_mapping': SUBJECT_MAPPING,
                'persona_reference_rule': PERSONA_RULE,
                'matcher_prompt_sha256': prompt_hash,
            }
            payload = {
                'model': MODEL,
                'temperature': TEMPERATURE,
                'enable_thinking': True,
                'thinking_budget': args.thinking_budget,  # NO reasoning_effort: mutually exclusive.
                'max_tokens': args.max_tokens,
                'messages': [
                    {'role': 'system', 'content': prompt},
                    {'role': 'user', 'content': json.dumps(content, ensure_ascii=False)},
                ],
            }
            binding = sha_obj({'payload': payload, 'endpoint': args.endpoint, 'version': VERSION,
                               'method': label, 'dialogue_id': did, 'direction': direction})
            tasks.append(Task(label, display, did, direction, tuple(pp), tuple(rr), payload, binding))
        all_tasks[label] = tasks

    manifest = {
        'version': VERSION, 'created_by': 'rejudge_njl_five.py',
        'model': MODEL, 'endpoint': args.endpoint, 'temperature': TEMPERATURE,
        'enable_thinking': True, 'thinking_budget': args.thinking_budget, 'max_tokens': args.max_tokens,
        'prompt_file': 'prompts-v2.py', 'prompt_file_sha256': prompt_file_sha,
        'matcher_prompt_sha256': prompt_hash,
        'reference_file': REFERENCE_FILE.as_posix(),
        'reference_sha256': sha_bytes(refpath.read_bytes()),
        'export_sha256': export_hashes,
        'methods': [{'name': n, 'label': l, 'export': p, 'method': m} for n, l, p, m in METHODS],
        'dataset': DATASET, 'direction': DIRECTION,
        'dialogues_per_method': len(refs), 'reference_attributes': reference_count,
        'grounded_reference_attributes': grounded_count,
        'scoring': {
            'strict_relations': ['equivalent'],
            'loose_relations': ['equivalent', 'broader'],
            'precision': 'correct original predictions / original predictions, duplicates preserved',
            'recall': 'maximum one-to-one reference matching / true references',
            'grounded_recall': 'independent maximum one-to-one E1/E2 matching / E1/E2 references',
            'scope': 'same frozen 298 A_to_B dialogues, same human-adjudicated reference',
        },
    }
    return refs, original_rows, all_tasks, manifest


def validate_matches(obj: Any, task: Task) -> list[dict]:
    """Enforce the EXACT prompts-v2.py response contract; never silently repair labels."""
    if not isinstance(obj, dict) or set(obj) != {'matches'} or not isinstance(obj['matches'], list):
        raise ValueError('响应必须为 {"matches":[...]}，不可含额外字段')
    matches = obj['matches']
    allowed_p = {x['prediction_id'] for x in task.predictions}
    allowed_r = {x['claim_id'] for x in task.gold}
    if len(matches) != len(allowed_p):
        raise ValueError(f'预测未完整覆盖：应={len(allowed_p)}, 实得={len(matches)}')
    seen = set()
    for m in matches:
        if not isinstance(m, dict) or set(m) != {'prediction_id', 'reference_ids', 'relation'}:
            raise ValueError('match 条目字段不符合 prompts-v2.py 输出契约')
        pid, ids, rel = m['prediction_id'], m['reference_ids'], m['relation']
        if not isinstance(pid, str) or pid not in allowed_p or pid in seen:
            raise ValueError('未知或重复 prediction_id')
        seen.add(pid)
        if not isinstance(ids, list) or not all(isinstance(x, str) and x in allowed_r for x in ids):
            raise ValueError('未知 reference_id 或非数组 reference_ids')
        if len(ids) != len(set(ids)):
            raise ValueError('reference_ids 重复')
        if rel not in ('equivalent', 'narrower', 'broader', 'none'):
            raise ValueError('错误 relation')
        if rel == 'none' and ids:
            raise ValueError('none 必须有空 reference_ids')
        if rel != 'none' and not ids:
            raise ValueError('非 none 必须提供 reference_ids')
        if rel in ('broader','narrower') and len(ids) != 1:
            raise ValueError('broader/narrower 只能关联一个最佳参考')
    if seen != allowed_p:
        raise ValueError('漏报预测')
    return matches


def parse_response(response: dict, task: Task) -> tuple[list[dict], list[dict]]:
    if not isinstance(response, dict) or not response.get('choices'):
        raise ValueError('非 Chat Completions 响应')
    choice = response['choices'][0]
    if choice.get('finish_reason') != 'stop':
        raise ValueError(f'响应未正常完成，finish_reason={choice.get("finish_reason")}')
    content = choice.get('message', {}).get('content')
    if not isinstance(content, str) or not content.strip():
        raise ValueError('模型未提供可用 JSON 内容（可能耗尽 max_tokens）')
    content = content.strip()
    if content.startswith('```'):
        lines = content.splitlines()
        if lines[-1].strip() != '```':
            raise ValueError('Markdown code fence 未闭合')
        content = '\n'.join(lines[1:-1]).strip()
    obj = json.loads(content)
    repairs = []
    # Conservative formatting normalization only.  Never change a semantic
    # relation; in particular, NEVER upgrade none into a positive match.
    # Save the raw model response in attempts/ for auditability.
    if isinstance(obj, dict) and isinstance(obj.get('matches'), list):
        allowed_refs = {x['claim_id'] for x in task.gold}
        normalized = []
        for m in obj['matches']:
            if (isinstance(m, dict) and m.get('relation') == 'none'
                    and isinstance(m.get('reference_ids'), list) and m['reference_ids']
                    and all(isinstance(r, str) and r in allowed_refs for r in m['reference_ids'])):
                repairs.append({
                    'prediction_id': m.get('prediction_id'),
                    'field': 'reference_ids', 'before': list(m['reference_ids']), 'after': [],
                    'reason': 'prompts-v2.py: none must have empty reference_ids; relation unchanged',
                })
                m = {**m, 'reference_ids': []}
            normalized.append(m)
        obj = {**obj, 'matches': normalized}
    return validate_matches(obj, task), repairs


def cache_path(out: Path, task: Task) -> Path:
    return out / 'matches' / task.algorithm / f'{task.did}__{task.direction}.json'


def cached_matches(out: Path, task: Task) -> list[dict] | None:
    p = cache_path(out, task)
    if not p.exists():
        return None
    data = read_json(p)
    if data.get('binding') != task.binding or data.get('evaluation_model') != MODEL:
        raise RuntimeError(f'存在旧/不兼容匹配缓存，拒绝混用：{p}；请使用新输出目录')
    return validate_matches({'matches': data.get('matches')}, task)


def persist_match(out: Path, task: Task, matches: list[dict], attempt: int | None,
                  usage: dict | None, recovered: bool = False, normalizations: list[dict] | None = None):
    atomic_json(cache_path(out, task), {
        'algorithm': task.algorithm, 'name': task.label,
        'dialogue_id': task.did, 'direction': task.direction,
        'binding': task.binding, 'evaluation_model': MODEL,
        'prompt_file': 'prompts-v2.py', 'relations': ['equivalent','broader','narrower','none'],
        'matches': matches, 'attempt_number': attempt, 'usage': usage,
        'recovered_from_attempt': recovered, 'normalizations': normalizations or [],
        'completed_utc': utcnow(),
    })


def attempt_path(out: Path, task: Task, n: int) -> Path:
    return out / 'attempts' / task.algorithm / f'{task.did}__{task.direction}__{n:02d}.json'


class FatalAPIError(RuntimeError):
    """An unrecoverable configuration/authentication error; stop all work."""


class ExhaustedAttemptsError(RuntimeError):
    """Only this per-dialogue error is skippable until the final retry phase."""


class Evaluator:
    def __init__(self, *, key: str | None, out: Path, args, stop: threading.Event):
        self.key = key
        self.out = out
        self.args = args
        self.stop = stop
        self.local = threading.local()

    def judge(self, task: Task, phase: str = 'initial') -> str:
        """One task, with immutable attempt numbers across restarts and phases.

        initial: 1..max_attempts; final: max_attempts+1..max_attempts+final_retry_attempts.
        Existing received responses are scanned first so old format-only failures
        (including train_4359) can be recovered without another paid API call.
        """
        if cached_matches(self.out, task) is not None:
            return 'cached'
        if self.stop.is_set():
            return 'stopped'
        if not task.predictions or not task.gold:
            matches = ([] if not task.predictions else [
                {'prediction_id': p['prediction_id'], 'reference_ids': [], 'relation': 'none'}
                for p in task.predictions])
            persist_match(self.out, task, matches, None, None)
            return 'deterministic'

        last_attempt = self.args.max_attempts + self.args.final_retry_attempts
        # A previous run may have returned an acceptable response, but crashed
        # before persisting matches.  Replay any stored response first.
        for attempt in range(1, last_attempt + 1):
            path = attempt_path(self.out, task, attempt)
            if not path.exists():
                continue
            old = read_json(path)
            if old.get('binding') != task.binding:
                raise FatalAPIError(f'请求记录与当前实验不兼容：{path}')
            if old.get('state') != 'received' or not old.get('response'):
                continue
            try:
                matches, repairs = parse_response(old['response'], task)
            except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                continue
            persist_match(self.out, task, matches, attempt, old.get('usage'),
                          recovered=True, normalizations=repairs)
            return 'recovered_normalized' if repairs else 'recovered'

        if phase == 'initial':
            first, end = 1, self.args.max_attempts
        elif phase == 'final':
            first, end = self.args.max_attempts + 1, last_attempt
        else:
            raise ValueError('Unknown evaluation phase: ' + phase)

        for attempt in range(first, end + 1):
            if self.stop.is_set():
                return 'stopped'
            path = attempt_path(self.out, task, attempt)
            if path.exists():
                old = read_json(path)
                if old.get('binding') != task.binding:
                    raise FatalAPIError(f'不兼容旧请求记录：{path}')
                # A previous 'started' entry could have cost tokens; do not
                # overwrite it. A previous failed entry also stays immutable.
                continue
            if not self.key:
                raise FatalAPIError('尚无 QWEN_API_KEY / DASHSCOPE_API_KEY')
            atomic_json(path, {'binding': task.binding, 'state': 'started', 'attempt': attempt,
                              'phase': phase, 'utc': utcnow(), 'algorithm': task.algorithm,
                              'dialogue_id': task.did,
                              'note': 'After an abrupt termination, billing for this request is unknown'})
            started = time.monotonic()
            try:
                if not hasattr(self.local, 'session'):
                    self.local.session = requests.Session()
                response = self.local.session.post(
                    self.args.endpoint, json=task.payload,
                    headers={'Authorization': 'Bearer ' + self.key, 'Content-Type':'application/json'},
                    timeout=(15, self.args.timeout), allow_redirects=False,
                )
                status = response.status_code
                try:
                    body = response.json()
                except ValueError:
                    body = {'error': response.text[:1200]}
            except requests.RequestException as e:
                atomic_json(path, {'binding': task.binding, 'state': 'network_error',
                                  'attempt': attempt, 'phase': phase, 'utc': utcnow(),
                                  'elapsed_seconds': round(time.monotonic()-started, 3),
                                  'error': f'{type(e).__name__}: {str(e)[:350]}'})
                self.backoff(attempt)
                continue

            # Preserve raw content (minus reasoning and credentials) in attempts/.
            safe_body = {}
            if status == 200 and isinstance(body, dict):
                safe_body = {
                    'choices': [
                        {'finish_reason': c.get('finish_reason'),
                         'message': {'content': c.get('message', {}).get('content')}}
                        for c in body.get('choices', [])[:1]
                    ]
                }
            usage = body.get('usage') if isinstance(body, dict) else None
            record = {'binding': task.binding, 'state': 'received' if status == 200 else 'http_error',
                      'attempt': attempt, 'phase': phase, 'utc': utcnow(),
                      'elapsed_seconds': round(time.monotonic()-started,3),
                      'http_status': status, 'usage': usage,
                      'response': safe_body if status == 200 else None,
                      'error': None if status == 200 else str(body.get('error', body) if isinstance(body, dict) else body)[:1200]}
            atomic_json(path, record)
            if status in (401, 403, 404):
                self.stop.set()
                raise FatalAPIError(f'HTTP {status}：密钥、地区或模型权限错误（{task.label} {task.did}）')
            if 400 <= status < 500 and status != 429:
                self.stop.set()
                raise FatalAPIError(f'HTTP {status}：请求参数被拒绝（{task.label} {task.did}）；详见 {path}')
            if status != 200:
                self.backoff(attempt)
                continue
            try:
                matches, repairs = parse_response(safe_body, task)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
                record['parse_error'] = f'{type(e).__name__}: {str(e)[:400]}'
                atomic_json(path, record)
                self.backoff(attempt)
                continue
            if repairs:
                record['normalizations'] = repairs
                atomic_json(path, record)
            persist_match(self.out, task, matches, attempt, usage, normalizations=repairs)
            return 'api_normalized' if repairs else 'api'
        raise ExhaustedAttemptsError(
            f'{task.label} {task.did}：{phase} 阶段请求次数用尽 '
            f'({first}..{end})，{"暂时跳过" if phase == "initial" else "最终补评失败"}')

    def backoff(self, n: int):
        self.stop.wait(min(20, 2 ** n))


def max_bipartite(edges: dict[str, set[str]]) -> dict[str, str]:
    """Verbatim algorithmic behavior of statistics.matching (one-to-one)."""
    owner: dict[str, str] = {}
    def visit(p: str, seen: set[str]) -> bool:
        for ref in sorted(edges[p]):
            if ref in seen:
                continue
            seen.add(ref)
            if ref not in owner or visit(owner[ref], seen):
                owner[ref] = p
                return True
        return False
    for prediction in sorted(edges):
        visit(prediction, set())
    return {p: r for r, p in owner.items()}


def score_input(original: dict, refs: list[dict], matches: list[dict], accepted: tuple[str, ...]) -> dict:
    """Exact P/R/Grounded Recall logic from evaluation.score_item, threshold=0."""
    cs = [c for c in original['claims'] if c['confidence'] >= 0]
    ref = {r['claim_id']: r for r in refs if r.get('review_status', 'reviewed') == 'reviewed'}
    grounded = {k: r for k, r in ref.items() if r['truth'] == 'true' and r['evidence_level'] in ('E1','E2')}
    by_p = {m['prediction_id']: m for m in matches}
    truth_edges, grounded_edges = {}, {}
    correct = 0
    for i, c in enumerate(cs):
        match = by_p.get(sha_obj(c['claim']), {'relation':'none','reference_ids':[]})
        ids = match['reference_ids'] if match['relation'] in accepted else []
        hits = {k for k in ids if k in ref and ref[k]['truth'] == 'true'}
        correct += bool(hits)  # Precision: each ORIGINAL claim gets credit, even duplicates.
        truth_edges[str(i)] = hits
        grounded_edges[str(i)] = hits.intersection(grounded)
    true_assignment = max_bipartite(truth_edges)
    grounded_assignment = max_bipartite(grounded_edges)
    return {
        'dialogue_id': original['dialogue_id'], 'direction': original['direction'],
        'output_assertions': len(cs), 'correct_output_assertions': correct,
        'recovered_reference_attributes': len(true_assignment),
        'true_reference_attributes': sum(r['truth'] == 'true' for r in ref.values()),
        'recovered_grounded_reference_attributes': len(grounded_assignment),
        'grounded_reference_attributes': len(grounded),
    }


def score_full_method(label: str, records: dict, refs: dict, tasks: list[Task], out: Path) -> dict:
    if any(cached_matches(out, task) is None for task in tasks):
        raise RuntimeError(f'{label} 尚未评完，拒绝输出可能误导的完整指标')
    summary = {}
    for policy, accepted in [('strict', ('equivalent',)), ('loose', ('equivalent', 'broader'))]:
        rows = [score_input(records[(t.did,t.direction)], refs[(t.did,t.direction)],
                            cached_matches(out, t), accepted) for t in tasks]
        sums = {k: sum(r[k] for r in rows) for k in (
            'output_assertions','correct_output_assertions','recovered_reference_attributes',
            'true_reference_attributes','recovered_grounded_reference_attributes','grounded_reference_attributes')}
        if len(rows) != 298 or sums['true_reference_attributes'] != 588 or sums['grounded_reference_attributes'] != 262:
            raise AssertionError(f'{label} 分母校验失败: {sums}')
        def ratio(a, b):
            return (a / b) if b else None
        sums.update({
            'precision': ratio(sums['correct_output_assertions'], sums['output_assertions']),
            'recall': ratio(sums['recovered_reference_attributes'], sums['true_reference_attributes']),
            'grounded_recall': ratio(sums['recovered_grounded_reference_attributes'], sums['grounded_reference_attributes']),
            'single_sided_inputs': len(rows), 'algorithm': label, 'accepted_relations': list(accepted),
        })
        atomic_json(out / 'scores' / label / f'{policy}_per_input.json', rows)
        summary[policy] = sums
    atomic_json(out / 'scores' / label / 'summary.json', summary)
    return summary


def make_final_report(out: Path, refs, original_rows, tasks_by_method, manifest):
    complete = all(cached_matches(out, task) is not None for tasks in tasks_by_method.values() for task in tasks)
    if not complete:
        return False
    result = {}
    for display, label, _, _ in METHODS:
        result[label] = score_full_method(label, original_rows[label], refs, tasks_by_method[label], out)
    atomic_json(out / 'five_algorithms_strict_loose.json', {
        'complete': True, 'manifest_sha256': sha_obj(manifest),
        'model': MODEL, 'enable_thinking': True, 'prompt_file': 'prompts-v2.py',
        'methods': result,
    })
    import csv
    import io
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['algorithm','policy','precision','recall','grounded_recall','correct_outputs',
                     'output_assertions','reference_hits','reference_total','grounded_hits','grounded_total'])
    for _, label, _, _ in METHODS:
        for policy in ('strict','loose'):
            row = result[label][policy]
            writer.writerow([label, policy, row['precision'], row['recall'], row['grounded_recall'],
                             row['correct_output_assertions'],row['output_assertions'],
                             row['recovered_reference_attributes'],row['true_reference_attributes'],
                             row['recovered_grounded_reference_attributes'],row['grounded_reference_attributes']])
    (out / 'five_algorithms_strict_loose.csv').write_text('\ufeff'+buffer.getvalue(),encoding='utf-8')
    lines = [
        '# 五算法统一 NJL 评价报告', '',
        f'- 评价模型：`{MODEL}`，`enable_thinking=true`，`thinking_budget={manifest["thinking_budget"]}`，`max_tokens={manifest["max_tokens"]}`，`temperature={manifest["temperature"]}`。',
        f'- **唯一匹配提示词**：`prompts-v2.py`，SHA256：`{manifest["prompt_file_sha256"]}`。',
        '- 只重新评价冻结预测，**没有重新推理**。五算法依次串行；每个算法内部最多 6 并发。',
        '- 固定 298 段 A→B 对话，588 条 true 参考；其中 E1/E2 有据参考 262 条。',
        '- Precision = 命中参考的原始输出条数 / 原始输出条数（重复输出仍保留在分母）。',
        '- Recall = 最大一对一命中参考数 / 588；Grounded Recall = E1/E2 最大一对一命中数 / 262。',
        '- 严格：仅 `equivalent`；宽松：`equivalent` 或 `broader`（**不包含** `narrower`）。',
        '- 固定参考集的模型语义匹配指标；非人工逐条验证每条预测的开放世界精确率。', '',
    ]
    for policy, title in (('strict','严格口径（equivalent）'), ('loose','宽松口径（equivalent + broader）')):
        lines.extend([f'## {title}', '',
                      '| 算法 | Precision | Recall | Grounded Recall |', '|---|---:|---:|---:|'])
        for display, label, _, _ in METHODS:
            r = result[label][policy]
            lines.append(f'| {display} | {r["precision"]:.4%} | {r["recall"]:.4%} | {r["grounded_recall"]:.4%} |')
        lines.extend(['', '| 算法 | Precision 分子/分母 | Recall 分子/分母 | Grounded Recall 分子/分母 |',
                      '|---|---:|---:|---:|'])
        for display, label, _, _ in METHODS:
            r = result[label][policy]
            lines.append(f'| {display} | {r["correct_output_assertions"]}/{r["output_assertions"]} | '
                         f'{r["recovered_reference_attributes"]}/588 | '
                         f'{r["recovered_grounded_reference_attributes"]}/262 |')
        lines.append('')
    (out / 'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    return True


def count_done(out: Path, tasks: list[Task]) -> int:
    return sum(cached_matches(out, task) is not None for task in tasks)


def execute_method(out: Path, label: str, display: str, tasks: list[Task], evaluator: Evaluator,
                   workers: int, limit: int | None, stop: threading.Event,
                   phase: str = 'initial') -> tuple[list[dict], int]:
    done_before = count_done(out, tasks)
    pending = [t for t in tasks if cached_matches(out, t) is None]
    if limit is not None:
        pending = pending[:limit]
    stage_name = '首轮' if phase == 'initial' else '最终补评'
    print(f'\n[{display} / {stage_name}] 全部={len(tasks)}，已有缓存={done_before}，'
          f'本轮待处理={len(pending)}，并发={workers}', flush=True)
    errors = []
    statuses: dict[str, int] = {}
    queue = deque(pending)
    with tqdm(total=len(pending), desc=f'{display[:18]} {stage_name}', unit='段',
              dynamic_ncols=True, leave=True) as bar:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix=label) as pool:
            running = {}
            def fill():
                while queue and len(running) < workers and not stop.is_set():
                    t = queue.popleft()
                    running[pool.submit(evaluator.judge, t, phase)] = t
            fill()
            while running:
                finished, _ = wait(running, timeout=.5, return_when=FIRST_COMPLETED)
                if not finished:
                    continue
                for future in finished:
                    task = running.pop(future)
                    try:
                        status = future.result()
                        statuses[status] = statuses.get(status, 0) + 1
                    except ExhaustedAttemptsError as e:
                        # Crucially: do NOT stop the queue or other algorithms.
                        errors.append({'dialogue_id': task.did, 'algorithm': label,
                                       'phase': phase, 'error': str(e)})
                        bar.write(f'[{display} / {stage_name}] 跳过 {task.did}: {e}')
                    except Exception as e:
                        # Fatal misconfiguration / broken caches must still stop.
                        errors.append({'dialogue_id': task.did, 'algorithm': label,
                                       'phase': phase, 'fatal': True,
                                       'error': f'{type(e).__name__}: {e}'})
                        stop.set()
                        bar.write(f'[{display} / {stage_name}] 致命失败 {task.did}: {e}')
                    bar.update(1)
                fill()
    completed = count_done(out, tasks)
    print(f'[{display} / {stage_name}] 当前已完成 {completed}/{len(tasks)}；'
          f'状态={statuses}；本轮跳过={sum(not e.get("fatal") for e in errors)}', flush=True)
    return errors, completed


def _read_phase_failures(out: Path) -> dict:
    path = out / 'phase_failures.json'
    if path.exists():
        return read_json(path)
    # Migrate pre-upgrade status errors, preserving previously observed skips.
    prior = out / 'status.json'
    history = {'initial': {label: [] for _, label, _, _ in METHODS},
               'final': {label: [] for _, label, _, _ in METHODS}}
    if prior.exists():
        old = read_json(prior)
        for item in old.get('errors', []):
            label = item.get('algorithm')
            did = item.get('dialogue_id')
            if label in history['initial'] and did:
                history['initial'][label].append(did)
    return history


def record_phase_failures(out: Path, phase_history: dict, phase: str, errors: list[dict]):
    for item in errors:
        if item.get('fatal'):
            continue
        label = item['algorithm']
        did = item['dialogue_id']
        phase_history.setdefault(phase, {}).setdefault(label, [])
        if did not in phase_history[phase][label]:
            phase_history[phase][label].append(did)
    atomic_json(out / 'phase_failures.json', phase_history)


def write_failure_summary(out: Path, all_tasks: dict[str, list[Task]],
                          phase_history: dict, args) -> dict:
    """Count both failed API attempts and failed *dialogues*, distinctly."""
    table = {}
    import csv
    import io
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(['algorithm', 'failed_attempts_total', 'parse_error_attempts',
                     'http_error_attempts', 'network_error_attempts', 'initial_skipped_dialogues',
                     'final_retry_failed_dialogues', 'currently_incomplete_dialogues',
                     'normalized_dialogues', 'normalized_match_rows'])
    for display, label, _, _ in METHODS:
        counts = {'parse_error_attempts': 0, 'http_error_attempts': 0,
                  'network_error_attempts': 0}
        normalized_dialogues = 0
        normalized_rows = 0
        incomplete = 0
        for task in all_tasks[label]:
            saved = cache_path(out, task)
            if saved.exists():
                doc = read_json(saved)
                fixes = doc.get('normalizations', [])
                if fixes:
                    normalized_dialogues += 1
                    normalized_rows += len(fixes)
            else:
                incomplete += 1
            for n in range(1, args.max_attempts + args.final_retry_attempts + 1):
                p = attempt_path(out, task, n)
                if not p.exists():
                    continue
                rec = read_json(p)
                if rec.get('binding') != task.binding:
                    raise RuntimeError(f'请求绑定不匹配，拒绝统计：{p}')
                if rec.get('parse_error'):
                    counts['parse_error_attempts'] += 1
                elif rec.get('state') == 'http_error':
                    counts['http_error_attempts'] += 1
                elif rec.get('state') == 'network_error':
                    counts['network_error_attempts'] += 1
        first = sorted(set(phase_history.get('initial', {}).get(label, [])))
        final = sorted(set(phase_history.get('final', {}).get(label, [])))
        row = {
            'name': display, 'failed_attempts_total': sum(counts.values()), **counts,
            'initial_skipped_dialogues': len(first), 'initial_skipped_ids': first,
            'final_retry_failed_dialogues': len(final), 'final_retry_failed_ids': final,
            'currently_incomplete_dialogues': incomplete,
            'normalized_dialogues': normalized_dialogues, 'normalized_match_rows': normalized_rows,
        }
        table[label] = row
        writer.writerow([label] + [row[k] for k in (
            'failed_attempts_total', 'parse_error_attempts', 'http_error_attempts',
            'network_error_attempts', 'initial_skipped_dialogues',
            'final_retry_failed_dialogues', 'currently_incomplete_dialogues',
            'normalized_dialogues', 'normalized_match_rows')])
    atomic_json(out / 'failure_summary.json', {
        'updated_utc': utcnow(), 'model': MODEL, 'prompt_file': 'prompts-v2.py',
        'meaning': 'failed_attempts_total counts failed requests; skipped_dialogues counts unique dialogues',
        'algorithms': table,
    })
    (out / 'failure_summary.csv').write_text('\ufeff' + csv_buffer.getvalue(), encoding='utf-8')
    return table


def save_status(out: Path, all_tasks, history: dict, args, *, complete=False,
                interrupted=False, stage='initial', errors=None):
    counts = write_failure_summary(out, all_tasks, history, args)
    atomic_json(out / 'status.json', {
        'complete': complete, 'updated_utc': utcnow(), 'model': MODEL,
        'prompt_file': 'prompts-v2.py', 'phase': stage,
        'completed': {lab: count_done(out, tasks) for lab, tasks in all_tasks.items()},
        'total_per_algorithm': 298,
        'failures_by_algorithm': {lab: {
            'failed_attempts_total': c['failed_attempts_total'],
            'initial_skipped_dialogues': c['initial_skipped_dialogues'],
            'final_retry_failed_dialogues': c['final_retry_failed_dialogues'],
            'currently_incomplete_dialogues': c['currently_incomplete_dialogues'],
        } for lab, c in counts.items()},
        'errors': (errors or [])[-100:], 'interrupted': interrupted,
    })


def main():
    parser = argparse.ArgumentParser(description='五算法 NJL prompts-v2 + qwen3.8-max 全量可恢复重新评价')
    parser.add_argument('--workers', type=int, default=6, help='每个算法内部并发数（默认6；算法之间始终串行）')
    parser.add_argument('--thinking-budget', type=int, default=8192, help='Qwen thinking token 上限（默认8192）')
    parser.add_argument('--max-tokens', type=int, default=12288, help='Qwen 生成总 token 上限（默认12288）')
    parser.add_argument('--timeout', type=int, default=240, help='每次 HTTP 读取超时秒数（默认240）')
    parser.add_argument('--max-attempts', type=int, default=5, help='首轮每对话最多5次尝试（默认5）')
    parser.add_argument('--final-retry-attempts', type=int, default=1,
                        help='五算法首轮全部完成后，对每个遗留失败任务最终再试几次（默认1）')
    parser.add_argument('--endpoint', default=DEFAULT_ENDPOINT)
    parser.add_argument('--output-dir', type=Path, default=Path('runs/njl_qwen38max_prompts_v2'))
    parser.add_argument('--limit-per-method', type=int, default=None, help='每个算法本次只评价前N条未完成对话（调试；不输出完整报告）')
    parser.add_argument('--dry-run', action='store_true', help='只检查数据和新旧缓存计数，不请求 API')
    args = parser.parse_args()
    if not 1 <= args.workers <= 128 or args.thinking_budget < 1 or args.max_tokens < 1:
        parser.error('workers、thinking-budget、max-tokens 必须是正整数')
    if (args.timeout <= 0 or args.max_attempts < 1 or args.final_retry_attempts < 1
            or (args.limit_per_method is not None and args.limit_per_method < 1)):
        parser.error('timeout、max-attempts、limit-per-method 必须是正整数')
    out = args.output_dir if args.output_dir.is_absolute() else HERE / args.output_dir
    out = out.resolve()
    prompt, prompt_file_sha = load_match_prompt()
    refs, original_rows, all_tasks, manifest = load_inputs(prompt, prompt_file_sha, args)
    print(f'NJL 评价: {MODEL} / Thinking ON / 唯一提示词 prompts-v2.py SHA256={prompt_file_sha[:16]}…')
    for display, label, _, _ in METHODS:
        claims = sum(len(x['claims']) for x in original_rows[label].values())
        print(f'  {display:<26} 298 段 / {claims} 条原始预测')
    print(f'评价输出: {out}', flush=True)

    with single_process_lock(out):
        manifest_path = out / 'manifest.json'
        if manifest_path.exists():
            saved = read_json(manifest_path)
            if saved != manifest:
                raise RuntimeError('当前模型/提示词/输入/参数与已有 manifest.json 不同：不能混用！'
                                   f'\n请使用 --output-dir 指定一个新的结果文件夹。现有: {manifest_path}')
        else:
            atomic_json(manifest_path, manifest)
        for display, label, _, _ in METHODS:
            print(f'缓存: {label}: {count_done(out, all_tasks[label])}/298')
        if args.dry_run:
            print('预检查通过：未发送任何 API 请求。')
            return 0
        if all(count_done(out, tasks) == len(tasks) for tasks in all_tasks.values()):
            make_final_report(out, refs, original_rows, all_tasks, manifest)
            print(f'五种算法已经完整评价，无需新请求：{out / "REPORT.md"}')
            return 0

        key = os.environ.get('QWEN_API_KEY') or os.environ.get('DASHSCOPE_API_KEY')
        if not key:
            if not sys.stdin.isatty():
                raise RuntimeError('请设置 QWEN_API_KEY 或 DASHSCOPE_API_KEY 环境变量')
            key = getpass.getpass('请输入百炼 API Key（不回显、不写盘）：').strip()
        if not key:
            raise RuntimeError('缺少有效 API Key')
        stop = threading.Event()
        interrupt_count = 0
        old_handler = signal.getsignal(signal.SIGINT)
        def handle_sigint(_signum, _frame):
            nonlocal interrupt_count
            interrupt_count += 1
            if interrupt_count == 1:
                print('\n收到 Ctrl+C：停止提交新请求，正在等待最多6个在途请求落盘；随后可原命令续跑。',flush=True)
                stop.set()
            else:
                raise KeyboardInterrupt
        signal.signal(signal.SIGINT, handle_sigint)
        try:
            evaluator = Evaluator(key=key, out=out, args=args, stop=stop)
            history = _read_phase_failures(out)
            all_errors = []
            # PHASE 1: all five algorithms strictly sequentially. Per-dialogue
            # exhaustion is recorded and skipped, not a reason to stop.
            for display, label, _, _ in METHODS:
                if stop.is_set():
                    break
                errors, completed = execute_method(out, label, display, all_tasks[label],
                                                    evaluator, args.workers,
                                                    args.limit_per_method, stop, phase='initial')
                all_errors.extend(errors)
                record_phase_failures(out, history, 'initial', errors)
                save_status(out, all_tasks, history, args, stage='initial',
                            errors=all_errors, interrupted=stop.is_set())
                if stop.is_set():
                    break
                # Defer ALL metric calculation until after the final-retry stage;
                # no method is scored early, and incomplete runs never emit totals.
            if stop.is_set():
                print('\n遇到致命配置错误或中断；保留全部成功缓存，原命令可续跑。')
                return 130 if interrupt_count else 2
            if args.limit_per_method is not None:
                print('\n--limit-per-method 调试模式已结束；不运行最终补评或生成完整指标。')
                return 0

            # PHASE 2: after ALL five algorithms' initial rounds, revisit ONLY
            # incomplete dialogues. One additional attempt by default.
            missing = sum(len(tasks) - count_done(out, tasks) for tasks in all_tasks.values())
            if missing:
                print(f'\n===== 五算法首轮已结束；仍有 {missing} 段未完成，开始最终集中补评 =====', flush=True)
            for display, label, _, _ in METHODS:
                if stop.is_set():
                    break
                if count_done(out, all_tasks[label]) == len(all_tasks[label]):
                    continue
                errors, completed = execute_method(out, label, display, all_tasks[label],
                                                    evaluator, args.workers, None,
                                                    stop, phase='final')
                all_errors.extend(errors)
                record_phase_failures(out, history, 'final', errors)
                save_status(out, all_tasks, history, args, stage='final',
                            errors=all_errors, interrupted=stop.is_set())
                if stop.is_set():
                    break
            if stop.is_set():
                print('\n最终补评遭遇致命配置错误或人工中断；成功缓存已保留。')
                return 130 if interrupt_count else 2

            full = make_final_report(out, refs, original_rows, all_tasks, manifest)
            save_status(out, all_tasks, history, args, stage='finished',
                        complete=full, errors=all_errors)
            summary = read_json(out / 'failure_summary.json')['algorithms']
            print('\n===== 各算法失败统计（历史请求次数 / 首轮跳过段数 / 最终仍缺段数） =====')
            for display, label, _, _ in METHODS:
                r = summary[label]
                print(f'{display}: {r["failed_attempts_total"]} / '
                      f'{r["initial_skipped_dialogues"]} / '
                      f'{r["currently_incomplete_dialogues"]}')
            print(f'失败日志：{out / "failure_summary.csv"}')
            if full:
                # Include audit counts alongside the final strict/loose metrics.
                report_path = out / 'REPORT.md'
                report = report_path.read_text(encoding='utf-8')
                if '## 请求失败与最终补评统计' not in report:
                    audit = [
                        '', '## 请求失败与最终补评统计', '',
                        '| 算法 | 历史失败请求次数 | 首轮跳过对话数 | 最终补评失败对话数 | 格式规范化对话数 |',
                        '|---|---:|---:|---:|---:|',
                    ]
                    for display, label, _, _ in METHODS:
                        r = summary[label]
                        audit.append(f'| {display} | {r["failed_attempts_total"]} | '
                                     f'{r["initial_skipped_dialogues"]} | '
                                     f'{r["final_retry_failed_dialogues"]} | '
                                     f'{r["normalized_dialogues"]} |')
                    audit += ['', '以上失败次数包含历史已恢复的请求错误；'
                              '完整原始请求记录见 attempts/，详细统计见 failure_summary.json。', '']
                    report_path.write_text(report.rstrip() + '\n' + '\n'.join(audit), encoding='utf-8')
                print(f'\n✅ 全部完成！报告：{out / "REPORT.md"}')
                print(f'CSV：{out / "five_algorithms_strict_loose.csv"}')
                print(f'JSON：{out / "five_algorithms_strict_loose.json"}')
                return 0
            print(f'\n最终补评仍有失败任务，停止且不输出新的总指标。'
                  f'详情见 {out / "failure_summary.json"}、{out / "status.json"}。'
                  '如需额外请求，请增大 --final-retry-attempts 并用原输出目录续跑。')
            return 2

        finally:
            signal.signal(signal.SIGINT, old_handler)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('\n强制中断：已落盘的对话级评价仍可恢复，下一次运行将跳过。',file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f'\n错误：{type(e).__name__}: {e}',file=sys.stderr)
        sys.exit(1)
