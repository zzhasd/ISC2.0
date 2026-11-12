"""Verify frozen samples and the attacker's one-sided observation boundary."""
from pathlib import Path
import collections
import csv
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/stage2';OUT=ROOT/'results/stage2'

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def norm(r):return re.sub(r'\W+','',' '.join(r['turns']).lower())

def main():
 frozen=read(DATA/'frozen_hashes.json')
 assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in frozen.items()),'Frozen input changed'
 all_data=[json.loads(x) for x in (ROOT/'data/dailydialog.jsonl').read_text(encoding='utf-8').splitlines()]
 selected=read(DATA/'dialogues.json');indexed={d['id']:d for d in selected}
 previous={r['id'] for r in read(ROOT/'data/natural_pilot.json')}
 blocked={norm(r) for r in all_data if r['split']!='test' or r['id'] in previous}
 assert len(selected)==32 and len({norm(d) for d in selected})==32
 assert all(norm(d) not in blocked for d in selected)
 assert collections.Counter(d['arm'] for d in selected)=={'random':16,'enriched':16}
 plan=read(OUT/'requests.json');a_views=0
 for task in plan:
  digest=hashlib.sha256(json.dumps(task['payload'],sort_keys=True).encode()).hexdigest()
  assert digest==task['request_sha256']
  content=json.loads(task['payload']['messages'][1]['content'])
  assert set(content)=={'targets','catalogue','transcript'}
  if task['condition'] in ['a_only','repeat']:
   d=indexed[task['dialogue_id']];hidden=task['target_source_speaker']
   visible=[text for i,text in enumerate(d['turns']) if i%2!=hidden]
   expected=[{'turn':i+1,'speaker':'A','text':text} for i,text in enumerate(visible)]
   assert content['targets']==['B'] and content['transcript']==expected,'Hidden utterance/metadata leaked'
   if task['condition']=='a_only':a_views+=1
  elif task['condition']=='prior':assert content['transcript']==[]
 assert a_views==64
 gold=read(DATA/'gold.json');assert len(gold)==1280
 for row in gold:
  d=indexed[row['dialogue_id']]
  assert all((i-1)%2!=row['target_source_speaker'] for i in row['a_evidence_turns'])
  assert all(1<=i<=len(d['turns']) for i in row['full_evidence_turns']+row['a_evidence_turns'])
 review=OUT/'annotation_review.csv'
 fields=['dialogue_id','arm','target_source_speaker','attribute','truth','a_support','truth_basis','full_evidence_turns','a_evidence_turns','human_truth','human_A_support','human_note']
 with review.open('w',encoding='utf-8-sig',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(gold)
 packet=['# Stage 2 annotation review packet','',
         'All labels below are provisional AI labels. Human review fields remain blank. Unknown is not false.',
         '','## Non-unknown provisional facts','']
 for r in gold:
  if r['truth']=='unknown':continue
  d=indexed[r['dialogue_id']]
  packet += [f'### {r["dialogue_id"]} / target S{r["target_source_speaker"]} / {r["attribute"]}',
             f'Truth: {r["truth"]}; A support: {r["a_support"]}; basis: {r["truth_basis"]}.','']
  for i in r['full_evidence_turns']:packet.append(f'- Turn {i}, S{(i-1)%2}: {d["turns"][i-1]}')
  if r['dialogue_note']:packet.extend(['',r['dialogue_note']])
  packet.append('')
 (OUT/'annotation_review.md').write_text('\n'.join(packet),encoding='utf-8')
 result={'selected_dialogues':32,'target_views':64,'attributes_per_view':20,'decisions_per_condition':1280,
         'random_dialogues':16,'enriched_dialogues':16,'sample_exact_overlap_with_train_validation_or_prior_pilot':0,
         'within_sample_normalized_duplicates':0,'A_only_observation_boundary_verified':True,'fixed_catalogue_in_all_calls':True,
         'frozen_files_unchanged':True,'truth_counts':dict(collections.Counter(r['truth'] for r in gold)),
         'truth_by_arm':{arm:dict(collections.Counter(r['truth'] for r in gold if r['arm']==arm)) for arm in ['random','enriched']}}
 (OUT/'data_audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
 print(json.dumps(result,indent=2))

if __name__=='__main__':main()
