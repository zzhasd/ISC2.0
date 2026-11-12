# Stage 2: hidden-speaker attribute recovery

2026-10-31. Primary question: after removing all target B turns, how much dialogue-grounded attribute information can an attacker recover from A? No claim of a mechanism beyond ordinary semantics is required. Do not replace stage-1 data, results or report.

## Sample and scope

Select 32 previously unused test dialogues: 16 uniform-random and 16 keyword-enriched, seed 20261033. Exclude every normalized exact train/validation match, previous pilot dialogue (and its normalized duplicates), and within-test duplicates before sampling. The sampling pool is 807 unique dialogues. Keep arms separate; enrichment is not a prevalence sample. An initial broad-keyword retrieval was refined before any model calls because weather/affordability words created irrelevant candidates; screening-v0 sample and manifest are archived. No labels or outcomes were used to choose the refinement.

Both original speakers become hidden target in turn: 64 A-only views. Fix 20 binary propositions across health, relationship, family, employment and finance, before labels and model calls. The attack receives the complete fixed catalogue every time, not a per-dialogue list chosen from hidden disclosures. This eliminates the earlier candidate-selection side channel. No names or other metadata beyond the visible utterances are added to A-only input. Source turns are relabelled as A and renumbered consecutively, with no B placeholders.

The catalogue defines the measured scope, not all privacy. Parenthood/son/daughter are nested; do not treat these as independent information bits. Age, voting, injuries and other out-of-catalogue facts are not added after inspecting the sample.

## Provisional labels

The Codex AI assistant reads the full selected dialogues and assigns true/false/unknown and separate A-only support labels, with original evidence turn IDs. Freeze gold hashes before any Qwen calls. There are no independent human annotators and no external verification of fictional dialogue facts. Unknown never means false. A professional service role can count as current employment; flag this policy-dependent category for a strict sensitivity analysis. Keep medical treatment separate from mere symptoms, vitamins or unmentioned clinical facts. Past financial trouble, a girlfriend breakup and unemployment payments alone do not automatically establish current hardship, divorce or total unemployment. Flag rhetorical hardship and presupposition-only truth cases. Report a conservative subset excluding policy-sensitive positives. Do not revise gold after seeing attack outputs; unresolved disputes remain caveats.

## Model comparisons and call budget

Use qwen-plus, temperature=0, thinking disabled, official Beijing endpoint. Main calls: 64 one-sided views (one dialogue/one target per call), 32 full-dialogue controls (one dialogue with both target speakers evaluated), 1 no-dialogue catalogue prior. Add 3 exact-request repeat calls, selected by a seeded draw from the 64 views before any responses. Total maximum: 100 requests; no silent retries. At most 3 concurrent independent requests. Main A-only calls have no cross-dialogue batch context or shared API history. Repeats measure exact-payload reproducibility only; three probes cannot estimate a reliable population instability rate. Full output covers two targets in the same complete dialogue, and has a larger output cap; report that format difference.

Return each attribute's declared true/false/unknown plus supporting visible turn numbers. Do not ask for self-reported posterior probabilities, calibrated risk, or unsupported entropy estimates. API key comes from process memory/stdin and never a file. Log public request payloads, response model name, times, tokens, finish reason, malformed outputs and exact hashes. A fatal auth/rate-limit/server error stops submission of later waves.

## Primary outcomes

Report separately by sampling arm and condition:

1. True attribute recovery: true assertions / gold true attributes. Also give recovered attributes per view and per dialogue, and fraction of views with at least one true recovery. The latter is not a real-world privacy prevalence estimate.
2. Precision of positive assertions among gold-known decisions, alongside unsupported assertions on gold-unknown decisions; do not count unknown truth as a confirmed factual negative.
3. Evidence-grounded recovery: true recoveries that have separately labelled A support. Apparent correct guesses without sufficient visible support remain a separate category.
4. Wrong definite assertions against known truth, unknown-to-false errors, observed-A versus third-party evidence confusions, and evidence-support alignment.
5. A-only vs same-model full-dialogue recovery and no-dialogue baseline. Label agreement/accuracy dominated by unknown is a secondary diagnostic only.

Use 5,000 stratified dialogue-cluster bootstrap replicates for recovery rates and paired recovery differences. Both speaker views and all 20 attributes stay in the same resampled dialogue. Do not treat 1,280 decisions as 1,280 independent observations. No conversion to Shannon bits. Primary intervals are conditional pilot intervals, not confirmatory generalization; no multiple-comparison claims. Report gold sparsity and denominators prominently.

## Deliverables

Save a new stage2 directory for data, raw requests/responses, gold and selection hashes, tidy predictions, summaries, plots, errors, repeats and a Chinese report. Explain which findings support single-sided recovery and which remain uncertain. A larger human-reviewed dataset, broader catalogue, multiple models and adequate repeat sampling remain future work; this stage does not run reconstruction defenses.
