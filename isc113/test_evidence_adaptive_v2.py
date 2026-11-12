"""V2 coverage/review isolation, citation restoration and epistemic gates."""
import copy
import importlib
import json
import unittest
v=importlib.import_module('isc113.Evidence-Adaptive v2')

class AdaptiveV2Tests(unittest.TestCase):
 def setUp(self):
  self.item=dict(item_id='dailydialog/test/A_to_B',dialogue_id='test',dataset='dailydialog',direction='A_to_B',visible_turns=[dict(turn_id=1,text='Your dog is lovely . Are you a doctor ?')])
  self.claim=dict(claim='B has a dog',attribute='pet',certainty='asserted',mechanism='presupposition',confidence=.9,evidence=[dict(turn_id=1,quote='Your dog is lovely.')])
 def test_whitespace_restoration_is_exact_and_audited(self):
  c=v.align_evidence([self.claim],self.item['visible_turns'])[0]
  self.assertEqual(c['evidence'][0]['quote'],'Your dog is lovely .')
  self.assertTrue(c['evidence_span_valid']);self.assertIn('whitespace_alignment',c)
  self.assertEqual(self.claim['evidence'][0]['quote'],'Your dog is lovely.')
 def test_no_semantic_or_ambiguous_repair(self):
  for quote,text in [('your dog','Your dog'),('Your cat','Your dog'),('Your dog.','Your dog . Your dog .')]:
   c=dict(self.claim,evidence=[dict(turn_id=1,quote=quote)])
   result=v.align_evidence([c],[dict(turn_id=1,text=text)])[0]
   self.assertFalse(result['evidence_span_valid'])
 def test_question_not_blanket_rejected_but_review_level_required(self):
  c=dict(self.claim,evidence=[dict(turn_id=1,quote='Are you a doctor ?')],evidence_level='E3')
  self.assertEqual(len(v.grounded_unique([c],self.item['visible_turns'])),1)
  self.assertEqual(v.grounded_unique([c],self.item['visible_turns'],reviewed=True),[])
  with self.assertRaises(ValueError):v.validate_review({'claims':[self.claim]},self.item['visible_turns'])
 def test_two_calls_even_empty_generation_and_standard_interface(self):
  calls=[];c=copy.deepcopy(self.claim);c['evidence_level']='E2'
  class Fake:
   def call(self,name,request,validator):
    calls.append((name,request))
    return validator({'claims':[] if len(calls)==1 else [copy.deepcopy(c)]}),'task'+str(len(calls))
  result=v.pipeline(Fake(),self.item)
  self.assertEqual(len(calls),2);self.assertEqual(result[0]['task_ids'],['task1','task2'])
  self.assertEqual(result[0]['method'],'evidence_adaptive_v2');self.assertEqual(len(result[0]['claims']),1)
  for name,request in calls:
   content=json.loads(request['messages'][1]['content'])
   self.assertEqual(content['visible_turns'],self.item['visible_turns']);self.assertNotIn('reference',content)
   self.assertEqual(request['thinking_budget'],512);self.assertEqual(request['max_tokens'],3072)
 def test_review_schema_explicitly_contains_required_level(self):
  schema=v.REVIEW_PROMPT.rsplit("Return ONLY JSON",1)[1]
  self.assertIn('"evidence_level":"E1|E2|E3|E4"',schema)
 def test_input_gate(self):
  for item in [dict(self.item,direction='B_to_A'),dict(self.item,reference=[]),dict(self.item,visible_turns=[dict(turn_id=2,text='hidden')])]:
   with self.assertRaises(ValueError):v.pipeline(None,item)
 def test_duplicate_and_invalid_citation_filtered_without_resampling(self):
  c=copy.deepcopy(self.claim);c['evidence_level']='E1'
  duplicate=dict(c,claim='B HAS a dog!')
  bad=dict(c,evidence=[dict(turn_id=1,quote='invented')])
  self.assertEqual(len(v.grounded_unique([c,duplicate,bad],self.item['visible_turns'],reviewed=True)),1)

if __name__=='__main__':unittest.main()
