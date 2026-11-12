"""Meaningful guards against hidden-side leakage, future leakage and false success."""
import copy
import json
import unittest
from isc4_open import DATA, OUT, ROOT, read, visible, task, sha, decode

class OpenDialogueGuards(unittest.TestCase):
    def test_pilot_preserves_source_boundaries_even_shortest_dialogue(self):
        source={r['id']:r for r in [json.loads(s) for s in (ROOT/'data/dailydialog.jsonl').read_text(encoding='utf-8').splitlines()]}
        rows=read(DATA/'dialogues.json')
        self.assertEqual(len(rows),32)
        self.assertEqual(min(len(r['turns']) for r in rows),2)
        for r in rows:self.assertEqual(r['turns'],source[r['id']]['turns'])

    def test_every_integer_prefix_is_independent_and_has_no_hidden_or_future_text(self):
        rows={r['id']:r for r in read(DATA/'dialogues.json')};seen=set()
        for t in read(OUT/'baseline/requests.json'):
            self.assertEqual(t['request_sha256'],sha(t['payload']))
            self.assertEqual(len(t['payload']['messages']),2)
            content=json.loads(t['payload']['messages'][1]['content'])
            self.assertEqual(set(content),{'visible_A'})
            if t['dialogue_id']=='shared_prior':self.assertEqual(content['visible_A'],[]);continue
            r=rows[t['dialogue_id']]
            self.assertEqual(content['visible_A'],visible(r,t['k']))
            self.assertTrue(all(v['turn']%2==1 for v in content['visible_A']))
            self.assertNotIn('catalogue',content);self.assertNotIn('facts',content)
            self.assertNotIn((t['dialogue_id'],t['k']),seen)
            seen.add((t['dialogue_id'],t['k']))
        self.assertEqual(seen,{(r['id'],k) for r in rows.values() for k in range(1,len(visible(r))+1)})

    def test_source_aware_reference_only_uses_A_evidence(self):
        for r in read(DATA/'assistant_reference_v1.json'):
            for f in r['facts']:
                self.assertTrue(f['evidence'])
                self.assertTrue(all(e['turn']%2==1 for e in f['evidence']))
                self.assertEqual(f['first_A_prefix'],(max(f['evidence_sets'][0])+1)//2)

    def test_truncation_missing_evidence_and_future_quote_are_invalid(self):
        t=task({'id':'fictional','turns':['Hello Bob.','hidden secret','You work at Acme.']},1)
        f={'claim':'B is Bob.','support':'explicit','confidence':.9,
           'evidence':[{'turn':1,'quote':'Bob'}]}
        def response(finish='stop'):
            return {'http_status':200,'body':{'choices':[{'finish_reason':finish,
                 'message':{'content':json.dumps({'facts':[copy.deepcopy(f)],'hypotheses':[]})}}]}}
        self.assertEqual(len(decode(response(),t)['facts']),1)
        with self.assertRaises(ValueError):decode(response('length'),t)
        f['evidence']=[{'turn':3,'quote':'Acme'}]
        with self.assertRaises(ValueError):decode(response(),t)
        f['evidence']=[{'turn':2,'quote':'hidden secret'}]
        with self.assertRaises(ValueError):decode(response(),t)
        f['evidence']=[]
        with self.assertRaises(ValueError):decode(response(),t)

    def test_full_reference_includes_B_but_does_not_change_Qwen_inputs(self):
        rows={r['id']:r for r in read(DATA/'dialogues.json')}
        ref=read(DATA/'full_AB_reference_v2.json')
        self.assertEqual(set(rows),{r['dialogue_id'] for r in ref})
        self.assertTrue(any(e['speaker']=='B' for r in ref for f in r['facts'] for e in f['full_evidence']))
        for r in ref:
            for f in r['facts']:
                for e in f['full_evidence']:
                    self.assertEqual(e['quote'],rows[r['dialogue_id']]['turns'][e['turn']-1])
                self.assertTrue(all(n%2 for s in f['A_support_sets'] for n in s))

    def test_semantic_duplicates_match_reference_only_once(self):
        from isc4_analyze import maximum_match
        self.assertEqual(maximum_match([['same'],['same']]),{'same'})
        self.assertEqual(maximum_match([['a','b'],['a']]),{'a','b'})

if __name__=='__main__':unittest.main()
