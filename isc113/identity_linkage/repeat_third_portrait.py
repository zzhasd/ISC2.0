"""Third anonymous B; unchanged inference modules, exclusion-only sampling change."""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import zipfile
from .core import HERE, digest, freeze, load, sanitize, save
from .prepare import read_corpus
from . import repeat_portrait as previous

OUT = HERE/'runs/portrait_repeat_third_b_20261107'


def prepare(folder):
    archive=HERE/'data/real-persona-chat.zip'
    records=read_corpus(archive)
    index=defaultdict(list)
    for r in records:
        for b in r['interlocutors']:index[b].append(r)
    prior_runs=['single_b_profile_v2','portrait_repeat_new_b_20261107']
    excluded=sorted({load(HERE/'runs'/run/'selection.json')['selected_b'] for run in prior_runs})
    assert len(excluded)==2
    eligible=sorted(b for b,rr in index.items() if b not in excluded and 10<=len(rr)<=20 and len({s for r in rr for s in r['interlocutors'] if s!=b})>=2)
    b=random.Random(previous.SEED).choice(eligible)
    selected=sorted(index[b],key=lambda r:r['dialogue_id'])
    speakers=sorted(index)
    partners=sorted({s for r in selected for s in r['interlocutors'] if s!=b})
    dialogues=[];provenance=[]
    for i,r in enumerate(selected,1):
        a=next(s for s in r['interlocutors'] if s!=b)
        turns=[dict(turn_id=j,text=sanitize(u['text'],speakers)) for j,u in enumerate([u for u in r['utterances'] if u['interlocutor_id']==a],1)]
        dialogues.append(dict(dialogue=f'D{i}',partner=f'A{partners.index(a)+1}',visible_turns=turns))
        provenance.append(dict(dialogue=f'D{i}',source=r['dialogue_id'],a_id=a,b_id=b))
    with zipfile.ZipFile(archive) as z:
        name=next(n for n in z.namelist() if n.endswith('/real_persona_chat/interlocutors.json'))
        profile=json.loads(z.read(name))[b]
    freeze(folder/'inputs.json',dict(dialogues=dialogues))
    freeze(folder/'archive_for_judges.json',[dict(archive_id=f'P{i}',statement=sanitize(s,speakers)) for i,s in enumerate(profile['persona'],1)])
    freeze(folder/'selection.json',dict(seed=previous.SEED,eligible=eligible,excluded_previous_b=excluded[0],excluded_previous_bs=excluded,previous_runs=prior_runs,selected_b=b,provenance=provenance,corpus_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),all_source_dialogues_included=True,duplicates_removed=False,rule='Same sorted 10..20 ALL-conversation / >=2-partner eligibility and same seed; exclude BOTH prior Bs before sampling; no persona/outcome selection'))
    freeze(folder/'design.json',dict(independent_repeat=True,third_b=True,user_authorized_new_extraction_for_new_b=True,attribute_count='natural output, no quota',extraction='unchanged elara_subject_v2.pipeline; no downstream admission gates',summary='unchanged TOP except actual input count and partner labels',direct='unchanged DIRECT except actual partner labels',generation='qwen3.8-flash thinking_budget=2048 max_tokens=20000 temperature=0',extraction_budget='unchanged 512/4096',scoring='none; user manual review',inputs_digest=digest(dict(dialogues=dialogues)),code_sha256=previous.hashes(),replication_entrypoint_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    for n in [*previous.hashes(),Path(__file__).name]:
        dest=folder/'source_snapshot'/n;dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():assert dest.read_bytes()==(HERE/n).read_bytes()
        else:dest.write_bytes((HERE/n).read_bytes())
    # Confirm the inference implementation is byte-identical to the second B run.
    for n,h in previous.hashes().items():
        assert hashlib.sha256((HERE/'runs/portrait_repeat_new_b_20261107/source_snapshot'/n).read_bytes()).hexdigest()==h
    print(json.dumps(dict(b=b,excluded=excluded,dialogues=len(dialogues),partners=len(partners),turns=sum(len(d['visible_turns']) for d in dialogues)),ensure_ascii=False),flush=True)


def finalize(folder):
    v=previous.audit(folder)
    selection=load(folder/'selection.json');b=selection['selected_b']
    assert b not in selection['excluded_previous_bs'] and len(selection['excluded_previous_bs'])==2
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==load(folder/'design.json')['replication_entrypoint_sha256']
    inp=load(folder/'inputs.json');summary=load(folder/'summary_portraits.json');direct=load(folder/'direct_portraits.json');archive=load(folder/'archive_for_judges.json')
    lines=[f'# 属性汇总组：第三个B（{b}）的画像','',f"Qwen3.8-flash + thinking 本次生成。{v['attributes']}条改进版抽取结果，经精确字符串去重成为{v['unique_strings']}项，再归并为{len(summary['portraits'])}条画像。未进行子代理评分，供人工审核。",'',summary['limitations'],'']
    for p in summary['portraits']:
        lines += ['## '+p['portrait_id'],'',p['statement'],'','### 原始属性与证据（完整保留）','']
        for u in p['source_details']:
            lines += ['- '+u['unique_id']+'：'+u['claim']]
            for m in u['members']:
                c=m['claim']
                lines += [f"  - 来源：{m['source_id']}；伙伴：{m['partner']}",f"  - attribute：{c['attribute']}",f"  - certainty：{c['certainty']}；confidence：{c['confidence']}"]
                for e in c['evidence']:lines += [f"  - A原文（turn {e['turn_id']}）：{e['quote']}"]
                extra={k:v for k,v in c.items() if k not in ('claim','attribute','certainty','confidence','evidence')}
                lines += ['  - 其余原始元数据：`'+json.dumps(extra,ensure_ascii=False)+'`']
        lines.append('')
    (folder/'summary_portraits.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    previous.export_portraits(folder,'direct')
    dest=folder/'direct_portraits.md';text=dest.read_text(encoding='utf-8')
    text=text.replace('# direct：B的画像',f"# direct+thinking组：第三个B（{b}）的画像\n\nQwen3.8-flash开启thinking，仅根据全部A侧原文直接生成{len(direct['portraits'])}条画像。未进行子代理评分，供人工审核。",1)
    dest.write_text(text,encoding='utf-8')
    lines=[f'# 第三个B（{b}）的个人自述','', '以下为语料中的原始日语自述，仅将身份占位符按原实验规则脱敏。未拆分原子命题、未翻译或补写；未提供给任何画像生成调用。','']
    for a in archive:lines += [f"## {a['archive_id']}",'',a['statement'],'']
    (folder/'new_B_self_statements.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    assert not list(folder.glob('judgment_*_sol.json'))
    for f in folder.rglob('*'):
        if f.is_file() and f.suffix in ('.py','.json','.jsonl','.md'):
            assert not re.search(r'sk-[A-Za-z0-9_.-]{20,}',f.read_text(encoding='utf-8')), 'Credential pattern found in artifacts'
    rows=[json.loads(s) for s in (folder/'attempts.jsonl').read_text(encoding='utf-8').splitlines()]
    starts=[r for r in rows if r['event']=='start'];ends=[r for r in rows if r['event']=='complete']
    start=min(datetime.fromisoformat(r['utc']) for r in starts)
    end=max(datetime.fromisoformat(r['utc'])+timedelta(seconds=r['elapsed_seconds']) for r in ends)
    tz=timezone(timedelta(hours=8))
    v.update(excluded_previous_bs=selection['excluded_previous_bs'],summary_portraits=len(summary['portraits']),direct_portraits=len(direct['portraits']),archive_statements=len(archive),credential_scan_passed=True,no_agent_evaluation=True,local_start=start.astimezone(tz).isoformat(),local_end=end.astimezone(tz).isoformat(),wall_seconds=round((end-start).total_seconds(),3))
    save(folder/'verification.json',v)
    freeze(folder/'manual_review_instruction.json',dict(user_instruction='排除之前两个B，流程不变，交付两组画像及第三个B原始自述，由用户人工审核',judge_evaluation=False))
    print(json.dumps(v,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run','finalize']);p.add_argument('--folder',type=Path,default=OUT);p.add_argument('--workers',type=int,default=8);a=p.parse_args()
    if a.command=='run':
        previous.extract(a.folder,a.workers)
        previous.generate(a.folder)
        finalize(a.folder)
    else:globals()[a.command](a.folder)
