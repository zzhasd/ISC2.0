# E2 reconstruction completeness amendment

2026-10-31, Asia/Shanghai. Added after inspecting v1 generation coverage, before v2 calls. V1 is preserved in full and is not relabeled as a complete reconstruction. This is an outcome-aware exploratory amendment, not pre-registration before v1.

V1 single-hypothesis reconstruction covered all A positions in only 30/90 controlled test views (mean position coverage 52.1%); multi-hypothesis coverage was 267/270. Natural single/multi full coverage was 38/46 and 135/138 hypotheses. These are instruction-adherence failures, so a strong E2 comparison needs a completeness-controlled baseline.

Rerun BOTH single and three-hypothesis generation for ALL 184 frozen views, calibration and test, not just failures. Preserve original reconstruction system prompts, append an explicit requirement to fill a provided output skeleton, and supply the observed reply positions. Give each a 3,200-token cap. No catalogue, gold, source B or world metadata enters generation. Require exactly the requested hypothesis count and exactly one nonempty reply per A position in every hypothesis. Invalid generation remains missing, with no selective repair or retry on 200 responses.

Extract with the unchanged evidence-constrained EXTRACT system, in a new context, using A, the hypothetical replies and the same frozen catalogue. This is the original E2 extraction task, not an external annotation/audit of sensitive generated text. No added external reconstruction-assertion judge is used; the rejected supplementary audit remains unexecuted.

At most 368 generation and 368 extraction requests, less if inputs deduplicate or generation fails validation. Existing 4,787 unique main-suite requests plus at most 736 added requests = 5,523 unique requests; bounded transport retries must remain below the original 6,000 attempts and 8 million recorded tokens. Use qwen3.8-flash and the same official Beijing endpoint, at most six concurrent calls, serially after the original runner. Credentials only through stdin/environment, never public files.

Report v1 and v2 separately, including coverage, missing/invalid outputs, supported recoveries, known-truth errors, unverified assertions, actual cost, and calibration-only risk thresholds on the unchanged split. V2 does not retroactively change v1 or establish a confirmatory method gain. All natural data are the same public scripted DailyDialog excerpts and all controlled people/worlds are fictional.
