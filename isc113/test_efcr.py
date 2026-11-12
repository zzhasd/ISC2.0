"""EFCR interface, evidence gates and inference isolation checks."""
import copy
import unittest
from . import EFCR
from .common import read, BASE
from .inference import METHODS


class EFCRTests(unittest.TestCase):
    def setUp(self):
        self.item = dict(item_id='dailydialog/test/A_to_B', dialogue_id='test',
                         dataset='dailydialog', direction='A_to_B',
                         visible_turns=[dict(turn_id=1, text='Your dog is lovely.')])
        self.claim = dict(claim='The target has a dog', attribute='pet',
                          certainty='asserted', mechanism='presupposition', confidence=.9,
                          evidence=[dict(turn_id=1, quote='Your dog')])

    def test_only_efcr_two_calls_and_compatible_record(self):
        calls = []
        claim = self.claim
        class Fake:
            def call(self, name, request, validate):
                calls.append((name, request))
                obj = ({'claims': [copy.deepcopy(claim)]} if len(calls) == 1 else
                       {'decisions': [dict(candidate_id='c1', verdict='keep',
                                          evidence_level='E2', confidence=.8,
                                          evidence=claim['evidence'])]})
                return validate(obj), 'task' + str(len(calls))
        result = EFCR.pipeline(Fake(), self.item)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result[0]['method'], EFCR.NEW_METHOD)
        self.assertEqual(result[0]['task_ids'], ['task1', 'task2'])
        self.assertEqual(len(result[0]['claims']), 1)
        self.assertEqual(len(METHODS), 6)
        for _, request in calls:
            content = __import__('json').loads(request['messages'][1]['content'])
            self.assertNotIn('reference', content)
            self.assertEqual(content['visible_turns'], self.item['visible_turns'])

    def test_invalid_proposal_quote_abstains_without_resampling(self):
        claim = copy.deepcopy(self.claim)
        claim['evidence'][0]['quote'] = 'invented'
        calls = []
        class Fake:
            def call(self, name, request, validate):
                calls.append(name)
                return validate({'claims': [claim]}), 'task'
        result = EFCR.pipeline(Fake(), self.item)
        self.assertEqual(result[0]['claims'], [])
        self.assertEqual(len(calls), 1)

    def test_repairs_require_valid_original_turn_evidence(self):
        candidates = EFCR.evidence_candidates(EFCR.validate_claims(
            {'claims': [copy.deepcopy(self.claim)]}, self.item['visible_turns']))
        decision = dict(candidate_id='c1', verdict='repair', evidence_level='E2',
                        confidence=.8, evidence=self.claim['evidence'],
                        revised=copy.deepcopy(self.claim))
        checked = EFCR.validate_counterfactual({'decisions': [decision]},
                                               self.item['visible_turns'], candidates)
        self.assertIn('repaired_from', EFCR.apply_counterfactual(candidates, checked)[0])
        decision['evidence'] = [dict(turn_id=1, quote='fabricated')]
        checked = EFCR.validate_counterfactual({'decisions': [decision]},
                                               self.item['visible_turns'], candidates)
        self.assertEqual(EFCR.apply_counterfactual(candidates, checked), [])

    def test_rejects_hidden_turns_and_wrong_direction(self):
        for bad in [dict(self.item, direction='B_to_A'),
                    dict(self.item, visible_turns=[dict(turn_id=2, text='hidden')]),
                    dict(self.item, reference=[])]:
            with self.assertRaises(ValueError):
                EFCR.pipeline(None, bad)

    def test_primary_scope(self):
        items = read(BASE / 'inputs/dailydialog.json')
        self.assertEqual(len(items), 298)
        for item in items:
            EFCR.validate_input(item)


if __name__ == '__main__':
    unittest.main()
