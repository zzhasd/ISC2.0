"""Data-flow checks for the four-subject filtered experiment runner."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import filtered_portrait_repeat as runner
from .core import digest, load, save


class FilteredRepeatTests(unittest.TestCase):
    def test_summary_count_tracks_filtered_unique_inputs(self):
        inputs = dict(dialogues=[dict(partner='A1'), dict(partner='A4')])
        prompt = runner.summary_prompt(inputs, [dict(unique_id='U001')])
        self.assertIn('inventory of 1 candidate', prompt)
        self.assertNotIn('209', prompt)
        self.assertIn('A1/A4', prompt)

    def test_pipeline_filters_original_records_before_dedup_and_keeps_direct_independent(self):
        inputs = dict(dialogues=[dict(dialogue='D1', partner='A1', visible_turns=[
            dict(turn_id=1, text='私は教師です。'), dict(turn_id=2, text='教師なんですね。')])])
        calls = []
        class FakeClient:
            def __init__(self, *args): pass
            def call(self, name, payload, validate):
                calls.append((name, copy.deepcopy(payload)))
                data = json.loads(payload['messages'][1]['content'])
                if name.endswith('/direct'):
                    self_test.assertEqual(set(data), {'dialogues'})
                    obj = dict(portraits=[dict(portrait_id='R1', statement='教师',
                        evidence=[dict(dialogue='D1', turn_id=2, quote='教師なんですね。')])], limitations='test')
                elif '/filter/' in name:
                    self_test.assertEqual(len(data['candidates']), 2)
                    obj = dict(decisions=[dict(source_id=f'D1/c{i}', actual_owner=owner,
                        decision=decision, reason_code=reason, self_quote=q, reason='test')
                        for i, owner, decision, reason, q in [(1,'A','DROP','A_SELF','私は教師です。'),
                                                              (2,'B','KEEP','B_REFERENT','')]])
                else:
                    self_test.assertEqual(len(data['unique_attributes']), 1)
                    self_test.assertEqual([m['source_id'] for m in data['unique_attributes'][0]['members']], ['D1/c2'])
                    obj = dict(portraits=[dict(portrait_id='R1', statement='教师', unique_ids=['U001'])], limitations='test')
                return validate(obj), name
        self_test = self
        claims = [dict(candidate_id=f'c{i}', claim='B is a teacher.', attribute='teacher',
                       certainty='asserted', evidence=[dict(turn_id=i, quote=t['text'])])
                  for i, t in enumerate(inputs['dialogues'][0]['visible_turns'], 1)]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save(root/'IA/inputs.json', inputs)
            save(root/'IA/design.json', dict(code_sha256={}, inputs_digest=digest(inputs)))
            with patch.object(runner, 'SOURCES', {'IA':'unused'}), patch.object(runner, 'Client', FakeClient), \
                 patch.object(runner, 'hashes', return_value={}), \
                 patch.object(runner.algorithm, 'pipeline', return_value=(dict(claims=claims), {})):
                runner.run(root, 2)
            self.assertEqual(load(root/'IA/subject_filter_report.json')['dropped_claims'], 1)
            self.assertEqual(load(root/'IA/attributes_all.json')[0]['claim'], claims[0])
            self.assertEqual(load(root/'IA/attributes_filtered.json')[0]['claim'], claims[1])
            self.assertEqual(sum('/filter/' in name for name, _ in calls), 1)
            self.assertEqual(len(calls), 3)
            for _, payload in calls:
                self.assertNotIn('archive', json.loads(payload['messages'][1]['content']))


if __name__ == '__main__': unittest.main()
