import copy
import importlib
import unittest
from .common import BASE,read,jsonlines,digest
from .inference import decode
v=importlib.import_module('isc113.Evidence-Adaptive v3')

class AdaptiveV3Tests(unittest.TestCase):
 def test_three_stage_interface_and_direct_only_augmentation(self):
  item=dict(item_id='dailydialog/test/A_to_B',dialogue_id='test',direction='A_to_B',dataset='dailydialog',visible_turns=[dict(turn_id=1,text='Your dog is lovely. You are a teacher.')])
  def claim(text,quote,level=None):
   c=dict(claim=text,attribute='test',certainty='asserted',mechanism='explicit',confidence=.9,evidence=[dict(turn_id=1,quote=quote)])
   if level:c['evidence_level']=level
   return c
  calls=[]
  class Fake:
   def call(self,name,request,validate):
    calls.append(name)
    obj={'claims':([claim('B has a dog','Your dog')] if len(calls)==1 else [claim('B is a teacher','You are a teacher.', 'E1'),claim('B likes teaching','You are a teacher.','E2')])}
    return validate(obj),'t'+str(len(calls))
  out=v.pipeline(Fake(),item)[0]
  self.assertEqual(out['task_ids'],['t1','t2','t3'])
  self.assertEqual([c['claim'] for c in out['claims']],['B has a dog','B is a teacher'])
 def test_all_298_frozen_stage_requests_replay_and_match_union(self):
  cache={}
  for folder in ('evidence_adaptive_v1_append','evidence_adaptive_v2_corrected'):
   for r in jsonlines(BASE/'runs'/folder/'attempts.jsonl'):
    if r['event']=='complete' and r.get('valid'):cache.setdefault(r['task_id'],r)
  class Recorded:
   def call(self,name,request,validate):
    tid=digest({'logical_name':name,'payload':request});return validate(decode(cache[tid]['body'])),tid
  a={p['item_id']:p for p in read(BASE/'runs/evidence_adaptive_v1_append/exports/dailydialog.json')};b={p['item_id']:p for p in read(BASE/'runs/evidence_adaptive_v2_corrected/exports/dailydialog.json')}
  total=0
  for item in read(BASE/'inputs/dailydialog.json'):
   out=v.pipeline(Recorded(),item)[0];base=a[item['item_id']]['claims'];expected=list(base);seen={' '.join(c['claim'].casefold().split()) for c in base}
   for c in b[item['item_id']]['claims']:
    key=' '.join(c['claim'].casefold().split())
    if c['evidence_level']=='E1' and key not in seen:expected.append(c);seen.add(key)
   self.assertEqual(out['claims'],expected);self.assertEqual(len(out['task_ids']),3);total+=len(out['claims'])
  self.assertEqual(total,701)
 def test_reject_hidden_input(self):
  with self.assertRaises(ValueError):v.pipeline(None,dict(reference=[]))

if __name__=='__main__':unittest.main()
