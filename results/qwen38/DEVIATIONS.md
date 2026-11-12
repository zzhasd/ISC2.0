# Revision execution and validity deviations

Historical stage-1 and stage-2 input/result files were preserved. `original_preservation_hashes.json` and `audit.json` verify this. The rerun payloads change only the model field. New data and provisional labels are separate under `data/revision/`.

## Transport

Repeated transient TLS EOFs occurred despite successful calls returning `qwen3.8-flash`. An earlier read timeout was also recorded. Requests were resumed with identical payloads and separate attempt IDs. HTTP/auth/rate-limit errors are not automatically retried. The runner was updated to reuse a distinct HTTPS session per persistent worker thread and to allow at most 12 transport-only wave resumes per invocation, three attempts per task and 50 extra attempts per plan. Aggregate recorded usage is capped at eight million tokens, checked before waves. Failed transport work may have reached the service; actual billing for work with no usage response is unknown.

The first stopped-on-error status was briefly mistaken for a terminated reconstruction process while its bounded retry was already running. A redundant resume process was launched; its preflight unreturned-attempt guard blocked it before any API submission. The original process completed. The temporary unresolved-attempt marker reflected then-active requests, all later returned; `defense_reconstruction/unresolved_attempts_resolution.json` records zero remaining unlogged attempts. A per-plan operating-system lock now also prevents concurrent runners.

Never combine a failed transport record with an answer or fill it as unknown. Successful retries are scored once; every attempt remains in raw logs. Exact counts, task IDs, usage and final completeness are in `audit.json`.

## Controlled-template validity

After v1, inspection of errors revealed ambiguous confirmation phrases such as “No, swap the assignment” and subject-agreement errors such as “you has”. These can confound the construction's intended label and are not legitimate evidence of model failure on a clean confirmation mechanism.

Preserve `controlled/` and `data/revision/controlled.json` unchanged. Freeze v2 with explicit reported acceptance/rejection of the original versus reversed assignment. Only the confirmation text changes; the other mechanisms, lexical assignments, intended labels, conditions and batching remain fixed. Repeat all 320 requests, not just the failures. The report's controlled findings use `controlled_v2/`; the two versions are not pooled or counted as independent samples. V2 is a post hoc validity repair, not an independent preregistered confirmation. Human naturalness and semantic-equivalence review remains incomplete.

One v1 word-bag response omitted declared labels for five of its six answers. The strict parser excludes that whole six-item batch from declared-label/probability joint metrics and preserves the raw output. It does not invent labels from probabilities. The effective denominator is reported. Apply the same strict rule to v2, and retain any validation errors there.

## Output-judge validity

The first complete 256-summary scoring pass sometimes assigned A's self-statements to B. Examples and original quotes are in `judge_validity_review.md`. These privacy counts are invalid as evidence of B's disclosure and are retained for audit rather than used in the main report.

Freeze a second scorer with explicit A/B counterexamples, an assertion-holder field and narrower explicit-assertion rules. Re-score all 256 identical summaries in separate contexts, with no gold, true B turns or method metadata supplied. Do not re-generate summaries or change source/gold. The main output analysis uses `defense_judge_v2/`. This scorer was repaired after seeing v1 validity errors; it is not a blinded independent human ground truth. Inspect its definite assertions and expose remaining errors or uncertainty. Automated utility ratings remain proxies, with possible ceiling effects and same-model bias.

## Scientific limits retained

After v2 scoring, the Codex assistant checked every one of its 63 definite candidates against the summary and relevant visible-A alias context. Twenty-eight candidates failed the explicit-assertion definition (e.g. gender-to-pregnancy negation, viral-infection-to-no-cold, success-to-employment, breakup-to-marital-status, future intent-to-current-job-search, or qualified predicted replies). These are marked rejected; a few ellipsis quotes are replaced by actual contiguous source spans with original quotes retained. The decisions, source hashes and reasons are in `defense_judge_v2/assertion_review.json`; model-only scores remain unchanged, and the derived reviewed analysis is in `defense_reviewed/`. This is post hoc AI candidate review, not independent human adjudication, and it does not estimate missed-assertion recall.

All natural truth/support labels were assigned by the Codex assistant before the corresponding attack calls. They are provisional AI labels, not independently verified human gold. Unknown is not false. The added random sample comes from the residual pool after prior selections, not an untouched population sample. There are only two explicit natural false labels in the added set; employment dominates the positives. Full dialogue model answers are not used as gold.

Controlled templates enforce exclusive attribute assignments for a reasoning diagnostic; real people may have both listed properties. Narrative controls preserve intended propositions, but length, wording, discourse semantics and naturalness are not perfectly matched to A-only. No conclusion of a newly identified causal pragmatic channel or real-world prevalence is warranted.

Two-person independent annotations, adjudication, naturalness judgments, externally validated utility, broader model-family replication and real-private-conversation authorization remain unfinished. The human review fields are blank and the agreement script reports pending until actual human entries exist.
