import copy
import unittest
from isc112_v2.quote_binding import bind_quote, bind


class QuoteBindingTests(unittest.TestCase):
    def test_restores_actual_source_span(self):
        source = 'Well , I ’ m here .'
        self.assertEqual(bind_quote("I'm here", source), 'I ’ m here')

    def test_rejects_lexical_changes_and_wrong_numbers(self):
        for q in ['seven days', 'three days', 'c a r']:
            with self.assertRaises(ValueError): bind_quote(q, 'A stayed six days in a carpet shop.')

    def test_never_changes_decisions(self):
        obj = {'items': [{'id': 'c1', 'claim': 'An unsupported claim remains unsupported.', 'support': 'unknown',
                           'checks': {'content': False}, 'anchors': [{'turn': 1, 'quote': "I'm here"}]}]}
        before = copy.deepcopy(obj)
        after, audit = bind(obj, [{'turn': 1, 'text': 'I ’ m here .'}])
        self.assertEqual(obj, before)
        self.assertEqual(after['items'][0]['support'], 'unknown')
        self.assertEqual(after['items'][0]['checks'], {'content': False})
        self.assertEqual(len(audit), 1)


if __name__ == '__main__': unittest.main()
