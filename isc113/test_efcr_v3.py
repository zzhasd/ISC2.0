import copy
import json
import unittest
from . import EFCR_v3 as v3
from .common import digest


class V3Tests(unittest.TestCase):
    def setUp(self):
        self.turns=[dict(turn_id=1,text='Your dog is lovely.'),dict(turn_id=3,text='Your cat is cute.')]
        self.item=dict(item_id='dailydialog/test/A_to_B',dialogue_id='test',direction='A_to_B',
                       dataset='dailydialog',visible_turns=self.turns)
        self.c=dict(candidate_id='c1',claim='B has a dog.',attribute='pet',certainty='asserted',
                    mechanism='presupposition',confidence=.95,evidence=[dict(turn_id=1,quote='Your dog')],
                    evidence_span_valid=True,proposal_sources=['evidence_first_v2'])
        self.bundle=dict(candidates=[self.c],generation_task_ids=['old_gen1','old_gen2'])

    def fact(self,cat=False):
        c=copy.deepcopy(self.c)
        c.pop('candidate_id');c.pop('proposal_sources')
        if cat:c.update(claim='B has a cat.',evidence=[dict(turn_id=3,quote='Your cat')])
        c['slots']=dict(subject='B',predicate='owns',object='cat' if cat else 'dog',
                        time=None,quantity=None,negation=False,modality='asserted')
        return c

    def test_strip_changes_only_two_fields(self):
        stripped=v3.strip_scores(self.c)
        self.assertEqual(set(self.c)-set(stripped),{'confidence','proposal_sources'})
        self.assertEqual(stripped['claim'],self.c['claim'])

    def test_invalid_citation_is_observable_not_resampled(self):
        c=self.fact();c['evidence']=[dict(turn_id=1,quote='invented')]
        self.assertFalse(v3.validate_witness(dict(facts=[c]),self.turns)[0]['evidence_span_valid'])

    def test_witness_requires_slots_and_target_ownership(self):
        for key,value in [('subject','A'),('negation','false'),('modality','certain')]:
            c=self.fact();c['slots'][key]=value
            with self.assertRaises(ValueError):v3.validate_witness(dict(facts=[c]),self.turns)

    def test_unknown_required_condition_demotes_keep(self):
        d=dict(candidate_id='c1',verdict='keep',evidence_level='E2',confidence=.99,
               evidence=self.c['evidence'],checks={k:'supported' for k in v3.CHECKS})
        d['checks']['time']='unknown'
        self.assertEqual(v3.validate_conditions(dict(decisions=[d]),self.turns,[self.c])[0]['verdict'],'reject')

    def test_witness_blindness_and_arms_cost_provenance(self):
        facts=[self.fact(),self.fact(True)];calls=[]
        class Fake:
            rows=[]
            def call(self,name,request,validator):
                content=json.loads(request['messages'][1]['content']);calls.append((name,content))
                if name.endswith('independent_witness'):obj=dict(facts=copy.deepcopy(facts))
                else:
                    ds=[]
                    for c in content['candidates']:
                        d=dict(candidate_id=c['candidate_id'],verdict='keep',evidence_level='E2',
                               confidence=.85 if c['candidate_id']=='c1' else .95,evidence=c['evidence'])
                        if 'condition_gate' in name:d['checks']={k:'supported' for k in v3.CHECKS}
                        ds.append(d)
                    obj=dict(decisions=ds)
                return validator(obj),digest(dict(logical_name=name,payload=request))
        outcomes,diag=v3.pipeline(Fake(),self.item,self.bundle)
        self.assertEqual(len(outcomes),8)
        self.assertEqual([len(p['claims']) for p in outcomes],[1,0,1,0,1,0,2,1])
        self.assertEqual([len(p['task_ids']) for p in outcomes],[3,3,3,3,4,4,5,5])
        self.assertEqual(len(calls),5)
        for name,content in calls:
            self.assertNotIn('reference',content)
            self.assertEqual(content['visible_turns'],self.turns)
            if name.endswith('independent_witness'):
                self.assertEqual(set(content),{'visible_turns','target'})
            elif name.endswith('g0_refresh'):
                self.assertIn('confidence',content['candidates'][0])
            else:
                for c in content['candidates']:
                    self.assertNotIn('confidence',c)
                    self.assertNotIn('proposal_sources',c)

    def test_transport_continuation_charges_original_bank(self):
        class Fake:
            def __init__(self):self.rows=[]
            def call(self,name,request,validator):
                tid=digest(dict(logical_name=name,payload=request))
                if 'transport_recovery' not in name:
                    self.rows=[dict(event='complete',task_id=tid,http_status=None) for _ in range(3)]
                    raise RuntimeError('transport')
                return validator({'ok':True}),tid
        obj,tids=v3.call_recorded(Fake(),'test',{},lambda obj:obj)
        self.assertTrue(obj['ok']);self.assertEqual(len(tids),2)

    def test_model_failure_not_given_additional_sampling_banks(self):
        class Fake:
            rows=[]
            def call(self,name,request,validator):
                tid=digest(dict(logical_name=name,payload=request))
                self.rows=[dict(event='complete',task_id=tid,http_status=200,body={'bad':True}) for _ in range(3)]
                raise RuntimeError('schema failure')
        with self.assertRaises(RuntimeError):v3.call_recorded(Fake(),'test',{},lambda obj:obj)

    def test_rejects_hidden_turns_and_reference_bundle(self):
        with self.assertRaises(ValueError):v3.pipeline(None,dict(self.item,direction='B_to_A'),self.bundle)
        with self.assertRaises(ValueError):v3.pipeline(None,self.item,dict(self.bundle,reference=[]))

    def test_presentation_repair_preserves_all_values_and_string_braces(self):
        expected={'decisions':[{'candidate_id':'c1','verdict':'reject','confidence':.1,
                              'checks':{'subject':'unknown'},'quote':'literal }}} text'},
                             {'candidate_id':'c2','verdict':'keep','confidence':.95,
                              'checks':{'subject':'supported'}}]}
        raw=json.dumps(expected).replace('text"}', 'text"}}')
        body={'choices':[{'finish_reason':'stop','message':{'content':raw}}]}
        obj,audit=v3.presentation_decode(body)
        self.assertEqual(obj,expected)
        self.assertEqual(len(audit['removed_object_closers']),1)

    def test_presentation_parser_never_completes_truncation_or_missing_ids(self):
        for text,finish in [('{"decisions":[{"candidate_id":"c1"}', 'stop'),
                            ('{"decisions":[]}', 'length')]:
            with self.assertRaises(ValueError):
                v3.presentation_decode({'choices':[{'finish_reason':finish,'message':{'content':text}}]})

    def test_uniform_first_presentable_selection_not_best_verdict(self):
        tid=digest(dict(logical_name='test',payload={}))
        first='{"decisions":[{"candidate_id":"c1","verdict":"reject","checks":{}}}]}'
        later='{"decisions":[{"candidate_id":"c1","verdict":"keep","checks":{}}]}'
        class Fake:
            def __init__(self):
                self.rows=[dict(event='complete',task_id=tid,attempt_id=str(i),http_status=200,
                      valid=bool(i),body={'choices':[{'finish_reason':'stop','message':{'content':text}}]})
                      for i,text in enumerate([first,later])]
            def append(self,row):self.rows.append(row)
            def call(self,*args):raise AssertionError('Must use recorded response')
        fake=Fake()
        obj,ids=v3.call_recorded(fake,'test',{},lambda obj:obj)
        self.assertEqual(obj['decisions'][0]['verdict'],'reject')
        self.assertFalse(fake.rows[0]['valid'])
        self.assertEqual(fake.rows[-1]['attempt_id'],'0')


if __name__=='__main__':unittest.main()
