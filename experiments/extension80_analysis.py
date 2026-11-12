"""Review queues, isolated new/merged views and unchanged historical scoring functions."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import isc4_open as i4
import isc4_review as r4
import isc4_analyze as a4
import isc7_analyze as a7
from isc4_open import ROOT,read,save,sha,freeze
from extension80 import DATA,OUT,configure

def queues():
    configure()
    if (OUT/'isc4/predictions.json').exists():
        r4.OUT=OUT/'isc4';r4.DATA=DATA;r4.build()
        q=read(OUT/'isc4/review_queue.json')
        for i,r in enumerate(q):r['index']=i
        save(OUT/'isc4/review_queue.json',q)
    if (OUT/'isc7/predictions.json').exists():
        a7.OUT=OUT/'isc7';a7.DATA=DATA;a7.prepare_review()

def make_views(merged=False,prefix_only=False):
    dd=ROOT/'data/merged112' if merged else DATA/'analysis'
    dest=ROOT/'results/merged112' if merged else OUT
    ds=read(DATA/'dialogues.json');refs=read(DATA/'reference.json')
    if merged:
        ds=read(ROOT/'data/isc4/dialogues.json')+ds
        refs=read(ROOT/'data/isc4/full_AB_reference_v2.json')+refs
    freeze(dd/'dialogues.json',ds);freeze(dd/'full_AB_reference_v2.json',refs);freeze(dd/'reference.json',refs)
    pp=read(OUT/'isc4/baseline/requests.json')
    if merged:pp=read(ROOT/'results/isc4/baseline/requests.json')+pp
    freeze(dd/'manifest.json',{'request_sha256':sha(pp),'reference_sha256':sha(refs),'dialogues':len(ds)})
    if merged:freeze(dest/'isc4/baseline/requests.json',pp)
    for kind,files in [('isc4',['predictions.json','assistant_semantic_review.json']),('isc7',['predictions.json','semantic_review.json','execution_audit.json'])]:
        if prefix_only and kind=='isc7':continue
        for name in files:
            rows=read(OUT/kind/name)
            if merged:rows=read(ROOT/'results'/kind/name)+[r for r in rows if r.get('dialogue_id')!='shared_prior']
            elif kind=='isc4' and name=='predictions.json' and not any(r['dialogue_id']=='shared_prior' for r in rows):
                rows += [r for r in read(ROOT/'results/isc4/predictions.json') if r['dialogue_id']=='shared_prior']
            save(dest/kind/name,rows)
    save(dest/'prior_provenance.json',{'shared_prior_reused_from':'results/isc4/predictions.json','new_empty_input_calls':0})
    return dd,dest

def analyze(merged=False,prefix_only=False):
    dd,dest=make_views(merged,prefix_only)
    a4.DATA=dd;a4.OUT=dest/'isc4';a4.main()
    sm=read(a4.OUT/'summary.json')
    sm['limitations']=[s for s in sm['limitations'] if not s.startswith('32 previously') and not s.startswith('reference finished')]
    sm['limitations']+=['new reference frozen before viewing new Qwen outputs; old reference timing unchanged',
        'new 80 random unobserved test dialogues; old 32 mixed random/enriched development dialogues',
        'new and old API runs on different dates; same requested model and settings, backend version not guaranteed']
    save(a4.OUT/'summary.json',sm)
    if not prefix_only:
        a7.DATA=dd;a7.OUT=dest/'isc7';a7.calculate()
        sm=read(a7.OUT/'summary.json');sm['interpretation']='Fixed-config replication on new random 80 and/or combined 112; same-assistant provisional references, not token-matched or independent human confirmation'
        save(a7.OUT/'summary.json',sm)
    oldhashes=read(DATA/'manifest.json')['original_artifact_hashes']
    unchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in oldhashes.items())
    assert unchanged
    save(dest/'preservation_audit.json',{'original_files_checked':len(oldhashes),'all_unchanged':unchanged})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['queues','new','merged','new4','merged4']);a=p.parse_args()
    if a.action=='queues':queues()
    else:analyze(a.action.startswith('merged'),a.action.endswith('4'))
