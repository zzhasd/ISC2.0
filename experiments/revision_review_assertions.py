"""Codex AI review of explicit candidates, NOT independent human gold.

Decisions were made by reading each definite candidate and its actual summary.
The source B transcript and original truth labels were not used to decide whether
the SUMMARY asserts a proposition. Keep original model labels and quotes intact.
"""
import hashlib
import json
from revision_api import ROOT,OUT,read,save,freeze

REJECT={
 ('64f49c6c07c4b438_r0','pregnant'):'Mentioning men is not an explicit assertion that B is not pregnant; do not infer medical negatives from gender.',
 ('765c474835783669_r0','divorce_separation'):'Being happily married does not explicitly assert absence of divorce/separation; the summary contains no such negation.',
 ('2b71a202d6e25c70_r0','marriage_planned'):'An existing wedding anniversary does not explicitly negate future wedding plans.',
 ('c1f1ca66ea07e695_r0','marriage_planned'):'An existing wedding anniversary does not explicitly negate future wedding plans.',
 ('68abbed7852c20d7_r0','marriage_planned'):'A past wedding date does not explicitly negate future wedding plans.',
 ('6a7998734e6b6e22_r0','employed'):'Only qualified as predicted replies indicating B is busy with work; not a definite assertion of an observed actual B job.',
 ('2852c471af55f17e_r0','job_seeking'):'A future idea to seek work after the current endeavor does not assert current active job seeking/applying.',
 ('dadf4037ea48b12b_r0','job_seeking'):'Intent to seek employment after graduation does not assert current active job seeking/applying.',
 ('15f113ca946251c7_r0','job_seeking'):'Intent to seek employment after graduation does not assert current active job seeking/applying.',
 ('6efd83def1121930_r0','married'):'Seeking a new girlfriend does not explicitly assert that B is unmarried.',
 ('eae4f8ba3352a7e2_r0','marriage_planned'):'An existing wedding anniversary does not explicitly negate future wedding plans.',
 ('17c60d2e92ba9c0b_r0','marriage_planned'):'An existing wedding anniversary does not explicitly negate future wedding plans.',
}
for t in ['2ced752e7028593a_r0','85c04398fd397d1b_r0','706b47316b18c738_r0','b97e0dd523969914_r0']:
    REJECT[(t,'cold')]='A slight viral infection does not explicitly negate a cold; the classifier introduced an unsupported medical exclusion.'
for t in ['0b681b47b43fe331_r0','4872bce1ab28f71e_r0','530bda940f7350bb_r0','ea67314be91cd596_r0']:
    REJECT[(t,'employed')]='Success/heartbreak does not explicitly assert current employment; one quote is copied from A rather than the summary.'
    REJECT[(t,'unemployed')]='Success/heartbreak does not explicitly negate current unemployment; one quote is copied from A rather than the summary.'
for t in ['0b681b47b43fe331_r0','4872bce1ab28f71e_r0','ea67314be91cd596_r0']:
    REJECT[(t,'married')]='A breakup or ended relationship does not explicitly negate current marriage.'
REJECT[('530bda940f7350bb_r0','divorce_separation')]='A breakup does not explicitly assert or negate marital divorce/separation.'

QUOTE_OVERRIDES={
 ('2b71a202d6e25c70_r0','married'):'their actual 10th wedding anniversary is July 20',
 ('c1f1ca66ea07e695_r0','married'):'their actual wedding anniversary is July 20',
 ('3873de0d77116dfa_r0','married'):"A asks B how he celebrates Valentine's Day with his wife.",
 ('eae4f8ba3352a7e2_r0','married'):'their actual 10th wedding anniversary is July 20',
}

def main():
    rawpath=OUT/'defense_judge_v2/api_raw.jsonl'
    status=read(OUT/'defense_judge_v2/run_status.json')
    assert status['complete'],'Wait until the complete judge run is available'
    plan={t['task_id']:t for t in read(OUT/'defense_judge_v2/requests.json')}
    raw=[json.loads(x) for x in rawpath.read_text(encoding='utf-8').splitlines()]
    items=[]
    for call in raw:
        if call.get('http_status')!=200:continue
        choice=call['body']['choices'][0];assert choice['finish_reason']=='stop'
        obj=json.loads(choice['message']['content'])
        summary=json.loads(plan[call['task_id']]['payload']['messages'][1]['content'])['summary']
        for fact in obj['facts']:
            if fact['label']=='unknown':continue
            key=(call['task_id'],fact['id'])
            quote=QUOTE_OVERRIDES.get(key)
            if quote:assert quote in summary,'Corrected quote must be verbatim source text'
            items.append({'task_id':key[0],'attribute':key[1],'raw_label':fact['label'],'raw_quote':fact.get('quote',''),
                'decision':'reject' if key in REJECT else 'accept',
                'reason':REJECT.get(key,'The summary supports the catalogue proposition about B or an unambiguous addressed alias; relationship presuppositions and explicit treatment/work-role descriptions count under the stated policy.'),
                'corrected_quote':quote,'summary_sha256':hashlib.sha256(summary.encode()).hexdigest(),
                'reviewer':'Codex AI assistant, post hoc explicit-candidate validity review; not an independent human'})
    # The full candidate count is set after the final remaining outputs have been read.
    completion=read(OUT/'defense_judge_v2/review_completion.json')
    expected=completion['reviewed_candidate_count']
    assert hashlib.sha256(rawpath.read_bytes()).hexdigest()==completion['raw_sha256'],'Raw outputs changed after candidate review'
    assert len(items)==expected,'New/unreviewed candidates appeared'
    known={(r['task_id'],r['attribute']) for r in items}
    assert set(REJECT)<=known and set(QUOTE_OVERRIDES)<=known
    freeze(OUT/'defense_judge_v2/assertion_review.json',{'all_definite_candidates_reviewed':True,
        'items':items,'reviewed_candidate_count':len(items),'rejected':sum(r['decision']=='reject' for r in items),
        'caveat':'Only all definite v2 candidates were reviewed; no independent human labels or missed-assertion recall estimate.'})
    print({'reviewed':len(items),'rejected':sum(r['decision']=='reject' for r in items)})

if __name__=='__main__':main()
