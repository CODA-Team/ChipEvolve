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
- You may change algorithms, objectives, candidate generation, data structures,
  source-level flow order inside evolved commands, internal
  `improve_placement_evolve` endpoint sequencing/parameterization, and stage
  handoff. External evaluator/ORFS/workspace helper scripts are not editable.
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
- Convert that target into implementation scale.  A change that can only move a
  tie-break, metadata flag, or tiny local repair is not enough by itself.  Your
  primary mechanism should expand or reshape the legal/improve search space in
  a bounded way: batch transactions, wider capped windows, exact affected-net
  scoring, better frontier generation, stronger handoff state, or parallel
  candidate scoring.

## Required Execution

- Use the workspace packet for exact prepare/build/evaluate/diff/knowledge commands.
- Treat build/evaluation as generated infrastructure. Run the packet commands
  exactly. Do not spend the main iteration reconstructing relink commands or
  doing binary archaeology (`link.txt`, `ar`, `ranlib`, `nm`, `strings`, `ldd`,
  `readelf`) unless the generated helper itself clearly fails there. If a
  helper fails, first fix your source change; report helper/tooling errors only
  when they are the real blocker.
- Treat the generated prompt, workspace packet, peer packet, knowledge files,
  and source tree as the complete task context. Do not search or read
  `~/.codex/memories`, rollout summaries, session archives, or event logs by
  default; those external records are not part of the Student execution loop.
- Plan A/B: legalization/detailed placement and improve placement. Implement both before judging the idea.
- Follow the Teacher step chain in order: source diagnosis, legalizer-stage
  patch, improve-placement patch, build/evaluate, inspect stage-wise
  metrics/log counters, revise by keeping, switching, or hybridizing the weak
  stage when evidence supports it, then keep the best clean candidate.
- If Teacher assigns continuation from an elite/final-donor source, keep the
  pre-seeded/materialized elite source as the parent. Do not switch to an
  `evolved_*` start branch unless Teacher's primary route explicitly says to
  use that prepared start branch.
- If you run multiple canonical evaluations, the final committed source,
  `metrics.json` row, `implementation.diff`, and knowledge card must correspond
  to the best clean evaluated code state. If a later cleanup or revision
  worsens metrics, restore the best clean source commit before running the
  commit/diff/report helpers. Do not claim an earlier best result while leaving
  a worse final source tree.
- Your implementation should be capable of discovering a large improvement, not
  only preserving a small donor.  Treat existing donors as evidence and
  regression guards, but search for larger mechanisms in objectives,
  frontier/candidate generation, stage handoff, local HPWL scoring, or
  co-optimization flow.
- If the inherited donor already gives only a small final HPWL win, do not
  spend the whole round preserving it.  Keep it as the best-source guard, then
  test at least one larger mechanism that could improve the unchanged or
  erased stage shown by stage-wise metrics.
- Build at least one explicit legalization/improve co-optimization link: move
  improve-placement scoring, candidate choice, local HPWL deltas, or
  residual-net priorities into the legal-state generation path.
- Also make improve placement a real algorithmic edit, not only telemetry or an
  external-script change. Valid improve-placement work changes source-level
  endpoint scheduling, candidate generation, ordering, local HPWL objective,
  acceptance or best-source restoration policy, touched-region cache, internal
  parameter use, or how legalization handoff state is consumed.
- Go deep enough in `Optdp`/detailed improvement to affect final HPWL. Prefer
  source changes around candidate queues, affected-net HPWL delta computation,
  move/swap/window evaluation, acceptance policy, local legality checks, and
  handoff-state consumers over superficial endpoint-script changes.
- Treat final HPWL as a product of legalization/improve co-optimization.
  Legalization and improve placement should pass useful state to each other;
  do not bet the whole attempt on only one stage.
- Hybrid legalizer routes are allowed when Teacher assigns them or source
  evidence supports them. Implement hybrids as source-level staged algorithms:
  one legalizer family produces a bounded frontier/residual, another legalizer
  family or repair policy consumes that residual, and improve placement
  consumes explicit handoff state. Do not implement a hybrid by rerunning
  unchanged endpoints multiple times.
- Build and evaluate; inspect canonical `metrics.json:hpwl` and the relevant OpenROAD log.
- If the result is weak or illegal, revise the algorithm or commit/selection logic, rebuild/evaluate, and keep the best clean candidate.
- Revisions must change the mechanism, not only constants.
- Evaluation loop is mechanism-driven, not count-limited.  Continue
  plan -> implement -> build/evaluate -> inspect metrics/logs -> revise while
  you have a concrete mechanism improvement, legality/build fix, or best-source
  restoration to test.  Stop when additional evaluations would repeat the same
  mechanism without new evidence, or when the runtime/complexity budget makes
  the route non-promotable.
- Treat runtime as a usable search budget. Within the generated DPL-flow timeout, use
  stronger bounded search when it can discover a better donor or mechanism. Cap
  endpoints and candidate lists, reuse cached touched data, log enough counters
  to explain cost, and remove duplicate endpoints before adding more expensive
  search.
