"""Deterministic A-quote localization; never changes propositions or decisions."""
import copy
import unicodedata


def sequence(text):
    chars = []; positions = []
    for pos, c in enumerate(text):
        for d in unicodedata.normalize('NFKC', c).casefold():
            if d.isalnum(): chars.append(d); positions.append(pos)
    return ''.join(chars), positions


def bind_quote(quote, source):
    if not isinstance(quote, str) or not quote.strip(): raise ValueError('Empty quote')
    if quote in source: return quote
    target, _ = sequence(quote); text, positions = sequence(source)
    if not target: raise ValueError('Quote contains no lexical content')
    start = text.find(target)
    while start >= 0:
        lo = positions[start]; hi = positions[start + len(target) - 1] + 1
        # Do not match inside a larger word or number in the original source.
        if (lo == 0 or not source[lo-1].isalnum()) and (hi == len(source) or not source[hi].isalnum()):
            return source[lo:hi]
        start = text.find(target, start + 1)
    raise ValueError('Quote has no formatting-equivalent span in cited A')


def bind(obj, turns):
    result = copy.deepcopy(obj); source = {t['turn']: t['text'] for t in turns}; audit = []
    for item in result.get('items', []):
        for a in item.get('anchors', []):
            if a.get('turn') not in source: raise ValueError('Anchor is not in observed A')
            before = a.get('quote'); after = bind_quote(before, source[a['turn']])
            if before != after:
                audit.append({'item_id': item.get('id'), 'turn': a['turn'], 'model_quote': before, 'source_quote': after})
                a['quote'] = after
    # No semantic field, check, or duplicate decision may change.
    def content(x):
        out = copy.deepcopy(x)
        for i in out.get('items', []): i.pop('anchors', None)
        return out
    assert content(result) == content(obj)
    return result, audit
