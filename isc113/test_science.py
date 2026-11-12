import copy
import unittest
from .common import BASE,read,visible,validate_input,digest
from .inference import validate_claims,validate_verdicts,accept
from .statistics import matching,metrics,four_metrics
from .evaluation import matching_content,score_item
from .annotation import rebuild_human_reference,validate_reviews,support_packets
from .export import reconstruct


class ScientificInvariants(unittest.TestCase):
    def test_only_A_turns_and_reverse_rejected(self):
        d={'turns':['a secret','b secret','a follow-up','b follow-up']}
        self.assertEqual([x['text'] for x in visible(d,'A_to_B')],['a secret','a follow-up'])
        with self.assertRaises(ValueError):visible(d,'B_to_A')
        with self.assertRaises(ValueError):visible(d,'typo')

    def test_both_frozen_scopes_are_isolated(self):
        full={d['id']:d for d in read(BASE/'data/confirmatory_dailydialog300.json')}
        for filename,count in [('dailydialog.json',298),('dailydialog300.json',300)]:
            records=read(BASE/'inputs'/filename);self.assertEqual(len(records),count)
            for item in records:
                validate_input(item)
                self.assertEqual(item['visible_turns'],visible(full[item['dialogue_id']],'A_to_B'))
        primary={x['dialogue_id'] for x in read(BASE/'inputs/dailydialog.json')}
        self.assertEqual(set(full)-primary,{'train_5847','train_9210'})

    def test_hidden_turns_and_extra_fields_rejected(self):
        item=read(BASE/'inputs/dailydialog.json')[0]
        for bad in [dict(item,direction='B_to_A'),dict(item,hidden_turns=[]),
                    dict(item,visible_turns=[{'turn_id':2,'text':'hidden'}]),
                    dict(item,visible_turns=[{'turn_id':1,'text':'x'}]*2)]:
            with self.assertRaises(ValueError):validate_input(bad)

    def test_invalid_citation_is_outcome_not_retry(self):
        c={'claim':'The target is a doctor.','attribute':'work','certainty':'asserted',
           'evidence':[{'turn_id':2,'quote':'doctor'}],'mechanism':'explicit','confidence':.99}
        result=validate_claims({'claims':[c]},[{'turn_id':1,'text':'Do you work at a hospital ?'}])
        self.assertFalse(result[0]['evidence_span_valid'])

    def test_verifier_cannot_admit_hidden_or_fabricated_quote(self):
        cs=[{'candidate_id':'c1'}]
        obj={'decisions':[{'candidate_id':'c1','verdict':'supported','evidence_level':'E2',
            'confidence':.99,'evidence':[{'turn_id':2,'quote':'I am a doctor.'}]}]}
        self.assertEqual(accept(cs,validate_verdicts(obj,[{'turn_id':1,'text':'Hello.'}],cs)),[])

    def test_duplicate_verifier_decisions_rejected(self):
        d={'candidate_id':'c1','verdict':'weak','evidence_level':'E3','confidence':.5}
        with self.assertRaises(ValueError):
            validate_verdicts({'decisions':[d,d]},[],[{'candidate_id':'c1'},{'candidate_id':'c2'}])

    def test_maximum_matching_does_not_double_count(self):
        m=matching({'p1':{'r1','r2'},'p2':{'r1'},'p3':{'r1'}})
        self.assertEqual(len(m),2);self.assertEqual(len(set(m.values())),2)

    def test_zero_denominator_and_unknown_usage(self):
        row={'predictions':0,'correct_output_assertions':0,'true_tp':0,'true_reference':0,
             'supported_tp':0,'supported_reference':0,'tokens':0,'missing_usage_attempts':1}
        result=four_metrics([row])
        for k in ['precision','recall','grounded_recall','mean_tokens']:self.assertIsNone(result[k])

    def test_matching_subject_and_direction(self):
        self.assertEqual(matching_content([],[],'A_to_B')['subject_mapping']['hidden partner / target'],'original B')
        with self.assertRaises(ValueError):matching_content([],[],'B_to_A')

    def test_unreviewed_claims_are_excluded(self):
        p={'dialogue_id':'d','direction':'A_to_B','dataset':'dailydialog','method':'direct_thinking',
           'claims':[{'claim':'has dog','confidence':.9}],'task_ids':[]}
        r=[{'claim_id':'r','truth':'true','evidence_level':'E1','review_status':'single_annotation'}]
        row=score_item(p,r,[{'prediction_id':digest('has dog'),'reference_ids':['r'],'relation':'equivalent'}],{})
        self.assertEqual(row['true_reference'],0);self.assertEqual(row['true_tp'],0)

    def test_export_reconstructed_from_raw_responses(self):
        actual,_=reconstruct()
        self.assertEqual(actual,read(BASE/'runs/main/exports/dailydialog.json'))

    def test_GPT_reviews_and_human_decisions_reconstruct_reference(self):
        self.assertEqual(rebuild_human_reference()['human_decisions'],63)
        refs=read(BASE/'references/dailydialog_human_adjudicated_588.json')
        self.assertEqual(validate_reviews(refs),{'dialogues':298,'claims':588})

    def test_independent_GPT_inventory_alignment_is_cached_for_300_A_to_B_inputs(self):
        from unittest.mock import patch
        from . import reconcile
        with patch.object(reconcile,'Client',side_effect=AssertionError('Unexpected API')),patch.object(reconcile,'save'):
            self.assertEqual(reconcile.reconcile('dailydialog',None,workers=2),{'items':300,'errors':0})

    def test_returned_human_review_DOCX_import_matches_all_63_frozen_decisions(self):
        import importlib.util
        folder=BASE/'results/human_disambiguation_63'
        spec=importlib.util.spec_from_file_location('isc113_review_reader',folder/'read_review.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        completed=next(folder.glob('*已完成.docx'))
        actual=module.read_decisions(completed)
        expected=read(folder/'human_adjudication_588_audit.json')
        self.assertEqual(actual['filled'],63);self.assertEqual(actual['unfilled'],0)
        labels={r['claim_id']:r['human_evidence_level'] for r in actual['decisions']}
        self.assertEqual(labels,{r['claim_id']:r['new_evidence_level'] for r in expected['changes']})

    def test_support_packets_never_include_B_or_truth_labels(self):
        packet=support_packets(read(BASE/'annotations/annotator_1/new_dailydialog_reference.json')[:1])
        row=packet['dialogues'][0]
        self.assertNotIn('turns',row)
        self.assertTrue(all(t['turn_id']%2==1 for t in row['visible_turns']))
        self.assertTrue(all(set(c)=={'claim_id','claim'} for c in row['claims']))

    def test_bad_review_labels_and_hidden_support_rejected(self):
        refs=copy.deepcopy(read(BASE/'references/dailydialog_human_adjudicated_588.json')[:1])
        refs[0]['claims'][0]['evidence_level']='E1'
        refs[0]['claims'][0]['evidence']=[{'turn_id':2,'quote':'hidden'}]
        with self.assertRaises(ValueError):validate_reviews(refs)

    def test_parser_recovery_requires_complete_terminal_JSON(self):
        from .recover_evaluations import terminal_matches
        body={'choices':[{'finish_reason':'stop','message':{'content':'Explanation.\n{"matches": []}'}}]}
        self.assertEqual(terminal_matches(body),{'matches':[]})
        body['choices'][0]['message']['content']='{"matches": []} unfinished'
        with self.assertRaises(ValueError):terminal_matches(body)


if __name__=='__main__':unittest.main()
