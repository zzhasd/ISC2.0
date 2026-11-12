"""Regressions for the human reference scope, cache reuse and four metrics."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from . import evaluation
from .common import BASE,read,save,digest
from .statistics import four_metrics


class HumanReferenceAdapterTests(unittest.TestCase):
    def test_default_reference_and_missing_file_do_not_fall_back(self):
        self.assertEqual(evaluation.reference_path('dailydialog').name,'dailydialog_human_adjudicated_588.json')
        with self.assertRaises(ValueError):evaluation.reference_path('personachat')
        with tempfile.TemporaryDirectory() as folder,patch.object(evaluation,'BASE',Path(folder)):
            save(Path(folder)/'references/dailydialog.json',[])
            with self.assertRaises(FileNotFoundError):evaluation.reference_map('dailydialog')

    def test_explicit_historical_reference_remains_available_for_reproduction(self):
        original=evaluation.reference_map('dailydialog',reference_file='dailydialog.json')
        self.assertEqual(len(original),300)
        self.assertNotIn(('train_7096','B_to_A'),original)

    def test_invalid_human_direction_or_unresolved_label_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(evaluation,'BASE',Path(folder)):
            path=evaluation.reference_path('dailydialog')
            row={'dialogue_id':'d','direction':'B_to_A','claims':[]}
            save(path,[row])
            with self.assertRaises(ValueError):evaluation.reference_map('dailydialog')
            row['direction']='A_to_B'
            row['claims']=[{'claim_id':'r','truth':'true','evidence_level':'E1_E2_disputed'}]
            save(path,[row])
            with self.assertRaises(ValueError):evaluation.reference_map('dailydialog')

    def test_subset_cache_is_projected_without_mutating_original(self):
        pp=[{'prediction_id':'p1','claim':'has dog'},{'prediction_id':'p2','claim':'has cat'}]
        legacy=[{'claim_id':'r1','claim':'has dog'},{'claim_id':'r2','claim':'has cat'}]
        saved={'binding':digest(evaluation.matching_content(pp,legacy,'A_to_B')),
               'matches':[{'prediction_id':'p1','reference_ids':['r1'],'relation':'equivalent'},
                          {'prediction_id':'p2','reference_ids':['r2'],'relation':'equivalent'}]}
        original=copy.deepcopy(saved)
        out=evaluation._cached_matches(saved,pp,legacy[:1],'A_to_B',legacy)
        self.assertEqual(out[0]['reference_ids'],['r1'])
        self.assertEqual(out[1],{'prediction_id':'p2','reference_ids':[],'relation':'none'})
        self.assertEqual(saved,original)
        changed=[{'claim_id':'r1','claim':'does not have dog'}]
        self.assertIsNone(evaluation._cached_matches(saved,pp,changed,'A_to_B',legacy))
        added=legacy+[{'claim_id':'r3','claim':'has bird'}]
        self.assertIsNone(evaluation._cached_matches(saved,pp,added,'A_to_B',legacy))
        changed_predictions=[dict(pp[0],claim='different prediction'),pp[1]]
        self.assertIsNone(evaluation._cached_matches(saved,changed_predictions,legacy[:1],'A_to_B',legacy))
        with self.assertRaises(ValueError):evaluation._cached_matches(saved,pp,legacy[:1],'B_to_A',legacy)

    def test_factual_precision_and_recall_do_not_require_visible_support(self):
        refs=[{'claim_id':'r1','truth':'true','evidence_level':'E1'},
              {'claim_id':'r2','truth':'true','evidence_level':'E4','support_consensus':True},
              {'claim_id':'r3','truth':'true','evidence_level':'E2'}]
        claims=['has a dog','owns a dog','has a cat','unknown attribute']
        p={'dialogue_id':'d','direction':'A_to_B','dataset':'dailydialog','method':'direct_thinking',
           'claims':[{'claim':c,'confidence':.9} for c in claims],'task_ids':[]}
        ms=[{'prediction_id':digest(c),'reference_ids':ids,'relation':'equivalent' if ids else 'none'}
            for c,ids in zip(claims,[['r1'],['r1'],['r2'],[]])]
        row=evaluation.score_item(p,refs,ms,{})
        result=four_metrics([row])
        self.assertEqual(result['precision'],3/4)
        self.assertEqual(result['recall'],2/3)
        self.assertEqual(result['grounded_recall'],1/2)
        self.assertEqual(result['correct_output_assertions'],3)
        self.assertEqual(result['recovered_reference_attributes'],2)

    def test_failed_abstention_retains_reference_denominator_and_actual_cost(self):
        p={'dialogue_id':'d','direction':'A_to_B','dataset':'dailydialog','method':'direct_thinking',
           'claims':[],'task_ids':['t'],'outcome':'failed_abstention'}
        refs=[{'claim_id':'r','truth':'true','evidence_level':'E2'}]
        row=evaluation.score_item(p,refs,[],{'t':{'tokens':30,'missing_usage':0}})
        result=four_metrics([row])
        self.assertIsNone(result['precision'])
        self.assertEqual(result['recall'],0)
        self.assertEqual(result['grounded_recall'],0)
        self.assertEqual(result['mean_tokens'],30)

    def test_saved_reference_and_predictions_reproduce_the_published_counts(self):
        refs=evaluation.reference_map('dailydialog');ps=evaluation.predictions('dailydialog')
        matches=evaluation.current_matches('dailydialog',ps,refs)
        self.assertEqual(len(refs),298)
        self.assertEqual(set(matches),set(refs))
        self.assertEqual(sum(len(rr) for rr in refs.values()),588)
        self.assertEqual(sum(r['evidence_level'] in ['E1','E2'] for rr in refs.values() for r in rr),262)
        expected=read(BASE/'audit/experiment_baseline.json')['methods']
        for published in expected:
            rows=[evaluation.score_item(p,refs[k],matches[k],{}) for p in ps
                  if (k:=(p['dialogue_id'],p['direction'])) in refs and p['method']==published['method']]
            result=four_metrics(rows)
            for key in ['single_sided_inputs','output_assertions','correct_output_assertions',
                        'recovered_reference_attributes','true_reference_attributes',
                        'recovered_grounded_reference_attributes','grounded_reference_attributes',
                        'precision','recall','grounded_recall']:
                self.assertEqual(result[key],published[key],(published['method'],key))

    def test_matching_all_cached_inputs_needs_no_key_or_new_api_calls(self):
        with patch.object(evaluation,'Client',side_effect=AssertionError('Unexpected API client')),patch.object(evaluation,'save'):
            result=evaluation.match_dataset('dailydialog',workers=2)
        self.assertEqual(result,{'cached':298})


if __name__=='__main__':unittest.main()
