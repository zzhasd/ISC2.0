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

verify(1)
e.publish_pool('train_9657__k01',[
 fact('B is addressed as Mrs. Vale.','E1',[('surname','Vale',True),('title','Mrs.',False)],[(0,[1]),(3,[1,2]),(6,[1]),(9,[2])]),
 fact('B is female.','E2',[('gender','female',True)],[(1,[1]),(4,[1]),(10,[1])]),
 fact('B is asked to sit down by A.','E1',[('requested_action','sit down',True)],[(2,[1])]),
 fact('B is present in the afternoon.','E2',[('time','afternoon',True)],[(5,[1])]),
 fact('B is not yet seated at turn 1.','E2',[('state','not yet seated',True)],[(7,[1])]),
 fact('B is married or identified as married.','E2',[('marital_status','married',True)],[(8,[1]),(11,[1])]),
])
verify(2)
e.show_pool('train_9657__k02')
