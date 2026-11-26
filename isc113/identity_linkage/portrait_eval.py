"""Evaluate frozen AT portraits using an anchor rubric and independently sampled evidence."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import math
from pathlib import Path
import re

import numpy as np

from .core import digest, load, save
from .portrait_eval_models import HOME, LocalRetrievalModel, model_manifest
from .portrait_eval_report import export_report
from .portrait_eval_protocol import (
    DEFAULT_SOURCE, GOLD, GOLD_SEARCH, METHODS, OUT, RUNS,
    anchor_inventory, key, pct, units, windows,
)

SEED = "at-portrait-audit-v1"
SAMPLE_PER_METHOD = 16
LABELS = ("full", "partial", "speaker_error", "contradicted", "unresolved")
CONTENT_LABELS = ("retained", "partial", "altered", "unresolved")
SELF_CUE = re.compile(r"(?:私|わたし|僕|俺|当方|自分)(?:は|が|も|の|に)|うち(?:は|では)")
QUESTION = re.compile(r"[？?]|(?:ます|です|でしょう|でした|ません|ない)か[。！!「」\s]?$")


def ordered(seed, items, identity):
    return sorted(items, key=lambda item: digest([seed, identity(item)]))


def inventory(source, methods=METHODS):
    dialogues = load(source / "inputs.json")["dialogues"]
    turns = {(d["dialogue"], t["turn_id"]): t["text"] for d in dialogues for t in d["visible_turns"]}
    bank = {row["unique_id"]: row for row in load(source / "deduplicated.json")}
    snapshot = {code: load(RUNS / folder / "portrait.json")["portraits"]
                for code, (_, folder) in methods.items() if (RUNS / folder / "portrait.json").exists()}
    return dialogues, turns, bank, snapshot


def quote_refs(row, bank):
    if "evidence" in row:
        yield from row["evidence"]
    else:
        for uid in row.get("unique_ids", []):
            for member in bank[uid]["members"]:
                for ref in member["claim"].get("evidence", []):
                    yield dict(ref, dialogue=member["dialogue"])


def native_windows(rows, bank, turns):
    by_passage = {}
    invalid = 0
    for row in rows:
        native = set()
        for ref in quote_refs(row, bank):
            location = (ref["dialogue"], ref["turn_id"])
            quote = ref.get("quote", "")
            if quote and quote in turns.get(location, ""):
                native.add(location)
            else:
                invalid += 1
        by_passage[row["portrait_id"]] = native
    return by_passage, invalid


def structure(rows, bank, turns, dialogue_count):
    local = list(units(rows))
    counts = Counter(key(unit.hypothesis) for unit in local)
    by_passage, invalid = native_windows(rows, bank, turns)
    cited = set().union(*by_passage.values())
    groups = Counter(dialogue for dialogue, _ in cited)
    evidence = {
        "resolved_passages": sum(bool(refs) for refs in by_passage.values()),
        "passage_trace_rate_100": pct(sum(bool(refs) for refs in by_passage.values()), len(rows)),
        "unresolved_quote_occurrences": invalid,
        "distinct_cited_turns": len(cited),
        "distinct_cited_dialogues": len(groups),
        "dialogue_reach_100": pct(len(groups), dialogue_count),
        "explicit_a_first_person_turns": sum(bool(SELF_CUE.search(turns[ref])) for ref in cited),
        "question_cued_turns": sum(bool(QUESTION.search(turns[ref])) for ref in cited),
    }
    if cited:
        evidence["effective_cited_dialogues"] = round(math.exp(-sum(
            (n / len(cited)) * math.log(n / len(cited)) for n in groups.values()
        )), 4)
    result = dict(
        passages=len(rows), text_characters=sum(len(row["statement"]) for row in rows),
        text_units=len(local), exact_repeat_units=len(local) - len(counts),
        exact_repeat_rate_100=pct(len(local) - len(counts), len(local)),
        exact_nonrepeat_rate_100=pct(len(counts), len(local)), evidence_trace=evidence,
    )
    if all("unique_ids" in row for row in rows):
        used = Counter(uid for row in rows for uid in row["unique_ids"])
        separately = defaultdict(list)
        for uid, row in bank.items():
            status = "supported" if all(m["claim"].get("audit_verdict") == "supported"
                                       for m in row["members"]) else "uncertain"
            separately[status].append(uid)
        def id_stats(refs):
            found = sum(used[uid] >= 1 for uid in refs)
            once = sum(used[uid] == 1 for uid in refs)
            multiply = sum(used[uid] > 1 for uid in refs)
            return dict(total=len(refs), found=found, exactly_once=once, repeated=multiply,
                        coverage_100=pct(found, len(refs)), exactly_once_100=pct(once, len(refs)))
        result["native_inventory"] = dict(all=id_stats(bank), **{
            status: id_stats(refs) for status, refs in separately.items()
        })
    return result, local, by_passage


def archive_partition(rows, archive, bank):
    body = Counter(uid for row in rows for uid in row["unique_ids"])
    archived = Counter(uid for row in archive for uid in row["unique_ids"])
    combined = body + archived
    if combined.keys() - bank.keys():
        raise ValueError("The portrait or archive cites an unknown ELARA attribute ID")
    reasons = Counter()
    for row in archive:
        reasons[row["reason_code"]] += len(row["unique_ids"])
    return {
        "portrait_ids": len(body), "archived_ids": len(archived),
        "body_archive_overlap_ids": len(body.keys() & archived.keys()),
        "missing_ids": len(bank.keys() - combined.keys()),
        "repeated_ids_in_combined": sum(count > 1 for count in combined.values()),
        "combined_exactly_once_100": pct(sum(count == 1 for count in combined.values()), len(bank)),
        "archived_assignments_by_reason": dict(reasons),
    }


def top_indices(scores, n, limit=None):
    candidates = np.arange(len(scores)) if limit is None else np.asarray(sorted(limit), dtype=int)
    if not len(candidates):
        return []
    order = np.argsort(-scores[candidates], kind="stable")[:n]
    return [int(i) for i in candidates[order]]


def unit_text(unit):
    return {"unit_id": unit.unit_id, "portrait_id": unit.portrait_id, "text": unit.text,
            "hypothesis": unit.hypothesis}


def prepare(out, source, home, gold, methods=METHODS):
    out.mkdir(parents=True, exist_ok=True)
    dialogues, turns, bank, snapshot = inventory(source, methods)
    items = list(windows(dialogues))
    text = [w["reference"] for w in items]
    by_turn = {(w["dialogue"], w["center"]): i for i, w in enumerate(items)}
    atoms = anchor_inventory(gold)
    model = LocalRetrievalModel(home)
    vectors = model.run(["passage: " + s for s in text])
    base = {
        "version": SEED, "source_digest": digest(dialogues), "gold_digest": digest(atoms),
        "unique_inventory_digest": digest(bank), "runtime": model.runtime,
        "models": model_manifest(home), "methods": {}, "evidence_sample_per_method": SAMPLE_PER_METHOD,
    }
    sample = []
    manifest = {}
    for code, (name, folder) in methods.items():
        if code not in snapshot:
            status = load(RUNS / folder / "report.json")["status"]
            base["methods"][code] = dict(name=name, status=status)
            continue
        rows = snapshot[code]
        results, local, native = structure(rows, bank, turns, len(dialogues))
        base["methods"][code] = dict(name=name, status="portrait_available", portrait_digest=digest(rows),
                                      **results)
        portrait = load(RUNS / folder / "portrait.json")
        if "archive" in portrait:
            base["methods"][code]["archive_partition"] = archive_partition(rows, portrait["archive"], bank)
        print(f"{code}: {len(local)} evaluation units", flush=True)
        docs = model.run(["passage: " + u.hypothesis for u in local])
        queries = model.run(["query: B " + a["fact_zh"] for a in atoms])
        shortlist = []
        for anchor, similarities in zip(atoms, queries @ docs.T):
            literal = re.compile(GOLD_SEARCH[anchor["fact_id"]], re.I)
            selected = set(top_indices(similarities, 8))
            selected.update(i for i, unit in enumerate(local) if literal.search(unit.text))
            shortlist.append(dict(anchor=anchor, candidates=[
                dict(unit_text(local[i]), similarity=round(float(similarities[i]), 5),
                     lexical_hit=bool(literal.search(local[i].text)))
                for i in sorted(selected, key=lambda i: (-float(similarities[i]), i))
            ]))
        save(out / f"self_candidates_{code}.json", shortlist)

        drawn = ordered(SEED + code, local, lambda u: [u.unit_id, u.text])[:SAMPLE_PER_METHOD]
        query = model.run(["query: " + u.hypothesis for u in drawn])
        for unit, similarity in zip(drawn, query @ vectors.T):
            hits = top_indices(similarity, 24)
            raw = []
            for i in hits:
                if all(items[i]["dialogue"] != items[j]["dialogue"] for j in raw):
                    raw.append(i)
                if len(raw) == 2:
                    break
            eligible = {by_turn[r] for r in native[unit.portrait_id] if r in by_turn}
            linked = top_indices(similarity, 4, eligible - set(raw))
            selected = raw[:]
            for idx in linked:
                if all(items[idx]["dialogue"] != items[j]["dialogue"] or
                       abs(items[idx]["center"] - items[j]["center"]) > 2 for j in selected):
                    selected.append(idx)
                if len(selected) == 4:
                    break
            # Use up to four windows in both modes, filling from the same full-corpus index.
            for idx in hits:
                if len(selected) == 4:
                    break
                if all(items[idx]["dialogue"] != items[j]["dialogue"] for j in selected):
                    selected.append(idx)
            audit_id = "A" + digest([SEED, code, unit.unit_id, unit.text])[:12]
            sample.append({
                "audit_id": audit_id, "statement": unit.hypothesis,
                "evidence": [dict(
                    window_id=items[idx]["window_id"], text=items[idx]["reference"],
                    turn_ids=items[idx]["turn_ids"],
                ) for idx in selected],
            })
            manifest[audit_id] = dict(method=code, **unit_text(unit), window_ids=[
                items[idx]["window_id"] for idx in selected
            ])
    shuffled = ordered(SEED, sample, lambda x: x["audit_id"])
    for index in range(0, len(shuffled), 48):
        save(out / f"blind_evidence_batch_{index // 48 + 1}.json", shuffled[index:index + 48])
    save(out / "evidence_sample_manifest.json", manifest)
    save(out / "structure.json", base)
    print(f"Wrote {len(shuffled)} blind A-only audit cards", flush=True)



def prepare_content(out, source, home, methods=METHODS):
    _, _, bank, snapshot = inventory(source, methods)
    partitions = defaultdict(list)
    for uid, row in bank.items():
        status = "supported" if all(m["claim"].get("audit_verdict") == "supported"
                                       for m in row["members"]) else "uncertain"
        partitions[status].append(uid)
    anchors = [
        (status, uid) for status, count in (("supported", 10), ("uncertain", 2))
        for uid in ordered(SEED + "/content/" + status, partitions[status], lambda uid: uid)[:count]
    ]
    model = LocalRetrievalModel(home)
    queries = model.run(["query: " + bank[uid]["claim"] for _, uid in anchors])
    cards, index = [], {}
    for code, rows in snapshot.items():
        local = list(units(rows))
        refs = {row["portrait_id"]: set(row.get("unique_ids", [])) for row in rows}
        vectors = model.run(["passage: " + u.hypothesis for u in local])
        for (status, uid), similarities in zip(anchors, queries @ vectors.T):
            top = top_indices(similarities, 12)
            picked = []
            for i in top:
                if all(key(local[j].hypothesis) != key(local[i].hypothesis) for j in picked):
                    picked.append(i)
                if len(picked) == 2:
                    break
            native = [i for i, unit in enumerate(local) if uid in refs[unit.portrait_id]
                      and all(key(local[j].hypothesis) != key(unit.hypothesis) for j in picked)]
            remainder = top_indices(similarities, 1, native)
            if not remainder:
                remainder = [i for i in top if all(
                    key(local[j].hypothesis) != key(local[i].hypothesis) for j in picked
                )][:1]
            picked.extend(remainder)
            audit_id = "C" + digest([SEED, code, uid])[:12]
            views = [{"candidate_id": f"M{j}", "text": local[i].hypothesis}
                     for j, i in enumerate(picked, 1)]
            cards.append({
                "audit_id": audit_id, "attribute": bank[uid]["claim"], "prior_status": status,
                "candidate_passages": views,
            })
            index[audit_id] = dict(method=code, attribute_id=uid, status=status,
                                  candidates={f"M{j}": unit_text(local[i])
                                              for j, i in enumerate(picked, 1)})
    shuffled = ordered(SEED + "/content", cards, lambda card: card["audit_id"])
    for i in range(0, len(shuffled), 36):
        save(out / f"blind_content_batch_{i // 36 + 1}.json", shuffled[i:i + 36])
    save(out / "content_sample_manifest.json", {
        "bank_digest": digest(bank),
        "portrait_digests": {code: digest(rows) for code, rows in snapshot.items()},
        "cards_digest": digest(shuffled), "cards": index,
    })
    print(f"Wrote {len(shuffled)} paired blind content audit cards", flush=True)


def self_scores(base, atoms, judgments, snapshot):
    expected = {atom["fact_id"]: atom for atom in atoms}
    output = {}
    validate_methods = set(snapshot)
    if set(judgments) != validate_methods:
        raise ValueError("The frozen self judgments must cover each completed method")
    for code, annotation in judgments.items():
        if Counter(row["fact_id"] for row in annotation) != Counter(expected.keys()):
            raise ValueError(f"Wrong AT gold atom inventory for {code}")
        texts = {r["portrait_id"]: r["statement"] for r in snapshot[code]}
        if digest(snapshot[code]) != base["methods"][code]["portrait_digest"]:
            raise ValueError(f"{code} portrait changed after evaluation preparation")
        rows = []
        for row in annotation:
            grade = row["grade"]
            if type(grade) is not int or not 0 <= grade <= 5:
                raise ValueError(f"Invalid rubric level for {code}/{row['fact_id']}")
            refs, quotes = row["portrait_ids"], row["quotes"]
            if len(refs) != len(quotes) or any(not quote or quote not in texts.get(ref, "")
                                               for ref, quote in zip(refs, quotes)):
                raise ValueError(f"Unresolved quotation at {code}/{row['fact_id']}")
            if (grade or row["conflict"]) and not refs:
                raise ValueError(f"Positive grade or conflict needs a cited passage in {code}")
            atom = expected[row["fact_id"]]
            rows.append(dict(**row, max_score=atom["score"], fact_zh=atom["fact_zh"],
                             awarded=round(atom["score"] * grade / 5, 2)))
        output[code] = {
            "score_100": round(sum(row["awarded"] for row in rows), 2),
            "full_hit_points": sum(row["max_score"] for row in rows if row["grade"] == 5),
            "score_without_conflicted_atoms": round(sum(row["awarded"] for row in rows if not row["conflict"]), 2),
            "score_from_near_full_hits": round(sum(row["awarded"] for row in rows if row["grade"] >= 4), 2),
            "conflicted_atoms": sum(row["conflict"] for row in rows),
            "atoms": rows,
        }
    return output


def wilson(successes, n):
    z = 1.959963984540054
    p = successes / n
    denominator = 1 + z * z / n
    mean = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denominator
    return [round(max(0, mean - half) * 100, 3), round(min(1, mean + half) * 100, 3)]


def evidence_scores(manifest, judgments):
    if Counter(row["audit_id"] for row in judgments) != Counter(manifest.keys()):
        raise ValueError("Every blind audit card needs one verdict")
    by_method = defaultdict(list)
    for row in judgments:
        spec = manifest[row["audit_id"]]
        if row["label"] not in LABELS or not row["reason"].strip():
            raise ValueError(f"Invalid evidence verdict {row['audit_id']}")
        cited = row["window_ids"]
        if len(cited) != len(set(cited)) or set(cited) - set(spec["window_ids"]):
            raise ValueError(f"Unresolved evidence pointer {row['audit_id']}")
        if row["label"] != "unresolved" and not cited:
            raise ValueError(f"Verdict requires a source window {row['audit_id']}")
        by_method[spec["method"]].append(dict(**row, unit_id=spec["unit_id"],
                                             portrait_id=spec["portrait_id"], statement=spec["text"]))
    return {method: {
        "sampled_units": len(rows), "labels": dict(Counter(row["label"] for row in rows)),
        "full_support_100": pct(sum(row["label"] == "full" for row in rows), len(rows)),
        "full_support_wilson_95": wilson(sum(row["label"] == "full" for row in rows), len(rows)),
        "full_or_partial_100": pct(sum(row["label"] in ("full", "partial") for row in rows), len(rows)),
        "attribution_error_100": pct(sum(row["label"] == "speaker_error" for row in rows), len(rows)),
        "explicit_conflict_100": pct(sum(row["label"] == "contradicted" for row in rows), len(rows)),
        "unresolved_100": pct(sum(row["label"] == "unresolved" for row in rows), len(rows)),
        "units": rows,
    } for method, rows in by_method.items()}




def content_scores(out, base):
    spec = load(out / "content_sample_manifest.json")
    if base["unique_inventory_digest"] != spec["bank_digest"]:
        raise ValueError("ELARA sample used a different inventory")
    if {code: row["portrait_digest"] for code, row in base["methods"].items()
        if "portrait_digest" in row} != spec["portrait_digests"]:
        raise ValueError("An evaluated portrait differs from the paired sample")
    cards = [card for path in sorted(out.glob("blind_content_batch_*.json")) for card in load(path)]
    if digest(cards) != spec["cards_digest"]:
        raise ValueError("The blinded content audit sample changed")
    judgments = load(out / "content_judgments.json")["judgments"]
    index = spec["cards"]
    if Counter(r["audit_id"] for r in judgments) != Counter(index.keys()):
        raise ValueError("Every content card needs one verdict")
    by_method = defaultdict(list)
    for row in judgments:
        review = index[row["audit_id"]]
        cited = row["candidate_ids"]
        if (row["label"] not in CONTENT_LABELS or not row["reason"].strip() or
                len(set(cited)) != len(cited) or set(cited) - review["candidates"].keys()):
            raise ValueError(f"Invalid content decision in {row['audit_id']}")
        if row["label"] != "unresolved" and not cited:
            raise ValueError(f"A content decision needs a cited excerpt in {row['audit_id']}")
        by_method[review["method"]].append(dict(**row, attribute_id=review["attribute_id"],
                                               audit_status=review["status"]))
    output = {}
    for method, rows in by_method.items():
        result = {"units": rows}
        for status in ("supported", "uncertain"):
            eligible = [r for r in rows if r["audit_status"] == status]
            counts = Counter(r["label"] for r in eligible)
            result[status] = {
                "sampled": len(eligible), "labels": dict(counts),
                "retained_100": pct(counts["retained"], len(eligible)),
                "retained_wilson_95": wilson(counts["retained"], len(eligible)),
            }
        output[method] = result
    return output


def frozen_self(out, base, source, gold, methods=METHODS):
    dialogues, _, bank, snapshot = inventory(source, methods)
    atoms = anchor_inventory(gold)
    if (base["source_digest"] != digest(dialogues) or base["gold_digest"] != digest(atoms)
            or base["unique_inventory_digest"] != digest(bank)):
        raise ValueError("Source A-only evidence, ELARA inventory or AT gold changed after preparation")
    for code, (_, folder) in methods.items():
        expected_archive = base["methods"][code].get("archive_partition")
        if expected_archive is not None:
            archive = load(RUNS / folder / "portrait.json")["archive"]
            if archive_partition(snapshot[code], archive, bank) != expected_archive:
                raise ValueError(f"The archive coverage changed after preparation for {code}")
    judgments = load(out / "self_judgments.json")
    result = self_scores(base, atoms, judgments["methods"], snapshot)
    save(out / "self_scores.json", result)
    return result, dialogues


def report(out, source, gold, methods=METHODS):
    base = load(out / "structure.json")
    self_result, dialogues = frozen_self(out, base, source, gold, methods)
    manifest = load(out / "evidence_sample_manifest.json")
    source_windows = {w["window_id"]: w for w in windows(dialogues)}
    seen = set()
    for path in sorted(out.glob("blind_evidence_batch_*.json")):
        for card in load(path):
            audit_id = card["audit_id"]
            if audit_id in seen or audit_id not in manifest:
                raise ValueError(f"Unknown or repeated audit card {audit_id}")
            seen.add(audit_id)
            wanted = manifest[audit_id]
            if card["statement"] != wanted["hypothesis"] or [r["window_id"] for r in card["evidence"]] != wanted["window_ids"]:
                raise ValueError(f"Evidence packet differs from its frozen sample {audit_id}")
            for window in card["evidence"]:
                origin = source_windows[window["window_id"]]
                if window["text"] != origin["reference"] or window["turn_ids"] != origin["turn_ids"]:
                    raise ValueError("Evidence windows must quote the original A-only input")
    if seen != manifest.keys():
        raise ValueError("An audit card is missing")
    annotations = load(out / "evidence_judgments.json")["judgments"]
    grounded = evidence_scores(manifest, annotations)
    if set(grounded) != set(self_result):
        raise ValueError("A completed portrait lacks an A-only evidence audit")
    contents = content_scores(out, base)
    if set(contents) != set(self_result):
        raise ValueError("A completed method lacks a paired content audit")
    for code, parsed in self_result.items():
        base["methods"][code]["self_report"] = parsed
        base["methods"][code]["grounded_audit"] = grounded[code]
        base["methods"][code]["content_audit"] = contents[code]
    base["annotation_digests"] = {
        "self": digest(load(out / "self_judgments.json")),
        "evidence": digest(annotations),
        "sample": digest(manifest),
        "content": digest(load(out / "content_judgments.json")),
        "content_sample": digest(load(out / "content_sample_manifest.json")),
    }
    export_report(out, base)
    print(f"Verified {len(self_result)} portraits and {len(annotations)} blind evidence judgments")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "prepare-content", "score-self", "report"))
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--gold", type=Path, default=GOLD)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--ours-run", type=Path, help="Evaluate only the portrait in this Ours run")
    parser.add_argument("--model-home", type=Path, default=HOME)
    args = parser.parse_args()
    methods, output = METHODS, args.output or OUT
    if args.ours_run is not None:
        run = args.ours_run.resolve()
        if not (run / "portrait.json").is_file():
            parser.error("--ours-run must contain portrait.json")
        methods = {"Ours": ("Ours " + run.name.removeprefix("portrait_"), run)}
        output = args.output or OUT.parent / f"portrait_evaluation_{run.name.removeprefix('portrait_')}"
        if output.resolve() in (OUT.resolve(), run):
            parser.error("use a separate output directory for this portrait evaluation")
    if args.stage == "prepare":
        prepare(output, args.source, args.model_home, args.gold, methods)
    elif args.stage == "prepare-content":
        prepare_content(output, args.source, args.model_home, methods)
    elif args.stage == "score-self":
        result, _ = frozen_self(output, load(output / "structure.json"), args.source, args.gold, methods)
        for code, row in result.items():
            print(f"{code}: {row['score_100']:.1f}/100")
    else:
        report(output, args.source, args.gold, methods)


if __name__ == "__main__":
    main()

