import hashlib
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def save(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    tmp.replace(path)

def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def filehash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def freeze(path, obj):
    if Path(path).exists():
        if read(path) != obj:
            raise ValueError('Frozen artifact changed: ' + str(path))
    else:
        save(path, obj)

def jsonlines(path):
    return [json.loads(x) for x in Path(path).read_text(encoding='utf-8').splitlines() if x.strip()] if Path(path).exists() else []

def visible(dialogue, direction):
    require_direction(direction)
    return [{'turn_id': i + 1, 'text': s} for i, s in enumerate(dialogue['turns']) if i % 2 == 0]

def require_dataset(dataset):
    if dataset != 'dailydialog':
        raise ValueError('ISC113 now supports only the frozen DailyDialog experiment')

def require_direction(direction):
    if direction != 'A_to_B':
        raise ValueError('ISC113 supports A_to_B only')

def run_folder(run_id):
    if not isinstance(run_id,str) or not re.fullmatch(r'[a-zA-Z0-9_-]+',run_id) or run_id in ['dailydialog','main'] or run_id.startswith('evaluation'):
        raise ValueError('Use a new run_id; historical inference and evaluation logs are frozen')
    return BASE/'runs'/run_id

def validate_input(item):
    if set(item) != {'item_id','dialogue_id','direction','dataset','visible_turns'}:
        raise ValueError('Unsafe input record')
    require_dataset(item['dataset']); require_direction(item['direction'])
    if item['item_id'] != 'dailydialog/'+item['dialogue_id']+'/A_to_B':
        raise ValueError('Input identity mismatch')
    ids=[]
    for turn in item['visible_turns']:
        if set(turn) != {'turn_id','text'} or type(turn['turn_id']) is not int or turn['turn_id'] < 1 or turn['turn_id'] % 2 != 1 or not isinstance(turn['text'],str):
            raise ValueError('Only original A turns are allowed')
        ids.append(turn['turn_id'])
    if ids != sorted(set(ids)):
        raise ValueError('Duplicate or unordered A turns')
    return item
