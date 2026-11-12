"""Four fixed anonymous subjects: unchanged subject_v2 -> one-pass filter -> Summary.

Run from the repository root with QWEN_API_KEY set. Each run uses its own
append-only request ledger; old predictions and response caches are never reused.
"""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import zipfile

from .api import Client
from .core import HERE, MODEL, ENDPOINT, digest, freeze, load, save, sanitize
from . import elara_subject_v2 as algorithm
from . import elara_ja_subject_filter as subject_filter
from . import portrait_summary as portraits
from .prepare import read_corpus

OUT = HERE / 'runs/portrait_subject_filter_20261108'
SOURCES = {
    'IA': 'portrait_repeat_fourth_b_20261107',
    'HW': 'portrait_repeat_third_b_20261107',
    'HS': 'portrait_summary_20261107',
    'HU': 'portrait_repeat_new_b_20261107',
}
CODE = ['filtered_portrait_repeat.py', 'elara_subject_v2.py',
        'elara_ja_subject_filter.py', 'portrait_summary.py', 'api.py', 'core.py', 'prepare.py']


def hashes():
    return {n: hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in CODE}


def original_selection(subject):
    source = HERE/'runs'/SOURCES[subject]
    selection = HERE/'runs/single_b_profile_v2/selection.json' if subject == 'HS' else source/'selection.json'
    return source, load(selection)


def verify_inputs(subject, inputs, selection, corpus, speakers):
    assert selection['selected_b'] == subject
    selected = sorted((r for r in corpus if subject in r['interlocutors']), key=lambda r: r['dialogue_id'])
    assert [r['dialogue_id'] for r in selected] == [p['source'] for p in selection['provenance']]
    assert len(selected) == len(inputs['dialogues'])
    for r, p, d in zip(selected, selection['provenance'], inputs['dialogues'], strict=True):
        assert p['b_id'] == subject and p['a_id'] != subject
        assert d['dialogue'] == p['dialogue']
        expected = [dict(turn_id=i, text=sanitize(u['text'], speakers))
                    for i, u in enumerate((u for u in r['utterances'] if u['interlocutor_id'] == p['a_id']), 1)]
        assert d['visible_turns'] == expected


def prepare(root):
    corpus = read_corpus(HERE/'data/real-persona-chat.zip')
    speakers = sorted({s for r in corpus for s in r['interlocutors']})
    for subject in SOURCES:
        source, selection = original_selection(subject)
        inputs = load(source/'inputs.json')
        verify_inputs(subject, inputs, selection, corpus, speakers)
        folder = root/subject
        freeze(folder/'inputs.json', inputs)
        freeze(folder/'selection.json', selection)
        freeze(folder/'design.json', dict(subject=subject, source_run=str(source),
            pipeline='elara_subject_v2 -> one-pass A-self misattribution filter -> exact dedup -> Summary',
            extraction_method=algorithm.METHOD, new_extraction=True, new_direct=True,
            old_response_cache_reused=False, self_profile_access_in_inference=False,
            filter_policy='DROP only clear cited A-self misattribution; KEEP UNKNOWN and all other cases',
            no_post_summary_audit=True, inputs_digest=digest(inputs), code_sha256=hashes()))
        for name in CODE:
            target = folder/'source_snapshot'/name
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                assert target.read_bytes() == (HERE/name).read_bytes()
            else:
                target.write_bytes((HERE/name).read_bytes())
        print(f'{subject}: verified ALL {len(inputs["dialogues"])} dialogues, '
              f'{sum(len(d["visible_turns"]) for d in inputs["dialogues"])} A turns', flush=True)


def summary_prompt(inputs, unique):
    labels = '/'.join(sorted({d['partner'] for d in inputs['dialogues']}))
    return portraits.TOP.replace('209', str(len(unique))).replace('A1/A2/A3', labels)


def direct_request(inputs):
    labels = '/'.join(sorted({d['partner'] for d in inputs['dialogues']}))
    marked = dict(dialogues=[dict(d, visible_turns=[dict(t, speaker='A', text='A says: '+t['text'])
                   for t in d['visible_turns']]) for d in inputs['dialogues']])
    return portraits.request(portraits.DIRECT.replace('A1/A2/A3', labels), marked)


