# ISC 3.0 E1–E5 and turn accumulation — frozen exploratory protocol

Date: 2026-10-31, Asia/Shanghai. User requested actual experiments with qwen3.8-flash. Preserve all ISC 2.0 data/results. This is an exploratory pilot, not a preregistered confirmatory study or a completed ACL submission.

## Data and independence

Use all 64 target views from the frozen stage-2 natural set (32 dialogues; AI provisional truth/support). Use 60 opposite-holder groups/120 views from controlled_v2: one surface form for each of five mechanisms × twelve lexical assignments, selected deterministically without reading prediction outcomes. Keep all four facts per structured view: two mutually exclusive assigned properties, a privately specified iguana-ownership fact invisible in A, and a sailboat fact unspecified even in the full world. True/false/unknown and A-evidence labels are separate. Iguana facts create paired indistinguishable worlds; do not reward lucky guesses as evidence-grounded recovery. Full structured worlds are deterministic assignments, not model-generated ground truth.

Calibration uses lexical assignments 0–3 except surface form 3; other structured groups are test. Natural calibration/test is by dialogue hash, never by target or attribute. No test-set threshold tuning. This is threshold calibration, not task training; the hand-written controlled templates and prior results were already known to the investigator. Additional templates/language/holder variants are test-only. No trained RECOVER-B/SGCI model is claimed.

## Methods

Direct fixed-catalogue recovery; one-attribute-at-a-time classification; a prompted evidence-graph baseline (not a reproduction of GraphProfiler); RECOVER-B prototype (graph candidates followed by an independent-context competing-hypothesis verifier); generic direct self-check (two-pass budget control); open-world atomic fact discovery followed by catalogue normalization; one missing-B reconstruction and three diverse missing-B reconstructions followed by extraction. Generated B is explicitly marked hypothetical. All methods use the same model, temperature 0, thinking disabled; multi-hypothesis reconstruction requests three alternatives in one call. Report actual tokens and calls; compute is not identical across methods.

Every inference request contains one target view only. Candidate propositions in the controlled set specify the same two possible properties in both opposite worlds; no truth, group, split or mechanism identifiers enter prompts. Gold and hidden B never enter A-only/reconstruction/verification requests. Open-world discovery sees no catalogue. Normalization sees only generated facts and catalogue, not the source transcript. Unmatched open facts are exported and cannot be scored as verified true facts against an incomplete catalogue.

## E1: recovery–risk

Evaluate held-out test views with frozen thresholds [0, .5, .7, .8, .9, .95, .99, 1, abstain]. Select the threshold on calibration only for risk targets .05/.10/.20; maximize supported correct definite recoveries. A definite positive or negative assertion is correct only if its label matches known truth; unknown truth is unverified, never false. Report known-truth error fraction separately from conservative nonverified-claim fraction and unsupported-claim rate. Reliability selection uses a dialogue/group-cluster bootstrap upper bound on nonverified fraction, explicitly exploratory, not a population FDR guarantee. With zero asserted claims, risk is undefined; zero coverage is a valid outcome. Report factual and evidence-grounded counts separately, both positive facts and definite assertions. Plot descriptive risk curves without choosing test-optimal operating points. Natural support labels cover the full visible transcript; prefix support is only an annotation proxy.

## E2: reconstruction

Compare direct, single reconstruction, and three-hypothesis reconstruction; report added unsupported assertions, known-truth errors, correct recovery, grounded recovery, and calls/tokens. Preserve generated text. Reconstruction is a representation experiment, not extra observed information. Catalogue normalization/AI judgments are not human validation.

## E3 and 4.1: cross-turn and accumulation

Run every chronological A prefix, including empty and complete, for direct and RECOVER-B. Reuse identical complete/empty requests rather than rebill them. On controlled views additionally run every singleton, every leave-one-out subset, the minimal ordered prefix at half length and an equal-count seeded random subset, and holder-A swaps. Half-prefix and random subsets are selected before outputs and may coincide; retain that fact. Gold for incomplete controlled views is the full-world truth, while support is identifiable only if the minimal rule-specific support set is present. A correction's obsolete intermediate assertion is not current-world truth; report temporary reversals and unknown separately. No monotonicity is imposed on outputs.

Report fixed-cohort normalized prefix curves and absolute-k curves only on the same conversations having at least k A turns; distinguish right-censored cohorts. Pair full-context outcomes against the union of singletons, and evidence deletion against full context. Bootstrap by dialogue for natural and by template family for controlled, never by attribute or prefix. Count co-supported discoveries separately from mere extra tokens; these ablations are exploratory and not a proof of a new reasoning mechanism. Minimal support rules are author-coded for synthetic templates, not empirical natural recoverability ceilings.

## E4: counterfactuals

Opposite-holder property swaps, Casey-to-A holder swaps (me/my), rule-based supporting-turn deletion, and identical-A hidden-iguana-world pairs. Evaluate both paired-label correctness and appropriate unknown/abstention; mere prediction flipping is not sufficient. Full dialogue is not observed by the A-only method. Sailboat is unknown truth; iguana has specified hidden truth but unknown A-support.

## E5: robustness

Report domain strata, test-only alternative surface forms, manually authored Chinese semantic counterparts, and natural-versus-controlled transfer of the operating threshold. Chinese prompts retain English candidate propositions to isolate transcript language as much as possible; surface/translation fidelity remains author-assessed. Use one frozen model as requested. Historical qwen-plus comparisons are descriptive same-family evidence, not an independent model-family replication. Independent generator/evaluator families, human adjudication, and real-world verified personal truth remain uncompleted requirements.

## Execution and audit

Official Beijing compatible endpoint; qwen3.8-flash; at most 6 concurrent calls, at most 6,000 attempts and 8 million recorded tokens in this new suite. Model errors/truncation/schema failures remain missing, never unknown; no repair that changes prompts after outcomes. Stop on HTTP errors. Allow at most three logged transport attempts per request, fifty transport failures total. Record attempt before submission, raw body/model/finish reason/usage/timing. Never store the API key in files or public payloads. An unresolved attempt blocks automatic resubmission. Hash protocol, scripts, inputs and plans before model calls; derived dependent plans are frozen after their prerequisites exist.
