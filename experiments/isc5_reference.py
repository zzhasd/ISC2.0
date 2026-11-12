"""Full A+B annotations for 16 newly selected dialogues, before ISC5 output review."""
from isc4_open import ROOT, read, save, freeze, sha
from isc5_run import DATA, OUT

# source ID, local ID, claim, category, full evidence, sufficient A evidence (or []).
ANNOTATIONS=[
('48','medicine','B wants A to get cold medicine for B.','personal_plan',[4],[]),
('48','mail','B agrees to mail A\'s item at the post office.','personal_plan',[3,4],[]),
('778','name','B is called Logan.','identity',[3],[3]),
('778','hat','B is wearing the white hat discussed in the conversation.','appearance',[1,3,4],[1,3]),
('778','contact','B is the person A was expecting to meet through the email contact.','relationship',[1,3,4],[]),
('260','guest','B is a guest at the hotel being called.','service_context',[1,2,3,4],[1,3]),
('260','name','B is named Yao Lan.','identity',[4],[]),
('260','room','B\'s hotel room number is 406.','location',[4],[]),
('260','suitcases','B has two blue suitcases.','possession',[6],[]),
('260','handbag','B has one red shoulder bag or handbag.','possession',[6],[]),
('260','wait','B has waited half an hour for undelivered baggage.','personal_event',[2],[]),
('260','tags','B\'s baggage has a name tag attached.','possession',[7,8],[]),
('173','name','B is called Mel.','identity',[1],[1]),
('173','work','B is employed and needs to go to work.','work',[2],[]),
('173','care','B is responsible for caring for children.','family',[2,3,5],[3,5]),
('173','pickup','B needs to pick up Jake and Maddie from school and make an afternoon snack for them.','personal_plan',[2],[]),
('173','activities','B takes Jake to soccer practice and Maddie to dance class.','family',[2],[]),
('173','tired','B frequently feels tired or sounds exhausted.','health',[3,6],[3]),
('173','busy','B has a busy schedule balancing responsibilities.','lifestyle',[2,5],[5]),
('173','nanny','B is considering hiring a nanny to help with childcare.','personal_plan',[3,4,6],[]),
('173','dan','B plans to discuss the nanny with Dan.','personal_plan',[6],[]),
('173','call','B plans to call the recommended nanny tomorrow.','personal_plan',[6],[]),
('610','car_preference','B likes the violet compact car being discussed.','preference',[2,5,6],[]),
('928','watch','B has a watch that is a few minutes fast.','possession',[2],[]),
('928','concert','B and A plan to get to a concert together.','personal_plan',[3,4],[3]),
('928','taxi','B proposes taking a taxi now to make the concert in time.','personal_plan',[4],[]),
('324','interest','B is seeking information about the Group Account Deposit Service.','finance_interest',[2,4],[]),
('536','travel','B plans to travel by plane.','personal_plan',[2,3],[3]),
('536','route','B wants flight FW58 to San Marino.','travel_plan',[2],[]),
('536','date','B wants to fly next Monday.','travel_plan',[4],[]),
('536','seat','B chooses an economy seat after hearing the first-class fare.','travel_plan',[6,7,8],[]),
('829','wish','B wishes to see the exceptionally narrow street mentioned by A.','personal_desire',[1,4],[]),
('180','passenger','B is a taxi passenger whose original ride has broken down.','travel_context',[1,4],[]),
('180','taxi','B intends to call another taxi.','personal_plan',[4],[]),
('180','late','B is concerned about being late.','personal_state',[4],[]),
]

def main():
    ds=read(DATA/'dialogues.json');index={r['id']:r for r in ds}
    old=read(ROOT/'data/isc4/full_AB_reference_v2.json')
    new={r['id']:{'dialogue_id':r['id'],'facts':[],'annotation_status':'current assistant reads full A+B; provisional, before new API output inspection'}
        for r in ds if r['evaluation_split']=='new_evaluation'}
    for num,local,claim,cat,ev,aev in ANNOTATIONS:
        did='test_'+num;r=index[did]
        assert all(1<=n<=len(r['turns']) for n in ev)
        assert all(n%2==1 for n in aev)
        new[did]['facts'].append({'id':did+'_'+local,'claim':claim,'category':cat,
            'full_evidence':[{'turn':n,'speaker':'A' if n%2 else 'B','quote':r['turns'][n-1]} for n in ev],
            'A_support_sets':[aev] if aev else [],'first_A_prefix':(max(aev)+1)//2 if aev else None,
            'A_support_status':'provisional_contextual_support' if aev else 'no_sufficient_A_evidence_identified'})
    refs=old+list(new.values());freeze(DATA/'full_AB_reference.json',refs)
    save(DATA/'reference_manifest.json',{'reference_sha256':sha(refs),'development_dialogues':32,
        'new_dialogues':16,'new_full_facts':len(ANNOTATIONS),'new_A_supported':sum(bool(a[-1]) for a in ANNOTATIONS),
        'timing':'new annotations frozen before any ISC5 response was inspected',
        'not_gold':True,'notes':['presupposition labels defeasible; not a hard ceiling',
            'new test_173 retains source mid-sentence truncations exactly; no missing text invented',
            'sales/service role and biological gender are not assumed from product requests or honorifics',
            'test_48 cold medicine request does not establish a cold diagnosis',
            'test_536 not a wall streeter is figurative; not a verified occupation or financial diagnosis']})
    print(read(DATA/'reference_manifest.json'))
if __name__=='__main__':main()
