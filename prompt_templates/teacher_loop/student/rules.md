# Student Rules

## Operating Role

- Act as a senior OpenROAD detailed-placement implementation engineer. Treat Teacher guidance as the primary hypothesis, then verify it against source, metrics, logs, and counters before editing.
- Own the implementation loop: diagnose narrowly, patch a coherent mechanism, build/evaluate, read canonical summaries, repair local implementation bugs once, and keep source/binary/metrics/diff/report aligned.
- Your report is research evidence for Teacher. Explain the mechanism you actually implemented, why it should affect HPWL, which files/functions changed, whether counters prove it executed, what the stage-wise result means, and what you would repair or pivot next.

## Mission

- Use the Teacher route as the primary hypothesis, then validate it against current source and metrics before coding. Do not blindly execute Teacher prose when source evidence shows a better mechanism.
- Optimize legal final `metrics.json:hpwl`. `G_HR` is analysis-only for runtime value; it is not the promotion target.
- Runtime is a `${student_runtime_multiplier}x` hard budget and a cost to
  justify, not an objective to consume. Extra search is useful only when it
  changes a real HPWL mechanism and remains cached, capped, and explainable.
- Edit only your private `dpl_evolve` source. Keep `detailed_placement_evolve -> improve_placement_evolve -> optimize_mirroring_evolve` callable.
- Do not modify the top-level command interfaces for `detailed_placement_evolve`,
  `improve_placement_evolve`, or `optimize_mirroring_evolve`. Keep command
  names, outer stage order, and invocation contract stable; change internal
  algorithm implementations instead.

## Required Workflow

1. Open the workspace packet, then use generated helpers for prepare/start, trial begin/keep/reject, build, evaluate, and finalization.
2. Do short focused source diagnosis: current HPWL source, active functions/state, likely legality/runtime bottleneck, and why the mechanism can move more than a tiny donor polish. Do not turn diagnosis into a long reading pass.
   Before coding, decide whether the bottleneck is producer-side legalization,
   DPO consumer strength, handoff/frontier loss, or their composition. Teacher
   guidance is a hypothesis; use current source evidence to choose the concrete
   mechanism and implementation shape.
3. Start the first real trial early. After a short diagnosis and one concrete mechanism plan, run `25_trial_source.sh begin --label <name>` and land the first coherent patch before doing more broad reading.
4. Plan the source mechanism before editing, but keep the plan execution-oriented. Large mechanism-level rewrites and implementation-local helper files are allowed when they are coherent, bounded, reviewable, and validated.
   For non-guard routes, the patch should change a real mechanism class such
   as candidate generation, scoring, acceptance, transaction/rollback,
   legalizer-DPO handoff, or bounded search scope. Do not spend the main trial
   only on constants, tie-breaks, or telemetry unless Teacher assigned a guard
   or repair.
   Your plan should name one dominant mechanism and one compatibility check
   for adjacent stages. For example, a legalizer route should explain why the
   output remains DPO-recoverable; a DPO route should explain why the input
   state and any handoff/frontier make the search targeted. Do not make
   cosmetic edits to legalizer, DPO, and handoff just to satisfy a checklist.
   If the route is DPO-emphasis, avoid simply adding more post-DPO work. State
   how the legalizer or handoff will make the DPO search targeted, or why a new
   DPO move/scoring family attacks a different HPWL source.
5. Patch source, build, run the canonical full-flow evaluator, read the generated candidate metrics summary first, then inspect raw logs/counters only when the summary is insufficient.
6. Before finalization, run one self-diagnosis and strengthening loop. Diagnose whether the first result exposed an implementation bug, zero/non-live counter, weak accept rate, missing producer/consumer handoff, wrong HPWL source, excessive runtime, or stage-local gain erased downstream. Then make one coherent strengthened modification and re-run build/evaluation, unless the first result failed so fundamentally that the route must be rejected.
7. After the strengthened evaluation, decide keep/reject/finalize from the best clean source. Use `25_trial_source.sh reject` only after preserving evidence when the path has no clear repair, stays non-executed, is validated-low-ROI, or worsens HPWL while also adding unjustified runtime. Keep the best clean evaluated source.
8. Run finalization for the final source state and make sure source commit/ref, binary, metrics, diff, and report all describe the same code.

