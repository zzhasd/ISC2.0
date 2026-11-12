import unittest
from .subject_audit import OUT, validate, STRICT
from .core import load


class SubjectAuditChecks(unittest.TestCase):
    def test_all_outputs_cover_original_claims(self):
        cases=load(OUT/'cases.json')
        self.assertEqual(len(cases),200)
        self.assertEqual(sum(len(c['candidates']) for c in cases),3195)
        for case in cases:
            result=load(OUT/'decisions'/f"{case['case_id']}.json")
            validate(dict(decisions=result['decisions']),case)

    def test_invalid_quotes_or_incomplete_outputs_rejected(self):
        case=dict(candidates=[dict(claim_id='c1')],visible_turns=[dict(turn_id=1,text='私は大阪です。')])
        with self.assertRaises(ValueError):validate({'decisions':[]},case)
        row=dict(claim_id='c1',claim_label='A_TO_B',attribute_label='A_TO_B',turn_id=1,quote='B is in Osaka',reason='test')
        with self.assertRaises(ValueError):validate(dict(decisions=[row]),case)
        row['quote']='私は大阪です。'
        self.assertEqual(validate(dict(decisions=[row]),case),[row])

    def test_assistant_review_sampling_and_citations(self):
        review=load(OUT/'assistant_review_conservative_v2.json')
        sample=load(OUT/'review_sample.json')
        cases={c['case_id']:c for c in load(OUT/'cases.json')}
        self.assertEqual(len(sample['case_ids']),20)
        self.assertEqual(len({cases[c]['group_id'] for c in sample['case_ids']}),20)
        self.assertEqual(len(review['rows']),349)
        flags=[r for r in review['rows'] if r['strict_transfer_confirmed']]
        self.assertEqual(len(flags),65)
        for row in flags:
            decision=row['review']
            turns={t['turn_id']:t['text'] for t in cases[row['case_id']]['visible_turns']}
            self.assertIn(decision['quote'],turns[decision['turn_id']])
            self.assertTrue(STRICT & {decision['claim_label'],decision['attribute_label']})

    def test_summary_matches_row_level_flags(self):
        summary=load(OUT/'summary.json')
        rows=load(OUT/'all_claims_screening.json')
        self.assertEqual(summary['automatic_screening']['strict_flagged_claims'],sum(r['machine_strict_flag'] for r in rows))
        self.assertEqual(summary['assistant_review']['confirmed_strict_claims'],sum(r['assistant_confirmed_strict'] is True for r in rows))
        self.assertTrue(summary['original_inputs_and_extractions_unchanged'])


if __name__=='__main__':unittest.main()
