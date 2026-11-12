from review_train_9657_common import *
e.publish_pool('train_9657__k09',[
 fact("B is a candidate being interviewed for a consulting position at A's company.",'E2',[('role_context','consulting position',True),('interview','being interviewed',False),('employer',"A's company",False)],[(0,[1,3]),(1,[1]),(9,[1,2]),(23,[1,2])]),
 fact('B is addressed as Mrs. Vale.','E1',[('surname','Vale',True),('title','Mrs.',False)],[(2,[1,2]),(10,[1,2]),(24,[2]),(26,[1,2])]),
 fact('B is married.','E2',[('marital_status','married',True)],[(3,[1])]),
 fact('B is conditionally offered the consulting job if she performs well in the three-week course.','E1',[('offer','conditional job offer',True),('role','consulting',False),('performance_condition','does well in course',False),('course_duration','three weeks',False)],[(4,[1,2,3,4]),(12,[1,2,3])]),
 fact("B's prospective consulting job offers a starting salary of $150 per week plus five-percent commission.",'E2',[('compensation','starting salary',True),('amount','$150',False),('period','weekly',False),('additional_pay','commission',False),('commission_rate','five percent',False),('role','prospective consulting job',False)],[(5,[1,2,3,4,5,6]),(8,[1,2,3,4]),(15,[4,5]),(16,[5]),(17,[1,2,3,4])]),
 fact('B is in a job interview or formal meeting in the afternoon.','E2',[('event','meeting or interview',True),('setting','job interview or formal meeting',False),('time','afternoon',False)],[(6,[1,2]),(22,[1,3])]),
 fact('B is invited by A to sit down.','E1',[('requested_action','sit down',True)],[(7,[1])]),
 fact('B must attend a three-week training course as part of hiring before starting.','E2',[('required_action','attend course',True),('duration','three weeks',False),('type','training',False),('time','before starting',False),('process','hiring process',False)],[(11,[1,2]),(20,[1,2,3,4]),(21,[1,2,5])]),
 fact('The consulting position discussed with B requires visiting customers throughout the territory five days a week.','E1',[('duty','visit customers',True),('scope','throughout territory',False),('frequency','five days a week',False),('role','consulting position',False)],[(13,[1,2,3,4]),(14,[1,2,4]),(19,[1,2,3]),(25,[3,4])]),
 fact('B is female.','E2',[('gender','female',True)],[(18,[1])]),
])
e.show_support('train_9657__k10',0)
