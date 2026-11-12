"""Current assistant's source-aware provisional reference; not a fresh blind API run.

Written before inspecting this run's Qwen outputs. Evidence sets refer ONLY to A.
Ambiguous possibilities are preserved separately, not counted as supported facts.
"""
from isc4_open import DATA, OUT, ROOT, read, save, freeze, sha, visible

# dialogue, local ID, atomic claim, category, sufficient original A positions,
# original B positions for post-hoc checking (NEVER an extraction input).
ANNOTATIONS = [
('39','name','B is addressed as Professor Clark.','identity',[1,3],[2]),
('39','profession','B is a professor.','work',[1,3],[2]),
('39','teaching','B teaches a morning literature class attended by A.','education',[3],[]),
('709','kitchen','B shares the kitchen discussed by A.','household',[1],[]),
('806','name','B is called Kenny.','identity',[1],[]),
('826','name','B is called Mary.','identity',[1],[]),
('826','movies','B watches a lot of movies.','interest',[1,3],[2]),
('826','rental','B has a membership at Movie Salon.','membership',[11,15],[12]),
('987','college','B attended college courses.','education',[1],[2]),
('629','name','B is called Bob.','identity',[1],[]),
('629','graduation','B and A graduated ten years before this conversation.','education',[3],[]),
('629','partner','B has an ongoing relationship with Jenny.','relationship',[5,7],[6]),
('629','contact','B and A have been out of close contact.','relationship',[7],[]),
('102','seafood','B avoids or dislikes seafood.','preference',[1,3],[2]),
('526','pale','B looks pale.','health',[1],[]),
('526','ill','B is experiencing a current illness.','health',[1,3],[4]),
('526','temperature','B has a measured body temperature of 38.7 degrees (fever).','health',[5,7],[6]),
('526','throat','B has a somewhat sore-looking throat on examination.','health',[9,11],[]),
('526','xray','A proposes a chest X-ray and tests for B.','care_plan',[11],[12]),
('526','tests','B has undergone tests reported as showing nothing wrong.','health',[13],[]),
('526','infection','B is reported to have a slight viral infection.','health',[13],[]),
('526','antibiotics','B is prescribed antibiotic capsules every four hours.','care_plan',[15],[]),
('526','aspirin','B is prescribed aspirin when fever occurs.','care_plan',[15],[]),
('526','rest','B is instructed to rest at home in bed for two days.','care_plan',[15],[]),
('526','water','B is instructed to drink plenty of water.','care_plan',[15],[]),
('439','wife','B has a wife.','family',[1],[]),
('375','name','B is called Bob.','identity',[1],[]),
('796','english_work','English is expected to be useful in B\'s professional work.','work',[5],[6]),
('792','skaters','B is a fan of the skaters Shen Due and Hao Hongbo named by A.','interest',[9,11],[10]),
('697','name','B is called Brian.','identity',[1],[]),
('697','english','B speaks English well.','skill',[3,5],[2,4]),
('697','usa','B has been in the United States.','location',[7],[8]),
('697','wife','B has a wife.','family',[9],[10]),
('926','name','B is called Jack.','identity',[1],[]),
('926','down','B appears emotionally down.','health',[3],[2]),
('926','success','A describes B as successful in his career.','work',[5],[]),
('926','breakup','B has recently had a romantic breakup.','relationship',[5,7],[6]),
('369','trip','B is included in A\'s plan to fly to Paris the day after tomorrow.','travel_plan',[5,7],[26]),
('369','marriage','B and A have been married for ten years.','relationship',[17],[22]),
('369','anniversary','Their wedding anniversary is July 20, correcting A\'s June 20 claim.','relationship',[17,23,25],[22,24]),
('525','name','B is called Jim.','identity',[1],[]),
('525','birthday','The conversation takes place on B\'s birthday.','personal_event',[1],[]),
('91','broadcast','B obtains road news through broadcasts.','habit',[1,3],[4]),
('277','name','B is called Amy.','identity',[1],[]),
]

