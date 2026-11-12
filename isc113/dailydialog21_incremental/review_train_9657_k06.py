from review_train_9657_common import *
e.publish_pool('train_9657__k06',[
 fact('B is in a physical job interview or formal meeting with A in the afternoon.','E2',[('event','physical meeting with A',True),('setting','job interview or formal meeting',False),('time','afternoon',False)],[(0,[1]),(4,[3]),(12,[1,2])]),
 fact('B is instructed by A to sit down.','E1',[('requested_action','sit down',True)],[(1,[1])]),
 fact('B is addressed as Mrs. Vale.','E1',[('surname','Vale',True),('title','Mrs.',False)],[(2,[1,2]),(10,[1,2]),(11,[1,2])]),
 fact('B is female.','E2',[('gender','female',True)],[(3,[1]),(13,[1])]),
 fact("B is a candidate for a consulting position at A's company.",'E2',[('role_context','consulting position',True),('status','candidate',False),('employer',"A's company",False)],[(5,[1,2,3]),(7,[1,2,3])]),
 fact('The consulting position discussed with B requires visiting customers throughout the territory five days a week.','E1',[('duty','visit customers',True),('scope','throughout territory',False),('frequency','five days a week',False),('role','consulting position',False)],[(6,[3]),(8,[1,2,3]),(9,[1,2]),(14,[1,2,3,4]),(15,[1,2,3,4])]),
])
e.show_support('train_9657__k07',0)
p='train_9657__k07';q=e.support_packet(p);o=e.read(e.ROOT/'agd_eval/judgments/support'/f'{p}.json'); ids={c['id'] for c in q['batches'][0]};print({'items':[i for i in o['items'] if i['id'] in ids]})
