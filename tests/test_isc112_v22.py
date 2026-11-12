import copy
import unittest
from isc112_v2.core_v22 import render


class ExcludedDuplicateTests(unittest.TestCase):
    def test_excluded_duplicates_stay_excluded(self):
        a = {'id': 'c1', 'origin': 'candidate', 'claim': 'B was asked.', 'category': 'act', 'time': 'present',
             'holder': 'B', 'scope': 'dialogue_act', 'support': 'explicit', 'status': 'active',
             'checks': {'holder': True, 'content': True, 'qualifiers': True},
             'anchors': [{'turn': 1, 'quote': 'Hello'}], 'duplicate_of': None}
        b = {**copy.deepcopy(a), 'id': 'c2', 'duplicate_of': 'c1'}
        result = render({'checked_turns': [1], 'items': [a, b]}, [{'turn': 1, 'text': 'Hello.'}], [{'id': 'c1'}, {'id': 'c2'}])
        self.assertEqual(result['facts'], []); self.assertEqual(len(result['excluded']), 2)
        b['scope'] = 'profile'
        with self.assertRaises(ValueError): render({'checked_turns': [1], 'items': [a, b]}, [{'turn': 1, 'text': 'Hello.'}], [{'id': 'c1'}, {'id': 'c2'}])


if __name__ == '__main__': unittest.main()
