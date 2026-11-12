import copy
import unittest
from .portrait_summary import deduplicate, materialize, validate_portraits, DIRECT


class PortraitSummaryTests(unittest.TestCase):
    def test_exact_dedup_preserves_all_variants_and_does_not_normalize(self):
        records=[dict(source_id=str(i),claim=dict(claim=text,attribute=f'detail{i}',certainty='qualified')) for i,text in enumerate(['B likes X','B likes X','B likes X ','b likes X','B likes  X'])]
        before=copy.deepcopy(records);u=deduplicate(records)
        self.assertEqual(len(u),4);self.assertEqual(len(u[0]['members']),2)
        self.assertEqual(records,before)
        self.assertEqual(sorted(m['source_id'] for x in u for m in x['members']),['0','1','2','3','4'])
        self.assertEqual(u[0]['members'][1]['claim']['attribute'],'detail1')

    def test_partition_requires_every_unique_attribute_once(self):
        u=[dict(unique_id='U001'),dict(unique_id='U002')]
        good=dict(portraits=[dict(portrait_id='R1',statement='test',unique_ids=['U001','U002'])],limitations='test')
        validate_portraits(good,'summary',dict(dialogues=[]),u)
        for ids in [['U001'],['U001','U001'],['U001','U002','U002'],['U001','bad']]:
            bad=copy.deepcopy(good);bad['portraits'][0]['unique_ids']=ids
            with self.assertRaises(ValueError):validate_portraits(bad,'summary',dict(dialogues=[]),u)

    def test_materialized_details_are_verbatim(self):
        rs=[dict(source_id='D1/c1',claim=dict(claim='B may like X',attribute='qualified X',certainty='qualified',evidence=[dict(turn_id=1,quote='X?')]))]
        u=deduplicate(rs);obj=dict(portraits=[dict(portrait_id='R1',statement='possible X',unique_ids=['U001'])],limitations='test')
        final=materialize(obj,u)
        self.assertEqual(final['portraits'][0]['source_details'][0]['members'],rs)

    def test_direct_quotes_must_match_original_without_marker(self):
        x=dict(dialogues=[dict(dialogue='D1',visible_turns=[dict(turn_id=1,text='あなたの猫')])])
        o=dict(portraits=[dict(portrait_id='R1',statement='B has a cat',evidence=[dict(dialogue='D1',turn_id=1,quote='あなたの猫')])],limitations='test')
        validate_portraits(o,'direct',x,[])
        for q in ['A says: あなたの猫','あなたの犬']:
            o['portraits'][0]['evidence'][0]['quote']=q
            with self.assertRaises(ValueError):validate_portraits(o,'direct',x,[])

    def test_direct_prompt_has_no_intermediate_extraction_scaffolding(self):
        for word in ('extract','attribute','inventory','candidate','persona','archive','atomic'):
            self.assertNotIn(word,DIRECT.lower())

    def test_score_aggregate_distinguishes_unknown_and_counterevidence(self):
        from .score_portrait_summary import aggregate
        r=aggregate([dict(relation=k) for k in ['supported','partial','mixed','contradicted','not_covered']])
        self.assertEqual(r['all_item_alignment_score'],40)
        self.assertEqual(r['covered_consistency_score'],50)
        self.assertEqual(r['coverage'],.8)
        self.assertIsNone(aggregate([dict(relation='not_covered')])['covered_consistency_score'])

    def test_scoring_requires_full_coverage_real_refs_and_actual_contradiction(self):
        from .score_portrait_summary import validate_score
        packet=dict(portraits=[dict(portrait_id='R1',statement='test')],archive=[dict(archive_id='P1',statement='test')])
        obj=dict(judge_model='gpt-6.1-sol',reasoning_effort='high',condition='direct',portrait_judgments=[dict(portrait_id='R1',relation='partial',archive_refs=['P1'],reason='detail missing',contradiction_pair=None)],archive_judgments=[dict(archive_id='P1',relation='partial',portrait_refs=['R1'],reason='detail missing',contradiction_pair=None)],fidelity_checks=[],limitations='test')
        validate_score(obj,packet,'direct')
        bad=copy.deepcopy(obj);bad['archive_judgments']=[]
        with self.assertRaises(ValueError):validate_score(bad,packet,'direct')
        bad=copy.deepcopy(obj);bad['portrait_judgments'][0]['archive_refs']=['P999']
        with self.assertRaises(ValueError):validate_score(bad,packet,'direct')
        bad=copy.deepcopy(obj);bad['portrait_judgments'][0]['relation']='contradicted'
        with self.assertRaises(ValueError):validate_score(bad,packet,'direct')

    def test_full_fidelity_uses_complete_portrait_ids_and_own_detail_ids(self):
        from .score_portrait_summary import validate_full_fidelity
        ps=[dict(portrait_id='R1',source_details=[dict(unique_id='U001')])]
        obj=dict(judge_model='gpt-6.1-sol',reasoning_effort='high',source_context='full_generation_input_including_evidence',checks=[dict(portrait_id='R1',fidelity='faithful',reason='test',detail_refs=['U001'])])
        validate_full_fidelity(obj,ps)
        bad=copy.deepcopy(obj);bad['checks'][0]['detail_refs']=['U999']
        with self.assertRaises(ValueError):validate_full_fidelity(bad,ps)


if __name__=='__main__':unittest.main()
