from review_train_9657_common import *
e.publish_pool('train_9657__k05',[
 fact('B is addressed as Mrs. Vale.','E1',[('surname','Vale',True),('title','Mrs.',False)],[(0,[1,2]),(1,[1,2]),(8,[1,2]),(12,[1])]),
 fact('B is being offered or entitled to a company car as part of a consulting position.','E2',[('benefit','company car',True),('role_condition','consulting position',False)],[(2,[1,2]),(5,[1,2])]),
 fact("B is a candidate for a consulting position at A's company.",'E2',[('role_context','consulting',True),('status','candidate',False),('employer',"A's company",False)],[(3,[1]),(6,[1]),(7,[1,2,3])]),
 fact('B is in a formal meeting or interview with A in the afternoon.','E2',[('event','meeting or interview with A',True),('formality','formal',False),('time','afternoon',False)],[(4,[1,2]),(9,[1,3])]),
 fact('B is female.','E2',[('gender','female',True)],[(10,[1]),(11,[1])]),
])
e.show_support('train_9657__k06',0)
p='train_9657__k06';q=e.support_packet(p);o=e.read(e.ROOT/'agd_eval/judgments/support'/f'{p}.json'); ids={c['id'] for c in q['batches'][0]};print({'items':[i for i in o['items'] if i['id'] in ids]})
