# Student Rules

## Mission

- Execute the assigned Teacher packet. Do not redo Teacher's global review.
- Edit only your private `dpl_evolve` source.
- Keep `detailed_placement_evolve -> improve_placement_evolve -> optimize_mirroring_evolve` callable.
- Modify only the active patch surface for this track: legalization/detailed placement and improve placement.
- Do not edit downstream optimize-mirroring code unless the task explicitly reopens that scope; current evidence says its HPWL headroom is too small for this evolution loop.
- The three canonical lines are all usable evidence and donor/start-point
  choices: `openroad_dpl_flow`, `openroad_dpl_negotiation`, and
  `evolve_default`. You may explore the Diamond line, the negotiation line, the
  evolved line, or a hybrid of them. If you borrow from Diamond, state exactly
  what source-level behavior you reused or changed and why it helps this case.
- Implement Teacher's HPWL source mechanism as the primary route, but trust source-level evidence. If the source contradicts the plan or reveals a stronger route, adjust and report why.
- You may change algorithms, objectives, candidate generation, data structures, flow order inside evolved commands, and stage handoff.
- Before coding, do a focused source-level diagnosis of the remaining HPWL
  gap.  Identify the active function/state where the gap can be changed at the
  source, not only the donor knob you were given.  If the assigned route looks
  like another tiny donor retune, strengthen it into a larger source mechanism
  and report the reasoning.
- Optimize canonical `metrics.json:hpwl`; `hpwl_proxy` is debug-only.
- Report stage-wise HPWL from `metrics.json:hpwl_stages` when present, or from
  the OpenROAD/DPL legalize log: `HPWLg`, `delta HPWLlg`,
  `delta HPWLip`, `delta HPWL final`, and `HPWL final`.
- Treat 5% HPWL reduction as a credible research target, not a hard gate and
  not a ceiling.  Believe it is achievable, design mechanisms that can reach or
  exceed it, and keep useful below-5% mechanisms as donor evidence when they
  clearly improve a stage.

## Required Execution

- Use the workspace packet for exact prepare/build/evaluate/diff/knowledge commands.
- Treat build/evaluation as generated infrastructure. Run the packet commands
  exactly; do not reconstruct relink commands, inspect `link.txt`, or manually
  call `ar`, `ranlib`, `nm`, `strings`, `ldd`, `readelf`, or equivalent binary
  archaeology. If a generated helper fails, fix your source change or report the
  helper error as the blocker.
- Plan A/B: legalization/detailed placement and improve placement. Implement both before judging the idea.
- Your implementation should be capable of discovering a large improvement, not
  only preserving a small donor.  Treat existing donors as evidence and
  regression guards, but search for larger mechanisms in objectives,
  frontier/candidate generation, stage handoff, local HPWL scoring, or
  co-optimization flow.
- Build at least one explicit legalization/improve co-optimization link: move
  improve-placement scoring, candidate choice, local HPWL deltas, or
  residual-net priorities into the legal-state generation path.
- Also make improve placement a real algorithmic edit, not only a script
  string or telemetry change. Valid improve-placement work changes candidate
  generation, ordering, local HPWL objective, acceptance/rollback policy,
  touched-region cache, or how legalization handoff state is consumed.
- Go deep enough in `Optdp`/detailed improvement to affect final HPWL. Prefer
  source changes around candidate queues, affected-net HPWL delta computation,
  move/swap/window evaluation, acceptance policy, local legality checks, and
  handoff-state consumers over superficial endpoint-script changes.
- Treat final HPWL as a product of legalization/improve co-optimization.
  Legalization and improve placement should pass useful state to each other;
  do not bet the whole attempt on only one stage.
- Build and evaluate; inspect canonical `metrics.json:hpwl` and the relevant OpenROAD log.
- If the result is weak or illegal, revise the algorithm or commit/selection logic, rebuild/evaluate, and keep the best clean candidate.
- Revisions must change the mechanism, not only constants.
- Default evaluation loop: initial build/eval, one targeted mechanism revision,
  then keep the best clean candidate. A third canonical eval is only justified
  by a named mechanism change, a build/link correction, or a legality fix.
- Control runtime explicitly: cap endpoints and candidate lists, reuse cached
  touched data, log enough counters to explain cost, and remove duplicate
  endpoints before adding more expensive search.
- Use high-performance parallel exploration when it is natural.  OpenMP,
  thread-local scratch buffers, parallel candidate scoring, and deterministic
  reductions are encouraged for independent row/window/candidate/local-HPWL
  probes.  Parallelism should let you evaluate a stronger bounded mechanism
  within the timeout; it must not mask an unbounded or duplicate search.
- Do not chase small HPWL deltas with a slow or unbounded implementation. If an
  expensive path is not plausibly on track for material progress toward the 5%
  research target, replace the mechanism instead of extending the run.
- Do not improve HPWL by simply running an unchanged improve-placement flow
  more times, repeating random tails, or stacking endpoints. It is encouraged
  to spend available runtime on one new bounded improve-placement algorithm
  when it has a named HPWL source, candidate cap, cache plan, and stop
  condition.
- The generated evaluation command has a hard timeout at ${student_runtime_multiplier}x the canonical
  `openroad_dpl_flow` baseline runtime. If that timeout kills the run, stop
  that implementation path, report it as non-promotable, and do not rerun the
  same mechanism.
- Keep exploration bounded: use `rg` first and small source excerpts around exact symbols. Do not read whole donor trees, event logs, or memory registries by default.
- Trust generated helper commands. Do not inspect evaluator/build wrapper internals unless the exact helper returned nonzero and its error text is insufficient.
- If a patch does not apply, inspect only the nearby current source around the
  intended function/state, then re-apply a smaller patch. Do not turn patch
  recovery into build-system or relink investigation.

## Implementation Standard

- Aggressive case-focused change; no default-equivalent behavior.
- Bounded candidates, cached touched data, controlled complexity.
- No avoidable hot-loop `O(n^2)`, full-grid scans, or full-net recomputation inside candidate loops.
- Prefer data structures that make deeper search cheap: compact dirty-edge
  queues, per-net other-pin boxes, row/segment candidate caches, local legality
  caches, and thread-local score buffers merged by deterministic reduction.
- For `Optdp` work, precompute touched nets or local boxes, cache repeated
  HPWL deltas, keep candidate queues compact, and make the cost of each extra
  candidate explicit in telemetry.
- Runtime may exceed baseline only inside the generated ${student_runtime_multiplier}x timeout when the
  HPWL gain or algorithmic evidence justifies it.
- Runtime savings from cheap legalization work should be reallocated to the
  strongest bounded improve-placement mechanism before declaring the attempt
  finished.
- Low-ROI runtime growth is a failed implementation path, not a donor. Prefer a
  simpler bounded algorithm with a clear HPWL source over endpoint stacking.
- Runtime must stay explainable. If a run becomes several times slower than
  baseline, the final report must identify the exact pass or endpoint causing
  it and what should be pruned or parallelized next.
- Avoid public Tcl/SWIG ABI changes, especially `Opendp`, unless essential and smoke-tested.
- No case-name hardcoding.

## Final Report

Include a compact table with rows: legalization/detailed placement, improve placement, optional coordination. For each row, name the exact function/state changed and behavior change.

Also report touched files, mechanism, stage-wise HPWL deltas,
canonical HPWL/runtime/displacement delta, legality, metrics path, diff path,
knowledge card path, and next uncertainty.
