from review_train_9657_common import *
e.publish_pool('train_9657__k10',[
 fact('The consulting position discussed with B requires visiting customers throughout the territory five days a week.','E1',[('duty','visit customers',True),('scope','throughout territory',False),('frequency','five days a week',False),('role','consulting position',False)],[(0,[3]),(4,[1,2,3]),(14,[1,2,3,4]),(18,[1,2])]),
 fact("B's prospective consulting job offers a starting salary of $150 per week plus five-percent commission.",'E2',[('compensation','starting salary',True),('amount','$150',False),('period','weekly',False),('additional_pay','commission',False),('commission_rate','five percent',False),('role','prospective consulting job',False)],[(1,[4,5]),(5,[1,2,3,4,5]),(6,[1,2,3,4]),(13,[1,2,3,4,5,6])]),
 fact('B is addressed as Mrs. Vale.','E1',[('surname','Vale',True),('title','Mrs.',False)],[(2,[1,2]),(8,[1,2]),(15,[1,2])]),
 fact('B must attend a three-week course starting a week from tomorrow before starting the job.','E2',[('required_action','attend course',True),('duration','three weeks',False),('start','a week from tomorrow',False),('time','before starting job',False)],[(3,[1,2]),(12,[3]),(16,[1,2,3]),(22,[1,2,4])]),
 fact('B is female.','E2',[('gender','female',True)],[(7,[1])]),
 fact('B is present in a physical meeting with A.','E2',[('event','physical meeting with A',True)],[(9,[1])]),
 fact('B is invited by A to sit down.','E1',[('requested_action','sit down',True)],[(10,[1])]),
 fact('B is conditionally offered the consulting job if she does well in the course.','E1',[('offer','conditional job offer',True),('role','consulting',False),('performance_condition','does well in course',False)],[(11,[1,2]),(17,[1,2,3]),(19,[1,3])]),
 fact("B is a candidate for a consulting position at A's company.",'E2',[('role_context','consulting position',True),('employer',"A's company",False),('application_or_interview','applying or being interviewed',False)],[(20,[1,2]),(23,[1,3]),(24,[1])]),
 fact('B would be provided a company car as a consultant.','E2',[('benefit','company car',True),('role_condition','as a consultant',False)],[(21,[1,2])]),
])
e.show_support('train_9657__k11',0)
