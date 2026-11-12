# 1SC privacy pilot — protocol locked before Qwen evaluation

Date: 2026-10-31 (Asia/Shanghai). This is a feasibility pilot, not a confirmatory paper experiment.

## Questions and falsification criteria

1. Does A-only text permit recovery of dialogue-world attributes about B, beyond a query-only attacker? Compare per-item log score and positive disclosure with full dialogue, A-only, query-only, shuffled A turns, and unordered A words. Unknown ground truth is never a negative label. Log-score improvement is attacker-specific, not an estimator of true conditional mutual information.
2. Can a model discriminate opposite holder assignments when the words and word counts are identical? Construct 24 pairs (4 discourse mechanisms × 6 attribute pairs), report accuracy, both-members-correct rate, probability separation, and cluster bootstrap intervals. Unordered words must give identical inputs for each pair. Positive performance here demonstrates relational/compositional information beyond bag of words, not a novel privacy mechanism.
3. Is any effect specific to dialogue form rather than ordinary semantics? Compare each controlled item to a noninteractive statement preserving the correct holder and polarity. Comparable narrative performance weakens the stronger claim of a distinct interaction-specific inference mechanism. Narrative length and wording are not exactly matched, so this is a diagnostic, not a clean causal estimate.

## Attacker and labels

Attacker knows that A speaks to hidden B, may also mention third parties, and receives one candidate proposition about B. It has no hidden B turns except in the full-dialogue upper control. No demographic/medical inference beyond literal dialogue facts is considered ground truth. The statements describe characters in a written corpus, not verified personal facts about real people. Prior condition retains the candidate proposition and setting only.

Truth and observational support are separate: true / false / unknown. Unknown means insufficient evidence and is not proof of absence. Natural labels and evidence spans are assigned by a single investigator before calls, with provisional status; no independent annotator agreement is claimed. Natural items are a purposive diagnostic sample from the official test split, not a prevalence estimate. Full dialogue is not an automatically trusted gold judge.

Annotation provenance clarification: the "investigator" above is the AI assistant running this project. These are provisional AI-assigned research labels, not human annotations. Independent human adjudication remains outstanding.

## Model and call discipline

Use the official Alibaba Cloud Beijing compatible endpoint and qwen-plus, temperature=0, thinking disabled, JSON output. Capture returned model name, tokens, raw answers, request hash, time, malformed output, and HTTP errors. One successful 14-token connection probe preceded the experiment. At most 99 subsequent request attempts, max 3 concurrent requests, max 4,000 output tokens per request. No secret is written to disk. No retries for authorization errors. Experiment views and opposite members of a controlled pair are never in the same API context; item order is seeded. Each request contains at most 6 independent items. The API sees no gold labels or condition names. Blinded opaque IDs prevent item IDs revealing labels/mechanisms.

## Statistical treatment

Treat one natural dialogue or one controlled pair as the resampling unit. Use 5,000 seeded cluster bootstrap samples and report 95% percentile intervals. Report macro-F1, accuracy, log loss, Brier score, ECE, AUPRC where applicable; soft scores are model-reported probabilities, not token log probabilities and are not assumed calibrated. Three-class scores on all natural labels and binary truth-known subsets must be separately named. With only 6 lexical assignments and 4 handcrafted template families, intervals do not justify population generalization. No training or template tuning on model results. Negative findings remain in the report. Shuffling/word deletion can change semantics or naturalness and cannot by themselves identify a causal pragmatic mechanism.

Numerical analysis clarification, before completed results: model-reported zero probabilities are floored at 1e-6 and renormalized for log scores only. Raw probabilities are retained. The resulting log-score gains are sensitive to this arbitrary floor and should not be read as information-theoretic leakage in bits.

Post-run scoring clarification (no new calls, no changed gold): four word-bag outputs declare `unknown` while reporting probabilities (0.5, 0.5, 0). Primary discrete accuracy, disclosure and unsupported assertion rates use the model's declared label, because it describes the actual assertion action. Probability scores use the reported distribution. The raw probability argmax, tie indicator and label disagreement are separately retained; forced-binary scoring breaks ties to false. This affects only word-bag discrete scores, not A-only or narrative findings.

## Scope and next step

This run tests RQ1 and parts of RQ2 plus unsupported sensitive assertions. It does not validate privacy-constrained reconstruction, general summary utility, real-world prevalence, novelty, or privacy–utility tradeoffs. A credible next stage needs independent human labels and naturalness ratings, more diverse paired rewrites, additional models/prompts and stochastic repeats, and a frozen held-out set.

## Data provenance

DailyDialog original archive: https://aclanthology.org/attachments/I17-1099.Datasets.zip . Paper: https://aclanthology.org/I17-1099/ . Original data is human-written conversation material; do not describe it as consented recordings of private conversations. License metadata for the maintained ConvLab conversion: https://huggingface.co/datasets/ConvLab/dailydialog (CC BY-NC-SA 4.0). Preserve noncommercial attribution/share-alike restrictions for derivatives. Archive hash is in data/source.json.
