import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from . import subject_one_portrait_tokenplan_v1 as runner


def portrait(pid, statement, *refs):
    return dict(portrait_id=pid, statement=statement, unique_ids=list(refs))


def attribute(uid, claim, verdict='supported'):
    return dict(unique_id=uid, claim=claim, members=[dict(claim=dict(audit_verdict=verdict))])


class SummaryClient:
    def __init__(self, folder, responses):
        self.folder = folder
        self.responses = responses
        self.calls = []

    def call_portrait(self, method, request, validate):
        self.calls.append(method)
        runner.save(self.folder / f'{method}_request.json', request)
        prediction = validate(self.responses[method])
        return prediction, method


class SummaryRepairTests(unittest.TestCase):
    inputs = dict(dialogues=[])

    def test_omissions_are_applied_before_duplicate_ownership_and_resume(self):
        unique = [
            attribute('U1', '有一只猫'), attribute('U2', '经常露营'),
            attribute('U3', '买了帐篷'), attribute('U4', '可能计划再次露营', 'uncertain'),
            attribute('U5', '周末做饭'),
        ]
        first = dict(portraits=[
            portrait('R1', '有一只猫，经常露营', 'U1', 'U1', 'U2'),
            portrait('R2', '有一只猫', 'U1'),
            portrait('R3', '买了帐篷', 'U3'),
            portrait('R4', '周末做饭', 'U5'),
        ], limitations='基于单侧对话')
        second = dict(portraits=[
            dict(portrait_id='R1', statement='有一只猫，经常露营，可能计划再次露营',
                 added_unique_ids=['U4']),
        ])
        bad_third = dict(owners={'U1': 'R3'}, portraits=[])
        third = dict(owners={'U1': 'R2'}, portraits=[
            dict(portrait_id='R1', statement='经常露营，可能计划再次露营'),
        ])
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            initial = SummaryClient(folder, dict(summary=first, summary_stage2=second, summary_stage3=bad_third))
            with self.assertRaisesRegex(ValueError, 'owner must be an existing candidate'):
                runner.generate_summary(folder, self.inputs, initial, unique)
            self.assertEqual(initial.calls, ['summary', 'summary_stage2', 'summary_stage3'])
            self.assertFalse((folder / 'summary_portraits.json').exists())

            request = runner.load(folder / 'summary_stage3_request.json')
            packet = json.loads(request['messages'][1]['content'])
            self.assertEqual(packet['duplicate_candidates'], {'U1': ['R1', 'R2']})
            self.assertEqual(packet['portraits'][0]['statement'], second['portraits'][0]['statement'])
            self.assertEqual(packet['portraits'][0]['unique_ids'], ['U1', 'U2', 'U4'])
            self.assertEqual([item['unique_id'] for item in packet['attributes']], ['U1', 'U2', 'U4'])
            self.assertEqual(packet['attributes'][-1]['audit_verdict'], 'uncertain')

            resumed = SummaryClient(folder, dict(summary_stage3=third))
            runner.generate_summary(folder, self.inputs, resumed, unique)
            self.assertEqual(resumed.calls, ['summary_stage3'])
            report = runner.verify_summary_stages(folder, self.inputs, unique)
            self.assertEqual(report['missing_unique_ids'], ['U4'])
            self.assertEqual(report['duplicate_unique_ids'], ['U1'])
            self.assertEqual(report['extra_duplicate_occurrences'], 2)
            self.assertEqual(report['duplicate_modified_portrait_ids'], ['R1'])
            self.assertEqual(report['normal_generation_stages'], 3)
            final = runner.load(folder / 'summary_raw.json')['prediction']
            self.assertEqual(final['portraits'], [
                portrait('R1', '经常露营，可能计划再次露营', 'U2', 'U4'), *first['portraits'][1:],
            ])
            materialized = runner.load(folder / 'summary_portraits.json')['portraits']
            self.assertEqual(materialized[0]['source_details'], [unique[1], unique[3]])

    def test_duplicate_only_portrait_is_removed_and_local_repeats_use_no_model(self):
        unique = [attribute('U1', '有猫'), attribute('U2', '喜欢露营')]
        for cross_portrait in (False, True):
            with self.subTest(cross_portrait=cross_portrait), TemporaryDirectory() as tmp:
                folder = Path(tmp)
                items = [portrait('R1', '有猫并喜欢露营', 'U1', 'U2', 'U2')]
                if cross_portrait:
                    items.append(portrait('R2', '有猫', 'U1'))
                first = dict(portraits=items, limitations='')
                third = dict(owners={'U1': 'R1'}, portraits=[])
                client = SummaryClient(folder, dict(summary=first, summary_stage3=third))
                runner.generate_summary(folder, self.inputs, client, unique)
                report = runner.verify_summary_stages(folder, self.inputs, unique)
                self.assertFalse(report['stage2_executed'])
                self.assertEqual(report['stage3_executed'], cross_portrait)
                self.assertEqual(report['duplicate_removed_portrait_ids'], ['R2'] if cross_portrait else [])
                self.assertEqual(client.calls, ['summary', 'summary_stage3'] if cross_portrait else ['summary'])
                final = runner.load(folder / 'summary_raw.json')['prediction']
                self.assertEqual(final['portraits'], [portrait('R1', '有猫并喜欢露营', 'U1', 'U2')])

    def test_first_stage_normalizes_numeric_ids_and_optional_limitations(self):
        unique = [attribute('U049', '有猫'), attribute('U050', '喜欢露营')]
        obj = dict(portraits=[portrait('R1', '有猫', 'U49', 'M049', 'M49', 'U101'),
                              portrait('R2', '无有效引用', 'U102')])
        accepted = runner.validate_stage1(obj, self.inputs, unique)
        self.assertEqual(accepted, dict(
            portraits=[portrait('R1', '有猫', 'U049', 'U049', 'U049')], limitations=''))
        coverage = runner.stage1_coverage(accepted, self.inputs, unique)
        self.assertEqual(coverage['missing_unique_ids'], ['U050'])
        self.assertEqual(coverage['extra_duplicate_occurrences'], 2)

    def test_summary_parser_repairs_known_field_syntax(self):
        content = r'''{"portraits":[{"portrait_id":"R1","statement":"B在"家中有冰淇淋"这点相似，称为\"甜点\"。","unique_ids":"U049", "M50"}],"limitations":"观察有限"]}'''
        body = dict(choices=[dict(finish_reason='stop', message=dict(content=content))])
        parsed = runner.parse_summary_response(body, lambda obj: obj)
        self.assertEqual(parsed['portraits'], [
            portrait('R1', 'B在"家中有冰淇淋"这点相似，称为"甜点"。', 'U049', 'M50')])
        self.assertEqual(parsed['limitations'], '观察有限')
        self.assertEqual(body['choices'][0]['message']['content'], content)
        for incomplete in ('{"portraits":[{"statement":"broken', content[:-1]):
            body['choices'][0]['message']['content'] = incomplete
            with self.assertRaises(json.JSONDecodeError):
                runner.parse_summary_response(body, lambda obj: obj)
        body['choices'][0]['finish_reason'] = 'length'
        body['choices'][0]['message']['content'] = content
        with self.assertRaisesRegex(ValueError, 'Incomplete response'):
            runner.parse_summary_response(body, lambda obj: obj)

    def test_only_previously_accepted_summary_responses_are_recovered(self):
        unique = [attribute('U1', '有猫')]
        prediction = dict(portraits=[portrait('R1', '有猫', 'U1', 'U1')], limitations='')
        payload = runner.portrait_payload(runner.portraits.compact_summary_request(unique), self.inputs)
        name = 'filtered_repeat/summary'

        def ledger_row(request, valid):
            return dict(
                event='complete', logical_name=name, http_status=200, valid=valid,
                attempt=1, elapsed_seconds=0.0,
                task_id=runner.digest(dict(name=name, endpoint=runner.ENDPOINT, payload=request)),
                body=dict(choices=[dict(finish_reason='stop', message=dict(content=json.dumps(prediction)))]),
            )

        for budget in (runner.PREVIOUS_PORTRAIT_MAX_TOKENS, runner.PORTRAIT_MAX_TOKENS):
            with self.subTest(budget=budget), TemporaryDirectory() as tmp:
                folder = Path(tmp)
                saved = dict(payload, max_tokens=budget)
                runner.save(folder / 'summary_request.json', saved)
                (folder / 'attempts.jsonl').write_text(
                    json.dumps(ledger_row(saved, False)) + '\n', encoding='utf-8')
                client = runner.DeferredClient('test-token', folder, runner.ENDPOINT)

                def validate(obj):
                    return runner.validate_stage1(obj, self.inputs, unique)

                with patch.object(client, 'send_current', return_value=(prediction, 'fresh')) as send:
                    self.assertEqual(client.call_portrait('summary', payload, validate), (prediction, 'fresh'))
                    send.assert_called_once_with(name, payload, validate)
                self.assertEqual(runner.load(folder / 'summary_request.json'), payload)

                accepted = ledger_row(payload, True)
                client.clients[client.epoch].append(accepted)
                with patch.object(client, 'send_current') as send:
                    recovered = client.call_portrait('summary', payload, validate)
                    self.assertEqual(recovered, (prediction, accepted['task_id']))
                    send.assert_not_called()

    def test_valid_v2_summary_checkpoint_resumes_in_place(self):
        unique = [attribute('U1', '有猫')]
        first = dict(portraits=[portrait('R1', '有猫', 'U1')], limitations='')
        legacy_coverage = dict(total_attributes=1, stage1_portrait_count=1, stage1_covered_count=1,
                               missing_count=0, missing_unique_ids=[], duplicate_count=0,
                               unknown_count=0, stage2_required=False)
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            payload = runner.portrait_payload(runner.portraits.compact_summary_request(unique), self.inputs)
            runner.save(folder / 'summary_request.json',
                        dict(payload, max_tokens=runner.PREVIOUS_PORTRAIT_MAX_TOKENS))
            runner.save(folder / 'summary_stage1_raw.json', dict(prediction=first, task_id='v2'))
            runner.save(folder / 'summary_stage1_coverage.json', legacy_coverage)
            client = SummaryClient(folder, {})
            runner.generate_summary(folder, self.inputs, client, unique)
            self.assertEqual(client.calls, [])
            self.assertEqual(runner.load(folder / 'summary_stage1_coverage.json'), legacy_coverage)
            self.assertEqual(runner.verify_summary_stages(folder, self.inputs, unique)['summary_version'],
                             runner.LEGACY_SUMMARY_VERSION)
