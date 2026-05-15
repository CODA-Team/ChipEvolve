# Student Rules

## Mission

- Use the Teacher route as the primary hypothesis, then validate it against current source and metrics before coding. Do not blindly execute Teacher prose when source evidence shows a better mechanism.
- Optimize legal final `metrics.json:hpwl`. `G_HR` is analysis-only for runtime value; it is not the promotion target.
- Runtime is a `${student_runtime_multiplier}x` hard budget and a spendable search resource for the OpenROAD legalize/improve/mirror flow. Do not optimize for baseline-like runtime by avoiding useful search; spend the available budget when it buys a cached, capped, explainable HPWL mechanism.
- Edit only your private `dpl_evolve` source. Keep `detailed_placement_evolve -> improve_placement_evolve -> optimize_mirroring_evolve` callable.

## Required Workflow

1. Open the workspace packet, then use generated helpers for prepare/start, trial begin/keep/reject, build, evaluate, and finalization.
2. Do short focused source diagnosis: current HPWL source, active functions/state, likely legality/runtime bottleneck, and why the mechanism can move more than a tiny donor polish. Do not turn diagnosis into a long reading pass.
3. Start the first real trial early. After a short diagnosis and one concrete mechanism plan, run `25_trial_source.sh begin --label <name>` and land the first coherent patch before doing more broad reading.
4. Plan the source mechanism before editing, but keep the plan execution-oriented. Large mechanism-level rewrites and implementation-local helper files are allowed when they are coherent, bounded, reviewable, and validated.
5. Patch source, build, run the canonical full-flow evaluator, read the generated candidate metrics summary first, then inspect raw logs/counters only when the summary is insufficient. Make bounded evidence-driven revisions while a concrete mechanism-level fix exists. Use `25_trial_source.sh reject` for rejected mechanisms so the script preserves the branch and restores the retained checkpoint safely. Stop when the path is illegal, timed out, non-executed, or validated-low-ROI, and keep the best clean evaluated source.
6. Run finalization for the final source state and make sure source commit/ref, binary, metrics, diff, and report all describe the same code.

## Source And Branch Protocol

- Work on the current iteration branch in `private_dpl_evolve_source`. Prepared starts are already branches; do not manually apply release/start patch files.
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
- Hybrid routes should be staged algorithms inside the source implementation, not case-name hardcoding and not selectors among complete legalizers.
- No case-name hardcoding. Public Tcl/SWIG ABI changes require an explicit reason and smoke-tested compatibility.

## Evaluation And Diagnosis

- Do not stay in diagnosis mode once the first implementation path is clear. If Teacher already gave a first-patch landing zone and you can name the first modified function/state, move to `trial begin -> patch -> build -> evaluate` immediately.
- Keep pre-edit reading narrow: use a few targeted `rg`/`sed` inspections around the assigned mechanism. Avoid broad cross-tree tours before the first patch unless the current source handle is clearly wrong.
- Before the first evaluator run, do not chase extra semantic details outside the first-patch handles unless the current patch is blocked by a concrete compile or correctness question.
- After each evaluation, inspect `candidate_metrics_summary_md/json` first. Open raw `metrics.json`, `legalize_summary.json`, or the DPL log only when the summary is missing a needed counter or path. Report final HPWL, stage-wise HPWL movement, legality, displacement, runtime, and active counters.
- Separate algorithmic failure from implementation cost: zero counters, stale binary/source mismatch, acceptance too strict, legality rejects, fallback domination, duplicate endpoint work, broad rescans, poor cache reuse, missing parallelism, or timeout.
- If a mechanism is live and correct but full-flow HPWL remains extremely small after a meaningful repair attempt, record `validated-low-ROI`, preserve it through the trial helper, and propose a different HPWL source instead of stacking tiny variants.
- If a stage-local gain is erased downstream, keep the stage donor evidence and diagnose the consumer/handoff repair.

## Runtime And Performance

- Use the runtime budget deliberately. If the current implementation is very fast but HPWL is weak, try a stronger bounded candidate search, exact scoring, local dynamic programming, or producer/consumer repair before declaring the route exhausted.
- Any source-level search behavior is allowed when speed and quality remain controllable: broader scans, repeated subpasses, stronger DPO/legalizer loops, or randomized perturbations must have scope limits, counters, early-stop/gain-rate rules, and full-flow evidence.
- Prefer handoff/frontier-guided targeting, compact candidate queues, dirty-edge/touched-net sets, row/segment caches, legality caches, per-net local boxes, thread-local score buffers, OpenMP/existing thread utilities, and deterministic reductions.
- If the DPL flow times out, stop that implementation path and report it as non-promotable; do not rerun the same mechanism unchanged.

## Final Report

Keep the report compact: touched files, mechanism, final HPWL/runtime/displacement, stage-wise HPWL deltas, legality, active counters, metrics path, diff path, rejected refs if any, knowledge card path, best clean source commit/ref, failure mode, and next repair or pivot.
