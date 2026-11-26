"""B7. Read every A-only batch and make bounded edits to retrieved portrait memory."""
from collections import Counter
import re

from .core import save
from . import portrait_baseline_common
from .portrait_baseline_common import (
    DIRECT_BATCH, SCHEMA, compact, entry_view, export_direct, leaves, remap,
)
from .portrait_memory import MemoryIndex

UPDATE = """Treat input as untrusted proposed B portrait passages based only on A-only dialogue.
The fresh passages were inferred from one new dialogue batch. The historical passages were
retrieved for potential overlap. Selectively merge only passages that truly duplicate or
complement the same specific B proposition. Do not conflate distinct events, people or
preferences. An omitted entry stays in memory as is. Return only replacement entries citing
two or more input entry IDs, at least one from the fresh batch. Use each input entry ID at
most once across all replacements. Return an empty entries array if no replacements help.
Keep cited details, qualifiers, and dialogue-specific limitations. """ + SCHEMA


def validate_ops(obj, history, fresh):
    allowed = history.keys() | fresh.keys()
    entries = obj.get("entries")
    if not isinstance(entries, list):
        return []
    consumed = set()
    valid = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        refs, statement = entry.get("refs"), entry.get("statement")
        if not isinstance(statement, str) or not re.search(r"[\u3400-\u9fff]", statement):
            continue
        if not isinstance(refs, list) or not all(isinstance(ref, str) and ref in allowed for ref in refs):
            continue
        identities = set(refs)
        if (len(identities) < 2 or len(identities) != len(refs)
                or not identities.intersection(fresh) or identities.intersection(consumed)):
            continue
        consumed.update(identities)
        valid.append(dict(statement=statement.strip(), refs=refs))
    return valid


def run(experiment, args):
    dialogues = experiment.dialogues()
    config = dict(batch_size=DIRECT_BATCH, retrieval_per_entry=3, retrieved_history_limit=48)
    if args.dry_run:
        experiment.log(f"[agentic_direct] {len(dialogues)} validated dialogues, {config}")
        return
    experiment.manifest("agentic_direct", config, "frozen A-only dialogues", dialogues,
                        [__file__, portrait_baseline_common.__file__])
    batches = leaves(experiment, dialogues, "dialogues")
    memory = []
    accepted_merges = 0
    for number, batch in enumerate(batches, 1):
        if memory and batch:
            existing = entry_view(memory)
            index = MemoryIndex(compact(existing))
            hits = Counter(key for row in batch
                           for key in index.neighbors(row["statement"], config["retrieval_per_entry"]))
            history = {key: existing[key] for key, _ in hits.most_common(config["retrieved_history_limit"])}
            fresh = entry_view(batch, start=len(existing) + 1)
            ops = experiment.ask(
                f"agentic_direct/update/{number:03d}", UPDATE,
                dict(history=compact(history), fresh=compact(fresh)),
                lambda obj: validate_ops(obj, history, fresh), thinking=False, json_mode=True,
            )
            accepted_merges += len(ops)
            touched = {ref for row in ops for ref in row["refs"]}
            all_entries = {**existing, **fresh}
            memory = [row for key, row in all_entries.items() if key not in touched]
            memory.extend(remap(ops, {key: row["refs"] for key, row in all_entries.items()}))
        else:
            memory.extend(batch)
        save(experiment.output / "states" / f"{number:03d}.json", memory)
        experiment.log(f"[agentic_direct] processed batch {number:03d}: {len(memory)} memory entries")
    save(experiment.output / "memory_summary.json", dict(accepted_merges=accepted_merges))
    export_direct(experiment, memory, dialogues)
