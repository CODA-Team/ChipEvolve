## Evidence Discipline

- Read the artifact packet once first; it already contains validity, metrics, artifact sizes, and exact paths.
- Prefer each Student's `knowledge_card` for mechanism and lesson. Use final messages for compact summary only.
- Do not rerun or reread artifacts broadly unless a validity conflict needs it. Repeated artifact reads without a mechanism decision are review inefficiency.
- Use Student log/efficiency diagnosis when present; if missing, infer only the minimum from `metrics.json`, DPL logs, counters, and artifact state.

## Validity Gate

- A candidate is not promotable if build/evaluator failed, metrics are missing, diff is missing/empty, agent message is missing, legality failed, source/binary/metrics are stale, or the DPL flow timed out.
- Rank promotable candidates by legal final `metrics.json:hpwl`. Ignore bbox/proxy HPWL for promotion.
- Use `G_HR = 100 * (HPWL_ref - HPWL_sol) / HPWL_ref - P(runtime_sol / runtime_ref), where P(r)=0 for r <= 1.10 and P(2.0)=1.0 percentage point` only to explain runtime value and repair priority. A faster worse-HPWL candidate is not the headline elite unless lower-HPWL candidates fail validity gates.
- Treat runtime and displacement as diagnostics: useful controlled search, under-exploration, fixable implementation cost, or unsupported work. Do not over-reward baseline-like runtime that avoids the hard HPWL search; when a legal candidate stays far under budget and HPWL is weak, review it as possible under-exploration and route a stronger bounded search.

## Review Focus

- Identify the real executed mechanism, not only the claimed mechanism. Zero counters or stale artifacts mean non-executed/negative evidence even if inherited code produced acceptable metrics.
- If a Student spends substantial time in diagnosis without reaching a first patch/build/eval loop, review that as execution inefficiency and route the next packet toward a faster concrete implementation path.
- Treat `reject` as "not the final candidate for this trial", not as automatic method death. Inspect the source diff, counters, stage movement, and logs before deciding whether the failure is implementation, handoff/composition, or method-level.
- Attribute stage movement across legalization, improve placement/DPO, handoff, final mirror contribution, runtime, and counters.
- Classify each result as `final donor`, `stage donor`, `active mechanism workbench`, `validated-low-ROI`, `non-executed route`, or `negative evidence`.
- Preserve stage donors when downstream erases a gain; the next route should repair the consumer/handoff rather than discard the producer mechanism.
- Preserve an active workbench when counters are nonzero, legality is clean, runtime is bounded, and either stage-local HPWL improves or the final erase is diagnosable.
- If the Student restored a better final source, check `source_trials.jsonl` for rejected or kept refs before losing the failed workbench as evidence. If a rejected ref is repairable, route the next Student to start from it with `25_trial_source.sh begin --from-ref <ref>`.
- Use this rejection taxonomy: implementation-bug means the idea may be sound but source/counters/logs show it did not execute correctly; composition/handoff issue means stage-local gain was erased downstream; method-low-ROI means the mechanism is live, legal, bounded, and still cannot move HPWL after a meaningful repair; non-promotable means build/eval/legality/timeout/stale-artifact failure.
- If a live/correct mechanism still gives extremely small full-flow HPWL movement after a meaningful repair attempt, classify it as `validated-low-ROI` and stop assigning repeated variants of the same idea as primary routes.
- Separate algorithmic failure from implementation cost: timeout, broad untargeted scans, low accept rate, legality rejects, fallback domination, duplicate endpoint work, weak cache reuse, or missing parallelism.

## Next-Plan Requirements

- Next packets should be evidence-driven, not quota-driven. Do not force a fixed number of legalizer, DPO, or hybrid routes; choose routes from the current largest HPWL source and mechanism uncertainty.
- Each next route needs one primary HPWL-source hypothesis, exact source handles, concise A/B/C plan, runtime tier, liveness counters, expected metric proof, and a stop/pivot rule.
- A/B/C can include real source changes or explicit preservation/diagnosis. Do not require cosmetic edits in a stage just to fill the plan.
- Emphasis labels (`legalizer-emphasis`, `DPO-emphasis`, `co-optimization-emphasis`) are priorities, not exclusive permissions. Students may patch multiple stages when a coherent source mechanism needs producer/consumer support.
- Parameter tuning is valid only as source-internal mechanism work: constants, thresholds, scoring weights, pass schedules, adaptive policies, or compact internal config structs in `dpl_evolve`. Reject Tcl/flow-script knob sweeps.
- Hybridize only as staged source-level mechanism composition inside one candidate implementation. Do not implement case/scenario selectors among complete legalizers or fallback-to-default success paths.
- When feature-level insight suggests a strategy, translate it into source mechanisms and liveness counters. The feature card is inspiration, not a fixed route table.
- Broader-search plans should state candidate/window bound, cache/reuse point, runtime tier, counters, and whether parallel scoring or deterministic reductions are appropriate. The plan may intentionally consume the hard-budget headroom when the expected HPWL mechanism is stronger.
- Keep next packets concise and non-accumulative. Replace stale guidance with the current mechanism decision.
