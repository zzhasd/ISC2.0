import tempfile
from pathlib import Path
from types import SimpleNamespace
import agd_eval as a

def main():
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
        w=Path(temp);ds={}
        for did in ['d1','d2']:
            preds=[]
            if did=='d1':
                for m in a.METHODS:
                    preds.extend([{'id':m+':0','algorithm':m,'claim':'B reads since yesterday and lives in X','candidate_id':'p1'}, {'id':m+':1','algorithm':m,'claim':'B reads intently','candidate_id':'p2'}])
            ds[did]={'predictions':preds,'pred_candidates':[{'id':'p1'},{'id':'p2'}] if preds else []}
            atoms=[{'id':'p1','atoms':[{'text':'B reads since yesterday','label':'E1'},{'text':'B lives in X','label':'E4'}]},{'id':'p2','atoms':[{'text':'B reads intently','label':'E1'}]}] if preds else []
            a.dump(a.path_for(w,'pred',did),{'items':atoms})
            for s in ['gold','sweep_support']:a.dump(a.path_for(w,s,did),{'items':[]})
            a.dump(a.path_for(w,'sweep',did),{'claims':[]})
            slots=[{'id':'core','required':True,'core':True,'weight':2},{'id':'time','required':True,'core':False,'weight':1},{'id':'manner','required':True,'core':False,'weight':1}]
            members=[{'atom_id':'p1::0','slot_ids':['core','time']},{'atom_id':'p2::0','slot_ids':['core','manner']}] if preds else []
            a.dump(a.path_for(w,'pool',did),{'facts':[{'id':'f1','canonical_claim':'B reads intently since yesterday','level':'E1','slots':slots,'members':members}]})
        a.dump(w/'data.json',{'dialogues':ds})
        a.score(SimpleNamespace(work=str(w),allow_incomplete=False,bootstraps=30))
        summary=a.read(w/'results/summary.json')
        for m,r in summary.items():
            assert r['n_dialogues']==2 and r['denom_pool']==2
            assert r['P_raw']==.5 and abs(r['P_atom']-2/3)<1e-12
            assert r['R_full']==.5 and r['R_core']==.5 and r['slot_coverage']==.5
            assert r['useful_yield']==.5
        assert len(summary)==6
    print('PASS: composite precision, own-method slot union, zero-output shared denominator, six-method micro scores')

if __name__=='__main__':main()
