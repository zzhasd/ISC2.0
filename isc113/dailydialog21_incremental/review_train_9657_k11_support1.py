import evaluator_io as e
e.publish_support_batch('train_9657__k11',1,[
[12,'E2',[1,3,5],'cross_turn','Afternoon greeting and physical employment meeting'],
[13,'E1',[11],'explicit','Explicit five-day territorial customer visits'],
[14,'E2',[3,5,9,13],'cross_turn','Consulting employment discussion and conditional offer'],
[15,'E3',[3,5],'weak','Question does not establish prior employment'],
[16,'E1',[1],'explicit','Direct address Mrs. Vale'],
[17,'E2',[15,17],'coreference','Five percent refers to commissions'],
[18,'E2',[15,17],'coreference','Salary statement and commission-rate reference'],
[19,[["B is asked whether she has a diver's license.",'NOT_B',[],'none','Only an open question'],["B's consulting role may involve diving or require a relevant diver's license.",'E3',[7],'weak','Question does not establish role duties']]],
[20,'E3',[3,5],'weak','Contrast does not confirm past sales work'],
[21,'E2',[3,5,9,13],'cross_turn','Consulting candidate at A company'],
[22,[["A's company provides a company car for its consultants.",'NOT_B',[],'none','General company policy'],['A company car would be available to B if hired as a consultant.','E2',[9,13],'cross_turn','Benefit applies conditionally upon consulting employment']]],
[23,'E2',[13],'presupposition','Course performance precedes securing job'],
])
e.show_support('train_9657__k11',2)
