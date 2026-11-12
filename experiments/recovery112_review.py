"""Current assistant's explicit semantic review of newly returned assertions."""
from isc4_open import read,save
from recovery112 import OUT

def build(kind):
    queue=read(OUT/kind/'review_additions_queue.json');dec={}
    def put(indices,verdict,refs=(),ground=True,source='consistent',reason='',canonical=None):
        if isinstance(indices,int):indices=[indices]
        if isinstance(refs,str):refs=[refs]
        for i in indices:
            assert i not in dec
            did=queue[i]['dialogue_id'];ids=[did+'_'+r for r in refs]
            row={'kind':verdict,'verdict':verdict,'reference_ids':ids,'partial_reference_ids':[],
                'A_grounded':ground,'source_status':source,'rationale':reason,'conjunctive_atoms':len(ids)>1,
                'canonical_id':did+'_'+canonical if canonical else (ids[0] if ids else queue[i]['review_id']),
                'reviewer':'current conversational assistant reads full A+B; frozen references; not independent human gold'}
            if kind=='isc7' and verdict=='partial':row['partial_reference_ids']=ids;row['reference_ids']=[]
            dec[i]=row
    def m(i,ref,reason='Matches frozen B attribute/value with compatible time and specificity.'):
        put(i,'match',ref,reason=reason)
    def p(i,ref,reason,ground=True):put(i,'partial',ref,ground=ground,reason=reason)
    def u(i,reason,source='unverified'):put(i,'unverified',ground=False,source=source,reason=reason)
    def s(i,reason,ground=True):put(i,'out_of_scope',ground=ground,reason=reason)
    def n(i,canonical,reason):put(i,'supported_new',canonical=canonical,reason=reason)
    if kind=='isc4':
        m(0,'interview')
        p(1,'reply','Pending interview outcome recovered, two-week conditional telephone-notification rule omitted.')
        m(2,'trip','In the booked upcoming-trip context, present progressive traveling denotes the planned June20 journey; A7/day-after-tomorrow and A9/June18 anchor same frozen plan.')
        p(3,'faucet','Faulty faucet recovered; recommendation to fix it omitted.')
        p(4,'daughter','Small-child state agrees with hidden daughter, but A little-one statement is first-person A evidence; age and B parenthood not independently supplied by the quoted A.',ground=False)
        p(5,'pipes','Rust condition recovered; replacement recommendation omitted.')
        p([6,7],'toilet','Individual clog/flush or overflow component recovered, complete frozen diagnostic attribute not expressed.')
        s(8,'Being addressed for help is a pure conversation role.')
        p(9,'seller','Retail interaction is plausible but personal shop employment/representation is not uniquely established by A purchase narrative.',ground=False)
        p(10,'breakup','Former female relationship recovered; recent breakup event not explicitly recovered in this item.')
        m(11,'breakup');m(12,'down')
        put(13,'unsupported',ground=False,source='unverified',reason='The hidden source assigns career-pursuit priority to the former partner; A9 generic career/family conflict does not establish B own career dilemma.')
    elif kind=='isc7':
        m(0,'risk');p(1,'late','Prior two late arrivals recovered; complete current-repeat/manager-anger work-lateness attribute omitted.')
        m(2,'name');p(3,'late','Current lateness only; prior incidents and manager reaction omitted.')
        s(4,'An unspecified third-party office is not B concrete role or personal value.',ground=False)
        u(5,'One proposed after-church Sunday does not establish habitual Sunday church attendance.')
        p(6,'tree','Tree-atmosphere evaluation recovered, appearance and reluctant removal not all stated.')
        p(7,'christmas','Positive prior-Christmas evaluation recovered; specific family gathering details omitted.')
        m(8,'busy')
        u(9,'Honey alone does not uniquely identify spouse/romantic partner rather than another close family relationship.')
        m(10,'name');m(11,'name')
        n(12,'read_contract','A11 explicitly confirms reading relevant terms by that turn, before A15 signing instruction; does not assert reading before the meeting.')
        m(13,'internship');m(14,'holidays');m(15,'bonus')
        p(16,'insurance','Generic insurance benefit recovered, exact five-insurances-and-one-fund values hidden.')
        m(17,'pay');m(18,'overtime');m(19,'hours');m(20,'name');m(21,'project');m(22,'name');m(23,'name')
        p(24,'pressure','Stress/heavy burden supported by A consolation; considerable degree not clearly expressed.')
        m(25,'name')
    else:raise ValueError(kind)
    assert set(dec)==set(range(len(queue)))
    result=[{**q,**dec[i]} for i,q in enumerate(queue)]
    save(OUT/kind/'review_additions.json',result)
    return len(result)

if __name__=='__main__':
    print({k:build(k) for k in ['isc4','isc7']})
