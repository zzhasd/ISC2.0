import evaluator_io as e
e.publish_support_batch('train_9657__k11',0,[
[0,'E3',[13,15],'weak','Salary terms stated but hiring and receipt remain conditional'],
[1,'E2',[1],'presupposition','Mrs. is a female form of address'],
[2,'E1',[11],'explicit','Explicit five-day territorial customer visit duty'],
[3,'E2',[13],'presupposition','Required course in hiring context is training'],
[4,'E1',[13],'explicit','Explicit three-week course requirement'],
[5,'E2',[13,19],'coreference','Next course refers to required hiring course'],
[6,[['B is in a job interview setting.','E2',[1,3,5,9,13],'cross_turn','Formal consulting employment discussion'],['B is being offered a consulting position.','E2',[5,13],'speech_act','Consulting job offered conditionally']]],
[7,'E2',[15,17],'coreference','Five percent refers to commissions'],
[8,[['B must attend a three-week course starting a week from tomorrow.','E2',[13,19],'coreference','Next course is required three-week course'],['B will get the consulting job if B does well in the course.','E1',[5,13],'explicit','Explicit performance condition']]],
[9,'E2',[1],'presupposition','Sit invitation strongly implies standing before seating'],
[10,'E1',[1],'explicit','Direct name and title address'],
[11,'E1',[11],'explicit','Explicit future work requirement'],
])
e.show_support('train_9657__k11',1)
