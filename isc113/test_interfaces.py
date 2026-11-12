"""Transport contract tests and run isolation; no billable provider calls."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from . import client,evaluation,run as runner
from .common import read,save,jsonlines,BASE
from .inference import payload,validate_claims,pipeline
from .statistics import four_metrics

def response(content='{"claims":[]}',status=200,usage=12,finish='stop'):
    body={'choices':[{'finish_reason':finish,'message':{'content':content}}]}
    if usage is not None:body['usage']={'total_tokens':usage}
    return Mock(status_code=status,json=Mock(return_value=body))


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        for name in ['inference.py','prompts.py','client.py']:
            (self.root/name).write_bytes((BASE/name).read_bytes())
        self.patch=patch.object(client,'BASE',self.root);self.patch.start();self.addCleanup(self.patch.stop)
        self.request=payload('test',{'visible_turns':[{'turn_id':1,'text':'Hello'}]})
        self.validate=lambda x:validate_claims(x,[{'turn_id':1,'text':'Hello'}])

    def test_HTTP_contract_and_cached_response(self):
        c=client.Client('test-credential')
        with patch('requests.Session.post',return_value=response()) as post:
            claims,tid=c.call('dailydialog/x/A_to_B/direct',self.request,self.validate)
            self.assertEqual(claims,[])
            c.call('dailydialog/x/A_to_B/direct',self.request,self.validate)
        self.assertEqual(post.call_count,1)
        args=post.call_args
        self.assertEqual(args.args[0],client.URL)
        self.assertEqual(args.kwargs['json'],self.request)
        self.assertEqual(args.kwargs['timeout'],(15,180))
        self.assertFalse(args.kwargs['allow_redirects'])
        self.assertNotIn('test-credential',c.path.read_text(encoding='utf-8'))

    def test_invalid_completion_retry_and_all_attempt_usage_retained(self):
        c=client.Client('test-key',run_id='dailydialog')
        with patch('requests.Session.post',side_effect=[response('bad',usage=9),response(usage=12)]) as post,patch.object(client.time,'sleep'):
            _,tid=c.call('dailydialog/x/A_to_B/direct',self.request,self.validate)
        self.assertEqual(post.call_count,2)
        with patch.object(evaluation,'BASE',self.root):
            cost=evaluation.cost_map()[tid]
        self.assertEqual(cost,{'tokens':21,'attempts':2,'missing_usage':0})

    def test_three_attempt_limit_cannot_be_reset_by_resuming(self):
        c=client.Client('key')
        with patch('requests.Session.post',return_value=response('bad')) as post,patch.object(client.time,'sleep'):
            for _ in range(2):
                with self.assertRaises(RuntimeError):c.call('x',self.request,self.validate)
        self.assertEqual(post.call_count,3)

    def test_provider_rejection_is_not_retried(self):
        for status in [400,401,403,404]:
            c=client.Client('key',run_id='test'+str(status))
            with patch('requests.Session.post',return_value=response(status=status)) as post:
                with self.assertRaises(RuntimeError):c.call('x',self.request,self.validate)
            self.assertEqual(post.call_count,1)

    def test_interrupted_request_is_not_automatically_resubmitted(self):
        from .common import digest
        c=client.Client('key');tid=digest({'logical_name':'x','payload':self.request})
        c.append({'task_id':tid,'attempt_id':'a','event':'start'})
        with patch('requests.Session.post') as post:
            with self.assertRaisesRegex(RuntimeError,'in-flight'):c.call('x',self.request,self.validate)
        post.assert_not_called()

    def test_secret_redaction_in_provider_errors(self):
        c=client.Client('credential-to-redact')
        r=Mock(status_code=400,json=Mock(return_value={'error':'credential-to-redact'}))
        with patch('requests.Session.post',return_value=r):
            with self.assertRaises(RuntimeError):c.call('x',self.request,self.validate)
        self.assertNotIn('credential-to-redact',c.path.read_text(encoding='utf-8'))
        self.assertIn('[REDACTED]',c.path.read_text(encoding='utf-8'))

    def test_missing_usage_is_not_reported_as_zero_cost(self):
        c=client.Client('key',run_id='dailydialog')
        with patch('requests.Session.post',return_value=response(usage=None)):
            _,tid=c.call('x',self.request,self.validate)
        p={'dialogue_id':'d','direction':'A_to_B','dataset':'dailydialog','method':'direct_thinking',
           'claims':[],'task_ids':[tid]}
        with patch.object(evaluation,'BASE',self.root):costs=evaluation.cost_map()
        score=evaluation.score_item(p,[],[],costs)
        self.assertEqual(score['missing_usage_attempts'],1)
        self.assertIsNone(four_metrics([score])['mean_tokens'])

    def test_pipeline_rejects_reverse_before_client_call(self):
        item=copy.deepcopy(read(BASE/'inputs/dailydialog.json')[0]);item['direction']='B_to_A'
        c=Mock()
        with self.assertRaises(ValueError):pipeline(c,item)
        c.call.assert_not_called()

    def test_new_run_is_separate_and_resumable_without_key(self):
        item=read(BASE/'inputs/dailydialog.json')[0]
        with patch.object(runner,'BASE',self.root),patch.object(runner,'prepare_inputs',return_value=[item]),patch.object(runner,'pipeline',return_value=[]) as pipeline_mock,patch.object(runner,'Client') as ctor:
            result=runner.run(key='key',run_id='new')
            self.assertEqual(result['completed_files'],1)
            ctor.reset_mock()
            result=runner.run(run_id='new')
            self.assertEqual(result['cached'],1);ctor.assert_not_called()
            self.assertEqual(pipeline_mock.call_count,1)
            for name in ['dailydialog','main','../bad','evaluation_dailydialog']:
                with self.assertRaises(ValueError):runner.run(key='key',run_id=name)

    def test_frozen_run_rejects_changed_input(self):
        item=read(BASE/'inputs/dailydialog.json')[0]
        with patch.object(runner,'BASE',self.root),patch.object(runner,'prepare_inputs',return_value=[item]),patch.object(runner,'pipeline',return_value=[]),patch.object(runner,'Client'):
            runner.run(key='key',run_id='new')
            changed=copy.deepcopy(item);changed['visible_turns'][0]['text']='changed'
            with patch.object(runner,'prepare_inputs',return_value=[changed]):
                with self.assertRaisesRegex(ValueError,'Frozen artifact'):runner.run(key='key',run_id='new')

    def test_empty_matcher_input_needs_no_client(self):
        p={'dialogue_id':'d','direction':'A_to_B','claims':[]}
        with patch.object(evaluation,'BASE',self.root),patch.object(evaluation,'reference_map',return_value={('d','A_to_B'):[]}),patch.object(evaluation,'predictions',return_value=[p]),patch.object(evaluation,'Client',side_effect=AssertionError('Unexpected API')):
            self.assertEqual(evaluation.match_dataset('dailydialog',workers=1),{'complete':1})

    def test_semantic_matcher_rejects_fabricated_ids_and_missing_predictions(self):
        pp=[{'prediction_id':'p','claim':'dog'}];rr=[{'claim_id':'r','claim':'dog'}]
        for obj in [{'matches':[]},{'matches':[{'prediction_id':'p','reference_ids':['fake'],'relation':'equivalent'}]},
                    {'matches':[{'prediction_id':'p','reference_ids':['r'],'relation':'invalid'}]}]:
            with self.assertRaises(ValueError):evaluation.validate_matches(obj,pp,rr)

    def test_new_run_export_match_and_analysis_form_a_complete_isolated_flow(self):
        import json
        from . import common,export as exporter
        item=read(BASE/'inputs/dailydialog.json')[0]
        refs=evaluation.reference_map('dailydialog');ps=evaluation.predictions('dailydialog')
        key=(item['dialogue_id'],'A_to_B')
        ms=evaluation.current_matches('dailydialog',ps,refs)[key]
        source=[r for r in jsonlines(BASE/'runs/dailydialog/attempts.jsonl')
                if r['logical_name'].startswith(item['item_id']+'/')]
        folder=self.root/'runs/new'
        save(folder/'inputs.json',[item])
        (folder/'attempts.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in source),encoding='utf-8')
        save(self.root/'references/dailydialog_human_adjudicated_588.json',
             [r for r in read(BASE/'references/dailydialog_human_adjudicated_588.json') if r['dialogue_id']==key[0]])
        with patch.object(common,'BASE',self.root),patch.object(exporter,'BASE',self.root),patch.object(evaluation,'BASE',self.root):
            self.assertEqual(exporter.export(run_id='new')['outcomes'],6)
            with patch('requests.Session.post',return_value=response(json.dumps({'matches':ms}))) as post:
                result=evaluation.match_dataset('dailydialog',key='key',workers=1,run_id='new')
            self.assertEqual(result,{'complete':1});self.assertEqual(post.call_count,1)
            summary=evaluation.analyze('dailydialog',bootstrap=False,run_id='new')
            self.assertTrue(summary['complete_experiment'])
            self.assertEqual(len(summary['methods']),6)
            self.assertTrue((folder/'results/dailydialog_four_metrics.csv').exists())
            self.assertFalse((self.root/'runs/main').exists())
            self.assertFalse((self.root/'results').exists())


if __name__=='__main__':unittest.main()
