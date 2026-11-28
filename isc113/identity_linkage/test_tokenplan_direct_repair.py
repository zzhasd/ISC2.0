import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from . import subject_one_portrait_tokenplan_v1 as runner


ORIGINAL_QUOTE = '三が日に流しそうめんですか。珍しいですね。'
NEAR_QUOTE = '三が日に流そうめんか。珍しいですね。'
EXACT_QUOTE = '最近は図書館で本を借りています。'


def profile(portrait_id, quote, turn_id):
    return dict(portrait_id=portrait_id, statement=f'{portrait_id} の画像',
                evidence=[dict(dialogue='D1', turn_id=turn_id, quote=quote)])


class DirectRepairTests(unittest.TestCase):
    def test_alignment_recovers_a_cited_span_with_multiple_short_matching_blocks(self):
        self.assertIn(ORIGINAL_QUOTE, runner.similar_quote_candidates(NEAR_QUOTE, ORIGINAL_QUOTE))
        self.assertEqual(runner.similar_quote_candidates(NEAR_QUOTE, '話題に一切関係しない別の原文。'), [])
        self.assertEqual(
            runner.similar_quote_candidates(NEAR_QUOTE, ORIGINAL_QUOTE + ' 別の発言。 ' + ORIGINAL_QUOTE), [])

    def test_unmatched_quote_and_model_rejection_drop_only_their_portraits(self):
        inputs = dict(dialogues=[dict(dialogue='D1', partner='A1', visible_turns=[
            dict(turn_id=1, text=ORIGINAL_QUOTE),
            dict(turn_id=2, text=EXACT_QUOTE),
        ])])
        prediction = dict(portraits=[
            profile('R1', '原文には存在しない別の文章です。', 1),
            profile('R2', NEAR_QUOTE, 1),
            profile('R3', NEAR_QUOTE, 1),
            profile('R4', EXACT_QUOTE, 1),
        ], limitations='')
        client = Mock()
        client.call_portrait.side_effect = lambda method, request, validate, **kwargs: (validate(prediction), 'direct')

        def review(name, request, validate):
            packet = json.loads(request['messages'][1]['content'])
            pid = packet['portrait_id']
            if pid == 'R3':
                return validate(dict(portrait_id=pid, decision='reject', statement='', replacements=[])), name
            return validate(dict(portrait_id=pid, decision='repair', statement='証拠に沿った記述',
                                 replacements=[dict(index=0, quote=ORIGINAL_QUOTE)])), name

        client.send_current.side_effect = review
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            runner.generate_direct(folder, inputs, client)
            final = runner.load(folder/'direct_portraits.json')['portraits']
            self.assertEqual([p['portrait_id'] for p in final], ['R2', 'R4'])
            self.assertEqual(final[0]['evidence'][0]['quote'], ORIGINAL_QUOTE)
            self.assertEqual(final[1]['evidence'][0]['turn_id'], 2)
            self.assertEqual(client.send_current.call_count, 2)
