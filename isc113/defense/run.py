"""Run Direct LLM Sanitization and SHIELD through ELARA v1 and frozen AGD."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from getpass import getpass
from importlib import import_module
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import requests

from isc113 import common
from isc113.client import Client
from isc113.run_ELARA_v1_iterate import BASELINE_METHOD, BASELINE_RUN, FROZEN_INPUTS, METRICS
from . import sanitize

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "work"
INPUTS = ROOT / "sanitized"
RESULTS = ROOT / "results"
METHOD_IDS = {"direct": "defense_direct_elara_v1", "shield": "defense_shield_elara_v1"}
METHOD_NAMES = {"direct": "Direct LLM Sanitization", "shield": "SHIELD"}
BASELINE_NAME = "ELARA v1（原始 A）"
TOKEN_PLAN_BASE_URL = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"


def token_plan_post(url, *, json, **kwargs):
    # Model Studio maps the public model ID to the 0902 snapshot.
    # Keep the snapshot ID in the existing AGD cache and scoring metadata.
    return requests.post(url, json=dict(json, model="qwen3.8-max"), **kwargs)


def load_inputs():
    algorithm = import_module("isc113.ELARA-v1")
    records = common.read(FROZEN_INPUTS)
    baseline = common.read(BASELINE_RUN / "method_manifest.json")
    if (len(records) != 298 or len({item["dialogue_id"] for item in records}) != 298
            or common.digest(records) != baseline["inputs_sha256"]
            or common.filehash(algorithm.__file__) != baseline["algorithm_sha256"]
            or algorithm.MODEL != baseline["model"] or algorithm.METHOD != BASELINE_METHOD):
        raise ValueError("Source inputs or ELARA v1 differ from the original experiment")
    for item in records:
        common.validate_input(item)
    common.freeze(WORK / "experiment.json", {
        "original_inputs_sha256": baseline["inputs_sha256"],
        "elara_sha256": baseline["algorithm_sha256"],
        "elara_model": algorithm.MODEL,
        "sanitizer_sha256": common.filehash(sanitize.__file__),
        "sanitizer_model": sanitize.MODEL,
        "methods": METHOD_IDS,
    })
    return records, algorithm


def make_client(key, stage, arm):
    # Client uses a run directory for its resumable ledger. Point it at this experiment.
    ledger_dir = WORK / stage / arm
    return Client(key, run_id=os.path.relpath(ledger_dir, common.BASE / "runs"))


def run_jobs(label, jobs, work, workers, stop_events=()):
    jobs = list(jobs)
    failures = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(work, *job): job for job in jobs}
        for done, future in enumerate(as_completed(futures), 1):
            if not future.cancelled():
                try:
                    future.result()
                except Exception as error:
                    job = futures[future]
                    failures.append({"job": str(job[-1]), "error": str(error)})
                    if len(failures) <= 10:
                        print(f"{label} {job[-1]} failed: {error}", flush=True)
            if any(event.is_set() for event in stop_events):
                for pending in futures:
                    pending.cancel()
            if done % 25 == 0 or done == len(jobs):
                print(f"{label} {done}/{len(jobs)}, failures {len(failures)}", flush=True)
    common.save(WORK / f"{label}_errors.json", failures)
    if failures:
        raise RuntimeError(f"{label}: {len(failures)} failed jobs")


def release(records, key, workers, smoke=False):
    clients = {arm: make_client(key, "sanitize", arm) for arm in METHOD_IDS}
    by_id = {item["dialogue_id"]: item for item in records}

    def artifact(arm, did):
        return WORK / "sanitize" / arm / "dialogues" / f"{did}.json"

    def work(arm, did):
        common.freeze(artifact(arm, did), sanitize.rewrite(clients[arm], by_id[did], arm))

    run_jobs("sanitization", ((arm, did) for arm in METHOD_IDS for did in by_id
                              if not artifact(arm, did).exists()), work, workers,
             [client.stop for client in clients.values()])
    results = {}
    for arm in METHOD_IDS:
        items = []
        for did, original in by_id.items():
            item = common.validate_input(common.read(artifact(arm, did)))
            turns = sanitize.validated_turns({"visible_turns": item["visible_turns"]}, original["visible_turns"])
            if item != dict(original, visible_turns=turns):
                raise ValueError(f"Release changed metadata for {arm}/{did}")
            items.append(item)
        if not smoke:
            common.freeze(INPUTS / f"{arm}_A.json", items)
        results[arm] = items
    return results


def infer(releases, algorithm, key, workers, smoke=False):
    clients = {arm: make_client(key, "inference", arm) for arm in METHOD_IDS}
    items = {arm: {item["dialogue_id"]: item for item in rows} for arm, rows in releases.items()}

    def folder(arm):
        return WORK / "inference" / arm

    def artifact(arm, did):
        return folder(arm) / "predictions" / f"{did}.json"

    def work(arm, did):
        item = items[arm][did]
        prediction, diagnostics = algorithm.pipeline(clients[arm], item)
        common.save(folder(arm) / "diagnostics" / f"{did}.json", diagnostics)
        common.freeze(artifact(arm, did), {"inputs_sha256": common.digest(item), "prediction": prediction})

    run_jobs("elara_inference", ((arm, did) for arm in METHOD_IDS for did in items[arm]
                                if not artifact(arm, did).exists()), work, workers,
             [client.stop for client in clients.values()])
    exports = {}
    for arm, rows in items.items():
        exports[arm] = {}
        for did, item in rows.items():
            result = common.read(artifact(arm, did))
            prediction = result["prediction"]
            if (result["inputs_sha256"] != common.digest(item) or prediction["method"] != BASELINE_METHOD
                    or any(prediction[field] != item[field] for field in
                           ("item_id", "dialogue_id", "dataset", "direction"))):
                raise ValueError(f"Invalid ELARA output for {arm}/{did}")
            exports[arm][did] = prediction
        if not smoke:
            common.freeze(folder(arm) / "dailydialog.json", list(exports[arm].values()))
    return exports


def configure_agd(base_url=None):
    from isc113.agd_append_1sc_20261123 import evaluate as shared

    shared.WORK = shared.append.ROOT = shared.append.WORK = WORK / "agd"
    shared.transport.ROOT = shared.transport.WORK = shared.WORK
    shared.SNAPSHOT = shared.WORK / "frozen/baseline"
    shared.RECON = "defense"
    shared.METHODS = {method: METHOD_NAMES[arm] for arm, method in METHOD_IDS.items()}
    if shared.transport.MODEL != "qwen3.8-max-0902":
        raise ValueError("AGD transport model differs from the frozen protocol")
    endpoint = (base_url or shared.agd.BASE_URL).rstrip("/")
    parsed = urlsplit(endpoint)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.query or parsed.fragment):
        raise ValueError("The AGD base URL must be an HTTPS API endpoint")
    shared.transport.URL = f"{endpoint}/chat/completions"
    shared.transport.requests = (SimpleNamespace(post=token_plan_post)
                                 if endpoint == TOKEN_PLAN_BASE_URL else requests)
    return shared


def evaluate(records, exports, key, workers, smoke=False, base_url=None):
    shared = configure_agd(base_url)
    base = shared.prepare()
    agd = shared.agd
    originals = {item["dialogue_id"]: item["visible_turns"] for item in records}
    if any(originals[did] != base["dialogues"][did]["visible_turns"] for did in originals):
        raise ValueError("Canonical A differs between ELARA source and AGD")
    if any(set(predictions) != set(originals) for predictions in exports.values()):
        raise ValueError("Prediction scope differs between experimental arms")
    for did in originals:
        dialogue = base["dialogues"][did]
        known = {candidate["id"] for candidate in dialogue["pred_candidates"]}
        new = {}
        for arm, method in METHOD_IDS.items():
            for i, claim in enumerate(exports[arm][did]["claims"]):
                raw = claim["claim"]
                candidate_id = "p_" + agd.stable_hash({"did": did, "text": agd.clean_claim(raw)})[:14]
                if candidate_id not in known:
                    new.setdefault(candidate_id, {"id": candidate_id, "claim": raw})
                dialogue["predictions"].append({
                    "id": f"{method}:{i}", "algorithm": method, "claim": raw, "candidate_id": candidate_id,
                })
        dialogue["append_candidates"] = sorted(new.values(), key=lambda row: row["id"])
        dialogue["pred_candidates"].extend(dialogue["append_candidates"])
        common.freeze(shared.WORK / "bindings" / f"{did}.json", {
            "original_visible_turns_sha256": common.digest(originals[did]),
            "exports_sha256": common.digest({arm: exports[arm][did] for arm in METHOD_IDS}),
        })
    os.environ["DASHSCOPE_API_KEY"] = key
    run_jobs("agd_judge", ((did,) for did in originals
                          if not (shared.WORK / "complete" / f"{did}.json").exists()),
             lambda did: shared.append.process(did, base["dialogues"][did]), workers,
             [shared.transport.STOP])
    if smoke:
        return
    if set(originals) != set(base["dialogues"]):
        raise ValueError("Scoring requires the full frozen scope")
    for did in originals:
        original_pred = agd.read(agd.path_for(shared.SNAPSHOT, "pred", did))["items"]
        new_pred = agd.read(agd.path_for(shared.WORK, "pred", did))["items"]
        if new_pred[:len(original_pred)] != original_pred:
            raise ValueError(f"Original grounding decisions changed for {did}")
        for stage in ("sweep", "gold", "sweep_support"):
            if common.filehash(agd.path_for(shared.SNAPSHOT, stage, did)) != common.filehash(
                    agd.path_for(shared.WORK, stage, did)):
                raise ValueError(f"Original {stage} changed for {did}")
    base["methods"].update(shared.METHODS)
    base["prediction_counts"].update({
        method: sum(len(pred["claims"]) for pred in exports[arm].values())
        for arm, method in METHOD_IDS.items()
    })
    common.freeze(shared.WORK / "data.json", base)
    shared.append.score()
    report(shared.WORK / "results")


def report(agd_results):
    summary = common.read(agd_results / "summary.json")
    names = {BASELINE_METHOD: BASELINE_NAME, **{m: METHOD_NAMES[a] for a, m in METHOD_IDS.items()}}
    counts = {method: Counter() for method in names}
    fields = {field for _, numerator, denominator in METRICS.values()
              for field in (numerator, denominator)}
    with (agd_results / "per_dialogue.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["algorithm"] in counts:
                counts[row["algorithm"]].update({field: int(row[field]) for field in fields})
    rows = []
    for method, name in names.items():
        for key, (label, numerator, denominator) in METRICS.items():
            hit, total = counts[method][numerator], counts[method][denominator]
            value = hit / total if total else None
            if ((key in {"R_full", "R_E1_full", "R_E2_full", "slot_coverage"}
                 and total != counts[BASELINE_METHOD][denominator])
                    or value != summary[method][key]):
                raise ValueError(f"Inconsistent AGD metric for {name}/{label}")
            rows.append({"condition": name, "metric": label, "numerator": hit,
                         "denominator": total, "value": value})
    RESULTS.mkdir(parents=True, exist_ok=True)
    with (RESULTS / "metrics.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    common.save(RESULTS / "metrics.json", rows)
    for method, name in names.items():
        values = [f"{label}={summary[method][key]:.2%}" if summary[method][key] is not None
                  else f"{label}=NA" for key, (label, _, _) in METRICS.items()]
        print(name, " | ".join(values), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--agd-workers", type=int, default=24)
    parser.add_argument("--agd-base-url", help="HTTPS base URL for the OpenAI-compatible AGD endpoint")
    parser.add_argument("--prompt-key", action="store_true", help="read the credential through hidden terminal input")
    parser.add_argument("--smoke", action="store_true", help="exercise the same pipeline for the first dialogue")
    parser.add_argument("--verify", action="store_true", help="verify sources without any API requests")
    args = parser.parse_args()
    if min(args.workers, args.agd_workers) < 1:
        parser.error("Worker counts must be positive")
    records, algorithm = load_inputs()
    if args.verify:
        configure_agd(args.agd_base_url).prepare()
        print("Verified 298 source dialogues, original ELARA v1 and the 1,630-fact AGD snapshot.")
        return
    key = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY")
    if args.prompt_key:
        key = getpass("DashScope API key: ").strip()
    if not key:
        parser.error("Set DASHSCOPE_API_KEY or QWEN_API_KEY")
    if args.smoke:
        records = records[:1]
    releases = release(records, key, args.workers, args.smoke)
    exports = infer(releases, algorithm, key, args.workers, args.smoke)
    evaluate(records, exports, key, args.agd_workers, args.smoke, args.agd_base_url)


if __name__ == "__main__":
    main()
