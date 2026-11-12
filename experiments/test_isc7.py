import unittest
from isc4_open import ROOT,read,visible
from isc7_module import render,union_candidates

class Boundaries(unittest.TestCase):
    def test_common_gate(self):
        turns=[{'turn':1,'text':'I draw. You sing well.'}]
        item={'id':'f1','claim':'A draws.','category':'skill','holder':'A','scope':'profile',
              'support':'explicit','status':'active','time':'present','evidence_turns':[1]}
        self.assertEqual(render({'items':[item]},turns)['facts'],[])
        item.update(holder='B',claim='B sings well.')
        self.assertEqual(len(render({'items':[item]},turns)['facts']),1)
        item['evidence_turns']=[2]
        with self.assertRaises(ValueError):render({'items':[item]},turns)
    def test_missing_id(self):
        with self.assertRaises(ValueError):render({'items':[]},[],[{'id':'c1'}])
    def test_union_preserves_values(self):
        a={'id':'a','claim':'B submits on Tuesday.','time':'future','evidence_turns':[1]}
        b={**a,'id':'b','evidence_turns':[3]}
        c={**a,'claim':'B submits on Friday.'}
        result=union_candidates([a],[b,c])
        self.assertEqual(len(result),2);self.assertEqual(result[0]['evidence_turns'],[1,3])
    def test_factor_and_observation(self):
        ts=read(ROOT/'results/isc7/initial/requests.json');ds={d['id']:d for d in read(ROOT/'data/isc7/dialogues.json')}
        self.assertEqual(len(ts),192)
        import json
        by={}
        for t in ts:
            p=t['payload'];body=json.loads(p['messages'][1]['content'])
            self.assertEqual(body,{'visible_A':visible(ds[t['dialogue_id']])})
            self.assertEqual(p['enable_thinking'],t['arm'].endswith('_on'))
            key=(t['dialogue_id'],t['stage'])
            stripped={k:v for k,v in p.items() if k not in ['enable_thinking','thinking_budget']}
            if key in by:self.assertEqual(stripped,by[key])
            by[key]=stripped

if __name__=='__main__':unittest.main()
