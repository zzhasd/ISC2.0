from review_train_9657_common import *
e.revise_support_batch_retaining('train_9657__k04',0,{
8:[['B is in a formal setting.','E2',[1,3,5],'cross_turn','Formal address and employment discussion'],['B is asked by A to sit down.','E1',[1],'speech_act','Explicit invitation']],
9:[['B is currently in or transitioning to a consulting role.','E3',[3,5],'weak','Consulting discussion does not establish employment state'],['B has a salesperson background.','E3',[3,5],'weak','Open question does not establish prior sales work']]
},[0,1,2,3,4,5,6,7,10,11])
e.show_support('train_9657__k04',1)
p='train_9657__k04'; q=e.support_packet(p);o=e.read(e.ROOT/'agd_eval/judgments/support'/f'{p}.json'); ids={c['id'] for c in q['batches'][1]}; print({'items':[i for i in o['items'] if i['id'] in ids]})
