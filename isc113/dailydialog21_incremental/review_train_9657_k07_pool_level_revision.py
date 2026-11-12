from review_train_9657_common import *
e.publish_pool('train_9657__k07',[
 fact('B is female.','E2',[('gender','female',True)],[(0,[1]),(5,[1])]),
 fact("B is a candidate being interviewed for a consulting position at A's company.",'E2',[('role_context','consulting position',True),('interview','being interviewed',False),('employer',"A's company",False)],[(1,[1]),(9,[1,2]),(17,[1]),(18,[1,3])]),
 fact('The consulting role offered to B requires visiting customers throughout the territory five days a week.','E1',[('duty','visit customers',True),('scope','throughout territory',False),('frequency','five days a week',False),('role','consulting position',False)],[(2,[1,2,3,4]),(10,[1,2,3]),(16,[1,2,3,4])]),
 fact('B must attend a three-week course.','E1',[('required_action','attend course',True),('duration','three weeks',False)],[(3,[1,2]),(13,[1,2])]),
 fact('B is addressed as Mrs. Vale.','E1',[('surname','Vale',True),('title','Mrs.',False)],[(4,[2]),(7,[1]),(8,[1,2]),(20,[1,2]),(21,[1,2])]),
 fact('B is married or uses the title Mrs.','E1',[('status_or_title','married or uses Mrs.',True)],[(6,[1])]),
 fact('B is conditionally offered the consulting job subject to doing well in a three-week course.','E2',[('offer','conditional job offer',True),('role','consulting',False),('course_duration','three weeks',False),('performance_condition','does well in the course',False)],[(11,[1,3]),(14,[1,2,4])]),
 fact('The meeting with B takes place in the afternoon.','E2',[('time','afternoon',True)],[(12,[1])]),
 fact('B was standing or had not yet been seated at the start of the meeting.','E2',[('state','not yet seated',True),('time','start of meeting',False)],[(15,[1,2])]),
 fact('B would be provided a company car as a consultant.','E2',[('benefit','company car',True),('role_condition','as a consultant',False)],[(19,[1,2])]),
])