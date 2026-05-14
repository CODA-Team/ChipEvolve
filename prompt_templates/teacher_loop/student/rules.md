# Student Rules

## Mission

- Use the assigned Teacher packet as the primary research hypothesis; do not
  redo Teacher's global review, but do validate the route against current
  source and metrics before coding.
- Edit only your private `dpl_evolve` source and keep
  `detailed_placement_evolve -> improve_placement_evolve ->
  optimize_mirroring_evolve` callable.
- Modify the active patch surface: legalization/detailed placement and improve
  placement. Do not edit downstream optimize-mirroring code unless the task
  explicitly reopens it.
- External evaluator, ORFS, and workspace helper scripts are not editable.
- Use canonical `metrics.json:hpwl`; `hpwl_proxy` is debug-only.
- Optimize canonical HPWL first. Use the generated value gain
  `G_HR = 100 * (HPWL_ref - HPWL_sol) / HPWL_ref - P(runtime_sol / runtime_ref), where P(r)=0 for r <= 1.10 and P(2.0)=1.0 percentage point`,
  where higher is better and the OpenROAD DPL default-flow reference is 0, only
  as an analysis metric. Do not optimize for `G_HR`; optimize for legal final
  HPWL under the hard runtime budget. Report `G_HR` together with raw
  HPWL/runtime so Teacher can analyze whether a HPWL win needs runtime repair.
  Do not claim a faster but worse-final-HPWL result as the best result. Report it
  as runtime/control evidence; preserve the clean lower-HPWL source as the HPWL
  donor unless it fails legality, artifact gates, or the hard timeout budget.
  The runtime term has a deadband: runtime improvements and <=1.10x
  runtime noise receive no bonus; 2x runtime needs 1.0 percentage point of
  reference-normalized final-HPWL gain to break even.
- Treat 5% HPWL reduction as a credible research target, not a hard gate and
  not a ceiling. Build mechanisms that can move the source of HPWL loss, not
  only preserve a small donor.
- Implement the assigned route as the default plan, not a blind script. Combine
  Teacher's stage plan with your own source-level diagnosis; if current source
  shows a stronger route or contradicts the plan, adjust the mechanism and
  report the reason.
- Canonical lines `openroad_dpl_flow`, `openroad_dpl_negotiation`, and
  `evolve_default` are all usable evidence and donor/start choices. If you
  borrow from Diamond, negotiation, or evolved starts, state what source-level
  behavior you reused or changed.

## Required Execution

- Use the workspace packet for exact prepare/build/evaluate/diff/knowledge
  commands. Trust generated helpers; do not reconstruct relink/evaluator/git
  commands unless a helper fails and its error requires it.
- Treat the generated prompt, workspace packet, peer packet, knowledge files,
  and source tree as complete context. Do not read memories, rollout summaries,
  session archives, event logs, or broad donor trees by default.
- Before coding, do a focused source-level diagnosis: remaining HPWL loss,
  active function/state where it can be changed, and why the route is larger
  than a constant retune or local repair.
- If Teacher names LEGO-lite skill ids, query the generated skill helper or
  `scripts/query_knowledge.py` and keep only the relevant skill note. Use its
  source handles, metrics, log signals, and done criteria as the mechanism
  contract, but still inspect current local source before patching.
- If Teacher names an algorithm family or pseudocode mechanism, open only the
  relevant card under `algorithm_cards/legalization/`,
  `algorithm_cards/dpo_refinement/`, or `algorithm_cards/context/`. Convert the
  pseudocode into your own source-level plan and liveness counters before
  patching; do not paste it blindly.
- Use the Teacher chain as the execution outline: source diagnosis,
  legalization patch, improve-placement patch, build/evaluate, inspect stage
  metrics/log counters, revise the weak stage, then keep the best clean
  candidate. Refine the outline when code evidence shows a better mechanism.
- Required closure loop: plan the algorithm, patch source, build, run the
  canonical full-flow evaluator, inspect metrics and logs, revise once when the
  mechanism is live but weak, commit the best clean source state, write the
  diff, and report the exact evidence.
- After each evaluation, inspect the canonical `metrics.json` and the DPL log
  referenced by the metrics/log path. Diagnose mechanism liveness, stage that
  lost HPWL, runtime growth, timeout/failure reason, zero or implausible
  counters, stale-binary/source mismatch, and hot-loop/full-rescan symptoms.
- Follow the assigned route emphasis. `legalizer-emphasis`,
  `DPO-emphasis`, and `co-optimization-emphasis` name the primary HPWL source,
  not the only stage you may touch. Inspect both A legalization/detailed
  placement and B improve placement, then patch every stage where you have a
  coherent high-quality mechanism. If you leave a stage unchanged, explicitly
  diagnose how it preserved, consumed, or erased the gain and what source
  change would be worth doing next.
- If Teacher assigns an elite/final-donor continuation, keep the
  pre-seeded/materialized elite source. Switch to an `evolved_*` start branch
  only when the primary route explicitly says to use that prepared start.
- Use local git checkpoints for your workspace. The final committed source,
  `metrics.json`, `implementation.diff`, and knowledge card must correspond to
  the best clean evaluated code state.
- If you restore, revert, or switch the final source after an evaluation,
  rebuild and rerun the evaluator so the retained source commit, binary,
  `metrics.json`, diff, and final report all describe the same code.
- If a larger mechanism runs with nonzero counters but loses final HPWL, keep a
  workbench checkpoint and report the exact repair needed: liveness, objective,
  acceptance, persistence, handoff, final-safe survival scoring, or runtime
  implementation.
- A weak final result with active counters is not automatically failed. Revise
  the mechanism once by changing objective, acceptance, persistence, handoff,
  or runtime implementation before declaring it exhausted. Revisions must
  change the mechanism, not only constants.

