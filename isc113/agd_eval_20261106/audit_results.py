"""Fail closed before final scoring; no API calls."""
from pathlib import Path
import hashlib,json
import agd_eval as a
from run_pipeline import validate_pool
ROOT=Path(__file__).resolve().parent;W=ROOT/'final_eval'
def main():
    data=a.read(W/'data.json');ds=data['dialogues'];assert len(ds)==298
    assert sum(data['prediction_counts'].values())==7868
    assert sum(len(d['pred_candidates']) for d in ds.values())==6915
    for did,d in ds.items():
        turns=d['visible_turns']
        a.validate_sweep(a.read(a.path_for(W,'sweep',did)),turns)
        for stage,candidates in [('pred',d['pred_candidates']),('gold',d['gold_candidates'])]:
            a.validate_support(a.read(a.path_for(W,stage,did)),candidates,turns)
        sw=a.read(a.path_for(W,'sweep',did))['claims']
        a.validate_support(a.read(a.path_for(W,'sweep_support',did)),[{'id':'s_'+did+'_'+str(i)} for i in range(len(sw))],turns)
        validate_pool(a.read(a.path_for(W,'pool',did)),a.pool_atoms(W,did))
    calls=0
    for p in (W/'calls').rglob('*.json'):
        c=a.read(p);binding=c['binding'];stage=p.parts[-3];payload=binding['payload']
        assert set(payload).issubset({'visible_turns','candidates','atoms'})
        assert all(set(t)=={'turn_id','text'} for t in payload['visible_turns'])
        for x in payload.get('candidates',[]):assert set(x)=={'id','claim'} and x['id'].startswith('c')
        for x in payload.get('atoms',[]):assert x['atom_id'].startswith('a') and 'algorithm' not in x
        assert binding['model']=='qwen3.8-max-0902'
        assert binding['system']==(a.SWEEP_SYSTEM if stage=='sweep' else a.POOL_SYSTEM if stage=='pool' else a.SUPPORT_SYSTEM)
        assert binding['thinking_budget']==(8192 if stage=='pool' else 4096)
        calls+=1
    for rel,h in a.read(ROOT/'source_manifest.json').items():assert hashlib.sha256((ROOT.parent/rel).read_bytes()).hexdigest()==h
    result={'dialogues':298,'original_predictions':7868,'unique_candidates':6915,'validated_cached_calls':calls,'original_hashes_unchanged':True,'blinding_schema_passed':True,'complete_stages':5,'human_calibrated':False}
    a.dump(W/'audit.json',result);print(json.dumps(result))
if __name__=='__main__':main()
