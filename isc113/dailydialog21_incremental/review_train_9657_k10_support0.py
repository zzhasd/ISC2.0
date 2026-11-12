import evaluator_io as e
e.publish_support_batch('train_9657__k10',0,[
[0,'E1',[11],'explicit','Explicit five-day work requirement'],
[1,'E2',[15,17],'coreference','Five percent refers to commissions'],
[2,'E1',[1],'explicit','Direct address'],
[3,'E1',[13],'explicit','Explicit course requirement for job'],
[4,'E1',[11,13],'explicit','Explicit duties for conditionally offered job'],
[5,'E2',[15,17],'coreference','Salary statement and commission-rate reference'],
[6,'E3',[3,5],'weak','Question does not confirm prior employment'],
[7,'E1',[15],'explicit','Explicit starting salary and commission'],
[8,'E2',[1],'presupposition','Mrs. is a female form of address'],
[9,'E1',[1],'explicit','Direct name and title address'],
[10,[['B is present in a physical meeting with A.','E2',[1,3,5],'cross_turn','Sit invitation and employment discussion'],['B is in a meeting room.','E3',[1],'weak','Physical room is not specified'],['B is invited by A to sit down.','E1',[1],'speech_act','Explicit invitation']]],
[11,'E2',[5,13],'speech_act','Consulting job offered conditionally'],
])
e.show_support('train_9657__k10',1)