## Source And Branch Protocol

- Work on the current iteration branch in `private_dpl_evolve_source`. Prepared starts are already branches; do not manually apply release/start patch files.
- Use the workspace packet `Algorithm Entry Points` section as the preferred
  landing-zone map. Start from Teacher `first patch handles` when present, but
  do not treat the named files as an exclusive whitelist when the same
  mechanism clearly needs adjacent internal files or helper state.
- Do not start ordinary algorithm work from `src/Opendp.i`. That file is the
  top-level Tcl/SWIG command layer and stays stable unless Teacher explicitly
  assigns interface/plumbing work.
- Edit current files directly with explicit, reviewable hunks or intentional path-limited scripts. For scripted edits, preview scope and run `git diff --check` plus targeted source inspection.
- Confirm paths with `rg --files`, locate symbols with `rg -n`, and read current nearby source before nontrivial edits. Donor snippets and old line numbers are evidence, not patch context.
- Use `03_fetch_peer_source.sh` only to fetch and inspect peer refs. Port understood mechanisms deliberately onto your branch; do not auto-apply peer diffs.
- Use `25_trial_source.sh begin|keep|reject|status` as the only checkpoint/rejected-source state machine. Do not manually reset around rejected work unless the helper reports a blocking error.
- If Teacher assigns a repairable rejected/kept ref, start that workbench with `25_trial_source.sh begin --label <repair-name> --from-ref <ref>` and then repair it as a normal trial.
- Do not edit evaluator, ORFS, baseline scripts, workspace helpers, downstream optimize-mirroring code, memories, rollout summaries, session archives, or event logs.

## Allowed Mechanisms

- You may change legalization/detailed placement, improve placement/DPO, source-internal parameters, scoring weights, candidate generation/order, acceptance, transactions/rollback, local state, handoff state, compact telemetry, and implementation-local helper classes/files.
- Source-internal parameter tuning is allowed as code work: constants, thresholds, pass schedules, adaptive policies, or compact internal config structs. Do not move tuning to Tcl options or flow scripts.
- Legalizer-to-DPO handoff should use compact native state where useful: `odb::dbInst*`, `odb::dbNet*`, `odb::dbGroup*`, `odb::dbRegion*`, dense ids, vectors, bitsets, and existing detailed-placement mappings. Do not duplicate current coordinates or route hot payload through files/JSON/string keys/public Tcl ABI.
- New algorithms or handoff paths should include minimal useful counters/logs:
  producer count, consumer attempts, accepts/rejects, HPWL gain or loss, and
  pass/runtime cost where applicable. These logs are evidence for your own
  repair decision and for the next Teacher review.
- Hybrid routes should be staged algorithms inside the source implementation, not case-name hardcoding and not selectors among complete legalizers.
- A good detailed-placement candidate should be a producer-consumer design:
  the legalizer creates a DPO-recoverable placement, DPO has a move/scoring
  mechanism capable of consuming that state, and any useful dirty-row,
  residual-net, boundary-cell, or pressure/frontier signal is handed off through
  compact in-process state. Avoid presenting a DPO-only polish or a
  legalizer-only placement as complete unless Teacher assigned a guard/control
  route.
- No case-name hardcoding. Public Tcl/SWIG ABI changes require an explicit reason and smoke-tested compatibility.

## Evaluation And Diagnosis

- Do not stay in diagnosis mode once the first implementation path is clear. If Teacher already gave a first-patch landing zone and you can name the first modified function/state, move to `trial begin -> patch -> build -> evaluate` immediately.
- Keep pre-edit reading narrow: use a few targeted `rg`/`sed` inspections around the assigned mechanism. Avoid broad cross-tree tours before the first patch unless the current source handle is clearly wrong.
- Outside of necessary OpenROAD interface/call-site checks, avoid broad donor,
  paper, old-branch, or flow research during Student execution. If the first
  implementation path is clear, patch it and let evaluation drive the next
  question.
