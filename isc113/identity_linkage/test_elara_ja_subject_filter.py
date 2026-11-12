"""Regression tests for the fail-open-on-uncertainty A->B self attribution filter.

Tests validate policy enforcement / data flow. They do not measure the LLM's
Japanese subject-resolution accuracy; that requires independently annotated data.
"""
import importlib.util
import pathlib
import unittest

path=pathlib.Path(__file__).with_name('elara_ja_subject_filter.py')
spec=importlib.util.spec_from_file_location('subject_filter',path)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class JapaneseSubjectFilterTests(unittest.TestCase):
    def record(self,sid,quote,claim,turn_id=1):
        return {'source_id':sid,'dialogue':'D1','claim':{'claim':claim,
            'attribute':claim,'evidence':[{'turn_id':turn_id,'quote':quote}]}}

    def check(self, quote, claim, owner, decision, code, expect,
              self_quote=None, evidence_override=None):
        inputs={'dialogues':[{'dialogue':'D1','visible_turns':[
            {'turn_id':1,'text':quote}]}]}
        rec=self.record('D1/c1',evidence_override or quote,claim)
        out={'decisions':[{'source_id':'D1/c1','actual_owner':owner,
            'decision':decision,'reason_code':code,
            'self_quote':(quote if self_quote is None and decision=='DROP' else
                          (self_quote or '')),
            'reason':'test classification'}]}
        dec=mod.validate_model_output(out,None,[rec],mod.get_turns(inputs))[0]
        self.assertEqual(dec['decision'],expect)
        return dec

    def test_explicit_a_self_dropped(self):
        self.check('私は料理が得意ではないので','B is poor at cooking.',
                   'A','DROP','A_SELF','DROP')

    def test_a_zero_subject_honeymoon_dropped(self):
        self.check('新婚旅行でハワイに行っただけですね。','B went to Hawaii for honeymoon.',
                   'A','DROP','A_ZERO_SELF','DROP')

    def test_a_zero_subject_liking_dropped_not_mo_shared(self):
        self.check('焼き芋の香りも好きです','B likes the smell of roasted sweet potatoes.',
                   'A','DROP','A_ZERO_SELF','DROP')

    def test_b_about_presupposition_kept(self):
        self.check('どんな絵を描かれるのですか？','B draws pictures.',
                   'B','KEEP','B_REFERENT','KEEP')

    def test_subject_unknown_is_kept(self):
        self.check('そうですね。','B is a student.',
                   'UNKNOWN','KEEP','UNRESOLVED','KEEP')

    def test_unknown_subject_model_drop_is_overridden_to_keep(self):
        d=self.check('そうですね。','B is a student.',
                     'UNKNOWN','DROP','UNRESOLVED','KEEP')
        self.assertEqual(d['raw_decision'],'DROP')
        self.assertEqual(d['override_reason'],'NOT_CLEAR_A_SELF_OR_INVALID_QUOTE')

    def test_shared_first_person_mo_about_b_kept(self):
        self.check('私も20代です','B is in their twenties.',
                   'UNKNOWN','KEEP','B_SHARED_INFERRED','KEEP')

    def test_third_party_and_generic_not_in_scope(self):
        self.check('友達が犬を飼っています。','B has a dog.',
                   'THIRD','DROP','THIRD_PARTY','KEEP')
        self.check('一般的には温泉が人気です。','B likes hot springs.',
                   'GENERIC','DROP','GENERIC','KEEP')

    def test_weak_b_evidence_still_kept(self):
        self.check('なるほど！','B once visited Kyoto.',
                   'UNKNOWN','KEEP','INVALID_EVIDENCE','KEEP')

    def test_mixed_claim_with_clear_a_detail_dropped(self):
        self.check('私は大阪出身ですが、あなたは東京ですよね。',
                   'B is from Tokyo and grew up in Osaka.',
                   'MIXED','DROP','MIXED_A_B','DROP',self_quote='私は大阪出身')

    def test_a_quote_must_exist_in_original_cited_source(self):
        self.check('私は大阪出身です','B is from Osaka.',
                   'A','DROP','A_SELF','KEEP',self_quote='私は京都出身')

    def test_invalid_evidence_does_not_authorize_drop(self):
        d=self.check('私は料理が得意ではないので','B is poor at cooking.',
                     'A','DROP','A_SELF','KEEP',evidence_override='私は料理が得意')
        self.assertTrue(d['source_evidence_valid'])  # partial quote is valid
        # If the model's self_quote is absent from the partial cited quote,
        # the DROP is overridden even if it occurs in a wider turn.
        d=self.check('私は料理が得意ではないので','B is poor at cooking.',
                     'A','DROP','A_SELF','KEEP',
                     self_quote='私は料理が得意ではないので',evidence_override='私は料理が得意')
        self.assertTrue(d['source_evidence_valid'])

    def test_inconsistent_a_owner_reason_does_not_delete(self):
        self.check('私は大阪出身です','B is from Osaka.',
                   'B','DROP','B_REFERENT','KEEP')

    def test_keeping_record_does_not_need_evidence_quote(self):
        self.check('私は大阪出身です','B is from Osaka.',
                   'UNKNOWN','KEEP','UNRESOLVED','KEEP',self_quote='')

    def test_filter_records_removes_each_source_pre_dedup(self):
        inputs={'dialogues':[{'dialogue':'D1','visible_turns':[
            {'turn_id':1,'text':'私は教師です。'},
            {'turn_id':2,'text':'教師なんですね。'}]}]}
        r1=self.record('D1/c1','私は教師です。','B is a teacher',1)
        r2=self.record('D1/c2','教師なんですね。','B is a teacher',2)
        def judge(packet):
            return {'decisions':[
                {'source_id':r['source_id'], 'actual_owner':('A' if r['source_id']=='D1/c1' else 'B'),
                 'decision':('DROP' if r['source_id']=='D1/c1' else 'KEEP'),
                 'reason_code':('A_SELF' if r['source_id']=='D1/c1' else 'B_REFERENT'),
                 'self_quote':('私は教師です。' if r['source_id']=='D1/c1' else ''),
                 'reason':'test'} for r in packet['candidates']]}
        kept,decisions=mod.filter_records(inputs,[r1,r2],judge)
        self.assertEqual([x['source_id'] for x in kept],['D1/c2'])
        unique=mod.exact_dedup(kept)
        self.assertEqual(len(unique),1)
        self.assertEqual([x['source_id'] for x in unique[0]['members']],['D1/c2'])
        self.assertEqual([x['decision'] for x in decisions],['DROP','KEEP'])

    def test_bad_model_output_raises_not_silently_processes(self):
        inputs={'dialogues':[{'dialogue':'D1','visible_turns':[{'turn_id':1,'text':'私は教師です。'}]}]}
        rec=self.record('D1/c1','私は教師です。','B is a teacher')
        with self.assertRaises(ValueError):
            mod.validate_model_output({'decisions':[]},None,[rec],mod.get_turns(inputs))

if __name__=='__main__':unittest.main()
