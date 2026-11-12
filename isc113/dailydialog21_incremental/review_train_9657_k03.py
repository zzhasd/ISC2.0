from review_train_9657_common import *
e.publish_pool('train_9657__k03',[
 fact('B is associated with or being considered for a consulting role.','E2',[('role_context','consulting',True)],[(0,[1]),(8,[1]),(11,[1])]),
 fact('B is addressed as Mrs. Vale.','E1',[('surname','Vale',True),('title','Mrs.',False)],[(1,[1,2]),(3,[1,2])]),
 fact('B is married or uses the title Mrs.','E1',[('status_or_title','married or uses Mrs.',True)],[(2,[1])]),
 fact('B is female.','E2',[('gender','female',True)],[(4,[1])]),
 fact('B is in a formal meeting or interview with A in the afternoon.','E2',[('event','formal meeting or interview with A',True),('time','afternoon',False)],[(5,[1]),(7,[1,2]),(9,[1])]),
 fact('B is invited by A to sit down.','E1',[('requested_action','sit down',True)],[(6,[1]),(10,[1])]),
])
e.show_support('train_9657__k04',0)
