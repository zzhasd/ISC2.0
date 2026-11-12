"""Codex provisional annotation after reading all 104 full dialogues, before attacks.

Absence is never a negative. Professional-role and interview-based annotations
are explicitly policy sensitive; preserve them for strict sensitivity analysis.
"""
from collections import Counter
import json
from revision_api import ROOT, freeze, save, read, digest
DATA=ROOT/'data/revision'
# dialogue, target, attribute, truth, original evidence, annotation basis
FACTS=[
 (973,0,'employed','true',[1,3],'current_company'),
 (137,0,'employed','true',[3,5,7],'professional_service_role'),
 (486,1,'employed','true',[2,4],'professional_service_role'),
 (70,1,'employed','true',[2,4,6],'professional_service_role'),
 (52,0,'employed','true',[1,5,7,13],'professional_service_role'),
 (59,0,'employed','true',[1,9,11],'professional_service_role'),
 (844,1,'employed','true',[2,4,8,10],'professional_service_role'),
 (272,0,'employed','true',[1,3,7],'current_company'),
 (272,1,'employed','true',[4],'current_company'),
 (342,1,'employed','true',[2,4,6,8],'professional_service_role'),
 (403,1,'employed','true',[4,6,8],'professional_service_role'),
 (403,0,'medical_treatment','true',[8],'explicit_prescription'),
 (150,0,'employed','true',[1,3],'professional_service_role'),
 (150,1,'job_seeking','true',[1,2,3,4],'interview_context'),
 (168,0,'employed','true',[1,3],'professional_service_role'),
 (552,1,'employed','true',[2],'professional_service_role'),
 (605,1,'employed','true',[2,4],'professional_service_role'),
 (433,0,'employed','true',[11,15,17],'professional_service_role'),
 (433,1,'job_seeking','true',[11,12,15,16,17],'interview_context'),
 (29,0,'employed','true',[1],'professional_service_role'),
 (29,1,'job_seeking','true',[1,2],'interview_context'),
 (123,0,'job_seeking','true',[1,3],'explicit_interview'),
 (226,1,'employed','true',[2,4],'professional_service_role'),
 (889,0,'employed','true',[3,5,7,9],'explicit_current_work'),
 (889,1,'employed','true',[2],'explicit_boss_work_task'),
 (129,0,'employed','true',[3],'explicit_current_department'),
 (129,1,'employed','true',[2,4],'professional_service_role'),
 (222,0,'employed','true',[3,5],'professional_service_role'),
 (378,1,'employed','true',[2,4,6,14],'professional_service_role'),
 (398,1,'employed','true',[12],'professional_service_role'),
 (33,0,'employed','true',[1,3,5,7,9,11],'professional_service_role'),
 (33,1,'employed','true',[2,12],'explicit_current_work'),
 (33,1,'job_seeking','true',[1,2,3,4,9,10],'interview_context'),
 (185,1,'employed','true',[2,4],'professional_service_role'),
 (366,0,'employed','true',[3,5,7],'professional_service_role'),
 (309,0,'employed','true',[1,3,15],'current_company'),
 (309,1,'employed','true',[2,6,14],'current_company'),
 (568,0,'employed','true',[5,7,9],'current_office'),
 (568,1,'employed','true',[2],'current_company'),
 (504,0,'employed','true',[1,3,5,9],'professional_service_role'),
 (504,1,'job_seeking','true',[1,2,3,9,10],'interview_context'),
 (71,0,'employed','true',[1,3,7],'professional_service_role'),
 (188,0,'job_seeking','true',[1,3],'position_enquiry'),
 (188,1,'employed','true',[4],'professional_service_role'),
 (409,1,'employed','true',[10,12],'professional_service_role'),
 (565,0,'employed','true',[1,3],'professional_service_role'),
 (128,0,'employed','true',[1,7,9],'professional_service_role'),
 (462,0,'employed','true',[5,9,11,13,15],'professional_service_role'),
 (4,0,'employed','true',[1,3,5,7],'professional_service_role'),
 (4,1,'married','false',[8],'explicit_unmarried'),
 (4,1,'job_seeking','true',[1,2,3,4,7,8],'interview_context'),
 (666,1,'employed','true',[2,6,8,10,12],'professional_service_role'),
 (583,1,'employed','true',[4],'explicit_secretary_possession'),
 (599,0,'employed','true',[1,3,5,7],'professional_service_role'),
 (599,1,'job_seeking','true',[1,2,3,4,5,6,7,8],'interview_context'),
 (574,0,'has_children','true',[3],'explicit_children'),
 (574,1,'employed','true',[6],'professional_service_role'),
 (215,0,'employed','true',[1,3],'professional_service_role'),
 (265,0,'job_seeking','true',[1,3,5,7,9],'explicit_interview'),
 (45,1,'employed','true',[6,12,14],'professional_service_role'),
 (201,0,'employed','true',[1,5,7,9,11,13],'professional_service_role'),
 (922,0,'employed','true',[1],'explicit_new_job'),
 (515,0,'employed','true',[1,3],'current_company'),
 (515,1,'employed','true',[2,6],'current_company'),
 (417,0,'employed','true',[3,5,9,11],'professional_service_role'),
 (417,1,'employed','true',[2,4,6,8,10],'professional_service_role'),
 (69,0,'employed','true',[1,11],'professional_service_role'),
 (373,0,'job_seeking','true',[3],'explicit_application'),
 (373,1,'employed','true',[2,4],'current_company'),
 (72,0,'has_children','true',[3],'explicit_daughter'),
 (72,0,'has_daughter','true',[3],'explicit_daughter'),
 (113,0,'employed','true',[3,5,13,15,19],'professional_service_role'),
 (742,1,'financial_hardship','true',[2],'explicit_broke'),
 (749,1,'married','true',[6],'explicit_husband'),
 (749,1,'has_children','true',[8],'explicit_parenting'),
 (749,0,'married','true',[9],'presupposition_only'),
 (749,0,'has_children','true',[9],'explicit_past_parenting'),
 (791,1,'unemployed','true',[3,4],'not_working_homemaker_policy'),
 (791,1,'employed','false',[3,4],'not_working_homemaker_policy'),
 (791,1,'married','true',[5,6],'explicit_husband'),
 (791,1,'has_children','true',[4],'explicit_parenting'),
 (800,1,'has_children','true',[1,2,3],'explicit_mother'),
 (800,1,'employed','true',[2,3],'explicit_career_working'),
 (800,1,'married','true',[5,6],'confirmed_husband'),
 (822,0,'marriage_planned','true',[1,3],'explicit_upcoming_wedding'),
]
# Visible evidence only, indexed in the original full dialogue.
SUPPORT=[
 (272,0,'employed','true',[2],'role_address'),
 (342,1,'employed','true',[1],'role_address'),
 (403,0,'medical_treatment','true',[8],'direct_prescription'),
 (150,1,'job_seeking','true',[1,3],'interview_questions'),
 (433,1,'job_seeking','true',[11,15,17],'interview_outcome'),
 (29,1,'job_seeking','true',[1],'position_interview'),
 (123,0,'job_seeking','true',[2,4],'interview_preparation_confirmation'),
 (889,0,'employed','true',[2,4,6,8],'explicit_target_work'),
 (33,1,'job_seeking','true',[1,3,5,7,9,11],'interview_questions'),
 (504,1,'job_seeking','true',[1,3,5,9],'interview_questions'),
 (188,1,'employed','true',[3],'recruiter_role_address'),
 (4,1,'job_seeking','true',[1,3,5,7],'interview_questions'),
 (666,1,'employed','true',[1],'library_role_address'),
 (599,1,'job_seeking','true',[1,3,5,7],'interview_questions'),
 (215,0,'employed','true',[2],'guide_rate_question'),
 (265,0,'job_seeking','true',[2,4,6,10],'cross_turn_interview_preparation'),
 (515,0,'employed','true',[2,6],'shared_company'),
 (515,1,'employed','true',[1,3],'shared_company'),
 (373,0,'job_seeking','true',[4],'application_acceptance_policy'),
 (373,1,'employed','true',[1],'shared_company_policy'),
 (791,1,'unemployed','true',[3],'explicit_not_working_policy'),
 (791,1,'employed','false',[3],'explicit_not_working_policy'),
 (791,1,'married','true',[5],'possessive_presupposition'),
 (800,1,'has_children','true',[1,3],'mother_presupposition'),
 (800,1,'employed','true',[3],'working_mother_statement'),
 (800,1,'married','true',[5],'possessive_presupposition'),
]
NOTES={
 137:'Questions about future entitlements do not unambiguously establish that S1 already has this job.',
 29:'Part-time work in 2006 does not establish a current job.',
 613:'A past marriage is explicit, but current marital status is not; current-married remains unknown.',
 574:'Mrs is not treated as proof of current marriage. Not having a lot of money does not alone establish financial hardship.',
 160:'A request for permission to smoke is a proposed action, not a confirmed current tobacco habit; honorific Mrs is not marital gold.',
 224:'General questions about application procedures do not alone establish active job seeking.',
 147:'Questions about college history alone do not establish an ongoing job application.',
 791:'Not working while homemaking is mapped to no current job; unemployment definition is policy sensitive and excluded in strict analysis.',
 177:'First aid by a friend does not meet this catalogue medical-treatment-or-medicine definition; injury is out of scope.',
 373:'Applying to a department and prospective shared-company language do not establish that S0 already has a job.',
 113:'Broke describes an audio device, not financial hardship.',
 357:'An office example in general phone advice does not unambiguously establish a current job.',
 295:'Presidential candidacy is not itself evidence of current paid employment or of own marital status.',
 896:'The bereavement and child concern Mary, a third party.',
 870:'The debt belongs to David; needing repayment for a bill is not alone verified personal hardship.',
}
def main():
    dialogues=read(DATA/'dialogues.json'); inventory=read(ROOT/'data/stage2/inventory.json')
    facts={(f'test_{d}',s,a):(v,ev,b) for d,s,a,v,ev,b in FACTS}
    supports={(f'test_{d}',s,a):(v,ev,b) for d,s,a,v,ev,b in SUPPORT}
    assert len(facts)==len(FACTS) and len(supports)==len(SUPPORT)
    selected={d['id'] for d in dialogues}
    assert all(k[0] in selected for k in facts)
    gold=[]
    for d in dialogues:
        for s in [0,1]:
            for a in inventory:
                key=(d['id'],s,a['id'])
                truth,ev,basis=facts.get(key,('unknown',[],'insufficient_evidence_not_false'))
                support,aev,kind=supports.get(key,('unknown',[],'no_sufficient_A_only_evidence'))
                assert all(1<=i<=len(d['turns']) for i in ev+aev)
                assert all((i-1)%2!=s for i in aev)
                if support!='unknown': assert support==truth, key
                gold.append({'dialogue_id':d['id'],'arm':d['arm'],'target_source_speaker':s,
                    'view_id':f'{d["id"]}_target{s}','attribute':a['id'],'domain':a['domain'],
                    'truth':truth,'a_support':support,'full_evidence_turns':ev,'a_evidence_turns':aev,
                    'truth_basis':basis,'support_type':kind,
                    'sensitive_to_annotation_policy':any(x in basis for x in ['role','interview_context','policy','presupposition','position_enquiry']),
                    'dialogue_note':NOTES.get(int(d['id'].split('_')[1]),''),
                    'annotation_provenance':'Codex AI provisional after full transcript reading; no independent human annotation'})
    freeze(DATA/'gold.json',gold)
    save(DATA/'gold_manifest.json',{'items':len(gold),'truth_counts':dict(Counter(r['truth'] for r in gold)),
         'a_support_counts':dict(Counter(r['a_support'] for r in gold)),'sha256':digest(gold),
         'annotation':'AI provisional, frozen before any attacks on this added sample'})
    print(json.dumps(read(DATA/'gold_manifest.json')))

if __name__=='__main__': main()
