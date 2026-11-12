"""Current conversational assistant's direct full-A+B annotations, before Qwen inspection.

Rows: local ID | atomic B proposition | full evidence turn numbers | alternative A
support sets (semicolon separates alternatives). Empty last column means no sufficient
A evidence identified. This file is a transcription of semantic reading, not an API judge.
"""
from datetime import datetime,timezone
from isc4_open import read,save,freeze,sha,ROOT
DATA=ROOT/'data/extension80'
ANNOTATIONS={
'371':'''vegetable|B likes the green vegetable at the cafeteria counter.|8|
name_unknown|B does not know the name of that green vegetable.|8,9|9
queue|B is obtaining lunch in the cafeteria queue.|3,4,5,6,7|3,5,7''',
'74':'''name|B is addressed as Tom.|1|1
sister|Jenny is B's sister.|1,5,6|1,5
bother|B says Jenny kept bothering B.|4|
brother|B identifies as Jenny's brother.|6|''',
'229':'''name|B is addressed as Billy.|1|1
late|B is late again for work, after two previous late arrivals that angered the manager.|1,2,5|1,5
overslept|B overslept today.|2|
risk|B faces a possible risk of dismissal for further lateness.|5,6,7|5,7
apology|B plans to go immediately to the manager's office and apologize.|7,8|
traffic|B finds avoiding lateness difficult because of Beijing traffic.|8|''',
'20':'''stop|B has pulled A over in a traffic stop.|1,2|1
ticket|B intends to issue A a ticket for driving through a red light.|2,10,12|''',
'882':'''dream|B dreams of visiting the Great Wall.|2|
textbooks|B has seen the Great Wall many times in textbooks.|2|''',
'359':'''restaurant|B represents the restaurant to which A is applying for an usher position.|1,2,4|1''',
'455':'''shape|B is currently in good physical shape and looks good.|1,2|1
club|B has been attending the club regularly for training.|2|
knowledge|B says B knows more about keeping fit as a result of training.|2|
trainer|B has a trainer who advises B about fitness.|6,11,12,13|11,13
diet|B's trainer has advised regular exercise and a healthy balanced diet.|6|
mood|B's trainer has advised B to stay in a good mood.|12|''',
'104':'''name|B is addressed as Parker.|1|1
meeting|B wants to meet A next week.|3,4|3
wednesday|B can visit A first thing Wednesday next week.|3,4,5|''',
'765':'''search|B has not yet found a new job and is still searching.|1,2|
temp|B is doing temporary work through a temp agency.|2|
company|B is temping at a pharmaceutical company.|4|
duties|B mostly does office work, including filing.|6|
end|B's temporary assignment lasts until the end of the month.|8|''',
'340':'''company|B and A share a company or workplace affiliation.|1,2,5,6|1,5
network|B believes the company should equip every office and showroom with networked workstations as soon as possible.|2,5|
equipment|B considers the company's copying machines too slow and telephone system limited in function.|6,7|
catalogue|A proposes that B provide a catalogue of new equipment next week.|7|7''',
'762':'''english|B has an impressively strong knowledge of English according to A.|1,2,3|1,3''',
'661':'''practice|B proposes practising French dialogues together with A, and A accepts.|1,4,5|1,5''',
'85':'''diet|B is on a diet.|2|''',
'196':'''retail|B represents a retailer offering a range of sweaters, including round-neck sweaters.|1,2,4|''',
'87':'',
'891':'''girlfriend|B has a girlfriend.|1,2|1
love|B is in love with B's girlfriend.|3,4|3
marry|B plans to marry B's girlfriend.|9,10|9
male|A describes B as a man in the relationship discussion.|11|11''',
'596':'''jump|B jumped out of a window in response to an earthquake alarm.|1,2|1
reaction|Jumping was B's first thought on hearing the earthquake shout.|2|
opinion|B believes B should have jumped in any case, rather than using the stairs.|4,6|''',
'532':'''name|B is addressed as Gordon.|1|1
full|B is full after the meal.|2|
work|B must get up early for work tomorrow.|4|
cash|B is currently short of cash.|9|9
split|B agrees to split tonight's restaurant bill with A.|7,10,11|7,11
treat|B plans to treat A to dinner next week, and A agrees.|12,13|13
unfulfilled|B has repeatedly promised to treat A to dinner but has not yet done so.|8|''',
'640':'''name|B is addressed as John.|1|1
joke|B has played an April Fool's joke on A about A's father's presence.|1,2,3,4|1,3''',
'143':'''interview|B is a candidate interviewing for a job at A's company.|5,8,9,12|5,9
reply|B is to be notified by telephone within two weeks if B passes the interview; no call means B was unsuccessful.|3,5,7|3,5,7
learning|B says B has learned a lot from the interview conversation regardless of the result.|10|
mentality|A positively evaluates B's mentality in the interview.|11|11''',
'959':'''bag|B is offering the bag for sale, initially at 17 dollars.|1,2|
minimum|B says 14 dollars is the lowest price B will accept for the bag.|4,6|''',
'503':'''name|B is addressed as Monica.|1|1
office|B has a new office.|1,2|1
love|B loves the new office.|2|
room|B's office is spacious and clean with large windows and abundant sunshine.|2|
plants|There are plants along B's office corridor.|2|
desk|B has a personal desk equipped with a computer and telephone.|2,7|
phone|The telephone on B's desk has extension 506.|7|7
supplies|B can collect office supplies from the supply room at the end of the corridor.|7|7
environment|B believes a good office environment is important for working efficiently.|6|''',
'28':'''table|B and A obtained the last available table for two without a reservation.|1|1
hungry|B is very hungry.|2|
samosas|B proposes ordering a shared plate of samosas, which A accepts.|4,5,6,7|5,7
dahl|B tentatively plans to order dahl as a main course.|8,9|
kebabs|B agrees to share kebabs and proposes lamb kebabs.|11,12,13|
beer|B plans to have a beer with the meal.|14|
waitress|B would prefer to wait for the waitress rather than signal her over.|16,17|''',
'604':'''hot|B likes hot food, especially Sichuan cuisine.|4|
beer|B is drinking beer and wants another cup.|5,6|5
alone|B dislikes drinking alone, especially with someone sitting nearby.|6|
meal|B thinks this restaurant meal is excellent.|8|
return|B plans to return to this restaurant soon.|8|''',
'377':'''taj|B has visited the Taj Mahal and admires its architecture and art.|3,4|
rome|B would love to go to Italy and see the Colosseum.|6|
trip|B agrees to look for cheap airfare with A for a trip towards the end of the year.|7,8|''',
'209':'''company|B and A share an affiliation with a company occupying the sixth and seventh floors of this building.|3,5,6|
restaurant|B's company has a staff restaurant at the end of the hall.|7,8|''',
'840':'''spring|B's favourite season is spring.|3,4|
summer|B dislikes summer most because it is the hottest season.|6,8|''',
'925':'',
'392':'''resume_view|B believes A should include language abilities on A's engineering resume to show a rounded background.|2,4|
interview_view|B believes resumes are limited and interviews are important for showing the person beyond the resume.|6|''',
'208':'''never|B has never tried shopping online.|1,2|
touch|B prefers seeing and touching purchases before paying, especially clothes and shoes.|2|
physical|B only shops in physical shops because B considers online payment insufficiently safe.|6,7,8|7,9
friends|B has heard friends report discrepancies between online advertisements and delivered goods.|4|''',
'40':'''call|B called a plumber to B's old house.|1,2|
leak|B's bathroom is leaking water.|2|
toilet|B's toilet is clogged, will not flush, and overflows; A suspects a foreign object blocking the pipes.|3|3
daughter|B has a four-year-old daughter.|4|
flushing|B says B's daughter often flushes objects down the toilet.|4|
pipes|The water pipes in B's bathroom are rusty and A recommends replacement.|5|5
faucet|B's faucet does not shut off properly and A recommends fixing it.|5|5
repair|B accepts the offer to finish the plumbing repairs today, with A estimating a cost of about 800 dollars.|5,6,7|''',
'898':'''darkangel|B wants to watch Dark Angel and considers it a good show.|7,8|7
ally|B dismisses Ally McNeal as a girls' show.|4,6|
football|B proposes watching the football game instead.|10,11|11''',
'61':'''dressing|B prefers French dressing for the salad.|2,4,6|''',
'903':'''player|B believes the Phoenix team should replace player 21 and cannot beat the Rocket with that player.|2,4|''',
'857':'''duration|B has been here for approximately four months.|1,2|1
chinese|B's Chinese has improved since arrival.|3,4|
guangzhou|B arrived in Guangzhou.|4|
girlfriend|B has a girlfriend who bargained over a mobile phone when B first arrived.|4|
perception|B initially mistook the rapid bargaining for a violent shouting match.|6,7,8|7''',
'747':'',
'167':'''retail|B is acting as a suit seller, showing A a cheap suit that B says is not very durable.|2,4,6|''',
'684':'''party|B has a large outdoor party planned for tomorrow, with cancellation possible if the bad weather continues.|2|
worry|B is worried that the weather will force cancellation of the party.|2|''',
'595':'''visit|B plans to visit Deborah and her new baby.|9,10|''',
'485':'''name|B is addressed as John.|1|1
memo|B does not know where the office-procedures memo is and has not seen it for a long time.|3,4|''',
'783':'''grove|B and A agree not to enter the bamboo grove because entry is prohibited.|3,4,5|3,5''',
'471':'''name|B is addressed as Mr. Cook.|4,5|5
callback|B wants Michael Baker to return B's call as soon as he returns to the Oriental Hotel.|1,4,5|1,5''',
'512':'''forwards|B received and deleted Bean's superstitious good-luck forwards, including one attributed to the Dalai Lama.|1,2|
dislike|B is tired of forwarded good-luck messages and considers them superstition and a waste of bandwidth.|2,4|
case|B and A are working on a case for which they need ideas.|5|5''',
'850':'''looks|A considers B to be looking great.|1|1''',
'278':'''hire|B represents the employer that offered an accountant position to another, more experienced candidate instead of A.|1,2|1
trial|B responds positively to A's proposal for trial employment.|5,6|''',
'46':'''name|B is addressed as Saliva.|1|1
kitchen|B has a kitchen from which a pleasant cooking aroma is coming.|1|1
cooking|B is currently cooking steamed fish in a pressure cooker.|2,6|
school|B recently studied cooking skills at a training school.|4|
restaurant|B plans to run a restaurant and is practising cooking for that goal.|4|
fish_skill|A judges B's steamed fish to be delicious.|10,11,13|11,13
other_dishes|B is good at stewing beef with potatoes, frying chicken, and making hot and sour soup.|14|
party|B agrees to cook for A's birthday dinner party next Friday as cooking practice.|15,16,17|15,17''',
'977':'''frank|B thinks Frank lacks backbone because he gives in when things become difficult.|2,4|''',
'654':'',
'704':'''name|B is addressed as Helen.|1|1
busy|B is very busy with work these days and feels unable to finish it.|2|
pressure|B is under considerable pressure now.|4|3
behind|B is behind with work and says B cannot take a few days off.|5,6|''',
'126':'''name|B is addressed as Steven.|1|1
shopping|B and A plan to go shopping the day after tomorrow, Sunday.|2,3,5|3,5
crowds|B hates the hustle and bustle of Saturday shopping.|2|
rest|B wants a day to relax after a week's work.|4|
gift|B wants to buy A a crystal necklace as a birthday present at a jewellery shop.|8,9|''',
'608':'''taiji|B practises Taijiquan or shadow boxing.|4|
kungfu|B says B does not know how to practise the Bungfu A asks about.|3,4|
teach|B offers to teach A Taijiquan in exchange for A teaching B bowling, and both agree.|5,6,7,8|5,7''',
'413':'''beer|B orders a glass of Qingdao beer before the meal.|3,4,5|
meal|B is a customer preparing to order food at a restaurant.|1,2,5,6|1,3,5''',
'407':'''product|B and A share an affiliation with the product's company, whose competitive focus is quality rather than affordability.|9,10|9
price|B considers the product and the compatible system upgrades too expensive for most consumers.|2,4|''',
'400':'''seller|B is acting as the seller handling a vase A bought about an hour earlier.|3,4,6,8|
replace|B replaces the cracked vase with another one accepted by A.|8,9,10,11|9,11''',
'460':'''seller|B is acting as a retailer offering ladies' sports shirts.|1,2,4,6|''',
'2':'',
'769':'''eggplant|B believes eggplants are more nutritious than potatoes.|1,2|''',
'621':'''company|B represents the ABC company handling A's reserved car.|1,2,4,6|1,3
car|B's company has A's reservation J-221 but has not arranged the car.|5,6,7,8|''',
'362':'''magazine|B has a magazine A wants to borrow.|1,2|1
unfinished|B has not finished reading the current magazine and cannot lend it yet.|2|
back_issues|B has back issues of the magazine that B offers to lend A.|2,3|
frequency|B's magazine is published fortnightly.|4|''',
'543':'''restaurant|B is acting as restaurant service staff dealing with A's steak complaint.|1,2,4|
return|B plans to take A's steak back to the kitchen immediately, acknowledging a mistake.|2|''',
'99':'',
'231':'''assessment|B represents the organization that will assess A's financial proof documents, requiring originals and duplicates.|2,4,6|''',
'175':'''shoes|B wants to buy a pair of shoes.|2|
type|B is considering sneakers or rubber shoes.|4|
canvas|B likes the look of a particular pair of canvas shoes.|6|''',
'955':'''job|B has found a new job at a company.|1,2|1
happy|B is happy with the new job and enjoys the work.|3,4|3''',
'492':'''waves|B wants B's hair styled in big waves.|1,2|''',
'651':'''name|B is addressed as Tim.|7|7
male|A describes B as a guy.|7|7
breakup|A, Laura, is ending a romantic relationship with B.|5,7,8,10,11,12,13|5,7,11,13
repair|B wants another chance to preserve the relationship and does not want Laura to leave.|10|
keys|A returns B's keys and plans to send A's sister to collect A's remaining things next week.|13|13
past|B has made A happy in the past.|9|9''',
'589':'''company|B and A are involved in setting up their company's new branch office.|1,2,4,10|1,3,5
lawyer|B recommends hiring a good local corporate lawyer for the branch.|2|
hr|B prefers sending an existing HR employee rather than using an agency to hire branch staff.|4|
location|B's company's branch site is in the northeast of the city, near the airport on the edge of the CBD, because CBD offices were too expensive.|5,6,7|5,7
contracts|B's company has signed two contracts with existing international clients and hopes to sign three more this month.|8|
opening|B hopes the new branch office will open next month.|10|
ads|B's company has prepared advertising aimed at the business community through business magazines.|12|''',
'281':'''home|B and A share a room or home containing their Christmas tree.|1,3,5,7,10|1,3,5,7
tree|B likes the Christmas tree's appearance and atmosphere and is reluctant to remove it.|4,6,8|
busy|B and A have been too busy to remove their Christmas tree in the two weeks since Christmas.|7|7
christmas|B enjoyed a recent Christmas celebration with B's parents, A's parents, children, and cousins.|10,11|
cat|A cat in the shared household keeps playing with the Christmas tree's lower branches.|9|9
removal|A proposes that B and A leave the tree up until Sunday and take it down after church.|13|13''',
'573':'''viewing|B and A are viewing an open house that appears on their shared list.|1,2,3,4,5|1,3,5
neighborhood|B thinks the open house is in a wonderful neighborhood.|2|
kitchen|B wants to inspect the kitchen next.|6|
flyer|B wants a flyer containing the property's information.|8|''',
'727':'''concert|B did not attend the concert last weekend.|1,2|''',
'499':'''lab|B is affiliated with an organization whose computer lab on the first floor has a copy machine.|2|''',
'493':'''name|B is addressed as Jack.|1|1
internship|B's offered employment contract requires a three-month internship.|3,4|3
pay|B's offered permanent job pays monthly.|5|5
hours|B's offered permanent job has eight-hour working days.|5|5
insurance|B's permanent employment includes five insurances and one fund.|5,6,7|
holidays|B's offered job includes statutory holidays.|7|7
bonus|B's offered job includes a year-end bonus.|7|7
overtime|B is to receive double the usual salary for overtime work if required.|9|9
training|B's induction training is to last about two weeks.|12,13|13''',
'132':'''major|B majored in international banking at college.|2|
courses|B took many insurance courses at college.|2|
fieldwork|B worked at an insurance company for graduation fieldwork.|2|
agent|B wants to become an insurance agent.|3,4|3
care|B says B cares about people and understands the importance of insurance.|4|
sales|B has worked as a salesman for P & G Company Ltd.|5,6|
people|B considers B good with people.|7,8|''',
'541':'''name|B identifies as John.|6|
callback|B wants Marry Lin to call B back.|2,4,6|''',
'899':'''parents|B believes many parents do not know how to educate their children, agreeing with A's criticism of forcing unwanted learning.|3,4|''',
'890':'',
'828':'',
'984':'''name|B is addressed as Lander.|1|1
finances|B is having difficulty making ends meet these days.|2|
income|B's income has remained unchanged while prices rise.|4|
food|B has to spend 300 yuan more on food every month.|6|
worry|B worries price rises will spread beyond food to other areas.|12|
transport|B responds positively to A's suggestion to use public transport to work to reduce spending.|15,16|''',
'544':'''name|B is addressed as Allan.|1|1
project|B is working on a project with A.|1,2,3|1,3
effort|B says B has put as much work into the project as anyone else, disputing A's criticism.|1,2,3|''',
'67':'''stay|B must stay in A's city for only one day.|2|
landscape|B prefers a natural-landscape tour over a human-landscape tour.|3,4|
tour|A offers B a one-day river trip.|5|5''',
}

