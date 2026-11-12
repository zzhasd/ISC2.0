"""Offline recovery of terminal complete evaluation JSON after strict parser exhaustion."""
import json
import re
from .common import BASE,read,save,jsonlines,digest
from .evaluation import predictions,reference_map,matching_content,current_matches,validate_matches

def terminal_matches(body):
    ch=body['choices'][0]
    if ch.get('finish_reason')!='stop':raise ValueError('Incomplete response')
    s=ch['message']['content'];decoder=json.JSONDecoder()
    for m in re.finditer(r'\{\s*"matches"\s*:',s):
        try:obj,end=decoder.raw_decode(s[m.start():])
        except ValueError:continue
        tail=s[m.start()+end:].strip()
        if tail not in ['', '```']:continue
        return obj
    raise ValueError('No complete terminal matches object')

def recover(dataset):
    ps=predictions(dataset);refs=reference_map(dataset);matched=current_matches(dataset,ps,refs);groups={}
    for p in ps:groups.setdefault((p['dialogue_id'],p['direction']),[]).append(p)
    raw=jsonlines(BASE/f'runs/evaluation_{dataset}/attempts.jsonl');fixed=[];missing=[]
    for k,arms in groups.items():
        if k in matched or k not in refs:continue
        inventory={digest(c['claim']):c['claim'] for arm in arms for c in arm['claims']}
        pp=[{'prediction_id':h,'claim':s} for h,s in sorted(inventory.items())]
        rr=[{'claim_id':r['claim_id'],'claim':r['claim']} for r in refs[k]]
        binding=digest(matching_content(pp,rr,k[1]));name=dataset+'/'+k[0]+'/'+k[1]+'/'+binding
        attempts=[r for r in raw if r.get('event')=='complete' and r['logical_name']==name]
        if len(attempts)<3:missing.append(k);continue
        success=False
        for r in attempts:
            if r.get('http_status')!=200:continue
            try:ms=validate_matches(terminal_matches(r['body']),pp,rr)
            except (ValueError,KeyError,TypeError):continue
            save(BASE/'evaluation/matches'/dataset/(k[0]+'__'+k[1]+'.json'),{
                'binding':binding,'matches':ms,'task_id':r['task_id'],'attempt_id':r['attempt_id'],
                'evaluation_model':'qwen3.8-flash','independent_human_correctness_review':False,
                'selection':'first schema-valid complete terminal JSON only after all strict parser attempts failed',
                'new_API_calls':0,'raw_strict_validation_flag_changed':False})
            fixed.append({'item':k,'attempt_id':r['attempt_id']});success=True;break
        if not success:missing.append(k)
    save(BASE/f'evaluation/{dataset}_parser_recovery.json',{'fixed':fixed,'remaining_missing':missing,'new_API_calls':0})
    return {'dataset':dataset,'recovered':len(fixed),'remaining_missing':len(missing)}

if __name__=='__main__':
    import sys
    print(recover(sys.argv[1]))