# High-recall candidates that A does NOT firmly establish. They are NEVER gold positives.
HYPOTHESES = [
('674','B is a prospective fitness-club customer.','A describes personalized services, but this does not establish membership or an occupation.'),
('674','B selected a one-month membership.','A says Wise decision without repeating the selected duration; one month is B-only.'),
('826','B likes art films and thrillers.','A says these two genres without naming them; genre names occur only in B.'),
('327','B is staying at the Hilton in Dalian.','A asks a question; the Hilton booking is only in hidden B.'),
('629','B is married to Jenny.','An ongoing relationship is supported; marriage specifically is not established by A alone.'),
('18','B works as a florist.','A is buying roses, but B could be an intermediary; occupational identity remains plausible.'),
('102','B is allergic to seafood.','A acknowledges a seafood restriction but never specifies an allergy.'),
('112','B works in a pearl or jewelry shop.','A asks about pearls and buys an item; this does not uniquely identify B\'s occupation.'),
('526','B has influenza.','A says sounds like, then reports a slight viral infection; do not upgrade a tentative diagnosis.'),
('526','B has a headache or chest pain.','A only asks; later A confirms a sore-looking throat but not these other symptoms.'),
('349','B works as a pharmacist or shop assistant.','A seeks vitamin advice; advice does not uniquely establish an occupation.'),
('514','B is Chinese or comes from China.','No A-side evidence; even B\'s at home remark would not uniquely identify nationality.'),
('796','B plans to seek work in Shanghai.','A endorses an unstated idea and discusses jobs there, but the specific commitment is not repeated.'),
('792','B likes watching the Winter Olympics.','A asks; A\'s own enthusiasm is not B\'s preference.'),
('663','B is a local guide or a local resident.','Questions about the city do not establish B\'s residence or profession.'),
('697','B learned English in college or has been in the US for three weeks.','The specific college and duration occur only in B.'),
('926','B\'s former partner is Jane and their relationship lasted almost five years.','Name and duration occur only in B.'),
('369','B forgot the wedding anniversary.','A accuses B, then admits A got the date wrong. Do not retain the accusation as an established trait.'),
('468','B is an unemployment-benefits caseworker.','A asks about benefits; institutional job title is inferred, not explicitly established.'),
('277','B is currently broke or has spent a week\'s salary.','Those claims occur only in B; A\'s Are you on the level does not repeat their content.'),
]

def main():
    dialogues=read(DATA/'dialogues.json');byid={r['id']:r for r in dialogues}
    result={r['id']:{'dialogue_id':r['id'],'facts':[],'hypotheses':[],
        'annotation_status':'current-assistant source-aware provisional; no independent human review'} for r in dialogues}
    for num,local,claim,cat,ev,be in ANNOTATIONS:
        did='test_'+num;r=byid[did]
        assert all(n%2==1 and 1<=n<=len(r['turns']) for n in ev)
        assert all(n%2==0 and 1<=n<=len(r['turns']) for n in be)
        result[did]['facts'].append({'id':did+'_'+local,'claim':claim,'category':cat,
            'support':'entailed','evidence_sets':[ev],
            'evidence':[{'turn':n,'quote':r['turns'][n-1]} for n in ev],
            'first_A_prefix':(max(ev)+1)//2,'last_A_prefix':None,
            'full_B_check':{'status':'consistent_with_cited_B' if be else 'no_independent_B_confirmation',
                'evidence':[{'turn':n,'quote':r['turns'][n-1]} for n in be]}})
    for num,claim,reason in HYPOTHESES:
        result['test_'+num]['hypotheses'].append({'claim':claim,'reason':reason})
    values=list(result.values());freeze(DATA/'assistant_reference_v1.json',values)
    save(DATA/'reference_manifest.json',{'facts':len(ANNOTATIONS),'hypotheses':len(HYPOTHESES),
        'dialogues':len(values),'reference_sha256':sha(values),
        'annotator':'current Codex conversation assistant; user requested gpt-6.1-sol',
        'identity_verification':'no independent API response/model ID for this manual assistant annotation',
        'blinding':'source-aware; saw complete A/B and historical reports; did not inspect new Qwen outputs before writing v1',
        'not_gold':True,'prefix_status':'evidence-availability reference only; NOT independent GPT prefix inference'})
    print({'reference_dialogues':len(values),'supported_reference_facts':len(ANNOTATIONS),'uncertain_candidates':len(HYPOTHESES)})
if __name__=='__main__':main()
