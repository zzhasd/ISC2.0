"""Offline-only finishing stage. No credentials and no network calls."""
from isc3_common import *
import hashlib
import importlib.metadata
import platform

def freeze_delivery():
    save(OUT/'environment.json',{'python':platform.python_version(),'platform':platform.platform(),
        'packages':{p:importlib.metadata.version(p) for p in ['numpy','scipy','scikit-learn','requests','matplotlib']}})
    paths=[ROOT/'ISC3_PROTOCOL.md',ROOT/'ISC3_RECONSTRUCTION_V2_PROTOCOL.md',*ROOT.glob('experiments/isc3_*.py'),ROOT/'experiments/test_isc3.py',
           ROOT/'experiments/revision_prepare.py',ROOT/'experiments/revision_api.py',
           ROOT/'data/stage2/inventory.json',ROOT/'data/source.json',*DATA.glob('*.json')]
    for directory in ['initial','dependent','reconstruction_v2_generate','reconstruction_v2_extract']:
        paths.extend(p for p in (OUT/directory).glob('*') if p.name in ['requests.json','api_raw.jsonl','attempts.jsonl','run_status.json'])
    paths.extend(p for p in OUT.glob('*') if p.is_file() and p.suffix in ['.json','.csv','.png','.md'] and p.name!='manifest_final.json')
    paths.extend(p for p in (OUT/'human_review').glob('*') if p.is_file())
    save(OUT/'manifest_final.json',{'sha256':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'note':'Console logs excluded because their final flush can occur after this file is written. This hashes final artifacts; no secrets are stored.'})

def main():
    required=['initial','dependent']
    if (OUT/'reconstruction_v2_generate/requests.json').exists():required+=['reconstruction_v2_generate','reconstruction_v2_extract']
    for name in required:
        if not read(OUT/name/'run_status.json')['complete']:
            raise SystemExit(f'Prerequisite {name} is incomplete')
    import isc3_local_reconstruction_audit as reconstruction
    reconstruction.main()
    import isc3_analyze
    import isc3_report
    isc3_analyze.main();isc3_report.main()
    save(OUT/'delivery_status.json',{'model_calls_finished':True,'offline_analysis_finished':True,
        'secondary_external_reconstruction_audit':'Rejected by automatic approval review; replaced by offline canonical-phrase audit of fictional structured cases.',
        'human_review_finished':False,'independent_model_family_finished':False,
        'report':'results/isc3/实验报告.md'})
    freeze_delivery()

if __name__=='__main__':main()
