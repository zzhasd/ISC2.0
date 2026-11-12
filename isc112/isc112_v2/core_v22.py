"""Same acceptance, with safe duplicate links between excluded decisions allowed."""
import re
from .core import checked, accepted


def render(obj, turns, proposed):
    checked(obj, turns); items = obj.get('items'); source = {t['turn']: t['text'] for t in turns}
    if not isinstance(items, list): raise ValueError('Missing items')
    ids = [i.get('id') for i in items]
    if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)): raise ValueError('Invalid decision IDs')
    expected = {c['id'] for c in proposed}
    if {i['id'] for i in items if i.get('origin') == 'candidate'} != expected: raise ValueError('Incomplete candidate decisions')
    enums = {'holder': {'B', 'A', 'third', 'unknown'}, 'scope': {'profile', 'dialogue_act', 'generic'},
             'support': {'explicit', 'entailed', 'presupposed', 'unknown', 'contradicted'},
             'status': {'active', 'superseded', 'unresolved'}, 'origin': {'candidate', 'addition'}}
    for i in items:
        for k, choices in enums.items():
            if i.get(k) not in choices: raise ValueError('Invalid ' + k)
        if i['origin'] == 'addition' and (not re.fullmatch(r'a[1-9][0-9]*', i['id']) or i['id'] in expected): raise ValueError('Invalid addition ID')
        if any(not isinstance(i.get(k), str) or not i[k].strip() for k in ['claim', 'time', 'category']): raise ValueError('Invalid decision text')
        cc = i.get('checks')
        if not isinstance(cc, dict) or set(cc) != {'holder', 'content', 'qualifiers'} or any(type(v) is not bool for v in cc.values()): raise ValueError('Invalid checks')
        anchors = i.get('anchors')
        if not isinstance(anchors, list) or not anchors: raise ValueError('Missing anchors')
        for a in anchors:
            if type(a.get('turn')) is not int or a['turn'] not in source or not isinstance(a.get('quote'), str) or not a['quote'].strip() or a['quote'] not in source[a['turn']]: raise ValueError('Anchor is not literal visible A')
        i['evidence_turns'] = sorted({a['turn'] for a in anchors})
        i['evidence'] = [{'turn': n, 'quote': source[n]} for n in i['evidence_turns']]
    by = {i['id']: i for i in items}
    for i in items:
        target = i.get('duplicate_of')
        if target is None: continue
        if target not in by or target == i['id'] or by[target].get('duplicate_of') is not None: raise ValueError('Invalid duplicate reference/chain')
        if accepted({**i, 'duplicate_of': None}) and not accepted(by[target]):
            raise ValueError('Potential accepted fact cannot point to excluded target')
    facts = [i for i in items if accepted(i)]
    hypotheses = [i for i in items if not accepted(i) and i['holder'] in {'B', 'unknown'} and i['scope'] == 'profile' and not i.get('duplicate_of') and (i['support'] == 'unknown' or i['status'] == 'unresolved' or not all(i['checks'].values()))]
    selected = {i['id'] for i in facts + hypotheses}
    return {'facts': facts, 'hypotheses': hypotheses, 'excluded': [i for i in items if i['id'] not in selected], 'items': items}
