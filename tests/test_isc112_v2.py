import copy
import unittest

from isc112_v2 import core


class EvidenceDualTests(unittest.TestCase):
    def setUp(self):
        self.turns = [{'turn': 1, 'text': 'You stayed here for six days.'}]
        self.cs = [{'id': 'c1', 'claim': 'B stayed here for six days.', 'time': 'past', 'category': 'stay', 'qualifiers': ['six days'], 'evidence_turns': [1]}]
        self.item = {'id': 'c1', 'origin': 'candidate', 'claim': 'B stayed here for six days.', 'time': 'past', 'category': 'stay',
                     'holder': 'B', 'scope': 'profile', 'support': 'explicit', 'status': 'active',
                     'checks': {'holder': True, 'content': True, 'qualifiers': True},
                     'anchors': [{'turn': 1, 'quote': 'six days'}], 'duplicate_of': None}

    def test_literal_evidence_and_hidden_turns(self):
        obj = {'checked_turns': [1], 'items': [copy.deepcopy(self.item)]}
        self.assertEqual(len(core.render(obj, self.turns, self.cs)['facts']), 1)
        for anchor in [{'turn': 2, 'quote': 'six days'}, {'turn': 1, 'quote': 'seven days'}]:
            bad = copy.deepcopy(obj); bad['items'][0]['anchors'] = [anchor]
            with self.assertRaises(ValueError): core.render(bad, self.turns, self.cs)

    def test_duplicate_cannot_discard_supported_fact_into_unknown(self):
        target = copy.deepcopy(self.item); target.update(id='a1', origin='addition', support='unknown')
        original = copy.deepcopy(self.item); original['duplicate_of'] = 'a1'
        with self.assertRaises(ValueError): core.render({'checked_turns': [1], 'items': [original, target]}, self.turns, self.cs)

    def test_unchecked_qualifier_not_accepted(self):
        item = copy.deepcopy(self.item); item['checks']['qualifiers'] = False
        out = core.render({'checked_turns': [1], 'items': [item]}, self.turns, self.cs)
        self.assertEqual(out['facts'], []); self.assertEqual(len(out['hypotheses']), 1)

    def test_union_keeps_different_specificity_and_merges_evidence(self):
        rich = copy.deepcopy(self.cs[0]); rich['claim'] = 'B stayed in a particular country for six days.'
        self.assertEqual(len(core.union(self.cs, [rich])), 2)
        same = copy.deepcopy(self.cs[0]); same['qualifiers'] = ['past']
        self.assertEqual(core.union(self.cs, [same])[0]['qualifiers'], ['six days', 'past'])

    def test_inference_surface_contains_only_A(self):
        self.assertEqual(core.visible({'turns': ['visible', 'SECRET', 'also visible']}),
                         [{'turn': 1, 'speaker': 'A', 'text': 'visible'}, {'turn': 3, 'speaker': 'A', 'text': 'also visible'}])

    def test_missing_candidate_and_unfounded_addition_id_rejected(self):
        with self.assertRaises(ValueError): core.render({'checked_turns': [1], 'items': []}, self.turns, self.cs)
        item = copy.deepcopy(self.item); item.update(id='z1', origin='addition')
        with self.assertRaises(ValueError): core.render({'checked_turns': [1], 'items': [self.item, item]}, self.turns, self.cs)


if __name__ == '__main__': unittest.main()
