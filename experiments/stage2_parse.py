"""Deterministic structural normalization; never invent missing labels/targets."""
import json
import re

def decode_response(text):
 try:
  return json.loads(text),False
 except json.JSONDecodeError:
  # Recover only complete target objects already present verbatim. Do not close
  # strings/brackets, decode guessed escapes, or fill a missing target.
  decoder=json.JSONDecoder();recovered=[]
  for match in re.finditer(r'\{\s*"target"\s*:',text):
   try:obj,end=decoder.raw_decode(text,match.start())
   except json.JSONDecodeError:continue
   if isinstance(obj,dict) and 'target' in obj and 'facts' in obj:recovered.append(obj)
  if not recovered:raise
  return {'targets':recovered},True

def normalize_targets(output,expected):
 """Recover explicit target/facts associations from several malformed arrays.

 All changes are structural: every emitted target, id, label and evidence list
 must already occur in the response. Missing targets remain missing. The caller
 retains raw responses and reports strict-format failures and normalization.
 """
 targets=output.get('targets')
 if not isinstance(targets,list):raise ValueError('targets is not a list')
 if len(targets)==len(expected) and all(isinstance(x,dict) and 'target' in x and 'facts' in x for x in targets) and {x['target'] for x in targets}==expected:
  return targets,False
 result=[];pending=None;i=0
 while i<len(targets):
  x=targets[i]
  if isinstance(x,dict) and 'target' in x and 'facts' in x:
   result.append(x);pending=None;i+=1;continue
  if isinstance(x,str) and x in expected:
   pending=x;i+=1;continue
  if x=='target' and i+1<len(targets) and targets[i+1] in expected:
   pending=targets[i+1];i+=2;continue
  if pending and isinstance(x,dict) and 'facts' in x and 'target' not in x:
   result.append({'target':pending,'facts':x['facts']});pending=None;i+=1;continue
  if pending and x=='facts' and i+1<len(targets) and isinstance(targets[i+1],list):
   result.append({'target':pending,'facts':targets[i+1]});pending=None;i+=2;continue
  if pending and x=='facts':
   # Flattened exact field sequence: id,<value>,label,<value>,evidence_turns,<list>.
   j=i+1;facts=[]
   while j+5<len(targets) and targets[j]=='id' and targets[j+2]=='label' and targets[j+4]=='evidence_turns' and isinstance(targets[j+5],list):
    facts.append({'id':targets[j+1],'label':targets[j+3],'evidence_turns':targets[j+5]});j+=6
   if facts:
    result.append({'target':pending,'facts':facts});pending=None;i=j;continue
  if result:
   # Retain the already complete explicit target(s). Ambiguous remainder is
   # missing data, never assigned to a target by positional guessing.
   break
  raise ValueError('Unrecognized/ambiguous malformed target structure')
 if not result:raise ValueError('No target could be parsed')
 if len({x['target'] for x in result})!=len(result):raise ValueError('Duplicate normalized target')
 if not {x['target'] for x in result}<=expected:raise ValueError('Unexpected normalized target')
 return result,True