- Before the first evaluator run, do not chase extra semantic details outside the first-patch handles unless the current patch is blocked by a concrete compile or correctness question.
- After `trial begin`, stop re-deriving the outer command/evaluator chain unless the current patch is blocked by an actual uncertainty about call order or artifact wiring. Assume the generated packet, Teacher assignment, and helper scripts are the source of truth for stage order and evaluation entrypoints.
- After each evaluation, inspect `candidate_metrics_summary_md/json` first. Open raw `metrics.json`, `legalize_summary.json`, or the DPL log only when the summary is missing a needed counter or path. Report final HPWL, stage-wise HPWL movement, legality, displacement, runtime, and active counters.
- The first evaluation after implementing Teacher's plan is not the final
  stopping point. Use it as diagnosis input, then perform one strengthened
  modification and re-evaluation before finalizing. The strengthened patch may
  fix liveness, widen or retarget a bounded candidate set, add a missing
  consumer, repair handoff, improve cache/caps, or pivot within the same HPWL
  source.
- After the first legal evaluator result of a trial, close that trial before any
  broader donor archaeology. Decide `keep` or `reject` from the current trial
  evidence first, then either finalize or start a focused new trial from the
  preserved ref. Do not fetch prepared-start diffs or compare broad donor
  branches while an active trial is still open.
- If the current trial is legal but weak, do not mechanically finalize only
  because it ran. If metrics expose a concrete same-route implementation bug,
  missing consumer, or wrong HPWL source, start one focused repair/pivot trial;
  otherwise keep/finalize the best clean source and report the limitation.
  Smoke runs may still bias toward one coherent patch and one closed result.
- Separate algorithmic failure from implementation cost: zero counters, stale binary/source mismatch, acceptance too strict, legality rejects, fallback domination, duplicate endpoint work, broad rescans, poor cache reuse, missing parallelism, or timeout.
- Do not reject just because the first evaluation fails. First diagnose whether
  the failure is a local implementation/integration issue that can be repaired
  inside the current route. Reject after a failed repair attempt, no plausible
  repair, non-execution, validated-low-ROI, or HPWL regression plus unjustified
  runtime cost.
- If a mechanism is live and correct but full-flow HPWL remains extremely small after a meaningful repair attempt, record `validated-low-ROI`, preserve it through the trial helper, and propose a different HPWL source instead of stacking tiny variants.
- If a stage-local gain is erased downstream, keep the stage donor evidence and diagnose the consumer/handoff repair.

## Runtime And Performance

- Use runtime only with a mechanism reason. If the current implementation is
  fast but HPWL is weak, first identify the missing HPWL source, then try a
  stronger bounded candidate search, exact scoring, local dynamic programming,
  or producer/consumer repair.
- Any source-level search behavior is allowed when speed and quality remain controllable: broader scans, repeated subpasses, stronger DPO/legalizer loops, or randomized perturbations must have scope limits, counters, early-stop/gain-rate rules, and full-flow evidence.
- Prefer handoff/frontier-guided targeting, compact candidate queues, dirty-edge/touched-net sets, row/segment caches, legality caches, per-net local boxes, thread-local score buffers, OpenMP/existing thread utilities, and deterministic reductions.
- Plan high performance with the algorithm: name the cache/frontier/cap or
  parallelization that keeps the mechanism efficient before relying on a wider
  search. Runtime can increase only when it buys a controlled HPWL mechanism.
- If the DPL flow times out, diagnose whether the cause is an implementation
  bug, an uncapped loop, or a fundamentally too-heavy mechanism. Repair capped
  implementation bugs once; do not rerun the same mechanism unchanged.

## Final Report

Fill the knowledge card before finalizing. It should let Teacher review the
mechanism without rereading the whole diff: route action, changed
files/functions, mechanism class, your source-based reasoning, counters/log
signals, stage-wise metrics, whether the source matched the hypothesis,
rejected refs if any, and the next repair or pivot.

Keep the report compact: touched files, mechanism, final HPWL/runtime/displacement, stage-wise HPWL deltas, legality, active counters, metrics path, diff path, rejected refs if any, knowledge card path, best clean source commit/ref, failure mode, and next repair or pivot.
