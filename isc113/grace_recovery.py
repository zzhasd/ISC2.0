"""Auditable, conservative recovery of GRACE v1 *format-invalid* API replies.

Never consults gold/reference files, and never invents evidence. Kept claims
must pass GRACE's original semantic-format validators and quote alignment.
Only outputs with complete JSON bodies and finish_reason='stop' are considered.
"""
from __future__ import annotations
import json
import re
from copy import deepcopy
from typing import Any


def embedded_object(body):
    if not isinstance(body, dict):
        return None
    choices = body.get('choices') or []
    if not choices or choices[0].get('finish_reason') != 'stop':
        return None
    message = choices[0].get('message') or {}
    content = message.get('content')
    if not isinstance(content, str):
        return None
    parser = json.JSONDecoder()
    for found in re.finditer(r'\{', content):
        try:
            obj, _ = parser.raw_decode(content, found.start())
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict) and ('claims' in obj or 'decisions' in obj):
            return obj
    return None


def _stage(logical_name):
    if '/grace_v1/' in logical_name:
        return logical_name.split('/grace_v1/', 1)[1].split('/format_retry_', 1)[0]
    return ''


def normalize(obj: Any, logical_name: str, payload: dict, algorithm):
    """Return (schema-normalized object, list of strictly format-level actions).

    For unrecoverable decision structures, return None, never fabricate a model
    judgment. Critically, neither claim text nor quoted text is invented.
    """
    if not isinstance(obj, dict):
        return None, []
    stage = _stage(logical_name)
    o = deepcopy(obj)
    action = []
    if stage.startswith(('E1_', 'E2_', 'targeted_anchor_rescue')):
        cs = o.get('claims')
        if not isinstance(cs, list) or len(cs) > 24:
            return None, []
        kept=[]
        for idx, raw in enumerate(cs):
            if not isinstance(raw, dict):
                action.append({'action': 'remove_invalid_candidate', 'index': idx, 'reason': 'non_object'})
                continue
            c=deepcopy(raw)
            claim=algorithm._clean_claim(c.get('claim'))
            if not claim:
                action.append({'action': 'remove_invalid_candidate', 'index': idx, 'reason': 'not_B_claim'})
                continue
            if not isinstance(c.get('attribute'), str) or not c['attribute'].strip():
                # Attribute is nonsemantic display metadata: GRACE independently
                # derives it from the final vetted proposition at finalization.
                c['attribute'] = ' '.join(claim.split()[1:]) or claim
                action.append({'action': 'derive_attribute_from_claim', 'index': idx})
            if c.get('mechanism') not in algorithm.MECHANISMS:
                action.append({'action': 'remove_invalid_candidate', 'index': idx, 'reason': 'invalid_mechanism'})
                continue
            if c.get('certainty') not in ('asserted','qualified'):
                action.append({'action': 'remove_invalid_candidate', 'index': idx, 'reason': 'invalid_certainty'})
                continue
            if type(c.get('confidence')) not in (int,float) or not 0<=c['confidence']<=1:
                c['confidence']=0.5 # not a threshold in GRACE
                action.append({'action': 'set_uninformative_confidence_metadata', 'index': idx})
            # No quote is added or modified here. Original validator handles it.
            kept.append(c)
        if cs and not kept:
            return None, action
        o['claims']=kept
        return o, action

    if stage.startswith(('verify_', 'dispute_', 'canonicalize')):
        ds=o.get('decisions')
        if not isinstance(ds,list):return None, []
        content=json.loads(payload['messages'][1]['content'])
        candidates=content.get('candidates', [])
        byid={c['id']:c for c in candidates}
        if (len(ds)!=len(byid) or len({d.get('id') for d in ds if isinstance(d,dict)})!=len(byid)
                or not all(isinstance(d,dict) and d.get('id') in byid for d in ds)):
            return None, []
        for d in ds:
            cid=d['id'];v=d.get('verdict')
            if stage.startswith('verify_'):
                if v not in ('keep','repair','reject','duplicate'):
                    return None, []
                if d.get('reason_code') not in algorithm.REASON_CODES:
                    d['reason_code']='other'
                    action.append({'action':'fill_reason_code_other','id':cid})
                if v in ('reject','duplicate') and d.get('mechanism') not in algorithm.MECHANISMS:
                    # No rejected/duplicate claim is emitted, so this field
                    # cannot alter an accepted proposition or its confidence.
                    d['mechanism']='explicit'
                    action.append({'action':'fill_unused_mechanism','id':cid})
                if v in ('keep','repair') and d.get('mechanism') not in algorithm.MECHANISMS:
                    return None, action
                if v != 'duplicate' and d.get('same_as') != '':
                    d['same_as']=''
                    action.append({'action':'clear_irrelevant_same_as','id':cid})
                if v == 'duplicate' and (d.get('same_as') not in byid or d.get('same_as')==cid):
                    # No fabricated equivalence: uncertain duplicates are
                    # conservatively reviewed again as rejected candidates.
                    d.update(verdict='reject',reason_code='no_entailment',same_as='',claim='',evidence=[])
                    action.append({'action':'convert_invalid_duplicate_to_challenge','id':cid})
                if v in ('keep','repair'):
                    cl=algorithm._clean_claim(d.get('claim'))
                    turns=content.get('visible_turns',[])
                    ev,_=algorithm.align_evidence(d.get('evidence'),turns)
                    if cl and not ev and cl == algorithm._clean_claim(byid[cid].get('claim')):
                        cev,_=algorithm.align_evidence(byid[cid].get('evidence'),turns)
                        if cev:
                            d['evidence']=cev
                            action.append({'action':'reuse_literal_candidate_quote_for_same_claim','id':cid})
                            ev=cev
                    if not cl or not ev:
                        # We do not accept a verifier assertion lacking
                        # literal evidence; route to the original independent
                        # rejection challenge where applicable.
                        d.update(verdict='reject',reason_code='no_entailment',same_as='',claim='',evidence=[])
                        action.append({'action':'downgrade_unverifiable_decision_to_challenge','id':cid})
                if d.get('verdict') in ('reject','duplicate'):
                    d['claim']='';d['evidence']=[]
            elif stage.startswith('dispute_'):
                if v not in ('recover','reject'):
                    return None, []
                if v=='reject' and d.get('mechanism') not in algorithm.MECHANISMS:
                    d['mechanism']='explicit'
                    action.append({'action':'fill_unused_mechanism','id':cid})
                if v=='recover':
                    if d.get('mechanism') not in algorithm.MECHANISMS:
                        return None, []
                    cl=algorithm._clean_claim(d.get('claim'))
                    ev,_=algorithm.align_evidence(d.get('evidence'),content.get('visible_turns',[]))
                    if not cl or not ev:
                        d.update(verdict='reject',claim='',evidence=[],mechanism='explicit')
                        action.append({'action':'downgrade_unverifiable_recovery','id':cid})
                if d['verdict']=='reject':d['claim']='';d['evidence']=[]
            else:
                if v not in ('keep','duplicate'):return None, []
                if v=='keep' and d.get('same_as')!='':
                    d['same_as']=''
                    action.append({'action':'clear_irrelevant_same_as','id':cid})
                if v=='duplicate' and (d.get('same_as') not in byid or d.get('same_as')==cid):
                    d.update(verdict='keep',same_as='')
                    action.append({'action':'conservatively_keep_unresolved_duplicate','id':cid})
        o['decisions']=ds
        return o,action
    return None, []


def validate_cached(body, logical_name, payload, validator, algorithm):
    obj=embedded_object(body)
    if obj is None:
        return None,[]
    # Call original strict validator first.
    try:
        return validator(deepcopy(obj)),[]
    except (ValueError,TypeError,AttributeError,KeyError):
        pass
    fixed,action=normalize(obj,logical_name,payload,algorithm)
    if fixed is None:
        return None,action
    try:
        return validator(fixed),action
    except (ValueError,TypeError,AttributeError,KeyError):
        return None,action