def main():
    ds=read(DATA/'dialogues.json');assert set(ANNOTATIONS)=={d['id'].split('_',1)[1] for d in ds}
    result=[]
    for d in ds:
        facts=[]
        for row in ANNOTATIONS[d['id'].split('_',1)[1]].splitlines():
            if not row.strip():continue
            local,claim,ev,asp=row.split('|')
            nums=[int(x) for x in ev.split(',')]
            supports=[[int(x) for x in s.split(',')] for s in asp.split(';') if s]
            assert all(n%2==1 for s in supports for n in s)
            assert all(1<=n<=len(d['turns']) for n in nums+[n for s in supports for n in s])
            facts.append({'id':d['id']+'_'+local,'claim':claim,'category':'personal_information',
                'status':'source_supported','full_evidence':[{'turn':n,'speaker':'A' if n%2 else 'B','quote':d['turns'][n-1]} for n in nums],
                'A_support_sets':supports,'A_support_status':'provisional_contextual_support' if supports else 'no_sufficient_A_evidence_identified',
                'first_A_prefix':min((max(s)+1)//2 for s in supports) if supports else None})
        result.append({'dialogue_id':d['id'],'facts':facts,'annotation_status':'current conversational assistant reads full A+B before new Qwen outputs; provisional AI reference, not independent human gold'})
    assert len({f['id'] for r in result for f in r['facts']})==sum(len(r['facts']) for r in result)
    freeze(DATA/'reference.json',result);freeze(DATA/'full_AB_reference_v2.json',result)
    freeze(DATA/'reference_manifest.json',{'reference_sha256':sha(result),'dialogues':len(result),
        'facts':sum(len(r['facts']) for r in result),'A_supported':sum(bool(f['A_support_sets']) for r in result for f in r['facts']),
        'created_utc':datetime.now(timezone.utc).isoformat(),'author':'current conversational assistant, direct source reading; no GPT API',
        'before_Qwen_output_inspection':True,'independent_human_gold':False,
        'scope':'best effort high recall B profile; pure dialogue acts and unanchored occupational guesses excluded; no completeness guarantee'})
    print({'dialogues':len(result),'facts':sum(len(r['facts']) for r in result)})

if __name__=='__main__':main()
