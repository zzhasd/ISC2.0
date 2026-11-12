import json
import unittest
from isc4_open import ROOT,visible
from isc6_module import clause_units,validate_candidates,collect_selection

class BoundaryTests(unittest.TestCase):
    def test_preserve_and_reject_hidden(self):
        turns=[{'turn':1,'text':'Send the form on Tuesday.'}]
        obj={'checked_units':['1.1'],'candidates':[{'id':'c1','claim':'B is instructed to send the form on Tuesday.',
             'category':'plan','route':'literal','evidence_turns':[1],'time':'future instruction'}]}
        validate_candidates(obj,turns)
        selection={'decisions':[{'id':'c1','action':'keep','rival':'already sent','reason':'imperative',
                   'support':'explicit','evidence_turns':[1]}],'additions':[]}
        final=collect_selection(selection,obj['candidates'],turns)
        self.assertEqual(final['facts'][0]['claim'],obj['candidates'][0]['claim'])
        self.assertEqual(final['facts'][0]['time'],'future instruction')
        selection['decisions'][0]['evidence_turns']=[2]
        with self.assertRaises(ValueError):collect_selection(selection,obj['candidates'],turns)
    def test_missing_decision_and_coverage(self):
        turns=[{'turn':1,'text':'Hi. You draw well.'}]
        with self.assertRaises(ValueError):validate_candidates({'checked_units':['1.1'],'candidates':[]},turns)
        with self.assertRaises(ValueError):collect_selection({'decisions':[],'additions':[]},[{'id':'c1'}],turns)
    def test_request_no_b_or_future(self):
        ds=json.loads((ROOT/'data/isc6/dialogues.json').read_text(encoding='utf-8'))
        ts=json.loads((ROOT/'results/isc6/initial/requests.json').read_text(encoding='utf-8'))
        by={d['id']:d for d in ds}
        self.assertEqual(len(ts),32)
        for t in ts:
            body=json.loads(t['payload']['messages'][1]['content'])
            self.assertEqual(body,{'visible_A':visible(by[t['dialogue_id']]),'clause_units':clause_units(visible(by[t['dialogue_id']]))})
            self.assertEqual(t['payload']['model'],'qwen3.8-flash')

if __name__=='__main__':unittest.main()
