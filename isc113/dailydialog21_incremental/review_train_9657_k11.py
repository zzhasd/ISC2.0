from review_train_9657_common import *
e.publish_pool('train_9657__k11',[
 fact('B is female.','E2',[('gender','female',True)],[(0,[1])]),
 fact('The consulting position discussed with B requires visiting customers throughout the territory five days a week.','E1',[('duty','visit customers',True),('scope','throughout territory',False),('frequency','five days a week',False),('role','consulting position',False)],[(1,[1,2,3]),(12,[1,2,3]),(14,[1,2,3,4]),(24,[1,2,3])]),
 fact('B must attend a three-week training course starting a week from tomorrow as a prerequisite to the job.','E2',[('required_action','attend course',True),('duration','three weeks',False),('type','training',False),('start','a week from tomorrow',False),('prerequisite','before obtaining job',False)],[(2,[1,2,3]),(3,[1,2]),(4,[3,4]),(8,[1,2,4]),(21,[1,2,5]),(23,[4])]),
 fact('B is in a job interview with A in the afternoon.','E2',[('event','meeting with A',True),('setting','job interview',False),('time','afternoon',False)],[(5,[1,2]),(13,[1,3])]),
 fact('B is conditionally offered a consulting job if she does well in the three-week course; the job is not yet confirmed.','E2',[('offer','conditional job offer',True),('role','consulting',False),('performance_condition','does well in course',False),('course_duration','three weeks',False),('status','not yet confirmed',False)],[(6,[1,2]),(9,[1,2,3]),(27,[1,2,3,4]),(28,[5])]),
 fact("B's prospective consulting job offers a starting salary of $150 per week plus five-percent commission.",'E2',[('compensation','starting salary',True),('amount','$150',False),('period','weekly',False),('additional_pay','commission',False),('commission_rate','five percent',False),('role','prospective consulting job',False)],[(7,[1,2,3,4,5]),(17,[1,2,3,4,5]),(18,[1,2,3,4,5,6])]),
 fact('B is standing or entering the room at the start of the meeting.','E2',[('state','standing or entering room',True),('time','start of meeting',False)],[(10,[1,2])]),
 fact('B is addressed as Mrs. Vale.','E1',[('surname','Vale',True),('title','Mrs.',False)],[(11,[1,2]),(16,[1,2]),(25,[1,2]),(26,[1,2])]),
 fact("B is a candidate applying or being interviewed for a consulting position at A's company.",'E2',[('role_context','consulting position',True),('employer',"A's company",False),('application','applying',False)],[(15,[1,2]),(19,[1,2]),(22,[1,3])]),
 fact('A company car would be available to B if hired as a consultant.','E2',[('benefit','company car',True),('condition','if hired as consultant',False)],[(20,[1,2])]),
])
