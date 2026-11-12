"""Offline contract, accounting and full-scope tests; no model accuracy claims."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import COVER as alg
from . import run_COVER as run
from .evaluation import score_item
from .statistics import four_metrics

TURNS=[{'turn_id':1,'text':'Your two cats are asleep .'}, {'turn_id':3,'text':'You will leave tomorrow .'}]
ITEM=dict(item_id='dailydialog/test_1/A_to_B',dialogue_id='test_1',direction='A_to_B',dataset='dailydialog',visible_turns=TURNS)
def claim(text='B owns two cats.',turn=1,quote='Your two cats'):
    return dict(claim=text,attribute='ownership',mechanism='presupposition',evidence=[dict(turn_id=turn,quote=quote)])
def verdict(cid='c1',verdict='keep',replacement=None):
    return dict(id=cid,verdict=verdict,level='E2',checks={k:True for k in alg.CHECKS},
                evidence=[dict(turn_id=1,quote='Your two cats')],basis='Definite possessive',alternative='',replacement=replacement)
def body(obj,tokens=10,finish='stop'):
    b={'choices':[{'finish_reason':finish,'message':{'content':json.dumps(obj)}}]}
    if tokens is not None:b['usage']={'total_tokens':tokens}
    return b

class AlgorithmTests(unittest.TestCase):
    def test_input_blocks_hidden_data(self):
        alg.validate_input(ITEM)
        for item in [dict(ITEM,reference=[]),dict(ITEM,visible_turns=[dict(turn_id=2,text='B')])]:
            with self.assertRaises(ValueError):alg.validate_input(item)
    def test_whitespace_alignment_keeps_original(self):
        ev,ok,fix,bad=alg.align_evidence([dict(turn_id=1,quote='cats are asleep.')],TURNS)
        self.assertTrue(ok);self.assertEqual(ev[0]['quote'],'cats are asleep .');self.assertTrue(fix)
    def test_invalid_premise_is_not_silently_dropped(self):
        ev,ok,_,bad=alg.align_evidence([dict(turn_id=1,quote='Your two cats'),dict(turn_id=3,quote='yesterday')],TURNS)
        self.assertFalse(ok);self.assertEqual(len(ev),1);self.assertEqual(len(bad),1)
    def test_no_word_boundary_collapse(self):
        self.assertFalse(alg.align_evidence([dict(turn_id=1,quote='now here')],[dict(turn_id=1,text='nowhere')])[1])
    def test_no_ambiguous_repair(self):
        self.assertFalse(alg.align_evidence([dict(turn_id=1,quote='cat.')],[dict(turn_id=1,text='cat . cat .')])[1])
    def test_distinct_symbols_preserved(self):
        self.assertNotEqual(alg.key('B knows C++'),alg.key('B knows C#'))
        self.assertNotEqual(alg.key('B has 1.5 dollars'),alg.key('B has 15 dollars'))
    def test_coverage_not_optional(self):
        with self.assertRaises(ValueError):alg.generation({'claims':[]},TURNS,[1,3])
    def test_nonempty_attribute(self):
        with self.assertRaises(ValueError):alg.claim_object(dict(claim(),attribute=''),TURNS)
    def test_inconsistent_keep_not_accepted(self):
        c=dict(alg.claim_object(claim(),TURNS),candidate_id='c1')
        for mutation in [dict(level='E3'),dict(alternative='B may merely be looking after cats'),
                         dict(checks={k:k!='subject' for k in alg.CHECKS}),dict(evidence=[])]:
            d=dict(verdict(),**mutation)
            self.assertFalse(alg.decisions({'decisions':[d]},[c],TURNS)[0]['accepted'])
    def test_duplicate_review_ids_rejected(self):
        candidates=[dict(alg.claim_object(claim(),TURNS),candidate_id='c'+str(i)) for i in (1,2)]
        with self.assertRaises(ValueError):alg.decisions({'decisions':[verdict(),verdict()]},candidates,TURNS)
    def test_pipeline_repair_and_post_verification_gap(self):
        stages=[]
        class Fake:
            def call(self,name,payload,validate):
                stages.append(name);data=json.loads(payload['messages'][1]['content'])
                assert 'reference' not in data and 'full_turns' not in data
                prompt=payload['messages'][0]['content']
                if prompt==alg.EXTRACT:
                    obj={'claims':[claim('B has cats.')],'coverage':[dict(turn_id=t,status='facts',reason='checked clauses') for t in data['focus_turn_ids']]}
                elif prompt==alg.IMPLICIT:obj={'claims':[]}
                elif prompt==alg.COMPLETE:
                    obj={'claims':[claim('B will leave tomorrow.',3,'You will leave tomorrow')],
                         'coverage':[dict(turn_id=t,status='facts',reason='checked all predicates') for t in data['focus_turn_ids']]}
                else:
                    ds=[]
                    for c in data['candidates']:
                        d=verdict(c['candidate_id'])
                        if c['claim']=='B has cats.':d=verdict(c['candidate_id'],'repair',claim())
                        else:d['evidence']=c['evidence']
                        ds.append(d)
                    obj={'decisions':ds}
                return validate(obj),str(len(stages))
        p,trace=alg.pipeline(Fake(),ITEM)
        self.assertEqual({c['claim'] for c in p['claims']},{'B owns two cats.','B will leave tomorrow.'})
        self.assertTrue(any('repair_check' in s for s in stages));self.assertTrue(any('coverage_review' in s for s in stages))
        self.assertEqual(len(p['task_ids']),len(stages))

class RunnerTests(unittest.TestCase):
    def test_first_complete_json_and_truncation(self):
        b=body({'claims':[]});b['choices'][0]['message']['content']='Answer:\n```json\n{"claims":[]}\n```'
        self.assertEqual(run.decode(b),{'claims':[]})
        with self.assertRaises(ValueError):run.decode(body({},finish='length'))
    def test_maximum_matching_augmenting_path(self):
        self.assertEqual(len(run.maximum_matching({'a':{'r1','r2'},'b':{'r1'}})),2)
    def test_metrics_equal_project_strict_lenient(self):
        refs=[dict(claim_id='r1',claim='B owns two cats.',truth='true',evidence_level='E1'),
              dict(claim_id='r2',claim='B leaves tomorrow.',truth='true',evidence_level='E2')]
        cs=[dict(claim(),confidence=1),dict(claim(),confidence=1),dict(claim('B leaves.'),confidence=1)]
        p=dict(ITEM,method=alg.METHOD,claims=cs,task_ids=[])
        ms=[dict(prediction_id=run.digest(cs[0]['claim']),reference_ids=['r1'],relation='equivalent'),
            dict(prediction_id=run.digest(cs[2]['claim']),reference_ids=['r2'],relation='broader')]
        for accepted in [('equivalent',),('equivalent','broader')]:
            row,_=run.score(p,refs,ms,accepted);metrics=run.summarize([row])
            existing=four_metrics([score_item(p,refs,ms,{},accepted_relations=accepted)])
            for k in ('precision','recall','grounded_recall'):self.assertEqual(metrics[k],existing[k])
        self.assertEqual(row['correct'],3);self.assertEqual(row['hits'],2)
    def test_empty_denominators(self):
        p=dict(ITEM,method=alg.METHOD,claims=[],task_ids=[])
        row,_=run.score(p,[],[],('equivalent',));m=run.summarize([row])
        self.assertIsNone(m['precision']);self.assertIsNone(m['recall'])
    def test_matcher_missing_duplicate_invented(self):
        pp=[dict(prediction_id='p',claim='x')];rr=[dict(claim_id='r',claim='x')]
        for ms in [[],[dict(prediction_id='p',reference_ids=['bad'],relation='equivalent')]]:
            with self.assertRaises(ValueError):run.validate_matches({'matches':ms},pp,rr)
    def test_retry_accounting_cache_and_key_redaction(self):
        with tempfile.TemporaryDirectory(dir=run.HERE) as d:
            calls=[]
            class Response:
                status=200
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def read(self):
                    calls.append(1)
                    return json.dumps(body({'wrong':'TEST_SECRET'} if len(calls)==1 else {'ok':True},7 if len(calls)==1 else 13)).encode()
            class Opener:
                def open(self,*args,**kwargs):return Response()
            def valid(x):
                if x!={'ok':True}:raise ValueError('bad schema TEST_SECRET')
                return x
            api=run.APIClient('TEST_SECRET',Path(d))
            with patch.object(run.urllib.request,'build_opener',return_value=Opener()),patch.object(run.time,'sleep'):
                result,tid=api.call('x',{'model':'fake'},valid)
                api.call('x',{'model':'fake'},valid)
            self.assertEqual(len(calls),2);self.assertEqual(run.cost_ledger(Path(d))['known_tokens'],20)
            self.assertNotIn('TEST_SECRET',(Path(d)/'calls'/(tid+'.json')).read_text())
    def test_interruption_guard_and_missing_usage(self):
        with tempfile.TemporaryDirectory(dir=run.HERE) as d:
            root=Path(d);payload={};tid=run.digest({'name':'x','endpoint':run.URL,'payload':payload})
            run.save(root/'calls'/(tid+'.json'),dict(task_id=tid,attempts=[dict(status='started')]))
            with self.assertRaisesRegex(RuntimeError,'Interrupted'):run.APIClient(None,root).call('x',payload,lambda x:x)
            self.assertEqual(run.cost_ledger(root)['missing_usage_attempts'],1)
            self.assertIsNone(run.summarize([],run.cost_ledger(root))['mean_tokens'])
    def test_frozen_configuration(self):
        with tempfile.TemporaryDirectory(dir=run.HERE) as d:
            p=Path(d)/'manifest.json';run.freeze(p,{'a':1});run.freeze(p,{'a':1})
            with self.assertRaises(ValueError):run.freeze(p,{'a':2})
    def test_full_298_588_evaluation_and_offline_replay(self):
        # Synthetic predictions matching reference text test arithmetic only;
        # temporary artifacts are destroyed and are NOT experiment results.
        records=run.read_inputs();refs=run.read_refs();pred=[]
        for item in records:
            cs=[dict(claim=r['claim'],confidence=1) for r in refs[item['dialogue_id']]]
            pred.append(dict(item,method=alg.METHOD,claims=cs,task_ids=[]))
        class Fake:
            endpoint='https://offline.invalid';calls=0
            def call(self,name,payload,validate):
                self.calls+=1;data=json.loads(payload['messages'][1]['content'])
                ms=[dict(prediction_id=p['prediction_id'],reference_ids=[r['claim_id'] for r in data['reference'] if r['claim']==p['claim']],relation='equivalent') for p in data['predictions']]
                return validate({'matches':ms}),name
        with tempfile.TemporaryDirectory(dir=run.HERE) as d,contextlib.redirect_stdout(io.StringIO()):
            root=Path(d);api=Fake()
            result=run.evaluate(records,pred,root,api,12,'v2',False)
            m=result['policies']['strict'][alg.METHOD]
            self.assertEqual(m['references'],588);self.assertEqual(m['grounded_references'],262)
            self.assertEqual(m['single_sided_inputs'],298)
            self.assertEqual(m['recall'],1);self.assertEqual(m['grounded_recall'],1)
            calls=api.calls;again=run.evaluate(records,pred,root,api,12,'v2',False)
            self.assertEqual(again,result);self.assertEqual(api.calls,calls)
    def test_historical_scores_match_all_methods(self):
        # Check numerical parity on ALL saved dialogues for both policies.
        from .analyze_COVER import SOURCES
        refs=run.read_refs()
        for folder,matchfolder in SOURCES:
            ps=run.read(run.HERE/'runs'/folder/'exports/dailydialog.json');cache={}
            for p in ps:
                did=p['dialogue_id'];path=run.HERE/matchfolder/(did+'__A_to_B.json')
                if not path.exists():continue
                if did not in cache:cache[did]=run.read(path)['matches']
                for accepted in [('equivalent',),('equivalent','broader')]:
                    row,_=run.score(p,refs[did],cache[did],accepted)
                    old=score_item(p,refs[did],cache[did],{},accepted_relations=accepted)
                    self.assertEqual((row['correct'],row['hits'],row['grounded_hits'],row['e1_hits'],row['e2_hits']),
                                     (old['correct_output_assertions'],old['true_tp'],old['supported_tp'],old['e1_hits'],old['e2_hits']))

if __name__=='__main__':unittest.main()