## Source And Patch Protocol

- Use `apply_patch` for source edits. Do not rewrite source with Python,
  heredocs, `sed -i`, `perl -pi`, or broad formatter-driven edits.
- Patch only current files from your private source tree. Confirm paths with
  `rg --files`, locate exact symbols with `rg -n`, and read a small nearby
  excerpt before each nontrivial patch.
- For donor-derived or Teacher-prose-derived edits, run the generated
  source-context helper before patching. Donor snippets and old line numbers
  are evidence, not patch context.
- Keep hunks small and anchored on currently visible unique lines. After each
  patch, re-check the changed symbol and run `git -C "$private_dpl_evolve_source"
  diff --check` before build, or `cd` into the private source repo first. Do
  not run source git checks from the outer agent repo.
- If `apply_patch` fails, refresh the current source around the intended
  function/state and apply a smaller semantic patch. Do not turn a patch
  failure into CMake/relink archaeology or broad source search.

## Algorithm Standard

- Make aggressive case-focused source changes; no default-equivalent behavior.
- Aim to improve both legalization and improve placement when the changes are
  real mechanisms rather than cosmetic edits. Valid improve-placement edits
  include candidate generation, ordering, local HPWL objective, acceptance,
  endpoint policy, touched-region cache, internal parameter use, and
  handoff-state consumption. If the secondary stage is unchanged, report the
  diagnostic reason and the next source-level mechanism that would make it
  worth changing.
- Parameter tuning is allowed when it is code-internal: adjust constants,
  heuristic thresholds, scoring weights, pass schedules, adaptive policies, or
  compact internal config structs inside your private `dpl_evolve` source.
  Treat those edits as source mechanisms that must be built, logged, and
  evaluated. Do not move the tuning to Tcl command options, ORFS flow scripts,
  evaluator scripts, or repeated external command invocations.
- Hybrid legalizer routes are allowed when assigned or supported by source
  evidence. Implement them as source-level staged algorithms with explicit
  residual/frontier handoff; do not hybridize by rerunning unchanged endpoints
  or by adding a case/scenario selector among complete legalizers.
- Strategy and feature cards are inspiration, not a menu that limits your
  implementation.  Translate them into a local source plan after inspecting the
  active code, then prove the mechanism with counters and stage-wise metrics.
- Prefer data structures that make deeper search cheap: compact candidate
  queues, dirty-edge/touched-net sets, per-net local boxes, row/segment caches,
  legality caches, and thread-local score buffers.
- For legalizer-to-DPO handoff, use OpenROAD-native compact state:
  `odb::dbInst*`, `odb::dbNet*`, `odb::dbGroup*`, `odb::dbRegion*`, dense ids,
  vectors, and bitsets. Do not duplicate current coordinates. Avoid files,
  JSON/text logs, string-keyed hot maps, and public Tcl/SWIG ABI changes for
  ordinary algorithm payloads.
- Avoid hot-loop full-cell/full-grid/full-net rescans and avoidable `O(n^2)`.
  Cache touched data and make each extra candidate's cost visible in telemetry.
- Add or reuse lightweight counters/logs that prove the primary mechanism ran.
  If key counters are zero, report the route as non-executed even if inherited
  code produced the final metrics.
- Log diagnosis must separate algorithmic failure from implementation cost:
  candidate generation too broad, acceptance too strict, legality rejects,
  fallback domination, duplicate endpoint work, full-cell/full-net rescans,
  poor cache reuse, missing parallelism, or source/binary/metrics mismatch.
- No case-name hardcoding. Avoid public Tcl/SWIG ABI changes unless essential
  and smoke-tested.

## Runtime And Search Budget

- The generated evaluation command applies a `${student_runtime_multiplier}x`
  timeout to the OpenROAD legalize/improve/mirror flow only; metrics/evaluator
  collection is not timeout-wrapped.
- Runtime is a usable hard budget, not the objective. Spend the tolerant
  `${student_runtime_multiplier}x` budget on bounded HPWL-source mechanisms:
  exact affected-net scoring, broader capped windows, batch transactions,
  parallel candidate evaluation, stronger donor hybridization, or stronger
  legalization-to-improve handoff.
- Do not optimize back to baseline-like runtime when the assigned route needs
  explore/aggressive search. Extra time is acceptable when it is cached,
  capped, explainable, and supported by stage-wise metrics.
- Do not buy HPWL by repeated random tails, duplicate passes, endpoint
  stacking, or unchanged repeated improve-placement runs.
- Use OpenMP or existing thread utilities for independent candidate scoring,
  local HPWL probes, row/window probes, and feasibility filters when using
  thread-local scratch data and deterministic reduction.
- If the DPL flow times out, stop that implementation path, record it as
  non-promotable, and do not rerun the same mechanism.

## Final Report

- Include a compact table with rows: legalization/detailed placement, improve
  placement, and optional coordination. For each row, name exact
  function/state changes and behavior changes.
- Include a stage transition table with columns: `stage`, `selected skill`,
  `touched function/state`, `expected behavior`, `metric/log evidence`, and
  `done/fail reason`.
- Report touched files, mechanism, stage-wise HPWL deltas, canonical
  HPWL/runtime/displacement delta, `G_HR`/HPWL_gain%/runtime_penalty_pp when
  available, legality, metrics path, diff path, knowledge card path, active
  counters, best clean commit, and next uncertainty.
- Include a `Log/efficiency diagnosis` paragraph: DPL log path or key line
  handles, dominant counters, runtime bottleneck classification, evidence of
  wrong or non-executed implementation, and the specific next repair Teacher
  should assign.
