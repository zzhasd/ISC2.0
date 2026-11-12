import unittest
from . import elara_subject_v2 as alg
from .profile_subject_v2 import admission, validate_gate, validate_synthesis, validate_pairs, marked_turns


class SubjectV2Tests(unittest.TestCase):
    def test_role_marker_added_to_every_request_and_evidence_stays_original(self):
        turns=[dict(turn_id=1,text='私は旅行が好きです。')]
        for prompt in (alg.EXPLICIT,alg.IMPLICIT,alg.GAP_SCAN,alg.AUDIT):
            req=alg.request(prompt,dict(visible_turns=turns,target='hidden B'))
            import json
            got=json.loads(req['messages'][1]['content'])['visible_turns'][0]
            self.assertEqual(got['speaker'],'A');self.assertEqual(got['text'],'A says: '+turns[0]['text'])
            self.assertEqual(req['model'],'qwen3.8-flash');self.assertTrue(req['enable_thinking'])
        self.assertNotIn('speaker',turns[0])
        self.assertFalse(alg.valid_evidence([dict(turn_id=1,quote='A says: 私は旅行が好きです。')],turns))

    def test_strict_audit_excludes_uncertain_instead_of_retaining_disputed(self):
        class Fake:
            def call(self,name,payload,validate):
                import json
                data=json.loads(payload['messages'][1]['content'])
                if '/audit_' in name:
                    obj=dict(decisions=[dict(candidate_id=c['candidate_id'],verdict='uncertain',reason='subject unknown',evidence_level='E2',evidence=c['evidence']) for c in data['candidates']])
                else:
                    obj=dict(claims=[] if name.endswith('gap_scan') else [dict(claim='B enjoys travel.',attribute='travel',certainty='asserted',mechanism='explicit',confidence=.9,evidence=[dict(turn_id=1,quote='私は旅行が好きです。')])])
                return validate(obj),'fake'
        item=dict(item_id='realpersonachat/test/A_to_B',dialogue_id='test',dataset='realpersonachat',direction='A_to_B',visible_turns=[dict(turn_id=1,text='私は旅行が好きです。')])
        pred,audit=alg.pipeline(Fake(),item)
        self.assertEqual(pred['claims'],[])
        self.assertTrue(all(c['action']=='reject_not_supported_E1_E2' for c in audit['candidates']))

    def test_admission_is_conjunction_and_never_unknown(self):
        good=dict(subject='B',subject_basis='reflection',entailment='entailed',stability='enduring')
        self.assertTrue(admission(good))
        for key,val in [('subject','A'),('subject','unknown'),('subject_basis','self_report'),('subject_basis','question'),('entailment','uncertain'),('stability','temporary'),('stability','uncertain')]:
            self.assertFalse(admission(dict(good,**{key:val})))

    def test_gate_rejects_missing_coverage_and_invented_quote(self):
        c=[dict(candidate_id='c1')];sessions={'D1':[dict(turn_id=1,text='あなたの猫ですね。')]}
        d=dict(candidate_id='c1',subject='B',subject_basis='direct_address',entailment='entailed',stability='enduring',reason='test',evidence=[dict(turn_id=1,quote='あなたの猫')])
        self.assertEqual(len(validate_gate(dict(decisions=[d]),c,sessions)),1)
        for obj in [dict(decisions=[]),dict(decisions=[dict(d,evidence=[dict(turn_id=1,quote='あなたの犬')])])]:
            with self.assertRaises(ValueError):validate_gate(obj,c,sessions)

    def test_synthesis_cannot_reference_excluded_candidate(self):
        obj=dict(traits=[dict(trait_id='T1',statement='test',references=[dict(dialogue='D1',claim_id='excluded')])],limitations='test')
        with self.assertRaises(ValueError):validate_synthesis(obj,[dict(dialogue='D1',claims=[dict(candidate_id='c1')])])

    def test_pair_audit_requires_complete_pair_coverage(self):
        pairs=[dict(left=dict(trait_id='T1'),right=dict(trait_id='T2'))]
        with self.assertRaises(ValueError):validate_pairs(dict(pairs=[]),pairs)
        self.assertEqual(validate_pairs(dict(pairs=[dict(left='T2',right='T1',relation='compatible',reason='different temporal scope')]),pairs)[0]['relation'],'compatible')

    def test_compound_scoring_requires_all_conjuncts_and_true_counterevidence(self):
        from .score_subject_v2 import compound_relation, summary
        self.assertEqual(compound_relation(['supported','insufficient']),'insufficient')
        self.assertEqual(compound_relation(['supported','supported']),'supported')
        self.assertEqual(compound_relation(['supported','contradicted']),'contradicted')
        self.assertEqual(compound_relation(['supported','mixed']),'mixed')
        self.assertEqual(compound_relation(['insufficient','mixed']),'contradicted')
        self.assertIsNone(summary(['insufficient'])['conditional_consistency_score'])

    def test_sol_judgments_require_actual_polarity_evidence(self):
        from .score_subject_v2 import validate_judgment
        atoms=dict(items=[dict(archive_id='P1',atoms=[dict(atom_id='P1.a1')])])
        inputs=dict(dialogues=[dict(dialogue='D1',visible_turns=[dict(turn_id=1,text='your cat')])])
        j=dict(archive_id='P1',atom_id='P1.a1',relation='supported',reason='test',support_references=[],contradiction_references=[],trait_refs=[])
        obj=dict(judge_model='gpt-6.1-sol',reasoning_effort='high',condition='direct',judgments=[j],trait_quality_issues=[],limitations='test')
        with self.assertRaises(ValueError):validate_judgment(obj,atoms,inputs,'direct',dict(traits=[]))
        j['support_references']=[dict(dialogue='D1',turn_id=1,quote='your cat')]
        validate_judgment(obj,atoms,inputs,'direct',dict(traits=[]))
        j['support_references'][0]['quote']='my dog'
        with self.assertRaises(ValueError):validate_judgment(obj,atoms,inputs,'direct',dict(traits=[]))
        j['support_references'][0]['quote']='your cat'
        obj['condition']='elara';j['trait_refs']=['T1']
        obj['trait_quality_issues']=[dict(trait_id='T1',issue='wrong_subject',reason='A self-report',references=[])]
        with self.assertRaises(ValueError):validate_judgment(obj,atoms,inputs,'elara',dict(traits=[dict(trait_id='T1',references=[dict(dialogue='D1',claim_id='c1')])]))


if __name__=='__main__':unittest.main()
