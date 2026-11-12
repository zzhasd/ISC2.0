"""User-corrected task: current assistant sees complete A+B; Qwen sees only A.

The earlier A-evidence reference is retained, not relabeled as a full-world annotation.
This full reference is source-aware and was finished after partial Qwen inspection.
"""
from isc4_open import DATA, OUT, read, save, freeze, sha

# Additional B-profile facts, with full-source evidence. B-only is not A-recoverable.
ADDITIONS = [
('709','kitchen_opinion','B considers the current kitchen convenient and good.','preference',[2]),
('709','fashion','B questions following kitchen-decoration fashion.','opinion',[4]),
('674','shape','B describes being somewhat out of shape.','health',[2]),
('674','exercise','B is considering exercise to keep fit.','personal_plan',[2]),
('674','membership','B tentatively chooses a one-month fitness membership as a trial.','personal_plan',[11,12]),
('674','intensity','B wants the initial exercise not to be too tough.','preference',[12]),
('806','alcohol','B is drinking and wants to finish the drink before leaving.','habit',[14]),
('806','meet','B plans to meet A later at Sammy\'s.','personal_plan',[14]),
('806','drink_plan','B accepts A\'s invitation to go for a drink.','personal_plan',[1,2]),
('723','cuisines','B\'s favorite cuisines are Mexican, Thai and Indian.','preference',[2]),
('723','moroccan','B has not tried Moroccan food.','experience',[3,4]),
('723','lunch','B proposes trying the Moroccan restaurant for lunch.','personal_plan',[6,7,8]),
('907','trade','B is most worried about the trade deficit in the economic discussion.','opinion',[2]),
('907','exports','B believes government should do more to encourage exports.','opinion',[2]),
('907','inflation','B worries that falling unemployment and increasing pay could increase inflation.','opinion',[4]),
('826','art','B\'s favorite movies are art films.','preference',[6]),
('826','thrillers','B also likes thrillers.','preference',[6,8]),
('826','cinema','B goes to the cinema once in a while.','habit',[10]),
('826','renting','B usually rents movies at Movie Salon.','habit',[10]),
('826','neighborhood','Movie Salon is in B\'s neighborhood.','location',[12]),
('327','hotel','B has booked a room at the Hilton.','travel_plan',[3,4]),
('987','courses','B took Philosophy, Logic, Ethics and Aesthetics in college.','education',[2]),
('987','favorite','B liked Aesthetics best among college courses.','preference',[4]),
('629','married','B married Jenny shortly after graduation.','relationship',[6]),
('629','past_finance','B and Jenny previously struggled financially while B supported both of them.','finance',[6]),
('629','finance_now','B says their financial situation is now improving.','finance',[6]),
('629','moved','B and Jenny recently moved to a new home.','location',[8]),
('629','party','B is hosting a house-warming party this Saturday.','personal_plan',[8]),
('102','allergy','B is allergic to the lobsters and crabs being discussed.','health',[1,2]),
('102','shopping','B plans to buy milk, eggs, orange juice, cooking wine and oil.','personal_plan',[4,6]),
('526','hot_cold','B feels hot and cold.','health',[2]),
('526','onset','B was sick for most of the preceding night.','health',[4]),
('349','job','B\'s job involves helping customers choose products such as vitamins.','work',[2,6,8]),
('514','dine_out','B would rather eat out than order Chinese takeout.','preference',[4]),
('514','home_food','B finds the local Chinese food different from the Chinese food at home.','experience',[4]),
('514','buffet','B suggests trying the all-you-can-eat restaurant later identified as Al\'s Steakhouse.','personal_plan',[4,5]),
('514','waste','B hates letting food go to waste.','preference',[8]),
('100','bag','B wanted a Chanel bag.','preference',[2]),
('100','watch','B won a Chanel watch at auction by bidding at the last minute, at sixty percent off.','purchase',[4]),
('375','appointment','B proposes an appointment tomorrow at 11 o\'clock.','personal_plan',[4]),
('796','shanghai','B plans to go to Shanghai for practical work or practice.','personal_plan',[2]),
('792','olympics','B likes watching the Winter Olympic Games.','preference',[1,2]),
('792','sport','B\'s favorite winter sport is figure skating.','preference',[7,8]),
('697','college','B learned English in college.','education',[4]),
('697','duration','B has been in the United States for three weeks.','location',[7,8]),
('697','wife_arrival','B\'s wife is with B and arrived yesterday.','family',[9,10]),
('697','california','B has never been to California.','travel_history',[11,12]),
('697','vegas','B went to Las Vegas once on a business trip.','travel_history',[13,14]),
('926','ex_name','B\'s former partner is named Jane.','relationship',[6]),
('926','length','B and Jane had been together for almost five years.','relationship',[12]),
('926','commitment','B is ready for a commitment and wants to settle down.','personal_plan',[8]),
('926','forget','B finds it difficult to forget the former partner.','health',[12]),
('369','postponed','B and A originally planned to marry on June 20 but postponed the wedding to July 20.','relationship',[22,24,25]),
('91','device','B has a Driver Mate device in B\'s car.','possession',[2]),
('468','role','B speaks as a representative of the unemployment-claims service.','work',[2,4,6]),
('277','style','B strongly dislikes the clothing style or item A is admiring.','preference',[3,4]),
]