- Do not default to baseline-like runtime when the mechanism needs more search.
  A clean result that uses only a few percent more runtime and gives only a
  sub-1% gain is usually under-explored unless you can show the source search
  space is exhausted.  It is acceptable to spend moderate extra runtime on
  bounded exact scoring, broader capped windows, batch transactions, or
  parallel candidate evaluation when the counters show useful work.
- Use high-performance parallel exploration when it is natural.  OpenMP,
  thread-local scratch buffers, parallel candidate scoring, and deterministic
  reductions are encouraged for independent row/window/candidate/local-HPWL
  probes.  Parallelism should let you evaluate a stronger bounded mechanism
  within the timeout; it must not mask an unbounded or duplicate search.
- Use the available timeout budget for credible HPWL-source mechanisms: deeper
  exact scoring, wider-but-capped windows, parallel candidate evaluation,
  stronger donor hybridization, or stronger legalization-to-improve handoff are
  valid when their complexity is bounded and the stage metrics can prove what
  changed.
- Treat runtime tiers as design choices.  `fast` preserves a donor,
  `explore` spends moderate extra runtime to test a larger bounded search, and
  `aggressive` spends a larger but timeout-safe budget on a mechanism that
  could materially change final HPWL.  If Teacher assigns an explore or
  aggressive route, implement a real larger search rather than optimizing back
  to baseline runtime.
- Do not improve HPWL by simply running an unchanged improve-placement flow
  more times, repeating random tails, or stacking endpoints. It is encouraged
  to modify the source-level `improve_placement_evolve` flow itself when the
  change is bounded: endpoint order, pass gating, candidate scoring, local
  search depth, or internal parameter policy are all valid if they have a named
  HPWL source, candidate cap, cache plan, stop condition, and stage-wise metric
  proof.
- The generated evaluation command has a DPL-flow timeout at
  ${student_runtime_multiplier}x the canonical `openroad_dpl_flow` baseline
  runtime. This timeout is applied only to the OpenROAD
  legalize/improve/mirror flow; metrics/evaluator collection is not
  timeout-wrapped and may still write failure evidence. Treat that timeout as
  the maximum usable flow budget. If the DPL flow times out, stop that
  implementation path, report it as non-promotable, and do not rerun the same
  mechanism.
- For every primary mechanism, add or reuse lightweight counters/logs that
  prove it actually executed. If the key accepted-target/frontier/transaction/
  candidate counter is zero, report the route as non-executed or negative
  evidence even if another inherited donor produced the final metrics.
- Keep exploration bounded: use `rg` first and small source excerpts around exact symbols. Do not read whole donor trees, event logs, or memory registries by default.
- Before opening an assumed source path, confirm it with `rg --files` or
  targeted `rg` on symbols. Do not spend time chasing guessed filenames that
  may not exist.
- Trust generated helper commands. Do not inspect evaluator/build wrapper internals unless the exact helper returned nonzero and its error text is insufficient.

## Patch Application Protocol

- Use `apply_patch` for source edits. Do not rewrite source files with Python,
  heredocs, `sed -i`, `perl -pi`, or broad formatter-driven edits.
- Patch only against current file contents from your private source tree. Before
  each nontrivial patch, confirm the file with `rg --files`, locate the exact
  function/state with targeted `rg -n`, and read a small nearby excerpt with
  line numbers.
- For donor-derived edits or Teacher-prose-derived hunks, running the generated
  source-context helper before `apply_patch` is mandatory. Do not reuse donor
  line numbers or old hunks as patch context.
- Do not apply patches against remembered snippets, Teacher text, donor-source
  snippets, or source from a different student workspace. Those are evidence,
  not patch context.
- Keep each patch hunk small and anchored on currently visible unique lines.
  Prefer one function, one state declaration, or one include/build-list change
  per hunk. For large mechanisms, apply several verified small patches instead
  of one broad patch.
- After every successful patch, run a targeted `rg -n` or small excerpt check
  on the changed symbol before continuing. Also run `git diff --check` before
  build.
- If `apply_patch` fails, do not retry the same hunk. Re-open the current source
  around the intended function/state, reduce the edit to the smallest semantic
  insertion or replacement, and apply a new patch based only on the refreshed
  current text.
- Patch recovery should stay local to the intended source function/state. Do not
  turn a patch failure into CMake/relink archaeology or broad source search.

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
- Runtime may use the generated ${student_runtime_multiplier}x timeout budget when the route is
  testing a bounded source mechanism rather than repeated endpoints or random
  tails.
- Runtime budget is not a penalty by itself.  It becomes a problem only when
  the extra time is duplicate endpoints, repeated random tails, broad rescans,
  or uninstrumented work.  Extra time spent on cached, capped, explainable
  HPWL-source search is valid evidence.
- Runtime savings from cheap legalization work should be reallocated to the
  best evidence-backed bounded improve-placement mechanism before declaring the
  attempt finished.
- Duplicate passes, repeated random tails, and endpoint stacking are not donor
  mechanisms. Prefer a deeper bounded algorithm with a clear HPWL source.
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
