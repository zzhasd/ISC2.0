# DailyDialog 21-turn incremental experiment

This directory is independent of historical ISC113 runs. The user's protocol is
implemented with the original Direct Thinking and ELARA v1 code, and the corrected
predictor model `qwen3.8-flash`. All external AGD judgments are authored by the
designated **GPT-6.1 Sol, high reasoning** subagents on disjoint dialogue shards.
See `evaluation_assignments.json`; all use the same frozen rubric hashes in
`judge_prompt_manifest.json`. No Qwen evaluator is used.
ELARA's original Flash candidate audit is part of the predictor and is preserved.

## Frozen design

- All 31 dialogues with exactly 21 turns from `data/dailydialog.jsonl` (27 train,
  2 validation, 2 test); 341 A-only prefixes; 682 independent predictions.
- Original Direct limit 10; ELARA three generation passes plus candidate audit
  batches of 8, with no final output cap. No earlier prefix predictions are input.
- Independent Sweep precedes exposure to any predictions. Support packets merge
  exact-normalized candidates from both algorithms and Sweep, using neutral IDs
  and at most 12 candidates per batch. Source mapping is separate and private.
- E1/E2 atoms only; every supported atom assigned once to a canonical fact. All
  actual slots required; core weight 2, other weight 1. No old Gold; old-Gold
  novelty metrics are inapplicable.
- 31 cross-prefix fact indexes; alignment only changes identity, never evidence,
  slots, or credit at earlier prefixes. First discoveries exclude reappearances.
- Whole-dialogue paired bootstrap: 2,000 resamples, seed 20261106. Empty-pool recall
  is missing. Raw precision and recall summaries are micro averages; count curves
  are dialogue means. Per-prefix CIs are descriptive, not 11 significance tests.

## Run and resume

Run from this directory with Python (requests, NumPy, Matplotlib installed):

```powershell
python prepare.py
# Provide QWEN_API_KEY in the process environment or use the hidden prompt.
python run_inference.py --workers 6
```

API requests and raw responses are recorded in `inference/api/attempts.jsonl`.
Credentials are never written by these scripts. First valid cached responses are
reused. No automatic retry of unresolved requests with uncertain billing.

`evaluator_io.py` transports independent Sweep decisions only; it has no model API
or semantic heuristics. After the entire Sweep and inference finish:

```powershell
python prepare_evaluation.py support
# Designated Sol subagent authors agd_eval/judgments/support/{prefix_id}.json.
python prepare_evaluation.py pool
# Designated Sol subagent authors agd_eval/judgments/pool/{prefix_id}.json.
python prepare_evaluation.py alignment
# Designated Sol subagent authors alignment/judgments/{dialogue_id}.json.
python analyze.py
python -m unittest test_experiment.py -v
```

Support uses original AGD `items -> atoms` schema. Pool uses original `facts ->
slots/members` schema. Each alignment judgment contains `dialogue_id`,
`unified_facts: [{id: '<dialogue_id>::u001', ...}]`, and `mapping:
[{prefix_id, fact_id, unified_fact_id}]`. Every local fact must be mapped exactly
once; two facts in the same prefix cannot silently collapse to one identity.

## Outputs and limits

`results/prefix_metrics.csv` has exactly 682 rows on completion; trajectories include
absent facts explicitly. Other outputs: per-prediction and per-fact audit tables,
paired differences, bootstrap CIs, effect summary, source hashes, nonmonotonic
Pool review queue, and four figures in PNG/PDF. Missing prerequisites stop scoring.

Human review is not performed by an automated subagent. `human_audit.csv` contains
a reproducible six-dialogue/66-prefix pending review sample; reports must say human
calibration is incomplete. Codex subagent token usage is not available per prefix,
so judge token counts remain missing rather than fabricated zeros. The shared
Pool is a model-evaluated reference, not guaranteed exhaustive ground truth.
Sweep sensitivity reports coverage of cores independently supported by Sweep
within that same canonical Pool. Direct's output-cap effect is diagnosed; any
future cap-relaxed rerun must be reported as a separate modified algorithm.

The user explicitly declined the Direct-20 sensitivity rerun; retain the original
10-claim main experiment only. See `user_decisions.json`.

Concurrent reviewers must restrict packet preparation to their own dialogue, e.g.
`python prepare_evaluation.py pool --available --dialogue-id train_9306`. Use the
same dialogue filter for `alignment`; never overwrite another shard's judgment.
Review corrections require fresh batch receipts before `refresh-pool`; old inputs
and dependent judgments are archived by hash before invalidation.
