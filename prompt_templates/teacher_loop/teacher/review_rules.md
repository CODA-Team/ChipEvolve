## Evidence Discipline

- Read the artifact packet once first; it already contains validity, metrics, artifact sizes, and exact paths.
- Prefer each Student's `knowledge_card` for implemented mechanism, bottleneck
  diagnosis, liveness evidence, and lesson. Use final messages for compact
  summary only.
- Artifact read order: `teacher_review_artifacts.md` -> per-student
  `knowledge_card` -> `source_trials.jsonl` for kept/rejected refs ->
  `implementation_diff`/logs only when the card or validity gate is unclear.
- Do not rerun or reread artifacts broadly unless a validity conflict needs it. Repeated artifact reads without a mechanism decision are review inefficiency.
- Use Student log/efficiency diagnosis when present; if missing, infer only the minimum from `metrics.json`, DPL logs, counters, and artifact state.

## Validity Gate

- A candidate is not promotable if build/evaluator failed, metrics are missing, diff is missing/empty, agent message is missing, legality failed, source/binary/metrics are stale, or the DPL flow timed out.
- Rank promotable candidates by legal final `metrics.json:hpwl`. Ignore bbox/proxy HPWL for promotion.
- Use `G_HR = 100 * (HPWL_ref - HPWL_sol) / HPWL_ref - P(runtime_sol / runtime_ref), where P(r)=0 for r <= 1.10 and P(2.0)=1.0 percentage point` only to explain runtime value and repair priority. A faster worse-HPWL candidate is not the headline elite unless lower-HPWL candidates fail validity gates.
- Treat runtime and displacement as diagnostics: useful controlled search, under-exploration, fixable implementation cost, or unsupported work. Do not over-reward baseline-like runtime that avoids the hard HPWL search; when a legal candidate stays far under budget and HPWL is weak, review it as possible under-exploration and route a stronger bounded search.

## Review Focus

- Identify the real executed mechanism, not only the claimed mechanism. Zero counters or stale artifacts mean non-executed/negative evidence even if inherited code produced acceptable metrics.
- Use the knowledge card as a source-to-evidence map. Prefer cards that name
  changed files/functions, route action, executed counters, stage movement, and
  next repair; treat vague cards as incomplete review evidence even when the
  metrics are valid.
- If a Student spends substantial time in diagnosis without reaching a first patch/build/eval loop, review that as execution inefficiency and route the next packet toward a faster concrete implementation path.
- Treat `reject` as "not the final candidate for this trial", not as automatic method death. Inspect the source diff, counters, stage movement, and logs before deciding whether the failure is implementation, handoff/composition, or method-level.
- Attribute stage movement across legalization, improve placement/DPO, handoff, final mirror contribution, runtime, and counters.
- Classify each result as `final donor`, `stage donor`, `active mechanism workbench`, `validated-low-ROI`, `non-executed route`, or `negative evidence`.
- Also classify donor scope when useful: `general donor` if it is a reusable
  guard/kernel, or `feature-matched donor` if it appears useful because this
  design has matching density, row-fragmentation, conflict, macro-edge, or DPO
  recoverability features.
- Preserve stage donors when downstream erases a gain; the next route should repair the consumer/handoff rather than discard the producer mechanism.
- Preserve an active workbench when counters are nonzero, legality is clean, runtime is bounded, and either stage-local HPWL improves or the final erase is diagnosable.
- If the Student restored a better final source, check `source_trials.jsonl` for rejected or kept refs before losing the failed workbench as evidence. If a rejected ref is repairable, route the next Student to start from it with `25_trial_source.sh begin --from-ref <ref>`.
- Use this rejection taxonomy: implementation-bug means the idea may be sound but source/counters/logs show it did not execute correctly; composition/handoff issue means stage-local gain was erased downstream; method-low-ROI means the mechanism is live, legal, bounded, and still cannot move HPWL after a meaningful repair; non-promotable means build/eval/legality/timeout/stale-artifact failure.
- If a live/correct mechanism still gives extremely small full-flow HPWL movement after a meaningful repair attempt, classify it as `validated-low-ROI` and stop assigning repeated variants of the same idea as primary routes.
- If multiple candidates only extend one donor family with constants,
  tie-breaks, telemetry, or small candidate-order changes, mark the round as
  same-family incremental exploitation and require the next plan to include a
  `switch`, `hybridize`, or `mechanism-redesign` route.
- Separate algorithmic failure from implementation cost: timeout, broad untargeted scans, low accept rate, legality rejects, fallback domination, duplicate endpoint work, weak cache reuse, or missing parallelism.
- If current-run legal candidates are tiny-gain, same-family, or too heavy for
  the HPWL gained, diagnose whether the issue is implementation cost,
  producer/consumer composition, or a weak mechanism. The next plan should
  preserve at most one guard and include a more aggressive within-run route:
  switch family, redesign the mechanism, or repair a current-run kept/rejected
  ref with `25_trial_source.sh begin --from-ref <ref>`.
- When a next route switches parent/ref, name the current-run source ref, new
  trial label, and preservation expectation. Do not use cross-experiment
  donors or historical runs as implementation starts.

## Next-Plan Requirements

- Next packets should be evidence-driven, not quota-driven. Do not force a fixed number of legalizer, DPO, or hybrid routes; choose routes from the current largest HPWL source and mechanism uncertainty.
- Before assigning next packets, synthesize three inputs: canonical stage metrics,
  Student knowledge-card reasoning, and the most relevant knowledge/algorithm
  card. The next route should say which knowledge idea is being tested or why
  evidence rejects it for this round.
- Each next route needs one primary HPWL-source hypothesis, a minimal first-patch landing zone, concise A/B/C plan, runtime tier, liveness counters, expected metric proof, and a stop/pivot rule. Usually give 1-3 primary handles and at most 2 support handles.
- Review whether the route mix is too narrow. If all next routes would polish
  one donor family while the case still trails baseline, require one broader
  new-family route from the algorithm cards.
- A/B/C can include real source changes or explicit preservation/diagnosis. Do not require cosmetic edits in a stage just to fill the plan.
- Emphasis labels (`legalizer-emphasis`, `DPO-emphasis`, `co-optimization-emphasis`) are priorities, not exclusive permissions. Students may patch multiple stages when a coherent source mechanism needs producer/consumer support.
- Parameter tuning is valid only as source-internal mechanism work: constants, thresholds, scoring weights, pass schedules, adaptive policies, or compact internal config structs in `dpl_evolve`. Reject Tcl/flow-script knob sweeps.
- Hybridize only as staged source-level mechanism composition inside one candidate implementation. Do not implement case/scenario selectors among complete legalizers or fallback-to-default success paths.
- When feature-level insight suggests a strategy, translate it into source mechanisms and liveness counters. The feature card is inspiration, not a fixed route table.
- Broader-search plans should state candidate/window bound, cache/reuse point, runtime tier, counters, and whether parallel scoring or deterministic reductions are appropriate. The plan may intentionally consume the hard-budget headroom when the expected HPWL mechanism is stronger.
- Weak-gain or over-cost plans should explicitly name the stronger mechanism
  family or repaired current-run ref and why it is different from donor
  polishing.
- Keep next packets concise and non-accumulative. Replace stale guidance with the current mechanism decision.