def filter_request(packet):
    return dict(model=MODEL, temperature=0, enable_thinking=True, thinking_budget=2048, max_tokens=8192,
                messages=[dict(role='system', content=subject_filter.SYSTEM),
                          dict(role='user', content=json.dumps(packet, ensure_ascii=False))])


def batch(jobs, function, workers, root, stage):
    errors = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(function, job): str(job[0:2]) for job in jobs}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                errors.append(dict(job=futures[future], error=f'{type(exc).__name__}: {exc}'))
                print(errors[-1], flush=True)
    save(root/f'{stage}_status.json', dict(complete=not errors, errors=errors))
    if errors:
        raise RuntimeError(f'{stage} incomplete; see status and per-subject ledgers')


def run(root, workers, endpoint=ENDPOINT):
    key = os.getenv('QWEN_API_KEY') or os.getenv('DASHSCOPE_API_KEY')
    clients = {s: Client(key, root/s, endpoint) for s in SOURCES}
    inputs = {s: load(root/s/'inputs.json') for s in SOURCES}
    for s in SOURCES:
        assert load(root/s/'design.json')['code_sha256'] == hashes()
        assert load(root/s/'design.json')['inputs_digest'] == digest(inputs[s])

    def extract_or_direct(job):
        s, kind, d = job
        folder = root/s
        if kind == 'direct':
            req = direct_request(inputs[s])
            freeze(folder/'direct_request.json', req)
            obj, tid = clients[s].call('filtered_repeat/direct', req,
                lambda x: portraits.validate_portraits(x, 'direct', inputs[s], []))
            freeze(folder/'direct_raw.json', dict(prediction=obj, task_id=tid))
            freeze(folder/'direct_portraits.json', obj)
            print(f'{s} direct: {len(obj["portraits"])} statements', flush=True)
        else:
            did = d['dialogue']; oid = 'subject_v2_'+did
            item = dict(item_id=f'realpersonachat/{oid}/A_to_B', dialogue_id=oid,
                        dataset='realpersonachat', direction='A_to_B', visible_turns=d['visible_turns'])
            pred, audit = algorithm.pipeline(clients[s], item)
            freeze(folder/'attributes'/f'{did}.json', dict(prediction=pred, audit=audit))
            print(f'{s} {did}: {len(pred["claims"])} attributes', flush=True)

    jobs = [(s, 'direct', None) for s in SOURCES]
    jobs += [(s, 'extract', d) for s in SOURCES for d in inputs[s]['dialogues']]
    batch(jobs, extract_or_direct, workers, root, 'extraction_and_direct')
    all_records = {}; filter_jobs = []
    for s in SOURCES:
        records = [dict(source_id=f'{d["dialogue"]}/{c["candidate_id"]}', dialogue=d['dialogue'],
                        partner=d['partner'], claim=c)
                   for d in inputs[s]['dialogues']
                   for c in load(root/s/'attributes'/f'{d["dialogue"]}.json')['prediction']['claims']]
        assert len({r['source_id'] for r in records}) == len(records)
        all_records[s] = records
        freeze(root/s/'attributes_all.json', records)
        for d in inputs[s]['dialogues']:
            group = [r for r in records if r['dialogue'] == d['dialogue']]
            filter_jobs += [(s, d['dialogue'], i//12+1, group[i:i+12]) for i in range(0, len(group), 12)]

    def filter_chunk(job):
        s, did, chunk_no, chunk = job
        packet = subject_filter.packet_for_dialogue(did, chunk, inputs[s])
        lookup = subject_filter.get_turns(inputs[s])
        def validate(obj):
            subject_filter.validate_model_output(obj, None, chunk, lookup)
            return obj
        obj, tid = clients[s].call(f'filtered_repeat/filter/{did}/{chunk_no}', filter_request(packet), validate)
        decisions = subject_filter.validate_model_output(obj, None, chunk, lookup)
        freeze(root/s/'filter_batches'/f'{did}_{chunk_no}.json',
               dict(task_id=tid, raw_prediction=obj, decisions=decisions))
        print(f'{s} filter {did}/{chunk_no}: DROP {sum(d["decision"]=="DROP" for d in decisions)}/{len(chunk)}', flush=True)

    batch(filter_jobs, filter_chunk, workers, root, 'filter')
    for s in SOURCES:
        records = all_records[s]
        decisions = [d for job in filter_jobs if job[0] == s
                     for d in load(root/s/'filter_batches'/f'{job[1]}_{job[2]}.json')['decisions']]
        byid = {d['source_id']: d for d in decisions}
        assert set(byid) == {r['source_id'] for r in records} and len(decisions) == len(records)
        decisions = [byid[r['source_id']] for r in records]
        kept = [r for r in records if byid[r['source_id']]['decision'] == 'KEEP']
        freeze(root/s/'subject_decisions.json', decisions)
        freeze(root/s/'attributes_filtered.json', kept)
        freeze(root/s/'deduplicated.json', portraits.deduplicate(kept))
        freeze(root/s/'subject_filter_report.json', dict(original_claims=len(records), kept_claims=len(kept),
            dropped_claims=len(records)-len(kept), kept_unique_claim_strings=len(portraits.deduplicate(kept)),
            decision_counts=dict(Counter(d['decision'] for d in decisions)),
            drop_reasons=dict(Counter(d['reason_code'] for d in decisions if d['decision']=='DROP')),
            overrides=sum(bool(d['override_reason']) for d in decisions), semantic_filter_passes=1))

    def summary(job):
        s = job[0]; folder = root/s
        unique = load(folder/'deduplicated.json')
        req = portraits.request(summary_prompt(inputs[s], unique), dict(unique_attributes=unique))
        freeze(folder/'summary_request.json', req)
        obj, tid = clients[s].call('filtered_repeat/summary', req,
            lambda x: portraits.validate_portraits(x, 'summary', inputs[s], unique))
        freeze(folder/'summary_raw.json', dict(prediction=obj, task_id=tid))
        freeze(folder/'summary_portraits.json', portraits.materialize(obj, unique))
        print(f'{s} summary: {len(obj["portraits"])} statements', flush=True)
    batch([(s,) for s in SOURCES], summary, min(workers, 4), root, 'summary')


def export(root):
    """Read self profiles only after both model outputs have been frozen."""
    bundle = {}; rows = []; combined = ['# 四位匿名者画像：主体错归属过滤后复验', '']
    with zipfile.ZipFile(HERE/'data/real-persona-chat.zip') as z:
        profiles = json.loads(z.read(next(n for n in z.namelist() if n.endswith('/real_persona_chat/interlocutors.json'))))
    corpus = read_corpus(HERE/'data/real-persona-chat.zip')
    speakers = sorted({s for r in corpus for s in r['interlocutors']})
    for s in SOURCES:
        folder = root/s
        assert all((folder/f'{m}_portraits.json').exists() for m in ('summary', 'direct'))
        self_profile = [dict(archive_id=f'P{i}', statement=sanitize(t, speakers))
                        for i, t in enumerate(profiles[s]['persona'], 1)]
        freeze(folder/'self_portrait.json', self_profile)
        bundle[s] = dict(self_portrait=self_profile,
                         summary=load(folder/'summary_portraits.json'), direct=load(folder/'direct_portraits.json'))
        for method, items in [('self', self_profile), ('summary', bundle[s]['summary']['portraits']),
                              ('direct', bundle[s]['direct']['portraits'])]:
            title = {'self': '自述画像（语料原文）', 'summary': 'Summary 画像', 'direct': 'direct 画像'}[method]
            lines = [f'# {s} — {title}', '']
            for item in items:
                pid = item.get('archive_id', item.get('portrait_id'))
                lines += [f'- **{pid}**：{item["statement"]}', '']
            if method != 'self':
                lines += ['模型输出的局限：'+bundle[s][method]['limitations'], '']
            (folder/f'{method}_portrait.md').write_text('\n'.join(lines), encoding='utf-8')
            combined += [f'## {s}：{title}', ''] + lines[2:]
        r = load(folder/'subject_filter_report.json')
        rows.append(dict(subject=s, dialogues=len(load(folder/'inputs.json')['dialogues']),
                         **r, self_statements=len(self_profile),
                         summary_statements=len(bundle[s]['summary']['portraits']),
                         direct_statements=len(bundle[s]['direct']['portraits'])))
    save(root/'all_portraits.json', bundle)
    (root/'四组画像汇总.md').write_text('\n'.join(combined), encoding='utf-8')
    save(root/'counts.json', rows)
    return rows


def verify(root):
    corpus = read_corpus(HERE/'data/real-persona-chat.zip')
    speakers = sorted({s for r in corpus for s in r['interlocutors']})
    results = {}
    for s in SOURCES:
        folder = root/s; inputs = load(folder/'inputs.json')
        assert load(folder/'design.json')['code_sha256'] == hashes()
        verify_inputs(s, inputs, load(folder/'selection.json'), corpus, speakers)
        records = load(folder/'attributes_all.json'); unique = load(folder/'deduplicated.json')
        expected_records = [dict(source_id=f'{d["dialogue"]}/{c["candidate_id"]}', dialogue=d['dialogue'],
                                partner=d['partner'], claim=c) for d in inputs['dialogues']
                            for c in load(folder/'attributes'/f'{d["dialogue"]}.json')['prediction']['claims']]
        assert records == expected_records
        decisions = {d['source_id']: d for d in load(folder/'subject_decisions.json')}
        assert set(decisions) == {r['source_id'] for r in records}
        kept = [r for r in records if decisions[r['source_id']]['decision'] == 'KEEP']
        assert kept == load(folder/'attributes_filtered.json') and portraits.deduplicate(kept) == unique
        lookup = subject_filter.get_turns(inputs)
        for rec in records:
            d = decisions[rec['source_id']]
            if d['decision'] == 'DROP':
                assert subject_filter.evidence_exact(rec, lookup)
                assert d['self_quote'].strip() and any(d['self_quote'] in e['quote'] for e in rec['claim']['evidence'])
                assert (d['actual_owner']=='A' and d['reason_code'] in subject_filter.A_DROP_REASONS) or (d['actual_owner']=='MIXED' and d['reason_code']=='MIXED_A_B')
        for m in ('summary', 'direct'):
            obj = load(folder/f'{m}_raw.json')['prediction']
            portraits.validate_portraits(obj, m, inputs, unique)
            assert load(folder/f'{m}_portraits.json') == (portraits.materialize(obj, unique) if m=='summary' else obj)
        assert load(folder/'direct_request.json') == direct_request(inputs)
        assert load(folder/'summary_request.json') == portraits.request(summary_prompt(inputs, unique), dict(unique_attributes=unique))
        ledger = [json.loads(line) for line in (folder/'attempts.jsonl').read_text(encoding='utf-8').splitlines()]
        starts = {r['attempt_id']: r for r in ledger if r['event']=='start'}
        ends = {r['attempt_id']: r for r in ledger if r['event']=='complete'}
        assert starts.keys() == ends.keys()
        counts = Counter(); usage = Counter()
        for r in starts.values():
            req = r['request']; name = r['logical_name']
            assert req['model']==MODEL and req['temperature']==0 and req['enable_thinking']
            content = json.loads(req['messages'][1]['content'])
            if '/elara/' in name:
                stage = name.rsplit('/', 1)[-1]
                prompt = algorithm.AUDIT if stage.startswith('audit_') else {'explicit':algorithm.EXPLICIT,'implicit':algorithm.IMPLICIT,'gap_scan':algorithm.GAP_SCAN}[stage]
                assert req['messages'][0]['content'] == prompt
                did = name.split('/')[1].removeprefix('subject_v2_')
                dialogue = next(d for d in inputs['dialogues'] if d['dialogue']==did)
                assert content['visible_turns'] == [dict(t, speaker='A', text='A says: '+t['text']) for t in dialogue['visible_turns']]
                assert set(content) <= {'visible_turns', 'target', 'existing_claims', 'candidates'}
                counts['extraction'] += 1
            elif '/filter/' in name:
                _, _, did, number = name.split('/')
                group = [rec for rec in records if rec['dialogue']==did]
                chunk = group[(int(number)-1)*12:int(number)*12]
                assert req == filter_request(subject_filter.packet_for_dialogue(did, chunk, inputs))
                counts['filter'] += 1
            else:
                m = name.rsplit('/', 1)[-1]
                assert m in ('direct', 'summary') and req == load(folder/f'{m}_request.json')
                counts[m] += 1
        for r in ends.values():
            for k, v in r.get('body', {}).get('usage', {}).items():
                if isinstance(v, (int,float)): usage[k] += v
        results[s] = dict(passed=True, all_A_only_sources_verified=True, unchanged_subject_v2=True,
            per_record_filter_before_dedup=True, summary_complete_partition=True,
            direct_only_original_dialogues=True, self_profile_excluded_from_inference=True,
            no_post_summary_model_audit=True, request_attempts=dict(counts), returned_usage=dict(usage),
            unknown_billing_attempts=sum(bool(r.get('billing_unknown')) for r in ends.values()))
    save(root/'verification.json', results)
    return results


def finish(root):
    verification = verify(root)
    rows = export(root)
    lines = ['# IA、HW、HS、HU 四组独立复验', '',
        'Summary 流程：原版 elara_subject_v2 → 一次主体错归属过滤 → 精确字符串去重 → Summary。', '',
        '四人沿用旧实验的全部对侧 A 发言，从头重新在线抽取、过滤并生成 Summary；direct 使用相同原文重新在线生成，提示词与参数沿用旧实验。未复用旧响应缓存。自述来自原始语料，仅在两路画像冻结后的交付阶段读取。', '',
        '| 匿名者 | 对话数 | 原始属性 | 删除 | 保留 | 去重后 | 自述条目 | Summary条目 | direct条目 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append('| '+' | '.join(str(r[k]) for k in ['subject','dialogues','original_claims','dropped_claims','kept_claims','kept_unique_claim_strings','self_statements','summary_statements','direct_statements'])+' |')
    lines += ['', '## 交付文件', '',
        '- [四组画像汇总](四组画像汇总.md)：12份画像的可读合并版。',
        '- `IA/`、`HW/`、`HS/`、`HU/`：各含 self_portrait.md、summary_portrait.md、direct_portrait.md。',
        '- `all_portraits.json`：全部画像；Summary JSON 保留逐条原始属性、证据及来源。',
        '- 每组的 subject_decisions.json、filter_batches/ 与 attempts.jsonl：过滤判断、原始响应和请求审计。',
        '- verification.json：全量输入、代码绑定、过滤约束、Summary覆盖、direct引用及请求隔离核验。', '',
        '只删除有逐字原文锚点且明确被标为 A 自述错归属的候选；UNKNOWN、第三方、泛化和证据不足等其他情况保留。不改写候选，不在 Summary 后追加模型审核。格式失败的重试会单独记入请求日志。', '',
        '引用匹配与流程核验通过不代表日语语义判断完全正确；本轮没有新增画像评分或错误率估计。自述保留日语原文。', '',
        '复现：设置进程环境变量 QWEN_API_KEY 后，在项目根目录运行：', '',
        '```powershell',
        'python -B -m isc113.identity_linkage.filtered_portrait_repeat all --out <新目录> --workers 8',
        '```', '', '模型与参数：抽取为原 subject_v2 的 512/4096；过滤为 thinking_budget=2048、max_tokens=8192；Summary/direct 为 2048/20000。均 qwen3.8-flash、temperature=0、enable_thinking=true。', '',
        '返回 usage 与未知计费请求数见 verification.json；不推算费用。']
    (root/'README.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    save(root/'completion.json', dict(complete=True, subjects=list(SOURCES), portrait_documents=12,
                                    verification=verification))
    print(json.dumps(rows, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['prepare', 'run', 'finish', 'all'])
    p.add_argument('--out', type=Path, default=OUT)
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--endpoint', default=ENDPOINT)
    a = p.parse_args()
    if a.workers < 1: p.error('workers must be positive')
    if a.command in ('prepare', 'all'): prepare(a.out)
    if a.command in ('run', 'all'): run(a.out, a.workers, a.endpoint)
    if a.command in ('finish', 'all'): finish(a.out)
