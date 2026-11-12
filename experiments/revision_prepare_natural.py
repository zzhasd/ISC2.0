"""Freeze additional held-out dialogues before investigator labels or attacks."""
from pathlib import Path
import json
import random
import re
from revision_api import ROOT, freeze, save, digest
from stage2_prepare import norm

DATA = ROOT/'data/revision'
def main():
    rows=[json.loads(x) for x in (ROOT/'data/dailydialog.jsonl').read_text(encoding='utf-8').splitlines()]
    old={r['id'] for r in json.loads((ROOT/'data/natural_pilot.json').read_text(encoding='utf-8'))}
    old.update(r['id'] for r in json.loads((ROOT/'data/stage2/dialogues.json').read_text(encoding='utf-8')))
    excluded={norm(r) for r in rows if r['split']!='test' or r['id'] in old}
    unique={}
    for r in rows:
        if r['split']=='test' and norm(r) not in excluded: unique.setdefault(norm(r),r)
    pool=list(unique.values()); rng=random.Random(20261101)
    random_arm=rng.sample(pool,96); used={r['id'] for r in random_arm}
    pat=re.compile(r'\b(?:my\s+(?:wife|husband|son|daughter|children)|your\s+(?:wife|husband|son|daughter|children)|headache|fever|stomachache|allerg\w*|unemployment|got fired|laid off|find a job|looking for a job|my salary|my debt|my loan|my wedding|our wedding|our marriage|I.{0,18}(?:pregnant|divorced|married|drunk|smoke|broke))\b',re.I)
    enriched=[r for r in pool if r['id'] not in used and pat.search(' '.join(r['turns']))]
    selected=[{**r,'arm':arm} for arm,subset in [('random',random_arm),('enriched',enriched)] for r in subset]
    freeze(DATA/'dialogues.json',selected)
    save(DATA/'selection_manifest.json',{'seed':20261101,'eligible_unique_dialogues':len(pool),
         'random_dialogues':len(random_arm),'residual_enriched_dialogues':len(enriched),
         'selected_dialogues':len(selected),'views':2*len(selected),'attributes_per_view':20,
         'normalized_exact_train_validation_prior_overlap':0,'dialogues_sha256':digest(selected)})
    print(json.dumps({'selected':len(selected),'random':len(random_arm),'enriched':len(enriched)}))

if __name__=='__main__': main()
