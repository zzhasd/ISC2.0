import json
import unittest
import tempfile
from pathlib import Path
import contextlib
import io
from .core import HERE, digest, elara_v1, load, metrics, sanitize, save
from .run import check_inputs, item_for
from .prompts import validate_partition
from .prompts import DIRECT
from .api import Client


class ProtocolTests(unittest.TestCase):
    def test_scorer_end_to_end_with_known_partitions(self):
        from .score import score
        with tempfile.TemporaryDirectory(dir=HERE/'data') as tmp:
            folder=Path(tmp)
            inputs=[{'group_id':'test'}]
            gold=[dict(group_id='test',setting='same_a',true_k=1,stratum='synthetic',
                       answers=[dict(dialogue=f'D{i}',b_id='same') for i in range(1,11)])]
            save(folder/'inputs.json',inputs)
            save(folder/'gold.json',gold)
            save(folder/'sampling.json',dict(input_digest=digest(inputs),gold_digest=digest(gold)))
            save(folder/'inference_manifest.json',dict(inputs_digest=digest(inputs)))
            for method,clusters in [('elara',[[f'D{i}' for i in range(1,11)]]),('direct',[[f'D{i}'] for i in range(1,11)])]:
                save(folder/'predictions'/f'test_{method}.json',dict(prediction=dict(clusters=clusters,merge_evidence=[],uncertainty='synthetic')))
            with contextlib.redirect_stdout(io.StringIO()):
                score(folder)
            result=load(folder/'results.json')
            self.assertTrue(result['complete_experiment'])
            self.assertEqual(result['summary']['same_a/elara']['absolute_count_error'],0)
            self.assertEqual(result['summary']['same_a/elara']['exact_partition'],1)
            self.assertEqual(result['summary']['same_a/direct']['absolute_count_error'],9)
            self.assertEqual(result['summary']['same_a/direct']['ari'],0)
            self.assertEqual(len(load(folder/'predictions_vs_gold.json')),2)

    def test_resumable_client_blocks_unresolved_and_unknown_billing(self):
        with tempfile.TemporaryDirectory(dir=HERE/'data') as tmp:
            client=Client('test-not-a-real-key',tmp)
            payload={'messages':[]}
            task=digest(dict(name='test',endpoint=client.endpoint,payload=payload))
            base=dict(task_id=task,attempt_id='a',logical_name='test')
            client.append(dict(base,event='start',request=payload))
            with self.assertRaisesRegex(RuntimeError,'Unresolved'):
                client.call('test',payload,lambda x:x)
            client.append(dict(base,event='complete',valid=False,billing_unknown=True))
            with self.assertRaisesRegex(RuntimeError,'uncertain billing'):
                client.call('test',payload,lambda x:x)

    def test_valid_response_cache_needs_no_network(self):
        with tempfile.TemporaryDirectory(dir=HERE/'data') as tmp:
            client=Client('test-not-a-real-key',tmp)
            payload={'messages':[]}
            task=digest(dict(name='test',endpoint=client.endpoint,payload=payload))
            client.append(dict(task_id=task,attempt_id='a',logical_name='test',event='complete',valid=True,
                               body={'choices':[dict(finish_reason='stop',message={'content':'{"answer":1}'})]}))
            self.assertEqual(client.call('test',payload,lambda x:x)[0],{'answer':1})

    def test_direct_prompt_has_no_extraction_scaffolding(self):
        for word in ('attribute','extract','persona','profile','inventory'):
            self.assertNotIn(word,DIRECT.lower())

    def test_complete_json_wrapper_recovery_never_repairs_truncation(self):
        body={'choices':[dict(finish_reason='stop',message={'content':'Brief prose\n```json\n{"ok":true}\n```'})]}
        def validate(x):
            if set(x)!={'ok'} or x['ok'] is not True:
                raise ValueError('wrong schema')
            return x
        self.assertEqual(Client.parse(body,validate),{'ok':True})
        for text in ('{"ok":true','{"ok":false}'):
            body['choices'][0]['message']['content']=text
            with self.assertRaises(ValueError):
                Client.parse(body,validate)
        body['choices'][0].update(finish_reason='length',message={'content':'{"ok":true}'})
        with self.assertRaises(ValueError):
            Client.parse(body,validate)

    def test_sampling_constraints_and_source_projection(self):
        from .prepare import read_corpus
        groups=load(HERE/'runs/pilot/inputs.json')
        gold=load(HERE/'runs/pilot/gold.json')
        corpus=read_corpus(HERE/'data/real-persona-chat.zip')
        by_source={r['dialogue_id']:r for r in corpus}
        speakers=sorted({s for r in corpus for s in r['interlocutors']})
        check_inputs(groups)
        used=set()
        for g,answer in zip(groups,gold):
            self.assertEqual(g['group_id'],answer['group_id'])
            self.assertEqual(len({a['b_id'] for a in answer['answers']}),answer['true_k'])
            a_ids={a['a_id'] for a in answer['answers']}
            b_ids={a['b_id'] for a in answer['answers']}
            self.assertEqual(len(a_ids),1 if g['setting']=='same_a' else 10)
            if g['setting']=='different_a':
                self.assertFalse(a_ids & b_ids)
            for visible,hidden in zip(g['dialogues'],answer['answers']):
                sid=hidden['source_dialogue_id']
                self.assertNotIn(sid,used)
                used.add(sid)
                original=[sanitize(u['text'],speakers) for u in by_source[sid]['utterances'] if u['interlocutor_id']==hidden['a_id']]
                self.assertEqual([t['text'] for t in visible['visible_turns']],original)
                self.assertEqual([t['turn_id'] for t in visible['visible_turns']],list(range(1,len(original)+1)))
                self.assertNotRegex(json.dumps(visible),r'<[A-Z]+>')
        self.assertEqual(len(used),200)

    def test_full_original_v1_pipeline_no_gold_or_ids_in_requests(self):
        algorithm=elara_v1()
        calls=[]
        class FakeClient:
            def call(self,name,payload,validate):
                data=json.loads(payload['messages'][1]['content'])
                calls.append((name,payload,data))
                self_outer.assertEqual(payload['model'],'qwen3.8-flash')
                self_outer.assertTrue(payload['enable_thinking'])
                self_outer.assertNotIn('b_id',json.dumps(payload))
                if '/audit_' in name:
                    obj={'decisions':[dict(candidate_id=c['candidate_id'],verdict='supported',reason='visible statement',evidence_level='E1',evidence=c['evidence']) for c in data['candidates']]}
                else:
                    claims=[] if name.endswith('gap_scan') else [dict(claim='B has a dog.',attribute='pet',certainty='asserted',mechanism='explicit',confidence=.9,evidence=[dict(turn_id=1,quote='Your dog is lovely.')])]
                    obj={'claims':claims}
                return validate(obj),'fake-task'
        self_outer=self
        item=dict(item_id='realpersonachat/test/A_to_B',dialogue_id='test',dataset='realpersonachat',direction='A_to_B',visible_turns=[dict(turn_id=1,text='Your dog is lovely.')])
        prediction,audit=algorithm.pipeline(FakeClient(),item)
        self.assertEqual(prediction['method'],'elara_evidence_lattice_v1')
        self.assertEqual(len(prediction['claims']),1)
        self.assertEqual(len(calls),4)
        self.assertTrue(any(name.endswith('explicit') for name,_,_ in calls))
        self.assertTrue(any(name.endswith('implicit') for name,_,_ in calls))
        self.assertTrue(any(name.endswith('gap_scan') for name,_,_ in calls))
        self.assertTrue(any('/audit_' in name for name,_,_ in calls))

    def test_metrics_permutation_and_extremes(self):
        for g in ([0]*10,list(range(10)),[0,0,1,1,1,2,2,3,3,3]):
            m=metrics(g,[str(x) for x in g])
            self.assertEqual(m['ari'],1)
            self.assertEqual(m['bcubed_f1'],1)
            self.assertEqual(m['exact_partition'],1)
        m=metrics([0]*10,list(range(10)))
        self.assertEqual(m['absolute_count_error'],9)
        self.assertEqual(m['pair_fn'],45)
        self.assertEqual(m['ari'],0)
        self.assertAlmostEqual(m['bcubed_f1'],2/11)
        self.assertIsNone(metrics(list(range(10)),list(range(10)))['pair_f1'])

    def test_reject_partition_and_fake_evidence(self):
        records=[dict(dialogue=f'D{i}',visible_turns=[dict(turn_id=1,text='hello')]) for i in range(1,11)]
        singleton=dict(clusters=[[f'D{i}'] for i in range(1,11)],predicted_k=10,merge_evidence=[],uncertainty='limited evidence')
        self.assertEqual(validate_partition(singleton,records,'direct')['predicted_k'],10)
        bad=dict(singleton,clusters=[['D1']]*10)
        with self.assertRaises(ValueError):
            validate_partition(bad,records,'direct')
        clusters=[['D1','D2']]+[[f'D{i}'] for i in range(3,11)]
        with self.assertRaises(ValueError):
            validate_partition(dict(singleton,clusters=clusters,predicted_k=9),records,'direct')
        refs=[dict(dialogue=f'D{i}',turn_id=1,quote='invented') for i in (1,2)]
        with self.assertRaises(ValueError):
            validate_partition(dict(singleton,clusters=clusters,predicted_k=9,merge_evidence=[dict(left='D1',right='D2',reason='test',references=refs)]),records,'direct')

    def test_private_adapter_does_not_patch_original_validator(self):
        from isc113.common import require_dataset
        elara_v1()
        with self.assertRaises(ValueError):
            require_dataset('realpersonachat')


if __name__=='__main__':
    unittest.main()
