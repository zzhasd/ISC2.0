"""Freeze an unseen dialogue sample and a fixed attribute inventory."""
from pathlib import Path
import hashlib
import json
import random
import re

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data/stage2'
SEED=20261033
ATTRIBUTES=[
 ('headache','The target currently has a headache.','health'),
 ('fever','The target currently has a fever.','health'),
 ('cold','The target currently has a cold.','health'),
 ('stomach_problem','The target currently has a stomach or digestive problem.','health'),
 ('allergy','The target has an allergy.','health'),
 ('medical_treatment','The target is currently receiving or has just been prescribed medical treatment or medicine.','health'),
 ('pregnant','The target is currently pregnant.','health'),
 ('alcohol_use','The target drinks or has recently drunk alcohol.','health'),
 ('smokes','The target currently smokes tobacco.','health'),
 ('married','The target is currently married.','relationship'),
 ('marriage_planned','The target is planning or preparing their own marriage.','relationship'),
 ('divorce_separation','The target is divorced or is currently separating/divorcing from a spouse.','relationship'),
 ('has_children','The target has at least one child.','family'),
 ('has_son','The target has a son.','family'),
 ('has_daughter','The target has a daughter.','family'),
 ('unemployed','The target is currently unemployed.','employment'),
 ('employed','The target currently has a job.','employment'),
 ('job_seeking','The target is currently seeking or applying for a job.','employment'),
 ('financial_hardship','The target currently has personal financial hardship or insufficient funds.','finance'),
 ('personal_debt','The target currently owes a personal debt or has an outstanding personal loan.','finance'),
]

def norm(r): return re.sub(r'\W+','', ' '.join(r['turns']).lower())

def main():
 OUT.mkdir(exist_ok=True,parents=True)
 rows=[json.loads(x) for x in (ROOT/'data/dailydialog.jsonl').read_text(encoding='utf-8').splitlines()]
 old=json.loads((ROOT/'data/natural_pilot.json').read_text(encoding='utf-8'))
 oldids={x['id'] for x in old}
 excluded={norm(r) for r in rows if r['split']!='test' or r['id'] in oldids}
 unique={}
 for r in rows:
  if r['split']=='test' and norm(r) not in excluded:unique.setdefault(norm(r),r)
 pool=list(unique.values())
 rng=random.Random(SEED)
 random_arm=rng.sample(pool,16)
 used={r['id'] for r in random_arm}
 # Refined after an outcome-free lexical screening: avoid "cold weather" and
 # "can afford" flooding enrichment. The original screen remains archived.
 pat=re.compile(r'\b(?:my\s+(?:wife|husband|son|daughter|children)|your\s+(?:wife|husband|son|daughter|children)|headache|fever|stomachache|allerg\w*|unemployment|got fired|laid off|find a job|looking for a job|my salary|my debt|my loan|my wedding|our wedding|our marriage|I.{0,18}(?:pregnant|divorced|married|drunk|smoke|broke))\b',re.I)
 enriched_pool=[r for r in pool if r['id'] not in used and pat.search(' '.join(r['turns']))]
 enriched=rng.sample(enriched_pool,16)
 selected=[]
 for arm,subset in [('random',random_arm),('enriched',enriched)]:
  for r in subset:selected.append({**r,'arm':arm})
 rng.shuffle(selected)
 for name,data in [('inventory.json',[{'id':i,'claim':c,'domain':d} for i,c,d in ATTRIBUTES]),('dialogues.json',selected)]:
  p=OUT/name
  if p.exists() and json.loads(p.read_text(encoding='utf-8'))!=data:raise RuntimeError('Refusing to replace frozen selection')
  p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
 manifest={'seed':SEED,'pool_unique_dialogues':len(pool),'enrichment_pool':len(enriched_pool),'selected_dialogues':32,
           'random_dialogues':16,'enriched_dialogues':16,'target_views':64,'attributes_per_view':20,
           'attribute_decisions_per_condition':1280,'excluded_prior_pilot_ids':sorted(oldids),
           'sha256':{n:hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in ['inventory.json','dialogues.json']}}
 (OUT/'selection_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 print(json.dumps(manifest,indent=2))
 for r in selected:
  print('\nID',r['id'],'ARM',r['arm'])
  print('\n'.join(f'{i+1} S{i%2}: {t}' for i,t in enumerate(r['turns'])))

if __name__=='__main__':
 import sys
 sys.stdout.reconfigure(encoding='utf-8')
 main()
