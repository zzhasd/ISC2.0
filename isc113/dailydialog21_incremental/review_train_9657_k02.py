from review_train_9657_common import *
e.publish_pool('train_9657__k02',[
 fact('B is asked to sit down by A.','E1',[('requested_action','sit down',True)],[(0,[1])]),
 fact('B is not yet seated at turn 1.','E2',[('state','not yet seated',True)],[(1,[1])]),
 fact('B is addressed as Mrs. Vale.','E1',[('surname','Vale',True),('title','Mrs.',False)],[(2,[1,2]),(3,[1,2]),(4,[1,2]),(7,[1])]),
 fact('B is female.','E2',[('gender','female',True)],[(5,[1]),(8,[1])]),
 fact('B is married.','E2',[('marital_status','married',True)],[(6,[1])]),
 fact('The conversation with B takes place in the afternoon.','E2',[('time','afternoon',True)],[(9,[1])]),
])
e.show_support('train_9657__k03',0)
print(e.read(e.ROOT/'agd_eval/judgments/support/train_9657__k03.json'))
