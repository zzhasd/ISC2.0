import evaluator_io as e
e.publish_support_batch('train_9657__k09',1,[
[12,[['B must attend a three-week course.','E1',[13],'explicit','Explicit course requirement'],['B will get the consulting job if B does well in the course.','E1',[5,13],'explicit','Explicit performance condition for job']]],
[13,'E1',[11],'explicit','Explicit customer visits and five-day requirement'],
[14,'E1',[11],'explicit','Explicit customer visits throughout territory'],
[15,'E2',[15,17],'coreference','Five percent answers commission amount'],
[16,'E2',[15,17],'coreference','Five percent refers to commissions'],
[17,'NOT_B',[],'none','Only being asked an open question'],
[18,'E1',[15],'explicit','Explicit starting salary plus commissions'],
[19,'E2',[1],'presupposition','Mrs. is a female form of address'],
[20,'E1',[11],'explicit','Explicit duties for prospective job'],
[21,'E2',[13],'presupposition','Course performance precedes obtaining the job'],
[22,'E2',[13],'presupposition','Required course conditions job eligibility'],
[23,'E2',[1,3,5],'cross_turn','Afternoon greeting and formal employment discussion'],
])
e.show_support('train_9657__k09',2)
