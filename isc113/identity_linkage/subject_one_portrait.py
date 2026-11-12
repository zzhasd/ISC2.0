"""Run the EXACT 2026-11-08 A-only portrait experiment for one anonymous B ID.

Put beside filtered_portrait_repeat.py in isc113/identity_linkage/.
Examples:
  python subject_one_portrait.py IB --dry-run
  python subject_one_portrait.py IB --workers 8 --retries 2
  python subject_one_portrait.py IB --workers 8 --retries 3  # resume/extend retries

Original inference code, prompts, input adapter, validators and request payloads
are imported unchanged. Only subject selection, scheduling, progress, deferred
retry orchestration, reporting, and artifact locations are implemented here.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import threading
import zipfile

if not __package__:
    # Support `python subject_one_portrait.py ...` without moving project files.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from identity_linkage import filtered_portrait_repeat as original
    from identity_linkage import elara_subject_v2 as algorithm
    from identity_linkage import elara_ja_subject_filter as subject_filter
    from identity_linkage import portrait_summary as portraits
    from identity_linkage.api import Client
    from identity_linkage.core import HERE, ENDPOINT, MODEL, digest, freeze, load, save, sanitize
    from identity_linkage.prepare import read_corpus
else:
    from . import filtered_portrait_repeat as original
    from . import elara_subject_v2 as algorithm
    from . import elara_ja_subject_filter as subject_filter
    from . import portrait_summary as portraits
    from .api import Client
    from .core import HERE, ENDPOINT, MODEL, digest, freeze, load, save, sanitize
    from .prepare import read_corpus

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None  # Stdlib fallback still counts completed jobs.

CODE = original.CODE  # Same seven original source files, unchanged.
PRINT_LOCK = threading.Lock()


def say(message: str) -> None:
    with PRINT_LOCK:
        if tqdm is None:
            print(message, flush=True)
        else:
            tqdm.write(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_subject(subject: str):
    """Same sorted ALL-dialogue selection and partner numbering as original repeats.

    IMPORTANT: Does NOT read the subject's persona. No dialogue sampled or deduped.
    """
    archive = HERE / 'data/real-persona-chat.zip'
    if not archive.is_file():
        raise FileNotFoundError(f'Missing the ORIGINAL corpus: {archive}')
    records = read_corpus(archive)
    selected = sorted((r for r in records if subject in r['interlocutors']),
                      key=lambda r: r['dialogue_id'])
    if not selected:
        raise ValueError(f'Unknown/unused anonymous ID {subject!r}: no corpus dialogues found')
    speakers = sorted({s for r in records for s in r['interlocutors']})
    partners = sorted({s for r in selected for s in r['interlocutors'] if s != subject})
    dialogues, provenance = [], []
    for i, r in enumerate(selected, 1):
        partner_id = next(s for s in r['interlocutors'] if s != subject)
        turns = [dict(turn_id=j, text=sanitize(u['text'], speakers))
                 for j, u in enumerate((u for u in r['utterances']
                                        if u['interlocutor_id'] == partner_id), 1)]
        if not turns:
            raise ValueError(f'No visible A turns for {subject}/{r["dialogue_id"]}')
        did = f'D{i}'
        dialogues.append(dict(dialogue=did,
                              partner=f'A{partners.index(partner_id)+1}',
                              visible_turns=turns))
        provenance.append(dict(dialogue=did, source=r['dialogue_id'],
                               a_id=partner_id, b_id=subject))
    inputs = dict(dialogues=dialogues)
    selection = dict(selected_b=subject, provenance=provenance,
                     corpus_sha256=sha256(archive),
                     all_source_dialogues_included=True, duplicates_removed=False,
                     rule='ALL dialogues containing B; source dialogue_id sorted; '
                          'A labels from sorted distinct partner IDs; ONLY partner A turns')
    # The original verifier checks the original A-only text and ordering precisely.
    original.verify_inputs(subject, inputs, selection, records, speakers)
    return inputs, selection, partners


def prepare(subject: str, folder: Path):
    inputs, selection, partners = select_subject(subject)
    folder.mkdir(parents=True, exist_ok=True)
    source_hashes = original.hashes()
    freeze(folder / 'inputs.json', inputs)
    freeze(folder / 'selection.json', selection)
    freeze(folder / 'design.json', dict(
        subject=subject,
        pipeline='elara_subject_v2 -> one-pass A-self misattribution filter -> exact dedup -> Summary',
        extraction_method=algorithm.METHOD,
        original_runner_sha256=source_hashes['filtered_portrait_repeat.py'],
        original_code_sha256=source_hashes,
        input_selection='ALL A-only turns, same sort/sanitize/partner labels as original',
        new_extraction=True, new_direct=True, old_response_cache_reused=False,
        self_profile_access_in_inference=False,
        filter_policy='DROP only clear cited A-self misattribution; KEEP UNKNOWN and all other cases',
        no_post_summary_audit=True, inputs_digest=digest(inputs),
        original_model=MODEL, original_endpoint=ENDPOINT))
    # Snapshot original code exactly, byte-for-byte, with no modifications.
    for name in CODE:
        destination = folder / 'source_snapshot' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if destination.read_bytes() != (HERE / name).read_bytes():
                raise ValueError('Original code snapshot changed: ' + str(destination))
        else:
            destination.write_bytes((HERE / name).read_bytes())
    total = sum(len(d['visible_turns']) for d in inputs['dialogues'])
    print(f'[{subject}] 找到 {len(inputs["dialogues"])} 段对话，'
          f'{len(partners)} 个不同的 A，{total} 条 A 发言。', flush=True)
    print('对侧 A 匿名ID：' + ', '.join(partners), flush=True)
    print(f'语料 SHA-256：{selection["corpus_sha256"]}', flush=True)
    return inputs, selection


class DeferredClient:
    """Uses the UNMODIFIED Client.call in separate logged retry epochs.

    A new retry epoch resets the original Client's 6-attempt transport budget
    without rewriting its append-only ledgers. Successful old responses are
    recovered by exact (logical_name, endpoint, payload) hash, even when a
    multi-call ELARA pipeline is resumed partway through.

    Unknown-billing requests and unresolved starts are NEVER silently re-sent;
    allow_unknown_billing=True explicitly opts into that financial risk.
    """
    def __init__(self, key: str, folder: Path, endpoint: str, allow_unknown_billing: bool):
        self.folder = folder
        self.endpoint = endpoint
        self.key = key
        self.allow_unknown_billing = allow_unknown_billing
        self.clients = {0: Client(key, folder, endpoint)}
        self.epoch = 0
        retry_root = folder / 'retry_epochs'
        if retry_root.exists():
            for sub in retry_root.iterdir():
                if sub.is_dir() and re.fullmatch(r'round_\d+', sub.name):
                    number = int(sub.name.split('_')[-1])
                    self.clients[number] = Client(key, sub, endpoint)

    def set_epoch(self, epoch: int):
        self.epoch = epoch
        if epoch not in self.clients:
            target = self.folder / 'retry_epochs' / f'round_{epoch}'
            self.clients[epoch] = Client(self.key, target, self.endpoint)

    def call(self, name, payload, validate):
        task = digest(dict(name=name, endpoint=self.endpoint, payload=payload))
        # Read caches from previous and current retry epochs, newest first.
        for epoch in sorted(self.clients, reverse=True):
            client = self.clients[epoch]
            if epoch > self.epoch:
                continue
            with client.lock:
                rows = [r for r in client.rows if r.get('task_id') == task]
            for r in reversed(rows):
                if r.get('event') == 'complete' and r.get('http_status') == 200:
                    try:
                        return Client.parse(r['body'], validate), task
                    except (ValueError, KeyError, AttributeError, TypeError, IndexError):
                        pass
        # A transport error may have been billed; do not assume otherwise.
        if not self.allow_unknown_billing:
            for epoch in sorted(self.clients):
                if epoch > self.epoch:
                    continue
                client = self.clients[epoch]
                with client.lock:
                    rows = [r for r in client.rows if r.get('task_id') == task]
                starts = {r['attempt_id'] for r in rows if r.get('event') == 'start'}
                ends = {r['attempt_id'] for r in rows if r.get('event') == 'complete'}
                acks = {r['attempt_id'] for r in rows if r.get('event') == 'network_retry_acknowledged'}
                if starts - ends or any(r.get('billing_unknown') and
                                        r['attempt_id'] not in acks for r in rows):
                    raise RuntimeError('Uncertain-billing / unresolved request: ' + name +
                                       ' (manual review required, or --allow-unknown-billing-retry)')
        return self.clients[self.epoch].call(name, payload, validate)

    def ledgers(self):
        return [(index, client.path) for index, client in sorted(self.clients.items())
                if client.path.exists()]


def run_jobs(jobs, func, workers, stage):
    """Do every independent job; never stop a stage on an individual failure."""
    if not jobs:
        return {}
    failures = {}
    say(f'[{stage}] 开始处理 {len(jobs)} 个任务，workers={workers}')
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(func, key, arg): key for key, arg in jobs.items()}
        if tqdm is not None:
            iterator = tqdm(as_completed(futures), total=len(futures), desc=stage,
                            unit='任务', dynamic_ncols=True)
        else:
            iterator = as_completed(futures)
        count = 0
        for future in iterator:
            key = futures[future]
            count += 1
            try:
                future.result()
            except Exception as exc:
                failures[key] = f'{type(exc).__name__}: {str(exc)[:600]}'
                say(f'[{stage}] 失败（先跳过）{key}：{failures[key]}')
            if tqdm is None:
                print(f'\r[{stage}] {count}/{len(futures)} 完成', end='\n' if count == len(futures) else '', flush=True)
    say(f'[{stage}] 完成：成功 {len(jobs)-len(failures)}，失败 {len(failures)}')
    return failures


def extracted_ready(inputs, folder):
    return {d['dialogue'] for d in inputs['dialogues']
            if (folder / 'attributes' / f'{d["dialogue"]}.json').exists()}


def collect_records(inputs, folder, allow_partial=False):
    records = []
    for d in inputs['dialogues']:
        file = folder / 'attributes' / f'{d["dialogue"]}.json'
        if not file.exists():
            if allow_partial:
                continue
            raise FileNotFoundError(f'Extraction not complete: {file}')
        for c in load(file)['prediction']['claims']:
            records.append(dict(source_id=f'{d["dialogue"]}/{c["candidate_id"]}',
                                dialogue=d['dialogue'], partner=d['partner'], claim=c))
    if len(records) != len({r['source_id'] for r in records}):
        raise ValueError('Non-unique claim IDs')
    return records


def filter_jobs(inputs, folder):
    records = collect_records(inputs, folder, allow_partial=True)
    jobs = {}
    for d in inputs['dialogues']:
        group = [r for r in records if r['dialogue'] == d['dialogue']]
        for idx in range(0, len(group), 12):
            number = idx // 12 + 1
            name = f'{d["dialogue"]}_{number}'
            target = folder / 'filter_batches' / (name + '.json')
            if not target.exists():
                jobs[name] = (d['dialogue'], number, group[idx:idx+12])
    return jobs


def assemble(inputs, folder):
    """Exact original ordering: dialogue -> claim -> filter chunk -> dedup."""
    records = collect_records(inputs, folder)
    filter_tasks = []
    for d in inputs['dialogues']:
        group = [r for r in records if r['dialogue'] == d['dialogue']]
        for idx in range(0, len(group), 12):
            number = idx//12 + 1
            path = folder / 'filter_batches' / f'{d["dialogue"]}_{number}.json'
            if not path.exists():
                return False
            filter_tasks.append(load(path)['decisions'])
    decisions = [decision for chunk in filter_tasks for decision in chunk]
    byid = {x['source_id']: x for x in decisions}
    if len(decisions) != len(records) or set(byid) != {r['source_id'] for r in records}:
        raise ValueError('Filter decisions missing, overlapping or extra')
    decisions = [byid[r['source_id']] for r in records]
    kept = [r for r in records if byid[r['source_id']]['decision'] == 'KEEP']
    unique = portraits.deduplicate(kept)
    freeze(folder / 'attributes_all.json', records)
    freeze(folder / 'subject_decisions.json', decisions)
    freeze(folder / 'attributes_filtered.json', kept)
    freeze(folder / 'deduplicated.json', unique)
    freeze(folder / 'subject_filter_report.json', dict(
        original_claims=len(records), kept_claims=len(kept),
        dropped_claims=len(records)-len(kept),
        kept_unique_claim_strings=len(unique),
        decision_counts=dict(Counter(x['decision'] for x in decisions)),
        drop_reasons=dict(Counter(x['reason_code'] for x in decisions if x['decision'] == 'DROP')),
        overrides=sum(bool(x['override_reason']) for x in decisions), semantic_filter_passes=1))
    return True


def audit_requests(inputs, folder, clients, unique):
    """Compare all sent request prompts and visible inputs against original code."""
    ledger = []
    for _, path in clients.ledgers():
        ledger.extend(json.loads(line) for line in path.read_text(encoding='utf-8').splitlines())
    starts = [row for row in ledger if row.get('event') == 'start']
    ends = [row for row in ledger if row.get('event') == 'complete']
    completed = {row['attempt_id'] for row in ends}
    # In-flight starts remain a hard verification failure, not silently ignored.
    if any(row['attempt_id'] not in completed for row in starts):
        raise ValueError('Ledger contains unresolved starts')
    dialogues = {d['dialogue']: d for d in inputs['dialogues']}
    requests_by_kind = Counter()
    for row in starts:
        req = row['request']
        if (req['model'] != MODEL or req['temperature'] != 0 or
                req['enable_thinking'] is not True):
            raise ValueError('Model parameters differ from original')
        name = row['logical_name']
        if name.endswith('/direct') or name.endswith('/summary'):
            method = name.rsplit('/', 1)[-1]
            if req != load(folder / f'{method}_request.json'):
                raise ValueError('Portrait request differs from original')
            requests_by_kind[method] += 1
        elif '/filter/' in name:
            _, _, did, number = name.split('/')
            group = [r for r in load(folder / 'attributes_all.json') if r['dialogue'] == did]
            chunk = group[(int(number)-1)*12:int(number)*12]
            expected = original.filter_request(subject_filter.packet_for_dialogue(did, chunk, inputs))
            if req != expected:
                raise ValueError('Filter request differs from original')
            requests_by_kind['filter'] += 1
        elif '/elara/' in name:
            stage = name.rsplit('/', 1)[-1]
            method = algorithm.AUDIT if stage.startswith('audit_') else {
                'explicit': algorithm.EXPLICIT, 'implicit': algorithm.IMPLICIT,
                'gap_scan': algorithm.GAP_SCAN}[stage]
            if req['messages'][0]['content'] != method:
                raise ValueError('Original ELARA prompt differs')
            did = name.split('/')[1].removeprefix('subject_v2_')
            expected_turns = [dict(t, speaker='A', text='A says: '+t['text'])
                              for t in dialogues[did]['visible_turns']]
            payload = json.loads(req['messages'][1]['content'])
            if (payload['visible_turns'] != expected_turns or
                    set(payload) - {'visible_turns', 'target', 'existing_claims', 'candidates'}):
                raise ValueError('Original ELARA A-only payload differs')
            requests_by_kind['extraction'] += 1
        else:
            raise ValueError('Unexpected request type: ' + name)
    usage = Counter()
    unknown_billing = 0
    for row in ends:
        unknown_billing += bool(row.get('billing_unknown'))
        for key, value in row.get('body', {}).get('usage', {}).items():
            if isinstance(value, (float, int)):
                usage[key] += value
    return dict(request_attempts=dict(requests_by_kind), returned_usage=dict(usage),
                unknown_billing_attempts=unknown_billing,
                ledger_files=[str(path) for _, path in clients.ledgers()])


def verify(subject, folder, inputs, selection, clients):
    if load(folder / 'design.json')['original_code_sha256'] != original.hashes():
        raise ValueError('Core code changed since prepare (refuse incompatible resume)')
    if load(folder / 'design.json')['inputs_digest'] != digest(inputs):
        raise ValueError('Inputs changed since prepare')
    if selection['selected_b'] != subject:
        raise ValueError('Wrong target ID')
    # Verify full A-only corpus matching, plus all output validation semantics.
    corpus = read_corpus(HERE / 'data/real-persona-chat.zip')
    speakers = sorted({s for r in corpus for s in r['interlocutors']})
    original.verify_inputs(subject, inputs, selection, corpus, speakers)
    records = collect_records(inputs, folder)
    if load(folder / 'attributes_all.json') != records:
        raise ValueError('Extracted records differ')
    decisions = load(folder / 'subject_decisions.json')
    byid = {d['source_id']: d for d in decisions}
    if len(byid) != len(records) or set(byid) != {r['source_id'] for r in records}:
        raise ValueError('Incomplete filter decisions')
    kept = [r for r in records if byid[r['source_id']]['decision'] == 'KEEP']
    unique = portraits.deduplicate(kept)
    if kept != load(folder / 'attributes_filtered.json') or unique != load(folder / 'deduplicated.json'):
        raise ValueError('Filtered / deduplicated attributes differ')
    lookup = subject_filter.get_turns(inputs)
    for rec in records:
        item = byid[rec['source_id']]
        if item['decision'] == 'DROP':
            if not subject_filter.evidence_exact(rec, lookup):
                raise ValueError('DROP is missing an exact original quote')
            if not item['self_quote'].strip() or not any(item['self_quote'] in e['quote']
                        for e in rec['claim']['evidence']):
                raise ValueError('DROP self-quote not grounded')
            if not ((item['actual_owner'] == 'A' and item['reason_code'] in subject_filter.A_DROP_REASONS)
                    or (item['actual_owner'] == 'MIXED' and item['reason_code'] == 'MIXED_A_B')):
                raise ValueError('DROP decision violates original policy')
    if load(folder/'direct_request.json') != original.direct_request(inputs):
        raise ValueError('Direct request differs')
    if load(folder/'summary_request.json') != portraits.request(
            original.summary_prompt(inputs, unique), dict(unique_attributes=unique)):
        raise ValueError('Summary request differs')
    for method in ('summary', 'direct'):
        raw = load(folder / f'{method}_raw.json')['prediction']
        portraits.validate_portraits(raw, method, inputs, unique)
        expected = portraits.materialize(raw, unique) if method == 'summary' else raw
        if load(folder / f'{method}_portraits.json') != expected:
            raise ValueError(f'{method} portrait mismatch')
    audit = audit_requests(inputs, folder, clients, unique)
    return dict(passed=True, all_A_only_sources_verified=True,
                unchanged_elara_subject_v2=True, one_pass_subject_filter=True,
                exact_string_dedup=True, complete_summary_partition=True,
                original_direct_prompt=True, persona_blind_until_export=True,
                original_code_sha256=original.hashes(), **audit)


def export(subject, folder, inputs):
    """Persona is FIRST read HERE, only after both model outputs and audit pass."""
    archive = HERE / 'data/real-persona-chat.zip'
    with zipfile.ZipFile(archive) as z:
        filename = next(n for n in z.namelist()
                        if n.endswith('/real_persona_chat/interlocutors.json'))
        profiles = json.loads(z.read(filename))
    corpus = read_corpus(archive)
    speakers = sorted({s for r in corpus for s in r['interlocutors']})
    profile = [dict(archive_id=f'P{i}', statement=sanitize(text, speakers))
               for i, text in enumerate(profiles[subject]['persona'], 1)]
    freeze(folder / 'self_portrait.json', profile)
    bundle = dict(self_portrait=profile,
                  summary=load(folder / 'summary_portraits.json'),
                  direct=load(folder / 'direct_portraits.json'))
    joined = [f'# {subject} 的三份画像（同口径单侧实验）', '']
    for method, items in [('self', profile), ('summary', bundle['summary']['portraits']),
                          ('direct', bundle['direct']['portraits'])]:
        title = {'self': '自述画像（语料原文）', 'summary': 'Summary 画像',
                 'direct': 'direct 画像'}[method]
        lines = [f'# {subject} — {title}', '']
        for item in items:
            pid = item.get('archive_id', item.get('portrait_id'))
            lines += [f'- **{pid}**：{item["statement"]}', '']
        if method != 'self':
            lines += ['模型输出的局限：' + bundle[method]['limitations'], '']
        (folder / f'{method}_portrait.md').write_text('\n'.join(lines), encoding='utf-8')
        joined += [f'## {subject}：{title}', ''] + lines[2:]
    save(folder / 'all_portraits.json', {subject: bundle})
    (folder / '三份画像汇总.md').write_text('\n'.join(joined), encoding='utf-8')
    report = load(folder / 'subject_filter_report.json')
    counts = dict(subject=subject, dialogues=len(inputs['dialogues']),
                  different_A=len({d['partner'] for d in inputs['dialogues']}),
                  A_turns=sum(len(d['visible_turns']) for d in inputs['dialogues']),
                  **report, self_statements=len(profile),
                  summary_statements=len(bundle['summary']['portraits']),
                  direct_statements=len(bundle['direct']['portraits']))
    save(folder / 'counts.json', counts)
    return counts


def execute(subject, folder, workers, retries, endpoint, allow_unknown_billing=False, dry_run=False):
    inputs, selection = prepare(subject, folder)
    if dry_run:
        print('DRY RUN：仅完成数据选择与冻结，未读取自述画像、未调用 API。', flush=True)
        return 0
    if endpoint != ENDPOINT:
        raise ValueError('For strict reproducibility, endpoint must remain original ' + ENDPOINT)
    key = os.getenv('QWEN_API_KEY') or os.getenv('DASHSCOPE_API_KEY')
    if not key:
        raise ValueError('缺少 QWEN_API_KEY / DASHSCOPE_API_KEY；请使用环境变量，不要写进脚本')
    clients = DeferredClient(key, folder, endpoint, allow_unknown_billing)

    def direct(_key, _arg):
        if (folder/'direct_portraits.json').exists(): return
        req = original.direct_request(inputs)
        freeze(folder/'direct_request.json', req)
        obj, tid = clients.call('filtered_repeat/direct', req,
                                lambda x: portraits.validate_portraits(x, 'direct', inputs, []))
        freeze(folder/'direct_raw.json', dict(prediction=obj, task_id=tid))
        freeze(folder/'direct_portraits.json', obj)

    def extract(did, item):
        target = folder/'attributes'/f'{did}.json'
        if target.exists(): return
        data = dict(item_id=f'realpersonachat/subject_v2_{did}/A_to_B',
                    dialogue_id=f'subject_v2_{did}', dataset='realpersonachat',
                    direction='A_to_B', visible_turns=item['visible_turns'])
        pred, audit = algorithm.pipeline(clients, data)  # UNMODIFIED!
        freeze(target, dict(prediction=pred, audit=audit))

    def filter_one(name, item):
        did, number, chunk = item
        path = folder/'filter_batches'/f'{name}.json'
        if path.exists(): return
        packet = subject_filter.packet_for_dialogue(did, chunk, inputs)
        lookup = subject_filter.get_turns(inputs)
        def validate(obj):
            subject_filter.validate_model_output(obj, None, chunk, lookup)
            return obj
        raw, tid = clients.call(f'filtered_repeat/filter/{did}/{number}',
                                original.filter_request(packet), validate)
        decisions = subject_filter.validate_model_output(raw, None, chunk, lookup)
        freeze(path, dict(task_id=tid, raw_prediction=raw, decisions=decisions))

    def summary(_key, _arg):
        if (folder/'summary_portraits.json').exists(): return
        unique = load(folder/'deduplicated.json')
        req = portraits.request(original.summary_prompt(inputs, unique),
                                dict(unique_attributes=unique))
        freeze(folder/'summary_request.json', req)
        obj, tid = clients.call('filtered_repeat/summary', req,
                                lambda x: portraits.validate_portraits(x, 'summary', inputs, unique))
        freeze(folder/'summary_raw.json', dict(prediction=obj, task_id=tid))
        freeze(folder/'summary_portraits.json', portraits.materialize(obj, unique))

    failures = {}
    def save_status(round_index, pending):
        save(folder/'task_status.json', dict(subject=subject, last_round=round_index,
            max_extra_retry_rounds=retries, pending=pending,
            finished_utc=datetime.now(timezone.utc).isoformat(),
            retry_strategy='skip failures, continue independent work; retry after initial pass; '
                           'original API Client.call, up to 6 internal attempts per task per retry epoch'))

    initial_jobs = {d['dialogue']: d for d in inputs['dialogues']
                    if not (folder/'attributes'/f'{d["dialogue"]}.json').exists()}
    initial_jobs.update({'direct': None} if not (folder/'direct_portraits.json').exists() else {})
    def first_job(key, item):
        return direct(key, item) if key == 'direct' else extract(key, item)
    failures.update(run_jobs(initial_jobs, first_job, workers, '首次：ELARA + Direct'))
    failures.update(run_jobs(filter_jobs(inputs, folder), filter_one, workers, '首次：主体过滤'))
    ready = all((folder/'attributes'/f'{d["dialogue"]}.json').exists() for d in inputs['dialogues'])
    if ready and assemble(inputs, folder):
        failures.update(run_jobs({'summary': None} if not (folder/'summary_portraits.json').exists() else {},
                                 summary, 1, '首次：Summary'))
    save_status(0, failures)

    for round_index in range(1, retries + 1):
        all_done = (all((folder/'attributes'/f'{d["dialogue"]}.json').exists() for d in inputs['dialogues'])
                    and not filter_jobs(inputs, folder)
                    and (folder/'direct_portraits.json').exists()
                    and (folder/'summary_portraits.json').exists())
        if all_done: break
        clients.set_epoch(round_index)
        say(f'========== 最终补跑：重试轮次 {round_index}/{retries} ==========')
        pending = {d['dialogue']: d for d in inputs['dialogues']
                   if not (folder/'attributes'/f'{d["dialogue"]}.json').exists()}
        if not (folder/'direct_portraits.json').exists(): pending['direct'] = None
        errors = run_jobs(pending, first_job, workers, f'补跑{round_index}：ELARA + Direct')
        errors.update(run_jobs(filter_jobs(inputs, folder), filter_one, workers,
                               f'补跑{round_index}：主体过滤'))
        ready = all((folder/'attributes'/f'{d["dialogue"]}.json').exists()
                    for d in inputs['dialogues'])
        if ready and assemble(inputs, folder):
            errors.update(run_jobs({'summary': None} if not (folder/'summary_portraits.json').exists() else {},
                                   summary, 1, f'补跑{round_index}：Summary'))
        failures = errors
        save_status(round_index, failures)

    missing = []
    for d in inputs['dialogues']:
        if not (folder/'attributes'/f'{d["dialogue"]}.json').exists():
            missing.append(f'extract/{d["dialogue"]}')
    missing += ['filter/'+key for key in filter_jobs(inputs, folder)]
    if not (folder/'direct_portraits.json').exists(): missing.append('direct')
    if not missing and not assemble(inputs, folder): missing.append('assemble')
    if not (folder/'summary_portraits.json').exists(): missing.append('summary')
    if missing:
        save(folder/'failed_items.json', dict(complete=False, missing=missing,
             errors=failures, completed_retry_rounds=retries,
             note='Successful artifacts preserved. Increase --retries and re-run the SAME output directory. '
                  'Review uncertain-billing failures before enabling their retry.'))
        say('仍有失败任务，未交付不完整的三份画像。失败详情：'+str(folder/'failed_items.json'))
        return 2
    verification = verify(subject, folder, inputs, selection, clients)
    save(folder/'verification.json', verification)
    counts = export(subject, folder, inputs)  # PERSONA LOADED ONLY AFTER INFERENCE
    save(folder/'completion.json', dict(complete=True, subject=subject,
        requested_retry_rounds=retries, verification_passed=True,
        original_pipeline_unchanged=True, counts=counts))
    if (folder/'failed_items.json').exists():
        (folder/'failed_items.json').unlink()
    say('=== 三份画像交付完成 ===')
    for method in ('self', 'summary', 'direct'):
        say(f'  {method}: {folder/f"{method}_portrait.md"}')
    say('  合并报告: '+str(folder/'三份画像汇总.md'))
    say('  校验记录: '+str(folder/'verification.json'))
    say('  统计: '+json.dumps(counts, ensure_ascii=False))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('subject', nargs='?', help='匿名 B 的 ID，例如 IB、IA、HW')
    parser.add_argument('--id', dest='subject_flag', help='与位置参数作用相同')
    parser.add_argument('--out', type=Path, help='输出目录，默认 runs/portrait_one_<ID>')
    parser.add_argument('--workers', type=int, default=8, help='并行任务数，默认 8')
    parser.add_argument('--retries', type=int, default=2,
        help='首次处理后在交付前补跑失败任务的轮次（每个轮次使用原版 Client 的重试策略）')
    parser.add_argument('--dry-run', action='store_true', help='仅抓取 A-only 输入和计数；不调用 API')
    parser.add_argument('--allow-unknown-billing-retry', action='store_true',
        help='明确允许补发可能已经计费的超时/中断请求（可能重复计费）')
    # Not configurable: strict comparability requires the exact reference endpoint.
    args = parser.parse_args(argv)
    subject = args.subject_flag or args.subject
    if not subject:
        parser.error('请提供匿名ID，如 python subject_one_portrait.py IB')
    if args.subject and args.subject_flag and args.subject != args.subject_flag:
        parser.error('位置参数匿名ID与 --id 不一致')
    if not re.fullmatch(r'[A-Z]{1,8}', subject):
        parser.error('匿名ID须为大写字母，例如 IA、HW、IB')
    if args.workers < 1 or args.retries < 0:
        parser.error('workers >= 1, retries >= 0')
    folder = (args.out or HERE/'runs'/f'portrait_one_{subject}').resolve()
    if folder == HERE or folder == HERE.parent:
        parser.error('输出不能覆盖项目源码目录')
    try:
        return execute(subject, folder, args.workers, args.retries, ENDPOINT,
                       args.allow_unknown_billing_retry, args.dry_run)
    except Exception as exc:
        print(f'FATAL: {type(exc).__name__}: {exc}', file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
