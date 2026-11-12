"""Scientific validity guards, run offline with python -m unittest discover ..."""
import collections
import copy
import json
import unittest
from isc3_common import *
from isc3_analyze import metric, paired, calibration

class ScientificGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases=read(DATA/'cases.json');cls.plan=read(OUT/'initial/requests.json')
        cls.bindings=read(DATA/'bindings_initial.json')

    def test_opposite_worlds_share_catalogue_and_word_counts(self):
        pairs=collections.defaultdict(list)
        for c in self.cases:
            if c['dataset']=='controlled':pairs[c['group']].append(c)
        import re
        for pair in pairs.values():
            self.assertEqual(len(pair),2)
            self.assertEqual(pair[0]['catalogue'],pair[1]['catalogue'])
            token=lambda c:collections.Counter(re.findall(r'\b\w+\b',' '.join(v['text'] for v in c['visible_A']).lower()))
            self.assertEqual(token(pair[0]),token(pair[1]))
            self.assertEqual({pair[0]['facts'][0]['truth'],pair[1]['facts'][0]['truth']},{'true','false'})
            self.assertEqual(pair[0]['split'],pair[1]['split'])

    def test_no_dialogue_or_pair_crosses_calibration_test(self):
        grouped=collections.defaultdict(set)
        for c in self.cases:grouped[(c['dataset'],c['group'])].add(c['split'])
        self.assertTrue(all(len(s)==1 for s in grouped.values()))

    def test_gold_and_hidden_worlds_are_not_in_initial_payloads(self):
        expected={'visible_A','catalogue'}
        for t in self.plan:
            content=json.loads(t['payload']['messages'][1]['content'])
            self.assertTrue(set(content).issubset(expected))
            self.assertEqual(t['request_sha256'],digest(t['payload']))
            self.assertEqual(t['task_id'],t['request_sha256'][:24])
            self.assertEqual(t['payload']['model'],MODEL)
            self.assertFalse(t['payload']['enable_thinking'])
            self.assertNotIn('sk-ws-',json.dumps(t['payload']))
            self.assertTrue(all(v['speaker']=='A' for v in content['visible_A']))

    def test_all_chronological_prefixes_exist_and_use_no_future_turns(self):
        by={(b['case_id'],b['method'],b['condition']):b for b in self.bindings}
        for c in self.cases:
            n=len(c['visible_A'])
            for method in ['direct','graph']:
                for k in range(n):
                    b=by[(c['case_id'],method,f'prefix_{k}')]
                    self.assertEqual(b['visible_turns'],list(range(1,k+1)))
                self.assertEqual(by[(c['case_id'],method,'full')]['visible_turns'],list(range(1,n+1)))

    def test_nonidentifiable_fact_has_truth_but_no_visible_evidence(self):
        for c in self.cases:
            if c['dataset']!='controlled':continue
            facts={f['id']:f for f in c['facts']}
            self.assertIn(facts['iguana']['truth'],['true','false'])
            self.assertEqual(facts['iguana']['a_support'],'unknown')
            self.assertEqual(facts['iguana']['support_turns'],[])
            self.assertNotEqual(c['full_world']['B_owns_iguana'],c['counter_world']['B_owns_iguana'])
            self.assertTrue(c['counter_world']['identical_A'])
            self.assertEqual(facts['sailboat']['truth'],'unknown')

    def test_unknown_truth_is_unverified_not_a_known_falsehood(self):
        r={'case_id':'c','truth':'unknown','prediction':'true','confidence':.9,
           'support_available':False,'a_support':'unknown','evidence_turns':[],'evidence_complete':False}
        m=metric([r]);self.assertEqual(m['known_truth_errors'],0)
        self.assertEqual(m['unverified_assertions'],1);self.assertEqual(m['unsupported_assertions'],1)
        self.assertEqual(m['nonverified_fraction'],1)

    def test_true_lucky_guess_is_not_grounded_recovery(self):
        r={'case_id':'c','truth':'true','prediction':'true','confidence':1,
           'support_available':False,'a_support':'unknown','evidence_turns':[],'evidence_complete':False}
        m=metric([r]);self.assertEqual(m['true_positive_recoveries'],1)
        self.assertEqual(m['grounded_true_recoveries'],0)

    def test_invalid_response_cannot_be_coerced_to_unknown(self):
        with self.assertRaises(ValueError):validate_facts({'facts':[]},[{'id':'x'}],[])
        with self.assertRaises(ValueError):
            validate_facts({'facts':[{'id':'x','label':'unknown','confidence':1,'evidence_turns':[2]}]},[{'id':'x'}],[])
        with self.assertRaises(ValueError):
            decode({'body':{'choices':[{'finish_reason':'length','message':{'content':'{"facts":[]}'}}]}})

    def test_abstention_does_not_invent_a_zero_observed_risk(self):
        r={'case_id':'c','truth':'true','prediction':'unknown','confidence':1,
           'support_available':False,'a_support':'unknown','evidence_turns':[],'evidence_complete':False}
        self.assertIsNone(metric([r])['known_error_fraction'])
        self.assertEqual(metric([r])['assertions'],0)

    def test_v2_reconstruction_rejects_missing_duplicate_or_empty_replies(self):
        from isc3_reconstruction_v2 import validate_hypotheses
        visible=[{'turn':1},{'turn':2}]
        valid={'hypotheses':[{'replies':[{'after_turn':1,'text':'Okay.'},{'after_turn':2,'text':'Thank you.'}]}]}
        self.assertEqual(len(validate_hypotheses(valid,visible,1)),1)
        for replies in [[{'after_turn':1,'text':'Only a fragment.'}],
                        [{'after_turn':1,'text':'First.'},{'after_turn':1,'text':'Duplicate.'}],
                        [{'after_turn':1,'text':'First.'},{'after_turn':2,'text':''}]]:
            with self.assertRaises(ValueError):validate_hypotheses({'hypotheses':[{'replies':replies}]},visible,1)

    def test_v2_generation_skeleton_contains_positions_not_answers(self):
        for t in read(OUT/'reconstruction_v2_generate/requests.json'):
            content=json.loads(t['payload']['messages'][1]['content'])
            self.assertEqual(set(content),{'visible_A','output_skeleton'})
            expected=[v['turn'] for v in content['visible_A']]
            self.assertEqual(len(content['output_skeleton']['hypotheses']),t['required_hypotheses'])
            for h in content['output_skeleton']['hypotheses']:
                self.assertEqual([r['after_turn'] for r in h['replies']],expected)
                self.assertTrue(all(r['text']=='' for r in h['replies']))

if __name__=='__main__':unittest.main()
