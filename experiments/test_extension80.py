import hashlib
import json
import unittest
from isc4_open import ROOT,read,sha,visible,task
from isc7_run import task as task7
from isc7_module import DIRECT,GLOBAL,LOCAL
from extension80 import DATA,OUT,normalized

class ExtensionGuards(unittest.TestCase):
    def test_new_source_and_preservation(self):
        m=read(DATA/'manifest.json');ds=read(DATA/'dialogues.json')
        source={r['id']:r for r in map(json.loads,(ROOT/'data/dailydialog.jsonl').read_text(encoding='utf-8').splitlines())}
        self.assertEqual(len(ds),80);self.assertEqual(len({d['id'] for d in ds}),80)
        self.assertFalse({d['id'] for d in ds}&set(m['excluded_used_ids']))
        self.assertEqual(len({normalized(d['turns']) for d in ds}),80)
        for d in ds:self.assertEqual(d['turns'],source[d['id']]['turns'])
        for p,h in m['original_artifact_hashes'].items():self.assertEqual(hashlib.sha256((ROOT/p).read_bytes()).hexdigest(),h)

    def test_all_prefixes_exact_original_payload(self):
        ds={d['id']:d for d in read(DATA/'dialogues.json')};ts=read(OUT/'isc4/baseline/requests.json')
        self.assertEqual(len(ts),306)
        self.assertEqual({(t['dialogue_id'],t['k']) for t in ts},{(d['id'],k) for d in ds.values() for k in range(1,len(visible(d))+1)})
        for t in ts:self.assertEqual(t,task(ds[t['dialogue_id']],t['k']))

    def test_factorial_exact_original_payload(self):
        ds={d['id']:d for d in read(DATA/'dialogues.json')};ts=read(OUT/'isc7/initial/requests.json')
        self.assertEqual(len(ts),480)
        for t in ts:
            s={'direct':DIRECT,'global':GLOBAL,'local':LOCAL}[t['stage']]
            self.assertEqual(t,task7(t['dialogue_id'],t['arm'],t['stage'],s,{'visible_A':visible(ds[t['dialogue_id']])}))

    def test_frozen_reference_evidence_and_timing(self):
        ds={d['id']:d for d in read(DATA/'dialogues.json')};refs=read(DATA/'reference.json')
        self.assertEqual({r['dialogue_id'] for r in refs},set(ds))
        self.assertEqual(sha(refs),read(DATA/'reference_manifest.json')['reference_sha256'])
        for r in refs:
            for f in r['facts']:
                for e in f['full_evidence']:self.assertEqual(e['quote'],ds[r['dialogue_id']]['turns'][e['turn']-1])
                self.assertTrue(all(n%2 for s in f['A_support_sets'] for n in s))
        ap=OUT/'isc4/baseline/attempts.jsonl'
        if ap.exists():
            first=json.loads(ap.read_text(encoding='utf-8').splitlines()[0])['utc']
            self.assertLess(read(DATA/'reference_manifest.json')['created_utc'],first)

if __name__=='__main__':unittest.main()
