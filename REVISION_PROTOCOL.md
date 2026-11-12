# Qwen3.8-Flash revision: frozen before added experiment calls

Date: 2026-10-31, Asia/Shanghai. Exploratory extension of the existing pilot; no confirmatory registration or new novelty claim. Preserve every original file and original qwen-plus result.

## Rerun

Change only `model` to `qwen3.8-flash` in the original 62 stage-1, eight singleton and 100 stage-2 planned requests. Include all three originally cancelled stage-2 repeats. Prompts, input grouping, temperatures and output caps remain unchanged. Compare models on actual available paired outputs; malformed/truncated output is missing, never unknown. The new probe used 29 tokens. Do not inherit the old probe's 14-token usage.

## Expanded natural data

Draw 96 additional uniform-random, deduplicated test dialogues, then include every remaining dialogue matching the pre-existing stage-2 enrichment regex. Exclude normalized train/validation matches, both earlier sample sets and within-test duplicates before selection. Keep random and enrichment arms separate and report the residual enrichment pool, which is small after the earlier samples. Fixed seed 20261101; retain the existing 20-attribute catalogue. Both speakers are hidden in turn. The Codex assistant reads all selected full dialogues and assigns provisional truth, A-only support and turn evidence before attacks; this is AI annotation, not independent human annotation. Unknown is not false. Human reviewer fields remain blank.

Evaluate A-only and one-target full dialogue in separate contexts. Unlike the original stage-2 full control, the added full control uses one target per call to avoid multi-target formatting confounding. The expanded data do not retroactively change stage-1 or stage-2 gold. Also run conservative no-evidence baseline and stratified dialogue-cluster bootstrap with 5,000 draws.

## Controlled scale and repeats

Construct 240 opposite-holder pairs (5 mechanisms × 12 lexical assignments × 4 surface forms), ten times the original 24 pairs. Mechanisms: confirmation, reference, correction, cross-turn binding, possessive presupposition. All opposite pair members have identical unigram multisets. Conditions: intact A-only, proposition-preserving noninteractive narrative, shuffled turns, unordered words. Conditions/opposite members never share an API context. Use opaque IDs; no truth, mechanism or condition labels in requests. Report template and lexical clustering, pair accuracy, F1, log loss, Brier, ECE and AUPRC; self-reported probabilities are not token likelihoods or true mutual information. Narrative controls preserve propositions but are not exact semantic/naturalness matches. Generated templates are not natural conversations; scale does not create independent template families.

Use a seed-selected 24-view stage-2 subset for exact temperature-0 repetition and three temperature-0.7 trials. Do not choose failures. Report both decision and view-level variation; stochastic sampling repeats are not additional independent conversations. Use controlled matched comparisons with permutation tests and Holm adjustment; name the resampling unit and retain all negative results. More syntactic variants do not solve human naturalness validation.

## Downstream amplification and utility

Use all 64 stage-2 A-only views and their frozen provisional labels. Compare direct summary, ordinary reconstruction then summary, privacy-constrained reconstruction then summary, and conservative evidence-only summary. Reconstruction and summary see only A. No gold labels or hidden B are sent to generation or output annotation. Freeze generation and scoring prompts before calls. Extract catalogue assertions from each summary in a separate context. Evaluate newly explicit true attributes absent from prelabelled sufficient A support, unsupported/false assertions, overall true disclosure, and paired utility. A separate same-model judge scores observable non-sensitive content retention and factual consistency against A (0–4), blinded to method, truth and source B. These are model-assessed utility proxies, not human quality scores; preserve text for human review. Token length is a descriptive measure, not utility. Report privacy–utility tradeoffs and dialogue-cluster intervals, including the possibility of ineffective defense. This cannot protect information already visible in A.

## Execution

Official Beijing endpoint, thinking disabled, nonstreaming JSON. At most 6 concurrent calls per process, at most two simultaneous processes (12 total), 1,800 requests per plan and 8 million recorded tokens across revision. Secret only stdin/environment. Freeze public payloads, hash inputs, log attempt before network submission and save raw response, model, usage, finish reason, errors and timing. Stop a process on any network/HTTP failure; any resume/retry is logged and must respect caps. Unreturned attempts are flagged rather than silently replayed. No automatic model fallback. Do not retune gold from attack results. Keep original and added experiments separate in analysis.

Execution clarification before expanded outcomes: a transient TLS EOF occurred in the rerun. Permit up to two transport-only resumes per invocation, with each retry recorded as a new attempt, identical payload, prior completion preserved, and a resume audit. No HTTP/auth/rate-limit retries. Failed or unreturned transport attempts may still incur unknown billing. The aggregate token limit is checked before each wave; in-flight output can exceed the boundary by at most one wave per active process.

Reliability clarification after observing repeated transient EOFs: reuse one HTTPS session per persistent worker thread. Allow up to twelve transport-only wave resumes per invocation, at most three attempts for a particular task and at most fifty extra attempts for a plan. These change transport handling only; frozen prompts, samples and models are unchanged. No retry is allowed for HTTP/auth/rate-limit errors. Every paid attempt remains logged, and the aggregate recorded-token cap remains in force.

## Remaining human work

Controlled construction deviation: inspection of v1 errors revealed ambiguous confirmation imperatives ("No, swap...") and subject-agreement errors. Preserve v1 and freeze a v2 dataset/plan that changes only the confirmation text to explicit reported acceptance/rejection of the original versus reversed assignment. Repeat the complete 320-request controlled experiment; do not pool versions or claim v2 was preregistered before v1 outcomes. All other samples, conditions, batch grouping and gold assignments are retained. The 8-million recorded-token ceiling remains unchanged.

Output-judge validity deviation: v1 inspection found that the scorer sometimes transferred A's self-statements to hidden B (e.g. A's unemployment-check request). Preserve v1 but do not use those privacy counts as valid findings. Freeze v2 with explicit A/B counterexamples, an assertion-holder field, and narrower explicit-assertion rules. Re-score all 256 unchanged summaries independently; do not change source/gold or generation. Utility remains an AI proxy. Inspect every definite v2 assertion and retain any remaining judge errors instead of presenting them as reliable leakage.

Two independent human annotations, agreement/adjudication, naturalness and semantic-equivalence ratings, broader model comparison and real-world data authorization cannot be manufactured in this run. Export concrete review packets and report these as incomplete. Related-work novelty needs a separate literature review and is not established by these experiments.
