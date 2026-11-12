import copy,importlib,json,unittest
from .common import BASE,jsonlines,read,digest
from .inference import decode
v=importlib.import_module('isc113.Evidence-Adaptive v4')
class AdaptiveV4Tests(unittest.TestCase):
 def setUp(self):
  self.item=dict(item_id='dailydialog/test/A_to_B',dialogue_id='test',dataset='dailydialog',direction='A_to_B',visible_turns=[dict(turn_id=1,text='Your dog is lovely . No one came .')])
  self.c=dict(claim='B has a dog',attribute='pet',certainty='asserted',mechanism='presupposition',confidence=.9,evidence=[dict(turn_id=1,quote='Your dog is lovely.')])
 def test_token_preserving_quote_alignment(self):
  c=v.align_evidence([self.c],self.item['visible_turns'])[0]
  self.assertEqual(c['evidence'][0]['quote'],'Your dog is lovely .');self.assertTrue(c['evidence_span_valid'])
  for quote,text in [('Noone','No one'),('no one','No one'),('Your dog.','Your dog . Your dog .'),('Your cat','Your dog')]:
   c=dict(self.c,evidence=[dict(turn_id=1,quote=quote)])
   self.assertFalse(v.align_evidence([c],[dict(turn_id=1,text=text)])[0]['evidence_span_valid'])
 def test_two_calls_and_blind_to_confidence_labels(self):
  calls=[];claim=copy.deepcopy(self.c)
  class Fake:
   def call(self,name,request,validate):
    calls.append((name,request));return validate({'claims':[copy.deepcopy(claim)]}),'t'+str(len(calls))
  out=v.pipeline(Fake(),self.item)[0]
  self.assertEqual(out['task_ids'],['t1','t2']);self.assertEqual(out['method'],'evidence_adaptive_v4')
  content=json.loads(calls[1][1]['messages'][1]['content']);self.assertEqual(set(content['draft_candidates'][0]),{'claim','attribute','evidence'})
  self.assertNotIn('reference',content);self.assertEqual(calls[1][1]['thinking_budget'],256);self.assertEqual(calls[1][1]['max_tokens'],2048)
 def test_generation_requests_match_frozen_coverage(self):
  cache={}
  for r in jsonlines(BASE/'runs/evidence_adaptive_v2_corrected/attempts.jsonl'):
   if r['event']=='complete' and r.get('valid'):cache.setdefault(r['task_id'],r)
  class Recorded:
   def call(self,name,request,validate):
    if name.endswith('/adaptive_v4_reconstruct'):return validate({'claims':[]}),'test_empty'
    tid=digest({'logical_name':name,'payload':request});return validate(decode(cache[tid]['body'])),tid
  for item in read(BASE/'inputs/dailydialog.json'):
   self.assertEqual(v.pipeline(Recorded(),item)[0]['claims'],[])
 def test_input_and_output_gates(self):
  for bad in [dict(self.item,direction='B_to_A'),dict(self.item,reference=[]),dict(self.item,visible_turns=[dict(turn_id=2,text='hidden')])]:
   with self.assertRaises(ValueError):v.pipeline(None,bad)
  with self.assertRaises(ValueError):v.validate_final({'claims':[copy.deepcopy(self.c)]*11},self.item['visible_turns'])
if __name__=='__main__':unittest.main()
