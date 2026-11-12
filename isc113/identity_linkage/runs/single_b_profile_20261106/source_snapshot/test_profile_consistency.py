import unittest
from .profile_consistency import validate_score, validate_traits, summarize, DIRECT, DEFAULT
from .core import load, HERE, sanitize
from .prepare import read_corpus


class ProfileTests(unittest.TestCase):
    def test_all_selected_source_dialogues_and_only_A_turns(self):
        source=read_corpus(HERE/'data/real-persona-chat.zip')
        selection=load(DEFAULT/'selection.json');b=selection['selected_b']
        source={r['dialogue_id']:r for r in source};speakers=sorted({s for r in source.values() for s in r['interlocutors']})
        self.assertEqual({r['source'] for r in selection['provenance']},{k for k,r in source.items() if b in r['interlocutors']})
        for d,p in zip(load(DEFAULT/'inputs.json')['dialogues'],selection['provenance']):
            expected=[sanitize(t['text'],speakers) for t in source[p['source']]['utterances'] if t['interlocutor_id']==p['a_id']]
            self.assertEqual([t['text'] for t in d['visible_turns']],expected)
            self.assertNotEqual(p['a_id'],b)

    def test_score_denominators_and_no_evidence(self):
        r=summarize([dict(relation=x) for x in ['supported','contradicted','mixed','insufficient']])
        self.assertEqual(r['coverage_adjusted_support_score'],37.5)
        self.assertEqual(r['conditional_consistency_score'],50)
        r=summarize([dict(relation='insufficient')])
        self.assertIsNone(r['conditional_consistency_score'])
        self.assertEqual(r['contradiction_rate'],0)

    def test_reject_unknown_or_invented_evidence_and_missing_items(self):
        archive=[dict(archive_id='P1',statement='test')]
        records=dict(dialogues=[dict(dialogue='D1',visible_turns=[dict(turn_id=1,text='your dog')])])
        obj=dict(judgments=[dict(archive_id='P1',relation='supported',reason='test',references=[dict(dialogue='D1',turn_id=1,quote='your dog')])],limitations='test')
        validate_score(obj,archive,records,'direct')
        obj['judgments'][0]['references'][0]['quote']='my cat'
        with self.assertRaises(ValueError): validate_score(obj,archive,records,'direct')
        obj['judgments'][0]['references']=[]
        with self.assertRaises(ValueError): validate_score(obj,archive,records,'direct')
        obj['judgments']=[]
        with self.assertRaises(ValueError): validate_score(obj,archive,records,'direct')
        traits=dict(traits=[dict(trait_id='T1',statement='test',basis='test',references=[dict(dialogue='D1',claim_id='absent')])],limitations='test')
        with self.assertRaises(ValueError): validate_traits(traits,[dict(dialogue='D1',claims=[])])

    def test_direct_has_no_extraction_scaffolding(self):
        for word in ('extract','attribute','trait','inventory','persona','profile'):
            self.assertNotIn(word,DIRECT.lower())


if __name__=='__main__':unittest.main()
