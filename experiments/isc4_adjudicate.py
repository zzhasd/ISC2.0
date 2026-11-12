"""Transparent CURRENT-ASSISTANT semantic review, not an independent model judge.

Ordinal assignments are pinned to exact review IDs before writing the review artifact.
No fuzzy-string matching or Qwen self-judging is used as an accuracy oracle.
"""
from isc4_open import OUT, DATA, read, save, freeze, sha

def main():
    q=read(OUT/'review_queue.json')
    assert len(q)==121 and q[0]['review_id']=='39e5277a0735feb87658' and q[-1]['review_id']=='d84048b20a1a8a0536c9'
    decisions={}
    def put(indices, kind, refs=(), grounded=True, reason='', source='consistent'):
        for i in indices:
            assert i not in decisions
            decisions[i]={'kind':kind,'reference_ids':list(refs),'A_grounded':grounded,
                'source_status':source,'rationale':reason,'canonical_id':refs[0] if refs else q[i]['dialogue_id']+'_'+q[i]['review_id']}
    def match(indices,ref,reason='Semantic equivalence at the recorded attribute granularity.'):
        put(indices,'match',[ref],True,reason)
    match([0],'test_102_seafood','A\'s neither pragmatically supports seafood avoidance; it does not establish allergy.')
    put([1],'out_of_scope',grounded=True,reason='A says B called A, but a conversational act is outside the frozen personal-profile counting policy.')
    match([2],'test_277_name')
    put([3],'unsupported',grounded=False,reason='A says I made a mistake; the model assigns A\'s admission to B.',source='contradicted')
    put([4,11],'partial',['test_369_marriage'],False,'Married for about ten years agrees at coarse level, but the June 20 anniversary qualifier is later corrected. No exact full-reference match.',source='incorrect_date_qualifier')
    put([5,16],'partial',['test_369_anniversary'],True,'July 20 is ultimately confirmed, but a report about B\'s belief is weaker than the final corrected anniversary fact.')
    put([6,7,10],'contested',grounded=False,reason='A alleges forgetting, but later admits A used the wrong anniversary date. Do not treat the accusation as verified truth.',source='contested')
    put([8,9],'partial',['test_369_trip'],False,'A booked tickets; B has a ticket only after A says we will fly. This weaker possession claim is not the full travel-plan fact.')
    put([12,13,14,15],'unsupported',grounded=False,reason='I have booked is A\'s action, not B\'s.',source='contradicted')
    put([17,18,19,21,22],'partial',['test_369_marriage'],False,'Honey alone does not uniquely identify spouse or romantic partner; full dialogue confirms marriage, but this prefix lacks sufficient A evidence.')
    put([20],'partial',['test_369_marriage'],True,'Spouse is supported, but the ten-year duration in the full reference is not recovered by this item.')
    match([23,24,25,26,27,28],'test_369_trip','Paris trip on June 20 is the same plan as the day after tomorrow with June 18 as current date.')
    put([29],'out_of_scope',grounded=True,reason='Current conversation date is not an independent personal attribute of B.')
    match([30,31],'test_375_name')
    put([32],'match',['test_39_profession','test_39_name'],True,'Compound item explicitly recovers both profession and surname; normalized to two atoms.')
    match([33],'test_39_profession','In full visible context, your morning literature class corroborates B\'s role. The cited office question alone is insufficient proof.')
    match([34,35,36,38],'test_39_teaching','Teaching and A\'s enrollment are merged into the same reference class/teacher relation; duplicate output cannot increase recovery count.')
    match([37],'test_39_name')
    match([39],'test_439_wife')
    put([40,41],'unsupported',grounded=False,reason='A\'s unemployment claim or missing form is wrongly assigned to B, the service representative.',source='contradicted')
    match([42,43],'test_525_name');match([44,45],'test_525_birthday')
    match([46,47],'test_526_temperature');match([48,53],'test_526_throat')
    match([49],'test_526_ill');match([50,51],'test_526_pale');match([52],'test_526_infection')
    match([54,58,60],'test_629_partner','A asks still with Jenn and subsequently endorses the relationship; Jenn is the truncated Jenny reference.')
    put([55],'supported_new',grounded=True,reason='A\'s glad that you came supports B being present at the gathering. This specific current-location event was omitted by the assistant reference.')
    match([56,57],'test_629_graduation')
    put([59],'partial',['test_629_married'],False,'Full source says marriage after graduation, but A\'s still with Jenn does not fix the relationship onset at graduation.')
    put([61],'partial',['test_629_graduation'],True,'Shared graduation context is supported, but this item omits the ten-year time interval.')
    match([62],'test_629_name')
    put([63],'unsupported',grounded=False,reason='One year is invented from Wise decision; complete B tentatively chooses one month.',source='contradicted')
    put([64,65,66,67,68,69,70],'out_of_scope',grounded=False,reason='Generic sales language about habits/needs/goals supplies no individualized value; do not count tautological profile facts.')
    put([71,72],'unverified',grounded=False,reason='Madam is a social form of address; gender identity/sex is not independently established.',source='unverified')
    match([73],'test_697_wife');match([74,75,77,78],'test_697_usa')
    put([76,79,81,82,83],'partial',['test_697_english'],True,'English knowledge is supported; the full reference\'s speaks well proficiency qualifier is absent.')
    match([80],'test_697_english');match([84,85],'test_697_name')
    put([86],'partial',['test_792_skaters'],True,'Knowing named skaters is weaker than being a fan. At this final prefix A\'s fan too supports familiarity; the must know quote alone is insufficient.')
    put([87],'match',['test_792_olympics'],False,'Complete B confirms the preference, but the cited I love it is A\'s preference. Source agreement is not grounded single-side recovery.')
    put([88,89],'unverified',grounded=False,reason='Finishing something does not identify studies, training or a particular life stage; the likely qualifier belongs in hypotheses.',source='unverified')
    put([90],'partial',['test_796_shanghai'],False,'Full B plans practice in Shanghai; neither a specific job-search commitment nor its stage is repeated in A.')
    put([91],'partial',['test_796_english_work'],False,'A/B discuss future usefulness of English, not established current job use. Preserve tense and uncertainty.')
    put([92],'unverified',grounded=False,reason='Invitation does not establish current co-location or an accepted plan.',source='unverified')
    put([93,94],'match',['test_806_drink_plan'],False,'B accepts in the full source, but A\'s invitation and Somewhere new do not establish acceptance on their own.')
    match([95],'test_806_name')
    put([96,97],'partial',['test_826_cinema'],False,'Cinema-frequency question does not establish regular attendance; full B says once in a while.')
    put([98,99,100],'unverified',grounded=False,reason='Corrupted phrase what a confidence is not reliable evidence of a psychological trait.',source='unverified')
    put([101,102,103],'unsupported',grounded=False,reason='Comedy and suspense are A\'s genres; full B prefers art films and thrillers.',source='contradicted')
    put([104,105,108,109],'partial',['test_826_movies'],True,'Watching movies is supported, but the amount a lot in the reference is omitted.')
    put([106],'out_of_scope',grounded=True,reason='Mentioning a place is a conversational act, not proof of membership, residence or preference.')
    put([107],'source_supported_new',grounded=None,reason='Full B says the store is good; the assistant reference omitted this opinion. A\'s reaction is compatible, but precise A-only entailment is uncertain.')
    match([110],'test_826_name')
    match([111,116,117],'test_926_down')
    put([112],'unsupported',grounded=False,reason='The dilemma primarily concerns the former partner pursuing her career; generic advice does not establish this as B\'s personal choice.',source='unverified')
    put([113],'partial',['test_926_breakup'],True,'Former partner and A\'s evaluation are supported; the breakup timing is not fully recovered by this item.')
    match([114,115],'test_926_breakup');match([118,120],'test_926_name');match([119],'test_926_success')
    assert set(decisions)==set(range(len(q))),sorted(set(range(len(q)))-set(decisions))
    reviewed=[]
    for i,item in enumerate(q):
        d=decisions[i]
        reviewed.append({**item,**d,'verdict':d['kind'],'reviewer':'current source-aware assistant; independent human review pending'})
    freeze(OUT/'assistant_semantic_review.json',reviewed)
    save(OUT/'semantic_review_manifest.json',{'queue_sha256':sha(q),'review_sha256':sha(reviewed),
        'reviewed_claim_evidence_pairs':len(reviewed),'independent_human_review':False,
        'warning':'Source-aware exploratory review; same assistant constructed the reference and reviewed Qwen. Not unbiased accuracy estimation.'})
    print({'reviewed':len(reviewed)})
if __name__=='__main__':main()
