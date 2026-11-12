from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import types

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'new_algorithm.py'
MODEL = 'qwen3.8-flash'
ENDPOINT = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'


def digest(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    tmp.replace(path)


def freeze(path, obj):
    if Path(path).exists():
        if load(path) != obj:
            raise ValueError('Frozen artifact differs: ' + str(path))
    else:
        save(path, obj)


def validate_item(item):
    if set(item) != {'item_id', 'dialogue_id', 'dataset', 'direction', 'visible_turns'}:
        raise ValueError('Unsafe adapter input')
    if item['dataset'] != 'realpersonachat' or item['direction'] != 'A_to_B':
        raise ValueError('Wrong dataset/direction')
    if item['item_id'] != 'realpersonachat/' + item['dialogue_id'] + '/A_to_B':
        raise ValueError('Wrong opaque item ID')
    ids = []
    for t in item['visible_turns']:
        if set(t) != {'turn_id', 'text'} or type(t['turn_id']) is not int or t['turn_id'] < 1 or not isinstance(t['text'], str):
            raise ValueError('Unsafe visible turn')
        ids.append(t['turn_id'])
    if not ids or ids != sorted(set(ids)):
        raise ValueError('Empty, duplicate or unordered visible turns')


def elara_v1():
    """Load the EXACT original source with a private dataset validator only.

    RPC need not alternate speakers; its turn IDs are local visible indices.
    No global patch, DailyDialog alias, algorithm/prompt edit or reference access.
    """
    package = '_rpc_elara_v1'
    if package + '.algorithm' in sys.modules:
        return sys.modules[package + '.algorithm']
    pkg = types.ModuleType(package)
    pkg.__path__ = [str(SOURCE.parent)]
    sys.modules[package] = pkg
    common = types.ModuleType(package + '.common')
    common.validate_input = validate_item
    sys.modules[common.__name__] = common
    spec = importlib.util.spec_from_file_location(package + '.algorithm', SOURCE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    if mod.METHOD != 'elara_evidence_lattice_v1' or mod.MODEL != MODEL:
        raise ValueError('Unexpected ELARA source')
    return mod


def sanitize(text, speaker_ids):
    # Every identity placeholder becomes the SAME token, including third parties.
    text = re.sub(r'<\s*[A-Z]{1,8}\s*>', '[PERSON]', text)
    if speaker_ids:
        pattern = r'(?<![A-Za-z])(?:' + '|'.join(re.escape(s) for s in sorted(speaker_ids, key=len, reverse=True)) + r')(?![A-Za-z])'
        text = re.sub(pattern, '[PERSON]', text)
    return text


def metrics(gold, predicted):
    if len(gold) != 10 or len(predicted) != 10:
        raise ValueError('Expected ten labels')
    pairs = [(i, j) for i in range(10) for j in range(i + 1, 10)]
    tp = sum(gold[i] == gold[j] and predicted[i] == predicted[j] for i, j in pairs)
    fp = sum(gold[i] != gold[j] and predicted[i] == predicted[j] for i, j in pairs)
    fn = sum(gold[i] == gold[j] and predicted[i] != predicted[j] for i, j in pairs)
    tn = 45 - tp - fp - fn
    # Undefined P/R/F1 recorded as null (e.g. K=10); never silently perfect.
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None
    contingency = {}
    for g, p in zip(gold, predicted):
        contingency[g, p] = contingency.get((g, p), 0) + 1
    choose = lambda n: n * (n - 1) / 2
    gcounts = [gold.count(g) for g in set(gold)]
    pcounts = [predicted.count(p) for p in set(predicted)]
    a, b = sum(map(choose, gcounts)), sum(map(choose, pcounts))
    expected = a * b / 45
    denom = (a + b) / 2 - expected
    ari = (sum(choose(n) for n in contingency.values()) - expected) / denom if denom else 1.0
    bc_p = sum(contingency[g, p] / predicted.count(p) for g, p in zip(gold, predicted)) / 10
    bc_r = sum(contingency[g, p] / gold.count(g) for g, p in zip(gold, predicted)) / 10
    k, khat = len(set(gold)), len(set(predicted))
    return dict(true_k=k, predicted_k=khat, signed_count_error=khat-k, absolute_count_error=abs(khat-k),
                exact_k=int(k == khat), exact_partition=int(fp == fn == 0),
                pair_tp=tp, pair_fp=fp, pair_fn=fn, pair_tn=tn,
                pair_precision=precision, pair_recall=recall, pair_f1=f1, ari=ari,
                bcubed_precision=bc_p, bcubed_recall=bc_r, bcubed_f1=2*bc_p*bc_r/(bc_p+bc_r))
