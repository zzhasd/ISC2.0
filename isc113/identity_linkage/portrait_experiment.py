"""Shared input, direct transport, exact-response reuse and export for AT experiments."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import threading
from uuid import uuid4

import requests

from .api import Client
from .core import HERE, MODEL, digest, freeze, load, save
from .portrait_summary import compact_summary_attributes, deduplicate, materialize

DEFAULT_SOURCE = HERE / "runs" / "portrait_one_elara_v1_summary_v2_AT"
ENDPOINT = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions"
LIMITATIONS = "依据仅有 A 方可见发言的候选属性。画像保留原有不确定性，缺少 B 的直接确认。"
DIRECT_LIMITATIONS = "依据 A 方可见发言推断 B。B 的回复不可见，证据引用对应 A 的发言。"


def chunks(items, size):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def ordered_map(function, jobs, workers):
    with ThreadPoolExecutor(max_workers=workers) as pool:
        yield from pool.map(function, jobs)


def now():
    return datetime.now(timezone.utc).isoformat()


def request(prompt, data, max_tokens=20000, thinking=True, json_mode=False):
    payload = {
        "model": MODEL, "temperature": 0, "enable_thinking": thinking,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(data, ensure_ascii=False, separators=(",", ":"))},
        ],
    }
    if thinking:
        payload["thinking_budget"] = 2048
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    return payload


def json_object(body, validate):
    choice = body["choices"][0]
    if choice.get("finish_reason") != "stop":
        raise ValueError("Provider did not finish the JSON reply")
    content = choice["message"]["content"].strip()
    if content.startswith("~~~"):
        content = content.split("\n", 1)[1].rsplit("~~~", 1)[0]
    fence = chr(96) * 3
    if content.startswith(fence):
        content = content.split("\n", 1)[1].rsplit(fence, 1)[0]
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object")
    return validate(parsed)


class DirectClient(Client):
    """Use the existing auditable request ledger with proxy handling disabled."""

    parse = staticmethod(json_object)

    def call(self, name, payload, validate):
        if not hasattr(self.local, "session"):
            self.local.session = requests.Session()
            self.local.session.trust_env = False
        return super().call(name, payload, validate)


class Experiment:
    def __init__(self, source, output, key, workers, cache):
        self.source = source
        self.output = output
        self.workers = workers
        self.cache = cache
        self.client = DirectClient(key, output, ENDPOINT) if key else None
        self.lock = threading.Lock()
        self.inherited = defaultdict(list)

    def attributes(self):
        unique = load(self.source / "deduplicated.json")
        filtered = load(self.source / "attributes_filtered.json")
        if unique != deduplicate(filtered):
            raise ValueError("AT deduplicated inventory differs from the exact dedup of filtered attributes")
        return unique, compact_summary_attributes(unique)

    def dialogues(self):
        inputs = load(self.source / "inputs.json")
        if digest(inputs) != load(self.source / "design.json")["inputs_digest"]:
            raise ValueError("AT A-only dialogue digest differs from its frozen design")
        return inputs["dialogues"]

    def log(self, message):
        with self.lock:
            print(message, flush=True)

    def run_jobs(self, function, jobs):
        return ordered_map(function, jobs, self.workers)

    def reuse_ledger(self, path):
        with path.open(encoding="utf-8") as file:
            for line in file:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    if not line.endswith("\n"):
                        break
                    raise
                if row["event"] == "complete" and row.get("http_status") == 200:
                    self.inherited[row["task_id"]].append((path, row["body"]))

    def ask(self, name, prompt, data, validate, *, share=False, max_tokens=20000, thinking=True, json_mode=False):
        payload = request(prompt, data, max_tokens, thinking, json_mode)
        cache_path = self.cache / (digest([ENDPOINT, payload]) + ".json")
        if share and cache_path.is_file():
            entry = load(cache_path)
            try:
                result = validate(entry["result"])
            except (ValueError, TypeError, KeyError, AttributeError):
                pass
            else:
                self.record(name, "shared_cache", cache_path.stem)
                return result

        task = digest(dict(name=name, endpoint=ENDPOINT, payload=payload))
        for source, body in self.inherited.get(task, ()):
            try:
                result = json_object(body, validate)
            except (ValueError, TypeError, KeyError, AttributeError, IndexError):
                continue
            self.record(name, "prior_ledger", task, source)
            return result
        if self.client is None:
            raise RuntimeError("Set TOKEN_PLAN_API_KEY before making live calls")
        def checked(obj):
            validate(obj)
            return obj

        raw, task = self.client.call(name, payload, checked)
        result = validate(raw)
        if share:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            temp = cache_path.with_name(f"{cache_path.stem}.{uuid4().hex}.tmp")
            temp.write_text(json.dumps({"result": raw}, ensure_ascii=False), encoding="utf-8")
            temp.replace(cache_path)
        self.record(name, "local_ledger", task)
        return result

    def record(self, name, origin, task, source=None):
        with self.lock, (self.output / "calls.jsonl").open("a", encoding="utf-8") as file:
            row = dict(name=name, origin=origin, task=task)
            if source is not None:
                row["source"] = str(source)
            file.write(json.dumps(row) + "\n")

    def manifest(self, method, config, input_name, data, files):
        design = load(self.source / "design.json")
        freeze(self.output / "experiment.json", {
            "method": method, "subject": design["subject"], "source": str(self.source),
            "input": input_name, "input_digest": digest(data), "input_count": len(data),
            "model": MODEL, "endpoint": ENDPOINT, "proxy": False, "call_output_limit": 20000,
            "thinking_budget": 2048, "temperature": 0, "config": config,
            "source_code_sha256": {
                Path(path).name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
                for path in (Path(__file__), *files)
            },
        })

    def statistics(self):
        rows = self.client.rows if self.client else []
        completions = [row for row in rows if row["event"] == "complete"]
        tokens = Counter()
        for row in completions:
            usage = (row.get("body") or {}).get("usage") or {}
            tokens.update({key: val for key, val in usage.items() if type(val) is int})
        calls = self.output / "calls.jsonl"
        shared = set()
        inherited = set()
        if calls.is_file():
            for line in calls.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                if row["origin"] == "shared_cache":
                    shared.add((row["name"], row["task"]))
                if row["origin"] == "prior_ledger":
                    inherited.add((row["name"], row["task"]))
        return {
            "requests_started": sum(row["event"] == "start" for row in rows),
            "requests_completed": len(completions),
            "valid_responses": sum(bool(row.get("valid")) for row in completions),
            "requests_with_reported_usage": sum(bool((row.get("body") or {}).get("usage")) for row in completions),
            "shared_cache_hits": len(shared),
            "prior_ledger_hits": len(inherited),
            "provider_reported_tokens": dict(tokens),
            "total_request_seconds": round(sum(row.get("elapsed_seconds", 0) for row in completions), 2),
        }

    def export(self, portraits, *, unique=None, audit=None, archive=None):
        limitations = LIMITATIONS if unique is not None else DIRECT_LIMITATIONS
        items = []
        for index, portrait in enumerate(portraits, 1):
            items.append(dict(portrait, portrait_id=f"R{index:04d}"))
        obj = {"portraits": items, "limitations": limitations}
        if archive is not None:
            obj["archive"] = archive
        save(self.output / "portrait.json", obj)
        if unique is not None:
            evidence = materialize(obj, unique)
            if archive is not None:
                by_id = {row["unique_id"]: row for row in unique}
                evidence["archive"] = [
                    dict(row, source_details=[by_id[uid] for uid in row["unique_ids"]]) for row in archive
                ]
            save(self.output / "portrait_evidence.json", evidence)
        lines = ["# 个人画像", "", limitations]
        previous = None
        for item in items:
            topic = item.get("topic")
            if topic and topic != previous:
                lines.extend(["", f"## {topic}", ""])
                previous = topic
            lines.append(f"- {item['statement']}")
        (self.output / "portrait.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        save(self.output / "report.json", {
            "finished_utc": now(), "portraits": len(items),
            "experiment_statistics": self.statistics(), **(audit or {}),
        })
        self.log(f"Exported {len(items)} portrait entries to {self.output}")


@contextmanager
def output_lock(output):
    output.mkdir(parents=True, exist_ok=True)
    lock_path = output / ".running"
    with lock_path.open("x", encoding="utf-8") as lock:
        lock.write(str(os.getpid()))
    try:
        yield
    finally:
        lock_path.unlink()


def cli(method, run, configure=None, argv=None):
    parser = argparse.ArgumentParser(description=method)
    parser.add_argument("subject", nargs="?", default="AT")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=3)
    parser.add_argument("--dry-run", action="store_true")
    if configure:
        configure(parser)
    args = parser.parse_args(argv)
    args.source = args.source.resolve()
    design = load(args.source / "design.json")
    if args.subject != design["subject"]:
        parser.error("subject does not match the frozen source design")
    output = (args.output or HERE / "runs" / f"portrait_{method}_{args.subject}").resolve()
    if output == args.source or args.source in output.parents:
        parser.error("use a separate experiment output directory")
    cache = HERE / "runs" / "portrait_exact_batch_cache"
    key = os.getenv("TOKEN_PLAN_API_KEY")
    with output_lock(output):
        experiment = Experiment(args.source, output, key, args.workers, cache)
        run(experiment, args)

