"""Scientific invariants tested without credentials or network access."""
import copy
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path
import analyze
from prepare_evaluation import agd,read,HERE
from run_inference import safe_item,PredictorClient
import prepare_evaluation

class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.p={'prefix_id':'test__k01','dialogue_id':'test','prefix_k':1,'split':'test',
                'direction':'A_to_B','visible_turns':[{'turn_id':1,'text':'Your dog is cute.'}]}
        self.private={'candidates':[{'id':'c1','claim':'B owns a dog and a cat.'},
                                    {'id':'c2','claim':'B owns a cute dog.'}],
                      'predictions':[{'id':'direct:0','algorithm':'direct_thinking',
                                      'claim':'B owns a dog and a cat.','candidate_id':'c1'}],
                      'sweep_candidate_ids':['c2']}
        self.support={'items':[{'id':'c1','atoms':[
                     {'text':'B owns a dog.','label':'E2','turn_ids':[1]},
                     {'text':'B owns a cat.','label':'E4','turn_ids':[]}]},
                     {'id':'c2','atoms':[{'text':'B owns a cute dog.','label':'E2','turn_ids':[1]}]}]}
        self.atom={'atom_id':'c1::0','claim':'B owns a dog.','turn_ids':[1],'level':'E2'}
        self.pool={'facts':[{'id':'f1','canonical_claim':'B owns a cute dog.','level':'E2',
                  'slots':[{'id':'s1','name':'relation','value':'owns dog','core':True,'required':True,'weight':2},
                           {'id':'s2','name':'quality','value':'cute','core':False,'required':True,'weight':1}],
                  'members':[{'atom_id':'c1::0','slot_ids':['s1']},
                             {'atom_id':'c2::0','slot_ids':['s1','s2']}]}]}
        self.mapping={('test__k01','f1'):'test::u001'}

    def run_score(self,pool=None,support=None,mapping=None):
        pool=self.pool if pool is None else pool;support=self.support if support is None else support
        def fake_read(path):
            if 'packets' in Path(path).parts:return {'atoms':[self.atom,dict(self.atom,atom_id='c2::0',claim='B owns a cute dog.')] if pool['facts'] else []}
            a='direct_thinking' if 'direct_thinking' in Path(path).parts else 'elara_v1'
            return {'claims':[{'claim':'B owns a dog and a cat.'}] if a=='direct_thinking' else [],
                    'usage':{'total_tokens':10},'api_attempt_count':1,'format_failure_count':0,'truncated_attempt_count':0}
        with patch.object(analyze,'read',fake_read):
            return analyze.score_prefix(self.p,self.private,pool,support,self.mapping if mapping is None else mapping)

    def test_frozen_dataset_all_prefix_boundaries(self):
        rows=read(HERE/'data/prefix_inputs.json');self.assertEqual(len(rows),341)
        self.assertEqual(len({r['dialogue_id'] for r in rows}),31)
        for r in rows:
            item=safe_item(r)
            self.assertEqual([t['turn_id'] for t in item['visible_turns']],list(range(1,2*r['prefix_k'],2)))
            self.assertEqual(set(item),{'dialogue_id','item_id','direction','dataset','visible_turns'})

    def test_mixed_raw_claim_preserves_supported_core_without_full_credit(self):
        rows,_,_=self.run_score();direct=rows[0]
        self.assertEqual(direct['valid_raw_count'],0)
        self.assertEqual(direct['unique_core_count'],1)
        self.assertEqual(direct['full_count'],0)
        self.assertAlmostEqual(direct['slot_coverage'],2/3)
        self.assertEqual(rows[1]['unique_core_count'],0)

    def test_future_evidence_rejected(self):
        bad=copy.deepcopy(self.support);bad['items'][0]['atoms'][0]['turn_ids']=[3]
        with self.assertRaises(ValueError):self.run_score(support=bad)

    def test_empty_pool_recall_is_missing(self):
        bad=copy.deepcopy(self.support);bad['items'][0]['atoms'][0]['label']='E3'
        bad['items'][1]['atoms'][0]['label']='E3'
        rows,_,_=self.run_score(pool={'facts':[]},support=bad)
        self.assertIsNone(rows[0]['r_core']);self.assertIsNone(rows[0]['slot_coverage'])
        self.assertEqual(rows[0]['raw_count'],1)

    def test_unassigned_supported_atom_rejected(self):
        bad=copy.deepcopy(self.pool);bad['facts'][0]['members']=[]
        with self.assertRaises(ValueError):self.run_score(pool=bad)

    def test_predictor_no_implicit_fallback(self):
        class Fake:
            def call(self,*args):raise AssertionError('Must reject before network')
        client=PredictorClient(Fake(),'qwen-max')
        with self.assertRaises(ValueError):client.call('test',{},lambda o:o)

    def test_disappearance_and_reappearance_are_not_first_discoveries(self):
        # The protocol's central distinction: a reappearing fact is already known.
        observations=[{'u1'},{'u1','u2'},{'u2'},{'u1','u2'},{'u3'}]
        previous=set();ever=set();states=[]
        for i,current in enumerate(observations):
            state=analyze.discovery_transition(previous,ever,current,i==0)
            states.append(state);previous=current;ever=state['ever']
        self.assertEqual([len(s['new']) for s in states],[1,1,0,0,1])
        self.assertEqual([len(s['ever']) for s in states],[1,2,2,2,3])
        self.assertEqual([len(s['reappeared']) for s in states],[0,0,0,1,0])
        self.assertEqual([s['net_change'] for s in states],[None,1,-1,1,-1])
        self.assertEqual(states[3]['reappeared'],{'u1'})

    def make_revision_fixture(self,root,stale_receipt=False):
        pid=self.p['prefix_id'];name=pid+'.json'
        packet={'prefix_id':pid,'visible_turns':self.p['visible_turns'],'batches':[self.private['candidates']]}
        support=copy.deepcopy(self.support)
        support['_meta']={'model':'gpt-6.1-sol','reasoning_effort':'high',
                          'input_sha256':agd.stable_hash(packet),'reviewed_batch_sizes':[2]}
        agd.dump(root/'data/prefix_inputs.json',[self.p])
        agd.dump(root/'agd_eval/packets/support'/name,packet)
        agd.dump(root/'agd_eval/judgments/support'/name,support)
        agd.dump(root/'agd_eval/batch_reviews/support'/pid/'000.json',
                 {'reviewed_items_sha256':'old' if stale_receipt else agd.stable_hash(support['items'])})
        old={'prefix_id':pid,'visible_turns':self.p['visible_turns'],'atoms':[self.atom]}
        agd.dump(root/'agd_eval/packets/pool'/name,old)
        agd.dump(root/'agd_eval/judgments/pool'/name,self.pool)
        agd.dump(root/'agd_eval/judgments/pool/other__k01.json',{'facts':[]})
        agd.dump(root/'agd_eval/judgments/sweep'/name,{'claims':[]})
        agd.dump(root/'alignment/packets/test.json',{'old_alignment_packet':True})
        agd.dump(root/'alignment/judgments/test.json',{'old_alignment_judgment':True})
        return old

    def test_refresh_archives_and_invalidates_only_affected_dependencies(self):
        with tempfile.TemporaryDirectory(prefix='isc21_refresh_') as temp:
            root=Path(temp);old=self.make_revision_fixture(root)
            original=(root/'agd_eval/packets/pool/test__k01.json').read_bytes()
            with patch.object(prepare_evaluation,'HERE',root):
                prepare_evaluation.refresh_pool('test__k01','Explicitly reviewed compound atom correction')
            self.assertFalse((root/'agd_eval/judgments/pool/test__k01.json').exists())
            self.assertFalse((root/'alignment/judgments/test.json').exists())
            self.assertFalse((root/'alignment/packets/test.json').exists())
            self.assertTrue((root/'agd_eval/judgments/pool/other__k01.json').exists())
            self.assertTrue((root/'agd_eval/judgments/sweep/test__k01.json').exists())
            archive=next((root/'agd_eval/revisions/pool_refresh/test__k01').iterdir())
            self.assertEqual((archive/'pool_packet.json').read_bytes(),original)
            self.assertEqual(len(read(root/'agd_eval/packets/pool/test__k01.json')['atoms']),2)
            self.assertTrue((root/'results/evaluation_revision_required.json').exists())

    def test_refresh_refuses_stale_batch_review_without_mutating_packet(self):
        with tempfile.TemporaryDirectory(prefix='isc21_refresh_') as temp:
            root=Path(temp);old=self.make_revision_fixture(root,True)
            with patch.object(prepare_evaluation,'HERE',root):
                with self.assertRaises(AssertionError):prepare_evaluation.refresh_pool('test__k01','Correction not yet reviewed')
            self.assertEqual(read(root/'agd_eval/packets/pool/test__k01.json'),old)
            self.assertTrue((root/'agd_eval/judgments/pool/test__k01.json').exists())

    def test_pool_only_revision_archives_judgment_without_changing_input(self):
        with tempfile.TemporaryDirectory(prefix='isc21_refresh_') as temp:
            root=Path(temp);self.make_revision_fixture(root)
            packet={'prefix_id':self.p['prefix_id'],'visible_turns':self.p['visible_turns'],
                    'atoms':[self.atom,dict(self.atom,atom_id='c2::0',claim='B owns a cute dog.')]}
            agd.dump(root/'agd_eval/packets/pool/test__k01.json',packet)
            original=(root/'agd_eval/judgments/pool/test__k01.json').read_bytes()
            with patch.object(prepare_evaluation,'HERE',root):
                prepare_evaluation.refresh_pool('test__k01','Explicitly re-reviewed member slot coverage',pool_only=True)
            self.assertEqual(read(root/'agd_eval/packets/pool/test__k01.json'),packet)
            self.assertFalse((root/'agd_eval/judgments/pool/test__k01.json').exists())
            archive=next((root/'agd_eval/revisions/pool_refresh/test__k01').iterdir())
            self.assertEqual((archive/'pool_judgment.json').read_bytes(),original)
            self.assertEqual(read(archive/'revision.json')['revision_kind'],'pool_semantic_review')
            self.assertTrue((root/'agd_eval/judgments/pool/other__k01.json').exists())

    def test_full_e1_fact_cannot_receive_an_e2_only_required_detail(self):
        pool=copy.deepcopy(self.pool);pool['facts'][0]['level']='E1'
        atoms=[dict(self.atom,level='E1'),dict(self.atom,atom_id='c2::0',claim='B owns a cute dog.')]
        findings=prepare_evaluation.pool_level_findings(pool,atoms)
        self.assertEqual(findings,[{'fact_id':'f1','required_slots_without_e1_member':['s2']}])
        pool['facts'][0]['level']='E2'
        self.assertEqual(prepare_evaluation.pool_level_findings(pool,atoms),[])
        pool['facts'][0]['level']='E1';atoms[1]['level']='E1'
        self.assertEqual(prepare_evaluation.pool_level_findings(pool,atoms),[])

if __name__=='__main__':unittest.main()
