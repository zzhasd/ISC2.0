"""Guard preservation, source-only dataflow and cost accounting after recovery."""
import json
import unittest
from PIL import Image
from isc4_open import ROOT,read,sha,visible
from isc7_module import union_candidates,JUDGE
from isc7_run import task as judge_task
from recovery112 import OUT,DATA,chosen,valid,attempts

class RecoveryGuards(unittest.TestCase):
    def test_previously_valid_outputs_are_identical(self):
        for kind in ['isc4','isc7']:
            current={r['task_id']:r for r in read(OUT/kind/'predictions.json')}
            for base in [ROOT/'results',ROOT/'results/extension80']:
                for r in read(base/kind/'predictions.json'):
                    self.assertEqual(current[r['task_id']],r)

    def test_visible_data_and_new_judge_union(self):
        ds={d['id']:d for d in read(DATA/'dialogues.json')}
        original={e['task']['task_id']:e for e in read(OUT/'original_tasks.json')}
        for e in read(OUT/'repair_plan.json'):
            t=e['task'];self.assertEqual(t['payload'],original[t['task_id']]['task']['payload'])
            body=json.loads(t['payload']['messages'][1]['content'])
            expected=visible(ds[t['dialogue_id']],t['k']) if e['kind']=='isc4' else visible(ds[t['dialogue_id']])
            self.assertEqual(body['visible_A'],expected)
        for t in read(OUT/'new_dependent_requests.json'):
            sources=[original[i] for i in t['source_task_ids']]
            cs=[valid(e['task'],chosen(e['task'],'isc7',e['original_response']),'isc7') for e in sources]
            content={'visible_A':visible(ds[t['dialogue_id']]),'candidates':union_candidates(*cs)}
            self.assertEqual(t,judge_task(t['dialogue_id'],t['arm'],'judge',JUDGE,content,t['source_task_ids']))

    def test_actual_cost_ledger_and_print_resolution(self):
        ledger=read(OUT/'isc7/execution_audit.json');selected=read(OUT/'isc7/selected_execution_audit.json')
        new=attempts()
        self.assertEqual(len(ledger),889+sum(r['kind']=='isc7' for r in new))
        self.assertEqual(len(selected),112*8)
        self.assertEqual(len(read(OUT/'isc7/predictions.json')),112*4)
        self.assertEqual(len(read(OUT/'isc4/predictions.json')),459)
        self.assertEqual(read(OUT/'execution_status.json')['total_actual_calls'],1348+len(new))
        self.assertEqual(read(OUT/'remaining_missing.json'),[])
        for stem in ['图1_三个主实验_论文分面图','图2_口径对齐与可靠性成本']:
            for ext in ['png','tiff']:
                with Image.open(OUT/'paper_figures'/f'{stem}.{ext}') as im:
                    self.assertTrue(all(abs(float(v)-600)<1 for v in im.info['dpi']))
            self.assertIn('<svg',(OUT/'paper_figures'/f'{stem}.svg').read_text(encoding='utf-8'))

if __name__=='__main__':unittest.main()
