from review_train_9657_common import *
e.publish_pool('train_9657__k04',[
 fact('B is in a formal physical meeting or office/interview setting in the afternoon.','E2',[('event','physical meeting',True),('formality','formal',False),('time','afternoon',False),('setting','office or interview context',False)],[(0,[1,3]),(4,[2]),(6,[1,4]),(13,[2,4])]),
 fact('B is being considered for or is in a consulting role.','E2',[('role_context','consulting',True)],[(1,[1])]),
 fact('B is addressed as Mrs. Vale.','E1',[('surname','Vale',True),('title','Mrs.',False)],[(2,[1,2]),(3,[1,2]),(7,[1]),(9,[1]),(10,[2]),(12,[2])]),
 fact('B is asked by A to sit down.','E1',[('requested_action','sit down',True)],[(5,[1]),(14,[1])]),
 fact('B is female.','E2',[('gender','female',True)],[(8,[1]),(11,[1])]),
])
e.show_support('train_9657__k05',0)
p='train_9657__k05';q=e.support_packet(p);o=e.read(e.ROOT/'agd_eval/judgments/support'/f'{p}.json'); ids={c['id'] for c in q['batches'][0]};print({'items':[i for i in o['items'] if i['id'] in ids]})
