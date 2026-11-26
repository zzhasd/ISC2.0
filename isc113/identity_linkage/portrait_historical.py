"""Read AT's previously incurred full-context attempts with their frozen request."""
from collections import Counter
import json

from .core import digest, load, save


def historical(experiment, args, method, model_name):
    source = experiment.source
    payload = load(source / f"{model_name}_request.json")
    paths = [source / "attempts.jsonl", *sorted((source / "retry_epochs").glob("*/attempts.jsonl"))]
    rows = []
    for path in paths:
        if not path.is_file():
            continue
        with path.open(encoding="utf-8") as file:
            ledger = [json.loads(line) for line in file]
        task_ids = {row["task_id"] for row in ledger
                    if row["event"] == "start" and row.get("request") == payload}
        rows.extend((str(path.relative_to(source)), row) for row in ledger if row["task_id"] in task_ids)
    if not rows:
        raise ValueError(f"No historical attempt matches the frozen {model_name} request")
    if args.dry_run:
        experiment.log(f"[{method}] found {len(rows)} historical events for the exact frozen request")
        return
    completions = [row for _, row in rows if row["event"] == "complete"]
    attempts = []
    totals = Counter()
    for row in completions:
        body = row.get("body") or {}
        usage = body.get("usage") or {}
        totals.update({key: value for key, value in usage.items() if type(value) is int})
        attempts.append({
            "attempt_id": row["attempt_id"], "http_status": row.get("http_status"),
            "valid": row.get("valid", False), "error": row.get("error"),
            "finish_reason": (body.get("choices") or [{}])[0].get("finish_reason"),
            "usage": usage,
        })
    prediction = source / f"{model_name}_prediction.json"
    report = dict(
        method=method, frozen_request_digest=digest(payload), reused_historical_attempts=True,
        request_model=payload["model"], max_tokens=payload["max_tokens"],
        ledger_files=sorted({path for path, _ in rows}),
        historical_requests_started=sum(row["event"] == "start" for _, row in rows),
        historical_requests_completed=len(completions), historical_reported_tokens=dict(totals),
        attempts=attempts, new_requests=0, status="portrait_available" if prediction.exists() else "failed",
    )
    save(experiment.output / "report.json", report)
    save(experiment.output / "request.json", payload)
    if prediction.exists():
        save(experiment.output / "portrait.json", load(prediction))
    experiment.log(f"[{method}] status: {report['status']}. Historical requests: "
                   f"{report['historical_requests_started']}; new requests: 0.")
