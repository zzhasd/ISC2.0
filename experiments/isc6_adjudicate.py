"""Source-aware assistant's explicit semantic decisions; no inference-time use."""
from isc4_open import read,save,freeze,sha
from isc6_review import OUT


def main():
    queue=read(OUT/'review_queue.json');decisions={}
    def put(d,indices,kind,refs=(),partial=(),ground=True,source='consistent',reason='',canonical=None):
        if isinstance(indices,int):indices=[indices]
        for i in indices:
            assert (d,i) not in decisions
            decisions[d,i]={'verdict':kind,'reference_ids':list(refs),'partial_reference_ids':list(partial),
                'A_grounded':ground,'source_status':source,'rationale':reason,
                'canonical_id':canonical or (refs[0] if refs else partial[0] if partial else f'{d}_{i}'),
                'conjunctive_atoms':len(refs)>1}
    def match(d,i,suffix,reason='Matches the frozen reference including time and specificity.'):
        suffix=[suffix] if isinstance(suffix,str) else suffix
        put(d,i,'match',[d+'_'+s for s in suffix],reason=reason)
    def part(d,i,suffix,reason,ground=True,source='consistent'):
        suffix=[suffix] if isinstance(suffix,str) else suffix
        put(d,i,'partial',partial=[d+'_'+s for s in suffix],ground=ground,source=source,reason=reason)
    def scope(d,i,reason,ground=True,source='consistent'):
        put(d,i,'out_of_scope',ground=ground,source=source,reason=reason)
    def uncertain(d,i,reason,source='unverified'):
        put(d,i,'unverified',ground=False,source=source,reason=reason)

    match('test_39',0,['name','profession'],'Professor Clark conveys both the title and name; later your class anchors B. Same policy-sensitive reference as ISC5.')
    match('test_39',1,'teaching')
    match('test_709',0,'kitchen')
    put('test_709',1,'supported_new',reason='A explicitly describes their shared kitchen decoration as outdated; attributed as A description, not independently measured condition.',canonical='test_709_outdated_kitchen')
    uncertain('test_674',0,'Madam is an address convention, not independent verification of personal sex/gender; same policy as ISC5.')
    scope('test_674',[1,2,3,4],'Generic fitness-service script supplies no individualized habit, need, fitness level or goal value.',ground=False)
    part('test_674',5,'membership','Membership menu and Wise decision support some choice, but not the hidden one-month duration.')
    match('test_806',0,'name')
    scope('test_806',1,'A invitation is observed but does not establish B accepted a personal plan.')
    uncertain('test_806',2,'Look at/get a load of that does not ensure B actually sees the woman; full B confirms a reaction but A alone is insufficient.',source='consistent')
    uncertain('test_806',3,'Physical co-presence is plausible but visible A conversation does not uniquely establish it.',source='consistent')
    uncertain('test_806',4,'A announces departure and the ex presence; this does not establish B witnessed the triggering event.',source='unverified')
    scope('test_806',[5,6],'Being told information or bid farewell is a pure conversational act under the frozen profile policy.')
    match('test_826',0,'name')
    part('test_826',1,'movies','Movie watching is recovered, but a lot/frequency qualifier is lost.')
    uncertain('test_826',2,'Corrupted phrase what a confidence does not establish a psychological trait or an expression of confidence; same policy as ISC5.')
    scope('test_826',3,'Unspecified genres and A evaluation are a vague conversational characterization, not recovered B genre values.')
    part('test_826',4,'renting','Movie Salon is a rental store; purpose to watch films there is not supplied by A.',ground=False,source='unverified')
    match('test_826',5,'rental','A says also sign up for its membership after the movie-salon exchange; frozen ordinary additive-background policy applies.')
    match('test_629',0,'name')
    scope('test_629',1,'Arrival at the unspecified current encounter is a conversation-setting event without a specific profile value.')
    match('test_629',2,'graduation')
    part('test_629',3,'graduation','Diploma collection is supported but this claim repeats the already recovered graduation event without its shared-A relation.')
    match('test_629',4,'partner')
    scope('test_629',5,'An invitation to an unspecified event is a conversational act; the housewarming type/date remain hidden.')
    uncertain('test_112',0,'A purchase-oriented questions suggest a retail interaction but do not establish B personal profession rather than assisting with a purchase.',source='consistent')
    uncertain('test_112',1,'Available goods are contextually indicated, but B personal possession/control of the string is not specified.',source='consistent')
    scope('test_349',0,'Source of recommendations is the current conversational function, not a demonstrated stable personal attribute.')
    scope('test_349',1,'A evaluates a selection; assigning its provision to B adds an uncertain holder and remains a conversational/service act.',ground=False,source='unverified')
    scope('test_349',2,'An unspecified recommendation is a conversational act; no personal job or exact product value recovered.')
    put('test_102',0,'supported_new',reason='A explicitly situates the shared shopping at the fish counter; a coarse concrete activity supported by the full visible sequence.',canonical='test_102_joint_shopping')
    match('test_102',1,'seafood','Neither anchors a seafood-avoidance/dislike inference, not an allergy diagnosis; same frozen policy.')
    for i,s in [(0,'pale'),(1,'ill'),(2,'temperature'),(3,'throat'),(4,'infection'),(6,'aspirin'),(7,'antibiotics'),(8,'rest'),(9,'water')]:match('test_526',i,s)
    part('test_526',5,['antibiotics','aspirin'],'Medication classes are correct but this line omits their conditions; detailed lines separately receive the two exact matches.')
    match('test_375',0,'name')
    scope('test_375',1,'Receiving an appointment request does not establish B accepted a plan or its hidden time.')
    match('test_439',0,'wife')
    scope('test_100',[0,1],'Output explicitly describes A, not B. Source truth does not make it an in-scope B fact.')
    scope('test_514',0,'Offer is a conversational act, not B acceptance or food preference.')
    uncertain('test_514',1,'Near here locates A; B co-location is not established by A-only.',source='unverified')
    uncertain('test_514',2,'Initial food-delivery proposal is not B commitment and later A endorses another option; the actual B rejects takeout.',source='contradicted')
    scope('test_663',[0,1,2],'Current advice-seeking/providing acts do not establish a personal role, residence or specific profile value.')
    scope('test_792',0,'Existence of an unspecified favorite without a recovered sport value is an unresolved variable, not an individualized profile fact.')
    part('test_792',1,'skaters','Familiarity is coarser than fandom; later fan too grounds the coarse fact but the cited turn alone is incomplete.')
    match('test_792',2,'skaters','Fan too links B to the named skaters through turn 9. Full visible context supplies the antecedent, although citation omits that turn.')
    match('test_697',0,'name')
    part('test_697',1,'english','English knowledge lacks the proficiency qualifier; a separate specific output recovers it.')
    part('test_697',2,'college','English learning is a supported coarse educational event; the location college remains hidden.')
    match('test_697',3,'english','Really well plus turn 1 English topic supplies the complete specific ability; cited turn alone needs that antecedent.')
    match('test_697',4,'wife')
    match('test_525',0,'name');match('test_525',1,'birthday')
    put('test_525',2,'supported_new',reason='A presents a birthday gift to B and reacts positively; same new-discovery policy as ISC5.',canonical='test_525_gift')
    for i,s in [(0,'name'),(1,'down'),(2,'success'),(3,'breakup')]:match('test_926',i,s)
    part('test_926',4,'breakup','Former relationship is supported but repeats a coarser version of the separately recovered recent breakup.')
    match('test_91',0,'broadcast','All news takes the local road-news scope. Preserve the frozen confirmatory-question policy; separately exclude this disputed label in sensitivity analysis.')
    part('test_369',0,'marriage','Close partner/spouse supported; ten-year duration omitted.')
    put('test_369',1,'contested',ground=False,source='contested',reason='Forgetting allegation rests on A incorrect anniversary date, later acknowledged; same policy as ISC5.')
    part('test_369',2,'anniversary','Reports the July 20 suggestion but fails to recover it as the final corrected anniversary.')
    scope('test_369',3,'Wrong subject for a B profile, and the mistake concerns the anniversary date, not the travel dates or tickets.',ground=False,source='contradicted')
    part('test_369',4,'marriage','Marriage supported but ten-year duration omitted.')
    part('test_369',5,'marriage','The time field keeps June 20 even after its correction; evaluate claim and time together.',ground=False,source='incorrect_date_qualifier')
    scope('test_369',6,'Generic conversation date is not an individualized B profile fact; it is also phrased as a confirmation question.',ground=False,source='consistent')
    scope('test_369',7,'A booking does not itself state B traveler identity; output is explicitly about A.')
    scope('test_464',[0,1],'Output explicitly describes A and A children, not B.')
    match('test_277',0,'name')
    scope('test_277',[1,2],'Questioning an item or initiating the call is a conversational act; no specific B attribute value.')
    put('test_468',0,'partial',partial=['test_468_role'],ground=False,source='consistent',reason='A calls about a check but this does not establish which entity employs B or B personal issuing authority.')
    uncertain('test_468',1,'A nonreceipt does not establish B failed to issue a check; assignment of agency and cause is unobserved.')
    uncertain('test_468',2,'A mentions forgetting an unspecified submission, not the exact requirement or B authority; full B gives the requirement.',source='consistent')

    required={(r['dialogue_id'],r['fact_index']) for r in queue}
    assert set(decisions)==required,{'missing':sorted(required-set(decisions)),'extra':sorted(set(decisions)-required)}
    result=[{**r,**decisions[r['dialogue_id'],r['fact_index']],
        'reviewer':'current source-aware assistant; same author as method; not independent human gold'} for r in queue]
    freeze(OUT/'semantic_review.json',result)
    save(OUT/'semantic_review_manifest.json',{'reviewed_assertions':len(result),'review_sha256':sha(result),
        'queue_sha256':sha(queue),'independent_human_review':False,'source_aware':True,
        'policy':'retain ISC5 reference policy; explicit conjunction atomization supplementary only; full claim/time inspected',
        'scope_note':'A-supported but out-of-scope acts are not equivalent to usable B facts; report separately'})
    print({'reviewed_assertions':len(result)})

if __name__=='__main__':main()
