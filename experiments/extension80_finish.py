"""Completion and preservation audit; refuses partial-response/partial-review delivery."""
import hashlib
import json
from pathlib import Path
from isc4_open import ROOT,read,save,sha
from isc4_review import review_key as key4
from isc7_analyze import review_key as key7
from extension80 import DATA,OUT

def lines(p):return [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines()]

def main():
    checks={};actual=0;allraw=[]
    for phase in ['isc4/baseline','isc7/initial','isc7/dependent']:
        base=OUT/phase;ts=read(base/'requests.json');rs=lines(base/'api_raw.jsonl');ats=lines(base/'attempts.jsonl')
        checks[phase+'_all_attempted_once']=len(rs)==len(ats)==len(ts)==len({r['task_id'] for r in rs})
        checks[phase+'_task_alignment']={r['task_id'] for r in rs}=={r['task_id'] for r in ts}=={r['task_id'] for r in ats}
        checks[phase+'_request_integrity']=all(sha(t['payload'])==t['request_sha256'] and t['task_id']==t['request_sha256'][:24] for t in ts)
        actual+=len(rs);allraw+=rs
    checks['fixed_request_caps']=len(lines(OUT/'isc4/baseline/api_raw.jsonl'))==306 and len(lines(OUT/'isc7/initial/api_raw.jsonl'))==480 and len(lines(OUT/'isc7/dependent/api_raw.jsonl'))<=160
    for kind,key,name in [('isc4',key4,'assistant_semantic_review.json'),('isc7',key7,'semantic_review.json')]:
        ps=read(OUT/kind/'predictions.json');rs=read(OUT/kind/name)
        expected={key(p['dialogue_id'],f) for p in ps for f in p['facts']}
        checks[kind+'_all_final_claims_reviewed']=expected=={r['review_id'] for r in rs} and len(rs)==len(expected)
        checks[kind+'_no_unreviewed_decisions']=all(r.get('rationale') and r.get('A_grounded') in [True,False] and r.get('verdict') not in [None,'unreviewed'] for r in rs)
        save(OUT/kind/'semantic_review_manifest.json',{'unique_reviews':len(rs),'review_sha256':sha(rs),
            'queue_sha256':sha(read(OUT/kind/'review_queue.json')),'reviewer':'current conversational assistant, same reference author',
            'independent_human_gold':False,'all_expected_claims_reviewed':checks[kind+'_all_final_claims_reviewed']})
    r7=lines(OUT/'isc7/initial/api_raw.jsonl')+lines(OUT/'isc7/dependent/api_raw.jsonl')
    checks['factorial_export_matches_all_raw']={r['task_id'] for r in r7}=={r['task_id'] for r in read(OUT/'isc7/execution_audit.json')}
    old=read(DATA/'manifest.json')['original_artifact_hashes']
    checks['all_original_artifacts_unchanged']=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in old.items())
    checks['reference_frozen_before_first_new_request']=read(DATA/'reference_manifest.json')['created_utc']<min(r['started_utc'] for r in allraw)
    checks['reference_hash_preserved']=sha(read(DATA/'reference.json'))==read(DATA/'reference_manifest.json')['reference_sha256']
    ds=read(DATA/'dialogues.json');oldids={d['id'] for d in read(ROOT/'data/isc4/dialogues.json')}
    checks['112_distinct_dialogues']=len(ds)==80 and len(oldids|{d['id'] for d in ds})==112
    # Only inspect task-created artifacts, never print credential-like strings.
    scanned=[p for base in [DATA,OUT,ROOT/'results/merged112',ROOT/'data/merged112'] for p in base.rglob('*') if p.is_file() and p.suffix in ['.py','.json','.jsonl','.md','.csv']]
    checks['credential_prefix_absent_from_artifacts']=not any('sk-ws-' in p.read_text(encoding='utf-8-sig') for p in scanned)
    for tag,base in [('new',OUT),('merged',ROOT/'results/merged112')]:
        rows=read(base/'isc7/dialogue_scores.json');common=read(base/'isc7/summary.json')['common_ids'];index={(r['dialogue_id'],r['arm']):r for r in rows}
        checks[tag+'_paired_cohort_valid']=all(index[d,a]['valid'] for d in common for a in ['direct_off','direct_on','dual_off','dual_on'])
    result={'complete':all(checks.values()),'checks':checks,'new_actual_calls':actual,'including_old_actual_calls':actual+408,
        'original_files_verified':len(old),'new_dialogues':80,'merged_unique_dialogues':112,
        'current_script_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'experiments').glob('extension80*.py')},
        'operational_runner_change':'After a recorded 429, skip failed attempt and pace never-attempted requests at 2.5 seconds. Inference payloads unchanged.',
        'http_failures':[{'task_id':r['task_id'],'http_status':r.get('http_status'),'error_type':r.get('error_type')} for r in allraw if r.get('http_status')!=200]}
    save(OUT/'final_checks.json',result);save(ROOT/'results/merged112/final_checks.json',result)
    assert result['complete'],{k:v for k,v in checks.items() if not v}
    print({'complete':True,'checks_passed':len(checks),'new_calls':actual,'total_calls':actual+408})

if __name__=='__main__':main()