def main():
    source={r['id']:r for r in read(DATA/'dialogues.json')}
    previous=read(DATA/'assistant_reference_v1.json')
    result=[]
    for r in previous:
        d=source[r['dialogue_id']];facts=[]
        for f in r['facts']:
            ev=sorted({e['turn'] for e in f['evidence']}|{e['turn'] for e in f['full_B_check']['evidence']})
            facts.append({'id':f['id'],'claim':f['claim'],'category':f['category'],
                'status':'source_supported','full_evidence':[{'turn':n,'speaker':'A' if n%2 else 'B','quote':d['turns'][n-1]} for n in ev],
                'A_support_sets':f['evidence_sets'],'A_support_status':'provisional_contextual_support',
                'first_A_prefix':f['first_A_prefix']})
        for num,local,claim,cat,ev in ADDITIONS:
            if r['dialogue_id']!='test_'+num:continue
            facts.append({'id':r['dialogue_id']+'_'+local,'claim':claim,'category':cat,
                'status':'source_supported','full_evidence':[{'turn':n,'speaker':'A' if n%2 else 'B','quote':d['turns'][n-1]} for n in ev],
                'A_support_sets':[],'A_support_status':'no_sufficient_A_evidence_identified',
                'first_A_prefix':None})
        result.append({'dialogue_id':r['dialogue_id'],'facts':facts,
            'annotation_status':'current assistant reads FULL A+B; source-aware provisional, not human gold'})
    freeze(DATA/'full_AB_reference_v2.json',result)
    save(DATA/'full_reference_manifest.json',{'dialogues':len(result),
        'full_reference_facts':sum(len(r['facts']) for r in result),
        'A_supported_reference_facts':sum(bool(f['A_support_sets']) for r in result for f in r['facts']),
        'reference_sha256':sha(result),'input_visibility':'GPT: full A+B; Qwen: A only',
        'annotation_timing':'v2 after user clarification; partial Qwen output had already been inspected',
        'model_comparison_limit':'Unequal information conditions; difference is NOT a pure model ability gap',
        'atomization':'one assertion per recorded attribute/event; multi-value lists and redundant paraphrases merged; hierarchical/coarse-specific dependencies remain possible',
        'scope':'32 exploratory dialogues; best-effort high recall, not exhaustive',
        'uncertain_or_disputed':[
          {'dialogue_id':'test_277','claim':'B is broke or spent a week\'s salary','evidence_turns':[10,12,14],'reason':'B later says Just joking; not treated as established financial truth.'},
          {'dialogue_id':'test_526','claim':'B has a headache and/or chest pain','evidence_turns':[7,8],'reason':'Yes I have responds to a compound/disjunctive question; individual symptoms cannot be uniquely resolved.'},
          {'dialogue_id':'test_369','claim':'B forgot the anniversary; June 20 is actual anniversary','evidence_turns':[17,19,22,24,25],'reason':'A admits a date error; superseded claims excluded from final profile.'}
        ]})
    print(read(DATA/'full_reference_manifest.json'))
if __name__=='__main__':main()
