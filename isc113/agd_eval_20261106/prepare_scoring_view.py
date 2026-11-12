"""Preserve raw judgments; apply one fixed completeness/weight policy to all methods."""
from pathlib import Path
import shutil,hashlib
import agd_eval as a
ROOT=Path(__file__).resolve().parent
def main():
    src=ROOT/'final_eval';dst=ROOT/'scored_eval';dst.mkdir(exist_ok=True)
    assert (src/'audit.json').exists(),'Run audit_results.py first'
    shutil.copy2(src/'data.json',dst/'data.json')
    changed=0;fields=0
    for stage in ['sweep','pred','gold','sweep_support','pool']:
        for f in (src/'judgments'/stage).glob('*.json'):
            target=dst/'judgments'/stage/f.name;target.parent.mkdir(parents=True,exist_ok=True)
            if stage!='pool':shutil.copy2(f,target);continue
            obj=a.read(f)
            for fact in obj['facts']:
                for slot in fact['slots']:
                    fields+=1;changed+=int(not slot['required'] or slot['weight']!=(2 if slot['core'] else 1))
                    slot['judge_required']=slot['required'];slot['judge_weight']=slot['weight']
                    slot['required']=True;slot['weight']=2 if slot['core'] else 1
            obj['_scoring_policy']={'all_slots_required':True,'core_weight':2,'other_weight':1,'raw_pool_sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
            a.dump(target,obj)
    a.dump(dst/'scoring_policy.json',{'all_slots_required':True,'core_weight':2,'other_weight':1,'fields':fields,'fields_with_changed_flag_or_weight':changed,'raw_judgments_preserved':'../final_eval','human_calibrated':False})
    print('SCORING VIEW',fields,'fields;',changed,'normalized flags/weights')
if __name__=='__main__':main()
