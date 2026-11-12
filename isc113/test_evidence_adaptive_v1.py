"""Interface, exact migration, input isolation and deterministic filter checks."""
import ast
import copy
import importlib
import unittest
from pathlib import Path
from .common import BASE, read

module = importlib.import_module('isc113.Evidence-Adaptive v1')

class AdaptiveTests(unittest.TestCase):
    def setUp(self):
        self.item = dict(item_id='dailydialog/test/A_to_B', dialogue_id='test', direction='A_to_B', dataset='dailydialog', visible_turns=[dict(turn_id=1, text='Your dog is lovely. Are you a doctor?')])
        self.claim = dict(claim='B has a dog', attribute='pet', certainty='asserted', mechanism='presupposition', confidence=.9, evidence=[dict(turn_id=1,quote='Your dog')])

    def test_original_algorithm_ast(self):
        original = Path('D:/GoogleDownloads/inference-evidence_adaptive_v1.py')
        if not original.exists():
            self.skipTest('Original external source unavailable')
        def selected(path):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            names = {'valid_evidence','validate_claims','payload','_adaptive_filter','pipeline_evidence_adaptive'}
            return {n.name: ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names}
        self.assertEqual(selected(original), selected(Path(module.__file__)))
        ns = {}
        tree = ast.parse(original.read_text(encoding='utf-8'))
        for n in tree.body:
            if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id == 'EVIDENCE_ADAPTIVE_PROMPT' for t in n.targets):
                self.assertEqual(ast.literal_eval(n.value), module.EVIDENCE_ADAPTIVE_PROMPT)

    def test_single_call_and_interface(self):
        calls=[]
        claim=self.claim
        class Fake:
            def call(self,name,request,validate):
                calls.append((name,request))
                return validate({'claims':[copy.deepcopy(claim)]}), 'task1'
        result=module.pipeline(Fake(),self.item)
        self.assertEqual(len(calls),1)
        request=calls[0][1]
        self.assertEqual(request['thinking_budget'],256)
        self.assertEqual(request['max_tokens'],1536)
        self.assertEqual(__import__('json').loads(request['messages'][1]['content']),{'visible_turns':self.item['visible_turns'],'target':'hidden partner'})
        self.assertEqual(result[0]['method'],'evidence_adaptive_v1')
        self.assertEqual(result[0]['claims'],[dict(self.claim,evidence_span_valid=True)])
        self.assertEqual(result[0]['task_ids'],['task1'])

    def test_filter_invalid_question_duplicate_and_limit(self):
        c=copy.deepcopy(self.claim)
        bad=copy.deepcopy(c);bad['evidence'][0]['quote']='fabricated'
        question=copy.deepcopy(c);question['claim']='B is a doctor';question['evidence'][0]['quote']='Are you a doctor?'
        duplicate=copy.deepcopy(c);duplicate['claim']='B HAS a dog!';duplicate['confidence']=.8
        claims=module.validate_claims({'claims':[c,bad,question,duplicate]},self.item['visible_turns'])
        self.assertEqual(module._adaptive_filter(claims,self.item['visible_turns']),[c])
        self.assertEqual(module._adaptive_filter([],self.item['visible_turns']),[])

    def test_rejects_hidden_data_and_wrong_direction(self):
        for item in [dict(self.item,direction='B_to_A'),dict(self.item,reference=[]),dict(self.item,visible_turns=[dict(turn_id=2,text='hidden')])]:
            with self.assertRaises(ValueError):module.pipeline(None,item)
        self.assertEqual(len(read(BASE/'inputs/dailydialog.json')),298)
        from .inference import METHODS
        self.assertEqual(len(METHODS),6)

if __name__=='__main__':unittest.main()
