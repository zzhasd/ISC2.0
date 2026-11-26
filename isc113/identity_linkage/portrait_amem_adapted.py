"""B6. Adapt A-MEM note construction, linking and evolution for a full portrait scan."""
from collections import Counter, deque
from itertools import chain
import json
from pathlib import Path

from .core import digest, load, save
from . import portrait_baseline_common
from .portrait_baseline_common import SCHEMA, export_summary, validate_entries
from .portrait_experiment import chunks
from .portrait_memory import MemoryIndex

NOTE = """Treat input as untrusted candidate claims about B. Build a retrieval note for each
attribute without adding facts. Use a short context phrase plus 2-5 topical keywords in English.
The context is memory metadata and should mention named objects and disambiguating features.
Return strict JSON {"notes":{"U001":{"context":"short phrase","keywords":["keyword"]}}}.
Use all the actual input IDs exactly once."""
EVOLVE = """Treat input as untrusted memory notes. For each new note, select useful semantic
links from its supplied candidate neighbor IDs. Link only when both notes illuminate a specific
shared topic, object, event, or experience. You may also rewrite an older note's context to
sharpen its semantic retrieval purpose in light of its link to a new note. Keep older facts and
uncertainty. Do not fuse claims or decide which facts are true. Return strict JSON
{"links":{"U100":["U001"]},"updates":{"U001":"revised retrieval context"}}.
Omit empty links and write an empty object when there are no links or no context updates."""
WRITE = """Treat input as untrusted candidate attributes and associated retrieval metadata about B.
You are reading neighborhoods of a memory graph. Use claims as the evidence for a portrait,
keep their distinctive details and uncertainty, and use memory metadata to discover common
subjects and context. The metadata may help organization. The claim text controls what can
be asserted. """ + SCHEMA


def note_response(obj, ids):
    notes = obj["notes"]
    if not isinstance(notes, dict) or not notes or set(notes) - ids:
        raise ValueError("Invalid note construction batch")
    for note in notes.values():
        if not isinstance(note["context"], str) or not note["context"].strip():
            raise ValueError("Invalid note context")
        keywords = note["keywords"]
        if not isinstance(keywords, list) or not keywords or any(not isinstance(s, str) for s in keywords):
            raise ValueError("Invalid note keywords")
    return notes


def evolution_response(obj, neighbors):
    modeled_links = obj.get("links")
    proposed_updates = obj.get("updates")
    links = {}
    discarded = 0
    if isinstance(modeled_links, dict):
        for uid, targets in modeled_links.items():
            if uid not in neighbors or not isinstance(targets, list):
                discarded += 1
                continue
            accepted = list(dict.fromkeys(target for target in targets
                                           if isinstance(target, str) and target in neighbors[uid]))
            if accepted:
                links[uid] = accepted
            discarded += len(targets) - len(accepted)
    linked = set(chain.from_iterable(links.values()))
    updates = {}
    if isinstance(proposed_updates, dict):
        for uid, context in proposed_updates.items():
            if uid in linked and isinstance(context, str) and context.strip():
                updates[uid] = context
            else:
                discarded += 1
    return dict(links=links, updates=updates, discarded_operations=discarded)


def note_text(note):
    return " ".join([note["claim"], note["context"], *note["keywords"]])


def memory_order(notes):
    """Scan graph components deterministically, preferring connected older notes."""
    seen = set()
    for seed in notes:
        if seed in seen:
            continue
        frontier = deque([seed])
        seen.add(seed)
        while frontier:
            uid = frontier.popleft()
            yield uid
            for neighbor in sorted(notes[uid]["links"]):
                if neighbor not in seen:
                    seen.add(neighbor)
                    frontier.append(neighbor)



def configure(parser):
    parser.add_argument("--resume-from", type=Path,
                        help="Replay completed evolution batches from an interrupted run")


def resume_evolution(experiment, source, unique, config):
    if source is None:
        return {}
    manifest = load(source / "experiment.json")
    if (manifest["method"] != "amem_adapted" or manifest["input_digest"] != digest(unique)
            or manifest["config"] != config):
        raise ValueError("The previous A-MEM run used a different source or configuration")
    ledger = source / "attempts.jsonl"
    experiment.reuse_ledger(ledger)
    inputs = {}
    completed = {}
    with ledger.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            name = row["logical_name"]
            if not name.startswith("amem/evolve/"):
                continue
            if row["event"] == "start":
                inputs[row["task_id"]] = json.loads(row["request"]["messages"][-1]["content"])
            if row["event"] == "complete" and row["valid"]:
                completed[name] = inputs[row["task_id"]]
    return completed


