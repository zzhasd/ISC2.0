import copy,importlib,unittest
from .common import BASE,read,jsonlines,digest
from .inference import decode
v=importlib.import_module('isc113.Evidence-Adaptive v5')
class AdaptiveV5Tests(unittest.TestCase):
 def setUp(self):
  self.item=dict(item_id='dailydialog/test/A_to_B',dialogue_id='test',direction='A_to_B',dataset='dailydialog',visible_turns=[dict(turn_id=1,text='You teach. Your dog is cute.')])
  self.direct=dict(claim='B teaches',attribute='work',certainty='asserted',mechanism='explicit',confidence=.9,evidence=[dict(turn_id=1,quote='You teach.')])
  self.weak=dict(claim='B has a dog',attribute='pet',certainty='asserted',mechanism='presupposition',confidence=.8,evidence=[dict(turn_id=1,quote='Your dog')])
 def test_selective_verification_interface(self):
  calls=[];direct=self.direct;weak=self.weak
  class Fake:
   def call(self,name,request,validate):
    calls.append((name,request))
    obj={'decisions':[dict(candidate_id='c1',verdict='keep',evidence=weak['evidence'])]} if name.endswith('/adaptive_v5_pragmatic') else {'claims':[copy.deepcopy(direct),copy.deepcopy(weak)]}
    return validate(obj),'t'+str(len(calls))
  out=v.pipeline(Fake(),self.item)[0]
  self.assertEqual(len(out['claims']),2);self.assertEqual(len(calls),3);self.assertEqual(out['task_ids'],['t1','t2','t3'])
  self.assertEqual(calls[-1][1]['thinking_budget'],128)
 def test_bad_verifier_quote_is_rejected_without_resampling(self):
  d=v.validate_decisions({'decisions':[dict(candidate_id='c0',verdict='keep',evidence=[dict(turn_id=1,quote='invented')])]},self.item['visible_turns'],[dict(self.weak,candidate_id='c0')])[0]
  self.assertEqual(d['verdict'],'reject')
  with self.assertRaises(ValueError):v.validate_decisions({'decisions':[]},self.item['visible_turns'],[dict(self.weak,candidate_id='c0')])
 def test_frozen_parent_requests_and_explicit_retention(self):
  cache={}
  for folder in ('evidence_adaptive_v2_corrected','evidence_adaptive_v4_append'):
   for r in jsonlines(BASE/'runs'/folder/'attempts.jsonl'):
    if r['event']=='complete' and r.get('valid'):cache.setdefault(r['task_id'],r)
  class Recorded:
   def call(self,name,request,validate):
    if name.endswith('/adaptive_v5_pragmatic'):
     import json
     cs=json.loads(request['messages'][1]['content'])['candidates']
     return validate({'decisions':[dict(candidate_id=c['candidate_id'],verdict='reject',evidence=[]) for c in cs]}),'test_gate'
    tid=digest({'logical_name':name,'payload':request});return validate(decode(cache[tid]['body'])),tid
  total=0
  for item in read(BASE/'inputs/dailydialog.json'):
   out=v.pipeline(Recorded(),item)[0];self.assertTrue(all(c['mechanism']=='explicit' for c in out['claims']));total+=len(out['claims'])
  self.assertEqual(total,351)
 def test_input_gate(self):
  with self.assertRaises(ValueError):v.pipeline(None,dict(reference=[]))
if __name__=='__main__':unittest.main()
