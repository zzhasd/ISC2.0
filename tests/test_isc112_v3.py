import unittest
import json
from isc112_v3.core import render
from isc112_v3.run import OUT, DATA, read, verify, blocked


class RevisionFlowTests(unittest.TestCase):
    def test_inspection_fallback_is_specific_and_not_a_retry(self):
        task={'task_id':'one'}
        rejection={'task_id':'one','http_status':400,'body':{'error':{'code':'data_inspection_failed'}}}
        self.assertTrue(blocked(task,[rejection]))
        self.assertFalse(blocked({'task_id':'other'},[rejection]))
        self.assertFalse(blocked(task,[{**rejection,'http_status':429}]))
        self.assertFalse(blocked(task,[{**rejection,'body':{'error':{'code':'invalid_request'}}}]))

    def test_actual_payloads_are_A_and_A_derived_items_only(self):
        verify()
        tasks=read(OUT/'requests.json');aa={d['id']:d['visible_A'] for d in read(DATA/'visible_A.json')}
        self.assertEqual(len(tasks),112)
        for t in tasks:
            u=json.loads(t['payload']['messages'][1]['content'])
            self.assertEqual(set(u),{'visible_A','prior_items'})
            self.assertEqual(u['visible_A'],aa[t['dialogue_id']])
            for p in u['prior_items']:self.assertEqual(set(p),{'id','claim','time','evidence_turns'})

    def test_proposal_is_accepted_with_B_recipient(self):
        item={'id':'a1','claim':'B is advised to inspect a valve tomorrow.','category':'plan','holder':'B','scope':'profile',
              'support':'explicit','status':'active','time':'tomorrow','evidence_turns':[1],'duplicate_of':None}
        out=render({'checked_turns':[1],'items':[item]},[{'turn':1,'text':'I suggest you inspect the valve tomorrow.'}],[])
        self.assertEqual(len(out['facts']),1)
        self.assertIn('advised',out['facts'][0]['claim'])

    def test_missing_prior_ids_and_B_evidence_are_rejected(self):
        with self.assertRaises(ValueError):render({'checked_turns':[1],'items':[]},[{'turn':1,'text':'Visible'}],[{'id':'b1'}])
        item={'id':'b1','claim':'B knows.','category':'knowledge','holder':'B','scope':'profile','support':'unknown',
              'status':'unresolved','time':'unspecified','evidence_turns':[2]}
        with self.assertRaises(ValueError):render({'checked_turns':[1],'items':[item]},[{'turn':1,'text':'Visible'}],[{'id':'b1'}])


if __name__=='__main__':unittest.main()
