import copy
import json
import unittest
from isc4_open import ROOT,read,visible,sha
from isc5_run import DATA,OUT
from isc5_module import compile_cues,guard_ledger,index_provenance,render_extraction

class LedgerGuards(unittest.TestCase):
    def test_no_B_gold_future_or_historical_predictions_in_payload(self):
        ds={d['id']:d for d in read(DATA/'dialogues.json')}
        for t in read(OUT/'initial/requests.json'):
            self.assertEqual(sha(t['payload']),t['request_sha256'])
            c=json.loads(t['payload']['messages'][1]['content'])
            self.assertEqual(c['visible_A'],visible(ds[t['dialogue_id']]))
            self.assertLessEqual(set(c),{'visible_A','lexical_cues'})
            self.assertTrue(all(v['turn']%2 for v in c['visible_A']))

    def test_new_selection_excludes_all_historical_IDs_and_keeps_complete_boundaries(self):
        source={r['id']:r for r in [json.loads(x) for x in (ROOT/'data/dailydialog.jsonl').read_text(encoding='utf-8').splitlines()]}
        old=set()
        for path in ['data/natural_pilot.json','data/stage2/dialogues.json','data/revision/dialogues.json']:
            old.update(r['id'] for r in read(ROOT/path))
        rows=read(DATA/'dialogues.json')
        self.assertEqual(len(rows),48)
        for r in rows:
            self.assertEqual(source[r['id']]['turns'],r['turns'])
            if r['evaluation_split']=='new_evaluation':self.assertNotIn(r['id'],old)

    def test_cues_are_indicators_not_asserted_private_values(self):
        q=compile_cues([{'turn':1,'text':'Has your wife arrived?'}])[0]
        self.assertIn('question',q['tags']);self.assertIn('possessive_background',q['tags'])
        self.assertEqual(set(q),{'turn','tags'})

    def test_provenance_tracks_repair_and_rejects_dangling_or_hidden_evidence(self):
        turns=[{'turn':1,'text':'Your old address was X.'},{'turn':3,'text':'Actually your address is Y.'}]
        obj={'nodes':[{'id':'n1','holder':'B','evidence_turns':[1]}, {'id':'n2','holder':'B','evidence_turns':[3]}],
            'links':[{'from':'n2','to':'n1','relation':'supersedes'}],
            'candidates':[{'node_ids':['n1'],'evidence_turns':[1]}]}
        guard_ledger(obj,turns)
        self.assertEqual(index_provenance(obj)['candidates'][0]['provenance']['superseded_node_ids'],['n1'])
        broken=copy.deepcopy(obj);broken['links'][0]['to']='missing'
        with self.assertRaises(ValueError):guard_ledger(broken,turns)
        broken=copy.deepcopy(obj);broken['nodes'][0]['evidence_turns']=[2]
        with self.assertRaises(ValueError):guard_ledger(broken,turns)

    def test_common_renderer_retrieves_exact_quotes_and_rejects_future_positions(self):
        source=[{'turn':1,'text':'Hello , Ren !'}]
        obj={'facts':[{'claim':'B is Ren.','support':'presupposed','confidence':.9,'evidence_turns':[1]}],'hypotheses':[]}
        self.assertEqual(render_extraction(obj,source)['facts'][0]['evidence'][0]['quote'],'Hello , Ren !')
        obj['facts'][0]['evidence_turns']=[3]
        with self.assertRaises(ValueError):render_extraction(obj,source)

    def test_dependent_payloads_match_their_actual_initial_outputs(self):
        from isc5_run import records,decode
        from isc5_module import index_provenance
        raw={r['task_id']:r for r in records('initial')}
        ds={d['id']:d for d in read(DATA/'dialogues.json')}
        for t in read(OUT/'dependent/requests.json'):
            self.assertEqual(t['request_sha256'],sha(t['payload']))
            source=decode(raw[t['source_task_id']]);c=json.loads(t['payload']['messages'][1]['content'])
            self.assertEqual(c['visible_A'],visible(ds[t['dialogue_id']]))
            if t['stage']=='selfcheck':
                self.assertEqual(set(c),{'visible_A','draft'});self.assertEqual(c['draft'],source)
            else:
                self.assertEqual(set(c),{'visible_A','lexical_cues','ledger'})
                self.assertEqual(c['ledger'],index_provenance(source))

    def test_all_output_claims_have_one_review_and_all_matches_use_their_own_dialogue(self):
        from isc5_review import key
        review={r['review_id']:r for r in read(OUT/'semantic_review.json')}
        refs={r['dialogue_id']:{f['id'] for f in r['facts']} for r in read(DATA/'full_AB_reference.json')}
        for p in read(OUT/'predictions.json'):
            for f in p['facts']:
                r=review[key(p['dialogue_id'],f)]
                self.assertNotEqual(r['verdict'],'unreviewed')
                self.assertLessEqual(set(r['reference_ids'])|set(r['partial_reference_ids']),refs[p['dialogue_id']])

if __name__=='__main__':unittest.main()
