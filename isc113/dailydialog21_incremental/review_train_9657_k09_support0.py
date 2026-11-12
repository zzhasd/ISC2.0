import evaluator_io as e
e.publish_support_batch('train_9657__k09',0,[
[0,'E2',[3,5,9,13],'cross_turn','Employment discussion and conditional job offer'],
[1,'E2',[3,5,13],'cross_turn','Consulting discussion and conditional offer'],
[2,'NOT_B',[],'none','General company policy rather than B property'],
[3,[["B is addressed as Mrs. Vale, with surname Vale.",'E1',[1],'explicit','Direct address'],['B is married.','E2',[1],'presupposition','Mrs. conventionally indicates married status']]],
[4,'E1',[13],'explicit','Explicit job conditional on doing well in course'],
[5,'E2',[15,17],'coreference','Five percent refers to commission just discussed'],
[6,[['B is in a job interview or formal meeting setting.','E2',[1,3,5,9,13],'cross_turn','Formal employment discussion'],['B is invited by A to sit down.','E1',[1],'speech_act','Explicit invitation']]],
[7,'E3',[3,5],'weak','Open employment question does not confirm experience'],
[8,'E1',[15],'explicit','Explicit salary amount and commissions'],
[9,'NOT_B',[],'none','Only being asked an open question'],
[10,'E2',[3,5,9,13],'cross_turn','Formal consulting employment discussion'],
[11,'E1',[1],'explicit','Direct address Mrs. Vale'],
])
e.show_support('train_9657__k09',1)
