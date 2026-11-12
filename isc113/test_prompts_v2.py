"""Contract checks specific to the new matcher adapter."""
import unittest
from .evaluate_prompts_v2 import load_prompt, validate_v2


class V2MatcherTests(unittest.TestCase):
    def test_loads_new_match_prompt(self):
        self.assertIn('BIDIRECTIONAL NATURAL LANGUAGE INFERENCE', load_prompt())

    def test_accepts_directional_and_empty_results(self):
        pp = [{'prediction_id': 'p'}]
        rr = [{'claim_id': 'r'}]
        for relation, ids in [('equivalent', ['r']), ('broader', ['r']),
                              ('narrower', ['r']), ('none', [])]:
            obj = {'matches': [dict(prediction_id='p', reference_ids=ids, relation=relation)]}
            self.assertEqual(validate_v2(obj, pp, rr), obj['matches'])

    def test_rejects_invented_reference_and_invalid_relation(self):
        pp = [{'prediction_id': 'p'}]
        rr = [{'claim_id': 'r1'}, {'claim_id': 'r2'}]
        for relation, ids in [('broader', ['invented']), ('invalid', [])]:
            with self.assertRaises(ValueError):
                validate_v2({'matches': [dict(prediction_id='p', reference_ids=ids,
                                               relation=relation)]}, pp, rr)

    def test_preserves_historical_multiple_reference_contract(self):
        obj = {'matches': [dict(prediction_id='p', reference_ids=['r1', 'r2'], relation='broader')]}
        self.assertEqual(validate_v2(obj, [{'prediction_id': 'p'}],
                                    [{'claim_id': 'r1'}, {'claim_id': 'r2'}]), obj['matches'])


if __name__ == '__main__':
    unittest.main()
