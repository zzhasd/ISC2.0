import evaluator_io as e
e.publish_support_batch('train_9657__k10',1,[
[12,'E2',[13,19],'coreference','Next course refers to required course for B'],
[13,'E2',[15,17],'coreference','Salary and five-percent commission reference'],
[14,'E3',[3,5],'weak','Question and contrast do not confirm prior experience'],
[15,'E1',[11],'explicit','Explicit five-day territorial customer visits'],
[16,'E1',[1],'explicit','Direct address Mrs. Vale'],
[17,[['B must attend a three-week course starting a week from tomorrow.','E2',[13,19],'coreference','Next course refers to required three-week course'],['B will get the consulting job if B does well in the course.','E1',[5,13],'explicit','Explicit job performance condition']]],
[18,'NOT_B',[],'none','Only being asked an open question'],
[19,[['B answered a question about her salesperson background.','NOT_B',[],'none','Unknown response is conversational metadata'],['B had relevant prior work experience.','E3',[3,5],'weak','I see does not establish prior experience']]],
[20,'E1',[11],'explicit','Explicit territorial customer visit duty'],
[21,'E1',[13],'explicit','Explicit good-performance job condition'],
[22,'E2',[3,5,9,13],'cross_turn','Consulting employment discussion at A company'],
[23,'E2',[9,13],'cross_turn','Company-car benefit if consultant'],
])
e.show_support('train_9657__k10',2)
