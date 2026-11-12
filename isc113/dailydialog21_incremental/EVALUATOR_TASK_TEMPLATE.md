# Single-dialogue Sol-high evaluation task

The coordinator assigns exactly one dialogue ID. Complete its remaining 11-prefix
Support, Pool, and Alignment work, then report completion and stop. The user
requires GPT-6.1 Sol with high reasoning for external evaluation. Do not call any
Qwen or other model API, spawn agents, modify shared code, or write other IDs.

Read this directory's README and the original frozen AGD rubric in
`../agd_eval_20261106/agd_eval.py` (SUPPORT_SYSTEM, POOL_SYSTEM and clarifications).
Read the relevant `evaluator_io.py` function signatures. All helpers perform
transport/validation only; **you must author the actual semantic decisions**.

Only read your dialogue's neutral `agd_eval/packets/support/{prefix_id}.json`,
its current A-only utterances, and its existing neutral judgments. Never read
`inference`, `data/selected_dialogues.json`, `private_source_mapping.json`, or
`results`. The independent Sweep is already frozen; do not modify it. Do not
inspect later A prefixes before completing the current prefix's Support and Pool.

Proceed in k=1 to 11 order. Check complete judgments and partial batch receipts
before submitting anything: retain valid existing work. Use
`show_support(prefix_id, batch)` to display one original batch, at most 12
candidates, then `publish_support_batch` to submit your real decisions. Preserve
all assertion strength, time, quantity, negation, conditions, and unsupported
details. Split independently meaningful B relations; do not fragment a single
event's necessary qualifiers. E1 and E2 are valid, other labels remain explicit.
Questions do not establish their unknown answers, A's attributes are not B's,
and empty conversation/question states are NOT_B. Evidence IDs must belong to
the current odd-turn prefix. Do not simulate judgments with keyword rules.

After a prefix's Support is complete, prepare its dialogue's neutral Pool input:

```powershell
python prepare_evaluation.py pool --available --dialogue-id ASSIGNED_ID
```

Use `show_pool` and `publish_pool` for real semantic consolidation: same entity,
event and relation; different relations remain different facts. Each valid atom
is assigned exactly once. Every slot is required, core weight 2 and other weight
1. Members cover only fields they actually express, not details from another
member. A compound atom mixing distinct relations needs a genuine Support
re-review before pooling.

An E1 full fact must have E1-member coverage of every required slot. If a required
detail is supported only by E2 members, do not promote the complete fact to E1;
genuinely re-review the fact level or the member coverage. The publisher checks
this necessary condition without making a semantic decision for you.

`revise_support_batch` archives old decisions and receipts. After an actual
atomic Support revision use `prepare_evaluation.py refresh-pool --prefix-id PID
--reason "specific reason"`. For a semantic Pool/coverage revision with unchanged
Support, add `--pool-only`. Both modes archive downstream artifacts and invalidate
stale alignment. Never overwrite old evidence without the revision trail.

Once all 11 Pools exist:

```powershell
python prepare_evaluation.py alignment --available --dialogue-id ASSIGNED_ID
```

Author the cross-prefix identity mapping with `publish_alignment` (read its
signature). Every local fact maps once, no two facts in one prefix map to the
same unified ID, and different events/time/negation are not overmerged. Alignment
is identity-only: do not backfill future support, slots, or credit. Metadata must
truthfully record `gpt-6.1-sol`, `high`, the exact packet hash, and
`identity_only_no_support_backfill=true`.

Report one completed dialogue to the coordinator, with local fact and identity
counts. If a helper blocks progress, send the exact issue for repair. If the
model usage limit recurs, report it honestly and stop; never substitute a model
or manufacture a completion record.
