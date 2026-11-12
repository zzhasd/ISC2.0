from review_train_9657_common import *
e.publish_pool('train_9657__k08',[
 fact('The consulting position discussed with B requires visiting customers throughout the territory five days a week.','E1',[('duty','visit customers',True),('scope','throughout territory',False),('frequency','five days a week',False),('role','consulting position',False)],[(0,[1,2,3]),(3,[3,4]),(4,[1,2,4]),(7,[1,2]),(11,[3]),(15,[1,2,4]),(18,[1,2,3,4])]),
 fact('B must attend a three-week course for the position.','E1',[('required_action','attend course',True),('duration','three weeks',False)],[(1,[1,2]),(8,[1,2]),(23,[1,2])]),
 fact("B is a candidate being interviewed for a consulting position at A's company.",'E2',[('role_context','consulting position',True),('interview','being interviewed',False),('employer',"A's company",False)],[(2,[1,2,3]),(5,[1,3]),(10,[1,3]),(16,[1])]),
 fact('B is addressed as Mrs. Vale.','E1',[('surname','Vale',True),('title','Mrs.',False)],[(6,[1,2]),(14,[1,2]),(20,[1,2]),(22,[1,2])]),
 fact('B is conditionally offered the consulting job subject to doing well in a three-week course.','E1',[('offer','conditional job offer',True),('role','consulting',False),('course_duration','three weeks',False),('performance_condition','does well in course',False)],[(9,[1,2,4]),(19,[1,3])]),
 fact("B's prospective consulting job has a starting salary of $150 per week plus commissions.",'E1',[('compensation','starting salary',True),('amount','$150',False),('period','weekly',False),('additional_pay','commissions',False),('role','prospective consulting job',False)],[(12,[1,2,3,4]),(13,[1,2,3,4]),(21,[1,2,3,4,5])]),
 fact('B is female.','E2',[('gender','female',True)],[(17,[1])]),
])
e.show_support('train_9657__k09',0)
