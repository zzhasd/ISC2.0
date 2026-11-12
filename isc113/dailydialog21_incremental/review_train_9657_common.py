import evaluator_io as e

def verify(k):
 p=f'train_9657__k{k:02d}'; q=e.support_packet(p); o=e.read(e.ROOT/'agd_eval/judgments/support'/f'{p}.json')
 assert o['_meta']['input_sha256']==e.agd.stable_hash(q)
 e.agd.validate_support(o,[c for b in q['batches'] for c in b],q['visible_turns'])
 for bi,b in enumerate(q['batches']):
  r=e.read(e.ROOT/'agd_eval/batch_reviews/support'/p/f'{bi:03d}.json')
  its=[x for x in o['items'] if x['id'] in {c['id'] for c in b}]
  assert r['input_sha256']==e.agd.stable_hash({'visible_turns':q['visible_turns'],'candidates':b})
  assert r['reviewed_items_sha256']==e.agd.stable_hash(its)
 print('VERIFIED',p)

def fact(claim,level,slots,members):
 return [claim,level,[(f's{i+1}',n,v,c) for i,(n,v,c) in enumerate(slots)],[(i,[f's{j}' for j in ss]) for i,ss in members]]
