import copy
import json
import unittest
from . import EFCR_v2 as v2


class V2Tests(unittest.TestCase):
    def setUp(self):
        self.turns = [dict(turn_id=1, text='Your dog is lovely .')]
        self.item = dict(item_id='dailydialog/test/A_to_B', dialogue_id='test',
                         direction='A_to_B', dataset='dailydialog', visible_turns=self.turns)
        self.c = dict(claim='B has a dog.', attribute='pet', certainty='asserted',
                      mechanism='presupposition', confidence=.9,
                      evidence=[dict(turn_id=1, quote='Your dog')])

    def test_whitespace_rendering_keeps_original_span(self):
        e = v2.render_evidence([dict(turn_id=1, quote='dog is lovely.')], self.turns)[0]
        self.assertEqual(e['quote'], 'dog is lovely .')
        self.assertEqual(self.turns[0]['text'][e['start']:e['end']], e['quote'])

    def test_word_boundaries_case_and_punctuation_are_not_repaired(self):
        turns = [dict(turn_id=1, text='no one knows .')]
        for quote in ['none knows .', 'No one knows .', 'no one knows !']:
            e = v2.render_evidence([dict(turn_id=1, quote=quote)], turns)
            self.assertFalse(v2.valid_evidence(e, turns))

    def test_ambiguous_whitespace_location_is_not_recovered(self):
        turns = [dict(turn_id=1, text='Hello ! Hello !')]
        e = v2.render_evidence([dict(turn_id=1, quote='Hello!')], turns)
        self.assertFalse(v2.valid_evidence(e, turns))

    def test_three_calls_no_reference_access_and_source_dedup(self):
        calls = []
        claim = self.c
        class Fake:
            def call(self, name, request, validate):
                content = json.loads(request['messages'][1]['content'])
                calls.append(content)
                if len(calls) <= 2:
                    c = copy.deepcopy(claim)
                    if len(calls) == 2:
                        c['claim'] = c['claim'].rstrip('.')
                    obj = dict(claims=[c])
                else:
                    self.assertion = len(content['candidates'])
                    obj = dict(decisions=[dict(candidate_id='c1', verdict='keep',
                        evidence_level='E2', confidence=.9, evidence=claim['evidence'])])
                return validate(obj), 't' + str(len(calls))
        result = v2.pipeline(Fake(), self.item)[0]
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(calls[2]['candidates']), 1)
        self.assertEqual(len(result['claims']), 1)
        self.assertEqual(result['task_ids'], ['t1','t2','t3'])
        self.assertEqual(len(result['claims'][0]['proposal_sources']), 2)
        for content in calls:
            self.assertEqual(content['visible_turns'], self.turns)
            self.assertNotIn('reference', content)

    def test_direct_threshold_and_final_threshold(self):
        calls = []
        claim = self.c
        class Fake:
            def call(self, name, request, validate):
                calls.append(name)
                if len(calls) == 1:
                    obj = dict(claims=[copy.deepcopy(claim)])
                elif len(calls) == 2:
                    c = dict(copy.deepcopy(claim), claim='B likes dogs', confidence=.79)
                    obj = dict(claims=[c])
                else:
                    obj = dict(decisions=[dict(candidate_id='c1', verdict='keep',
                        evidence_level='E2', confidence=.69, evidence=claim['evidence'])])
                return validate(obj), name
        self.assertEqual(v2.pipeline(Fake(), self.item)[0]['claims'], [])

    def test_no_repair_and_full_decision_coverage(self):
        c = dict(self.c, candidate_id='c1')
        for obj in [dict(decisions=[]), dict(decisions=[dict(candidate_id='c1',
                verdict='repair', evidence_level='E2', confidence=.9)])]:
            with self.assertRaises(ValueError):
                v2.validate_decisions(obj, self.turns, [c])

    def test_invalid_quote_demotes_without_resampling(self):
        d = dict(candidate_id='c1', verdict='keep', evidence_level='E1', confidence=.9,
                 evidence=[dict(turn_id=1, quote='fabricated')])
        self.assertEqual(v2.validate_decisions(dict(decisions=[d]),self.turns,
                         [dict(self.c,candidate_id='c1')])[0]['verdict'],'reject')

    def test_rejects_hidden_turns_and_unsafe_fields(self):
        for item in [dict(self.item, direction='B_to_A'), dict(self.item, reference=[]),
                     dict(self.item, visible_turns=[dict(turn_id=2, text='B secret')])]:
            with self.assertRaises(ValueError):
                v2.pipeline(None, item)


if __name__ == '__main__':
    unittest.main()