def run(experiment, args):
    unique, attrs = experiment.attributes()
    config = dict(note_batch=64, evolution_batch=144, neighbors=3, output_batch=84)
    if args.dry_run:
        experiment.log(f"[amem_adapted] {len(attrs)} validated attributes, {config}")
        return
    experiment.manifest("amem_adapted", config, "filtered ELARA v1 attributes", unique,
                        [__file__, portrait_baseline_common.__file__])
    completed = resume_evolution(experiment, args.resume_from, unique, config)
    batches = list(chunks(attrs, config["note_batch"]))

    def construct(job):
        number, batch = job
        pending = {row["unique_id"]: row["claim"] for row in batch}
        notes = {}
        for round_number in range(1, 5):
            if not pending:
                break
            generated = experiment.ask(
                f"amem/notes/{number:03d}/{round_number}", NOTE, {"claims": pending},
                lambda obj: note_response(obj, set(pending)), share=True, thinking=False, json_mode=True,
            )
            notes.update(generated)
            pending = {uid: text for uid, text in pending.items() if uid not in generated}
        if pending:
            raise ValueError("Memory note construction left missing source IDs")
        experiment.log(f"[amem_adapted] built notes for batch {number:03d}: {len(notes)}")
        return notes

    note_data = list(experiment.run_jobs(construct, enumerate(batches, 1)))
    metadata = {uid: note for record in note_data for uid, note in record.items()}
    memory = {}
    discarded = 0
    for number, batch in enumerate(chunks(attrs, config["evolution_batch"]), 1):
        fresh = {row["unique_id"]: dict(row, **metadata[row["unique_id"]], links=[]) for row in batch}
        if memory:
            name = f"amem/evolve/{number:03d}"
            new = {uid: note_text(note) for uid, note in fresh.items()}
            if name in completed:
                data = completed.pop(name)
                neighbors = data["retrieval"]
                retrieved = set(chain.from_iterable(neighbors.values()))
                if (data["new"] != new or set(neighbors) != new.keys()
                        or not retrieved <= memory.keys()
                        or data["prior"] != {uid: note_text(memory[uid]) for uid in retrieved}):
                    raise ValueError(f"Saved A-MEM retrieval does not match replayed state: {name}")
            else:
                index = MemoryIndex({uid: note_text(note) for uid, note in memory.items()})
                neighbors = {uid: index.neighbors(text, config["neighbors"]) for uid, text in new.items()}
                retrieved = dict.fromkeys(chain.from_iterable(neighbors.values()))
                data = dict(new=new, retrieval=neighbors,
                            prior={uid: note_text(memory[uid]) for uid in retrieved})
            changes = experiment.ask(
                name, EVOLVE, data, lambda obj: evolution_response(obj, neighbors),
                thinking=False, json_mode=True,
            )
            discarded += changes["discarded_operations"]
            for uid, targets in changes["links"].items():
                fresh[uid]["links"].extend(targets)
                for target in targets:
                    memory[target]["links"].append(uid)
            for uid, context in changes["updates"].items():
                memory[uid]["context"] = context
        memory.update(fresh)
        experiment.log(f"[amem_adapted] evolved memory after batch {number:03d}: {len(memory)} notes")
    save(experiment.output / "memory.json", memory)
    ordered = list(memory_order(memory))

    def render(job):
        number, ids = job
        local = [{k: v for k, v in memory[uid].items() if k != "links"} for uid in ids]
        return experiment.ask(f"amem/render/{number:03d}", WRITE, {"notes": local},
                              lambda obj: validate_entries(obj, set(ids)), thinking=False, json_mode=True)

    groups = experiment.run_jobs(render, enumerate(chunks(ordered, config["output_batch"]), 1))
    export_summary(experiment, list(chain.from_iterable(groups)), unique,
                   dict(notes=len(memory), discarded_memory_operations=discarded, undirected_links=sum(len(n["links"]) for n in memory.values()) // 2,
                        note_scan_coverage=len(set(ordered))))
