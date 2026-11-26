"""Input scope and scoring rules for the AT portrait evaluation."""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from .core import HERE, load
from .portrait_experiment import DEFAULT_SOURCE

RUNS = HERE / "runs"
GOLD = HERE / "data" / "persona_gold_233_approved(1).json"
OUT = RUNS / "portrait_evaluation_AT"
METHODS = {
    "B1": ("Direct", "portrait_direct_AT"),
    "B2": ("Hierarchical Direct", "portrait_hierarchical_direct_AT"),
    "B3": ("Summary v2", "portrait_summary_v2_AT"),
    "B4": ("Hierarchical Summary", "portrait_hierarchical_summary_AT"),
    "B5": ("Incremental Summary", "portrait_incremental_summary_AT"),
    "B6": ("A-MEM-adapted", "portrait_amem_adapted_AT_delivery"),
    "B7": ("Agentic Direct", "portrait_agentic_direct_AT_delivery"),
    "Ours": ("Ours", "portrait_ours_AT_complete"),
}
INLINE_REF = re.compile(r"\[[A-Z]\d+(?:[,\s]+[A-Z]\d+)*\]")
FALLBACK = re.compile(r"^(待确认的|待审阅的)?原始候选描述[:：]\s*")
ACTOR = re.compile(r"^[Bb](?![a-zA-Z])")
A_ONLY = re.compile(r"^[Aa](?=[\u3040-\u9fff\s:：])")
GOLD_SEARCH = {
    "P1a": r"システムエンジニア|系[统統]工程[师師]|systems? engineer|软件工程师|IT工程师|工程师",
    "P2a": r"出生|生まれ|born in|东京.{0,7}出身|出身.{0,7}东京|東京.{0,7}出身",
    "P2b": r"埼玉|saitama|长大|成长于|育った|grew up",
    "P3a": r"晨跑|早.{0,18}(?:跑|jog)|morning.{0,14}(?:run|jog)|(?:run|jog).{0,15}morning|ジョギング",
    "P4a": r"(?:酒|饮).{0,14}(?:聚会|应酬|酒会)|(?:聚会|应酬).{0,14}(?:酒|饮)|drinking part|飲み会|共饮|共飲",
    "P5a": r"西瓜|watermelon|スイカ|すいか",
    "P6a": r"环游世界|环球|世界一周|around the world|global travel|世界各地|世界旅行",
    "P7a": r"让人开心|让人快乐|让别人|给人带来|让他人|逗.{0,6}笑|取悦|使他人|给别人带来|entertain|人を楽し|人を喜",
    "P8a": r"周末.{0,26}(?:酒|喝)|(?:酒|喝).{0,24}周末|居酒屋|izakaya",
    "P9a": r"初次见面|第一次见面|初见|陌生人|初対面|strangers|first time",
    "P10a": r"腰痛|腰疼|腰.{0,8}疼痛|下背.{0,4}痛|lower.back|back pain|腰が痛",
}


@dataclass(frozen=True)
class Unit:
    unit_id: str
    portrait_id: str
    text: str
    hypothesis: str


def normalize(text):
    return unicodedata.normalize("NFKC", text).strip()


def key(text):
    return re.sub(r"\s+", " ", normalize(text)).rstrip("。！？.!?；;").casefold()


def split_statement(text):
    """Respect quoted text and parentheses. Use the same separator rule for every method."""
    close = {"(": ")", "（": "）", "「": "」", "『": "』", "“": "”", "【": "】", '"': '"'}
    stack = []
    start = 0
    for i, char in enumerate(text):
        if stack and char == stack[-1]:
            stack.pop()
        elif char in close:
            stack.append(close[char])
        elif not stack and (char in "。；！？;!?\n"
                            or (char == "." and (i == len(text) - 1 or text[i + 1].isspace())
                                and i - start >= 8)):
            piece = text[start:i + 1].strip()
            if piece:
                yield piece
            start = i + 1
    if text[start:].strip():
        yield text[start:].strip()


def hypothesis(text):
    clean = INLINE_REF.sub("", normalize(text)).strip()
    clean = FALLBACK.sub("", clean)
    has_a = bool(A_ONLY.match(clean))
    if not has_a and not ACTOR.match(clean):
        clean = ("B " if clean[:1].isascii() else "B") + clean
    return clean


def units(rows):
    for row in rows:
        for index, fragment in enumerate(split_statement(row["statement"]), 1):
            clean = hypothesis(fragment)
            if clean:
                yield Unit(f"{row['portrait_id']}.{index}", row["portrait_id"], fragment, clean)


def windows(dialogues):
    for dialogue in dialogues:
        turns = dialogue["visible_turns"]
        for index, turn in enumerate(turns):
            local = turns[max(0, index - 1):index + 2]
            evidence = "\n".join(f"A：「{line['text']}」" for line in local)
            yield {
                "window_id": f"{dialogue['dialogue']}T{turn['turn_id']}",
                "dialogue": dialogue["dialogue"],
                "center": turn["turn_id"],
                "turn_ids": [t["turn_id"] for t in local],
                "reference": evidence,
            }


def anchor_inventory(path=GOLD):
    gold = next(person for person in load(path)["people"] if person["person_id"] == "AT")
    atoms = [dict(atom, statement_ja=record["original_text_ja"])
             for record in gold["statements"] for atom in record["facts"]]
    if sum(a["score"] for a in atoms) != gold["total_score"] or gold["total_score"] != 100:
        raise ValueError("AT gold weights must sum to 100")
    return atoms


def pct(numerator, total):
    return round(100 * numerator / total, 4) if total else None
