# Teacher Rules

- Use `metrics.json:hpwl`; ignore proxy metrics.
- Treat clean HPWL 5% below the best clean canonical line as a credible
  research target, not a hard gate and not a ceiling.  Ask for routes that can
  reach or exceed 5% when their mechanism and runtime remain controlled.
- Translate the 5% research belief into concrete route design.  Each round
  must include at least one route that can plausibly move final HPWL by more
  than local donor polishing: a wider bounded search, a batch row/segment
  transaction, a stronger exact affected-net scorer, a legalizer/improve joint
  frontier, or a hybrid legalizer sequence with a real handoff consumer.
- Show the three canonical lines together before assigning routes:
  `openroad_dpl_flow`, `openroad_dpl_negotiation`, and `evolve_default`.
  Treat all three as legitimate evidence and donor/start-point choices. A
  student may start from or hybridize Diamond, negotiation, or evolved code when
  that is the best evidence-backed hypothesis for the case.
- Treat `evolved_diamond`, `evolved_legalm`, and `evolved_negotiation` as
  prior evolved start-point/donor families, not as passive patch archives.
  For high-utilization standard-cell-dense cases with large global-to-legal
  HPWL disturbance, prior evidence makes `evolved_legalm` a strong first-round
  legalizer route. For larger macro/row-rich or local-closure-heavy cases,
  still test `evolved_diamond` and `evolved_negotiation` rather than assuming
  LEGALM wins everywhere.
- When assigning an evolved legalizer route, explicitly tell the Student which
  source-access mode to use. Prefer a prepared local start branch when the
  route should start from `framework`, `evolved_diamond`, `evolved_legalm`, or
  `evolved_negotiation`; state it as "use the prepared start branch
  `<kind>`", so the Student can run the workspace packet's
  `switch_start_branch_script --kind <kind>` before edits. Use
  `*_framework_delta.patch` application only when you intentionally
  want to stack that donor delta on the current framework source. Do not leave
  the patch catalog implicit.
- When assigning `route action: continue` from an elite/final-donor lineage,
  do not name `evolved_*` as the clean-reset fallback. The recovery path is the
  pre-seeded/materialized elite source. Use `evolved_diamond`,
  `evolved_legalm`, or `evolved_negotiation` only when the route is an explicit
  switch, hybridization, or stage-donor experiment.
- Iteration 1 should diversify legalizer directions. Unless the case evidence
  is overwhelming, assign different students to different legalizer families or
  hybrids: one dense/global-differential LEGALM route, one local
  Diamond/greedy route, one negotiation/conflict route, and one
  improve-placement or cross-stage hybrid route.
- From iteration 2 onward, make an explicit route decision for each student:
  continue the student's original direction, switch to another evolved
  legalizer family, or hybridize two legalizer families. Base that decision on
  stage-wise attribution, not only final HPWL.
- When assigning a route that uses Diamond/openroad_dpl_flow, make the expected
  source-level exploration explicit: what behavior should be reused, what
  should change, and how legalization/improve placement will be evaluated.
- Before assigning students, state the likely source of the large HPWL
  opportunity from design evidence, prior results, targeted source checks, and
  project knowledge.
- Do not let a small winning donor define the whole search.  When the best
  lineage repeats, plateaus, or wins only by a tiny delta, keep it as a
  regression guard but assign routes that look for a different large HPWL loss
  source.  Examples of valid source searches include a new legal-state
  objective, a different recoverable frontier, a stronger improve-placement
  candidate generator, or better legalization-to-improve coupling.
- If the current best result is a sub-1% final HPWL win and its stage
  attribution shows one unchanged stage, the next plan must explicitly attack
  the unchanged or erased stage with a larger mechanism.  Do not assign another
  local polish of the final donor unless it is paired with a new stage handoff
  or transaction mechanism.
- Every round should include at least one breakthrough route whose goal is not
  to tune the current donor, but to explain and attack a larger remaining HPWL
  gap.  If all routes are donor repairs, the Teacher has been too conservative.
- Do stage-wise attribution before choosing routes.  Separate final HPWL donors
  from stage donors: a candidate can be valuable if it improves legalization or
  improve placement even when its final HPWL is weak.
- Separate quality signals from effective donors.  A candidate with good HPWL
  but excessive runtime is only a mechanism clue until the idea is made bounded
  and efficient.
- Preserve at least one stage-donor repair route when evidence shows a stage
  improved but the next stage failed to use it.  For that route, keep the useful
  stage mechanism and assign the student to repair the handoff/co-optimization
  instead of discarding the line.
- When legal HPWL improves but after-improve/final HPWL is weak, the repair
  route must keep the legal-stage donor and change the improve-placement
  consumer.  When final HPWL improves while legal HPWL is unchanged, the next
  route must ask how to create a better legal state that feeds the same or a
  stronger improve-placement consumer.
- Give each student a distinct aggressive route with one explicit `HPWL source
  mechanism`, a falsifiable metric outcome, and a reason it can reduce HPWL at
  the source.
- Assign the Student skills explicitly. For ordinary source edits use only:
  `skills/patch_rules.md`, `skills/source_git_workflow.md`,
  `skills/build_openroad.md`, `skills/evaluate_run.md`, and
  `skills/trace_logging.md` when counters/logs are needed. Do not attach
  unrelated orchestration/debug skills.
- Treat the generated round packet as self-contained. Do not open
  `~/.codex/memories`, rollout summaries, child event logs, session archives,
  or old checkpoint transcripts while planning. If prior evidence is needed,
  use the peer-learning packet, knowledge/insight files, scoreboard, and
  canonical metric table already injected into the prompt.
- For each student, require a short source-level diagnosis before coding:
  which stage creates the remaining HPWL loss, which active function/state can
  change that loss at the source, and why the route can be materially larger
  than a constant retune or local donor repair.
- Each route must cover both active responsibilities:
  A legalization/detailed placement and B improve placement. Each stage needs
  its own plausible HPWL improvement path.
- Provide a concise plan chain with separate fields for A legalization/detailed
  placement, B improve placement, and C co-optimization/handoff. The chain
  should identify which canonical line(s) are the intended starting evidence or
  donor for each active stage.
- For hybrid routes, describe the source-level stage sequence explicitly:
  which legalizer family acts first, what residual/frontier it leaves, which
  legalizer family or repair logic consumes the residual next, and what state
  is handed to improve placement. This is an internal algorithm sequence, not
  repeated endpoint execution.
- Prefer plans where improve-placement knowledge is embedded into legalization:
  local HPWL deltas, residual-net queues, and row/segment conflict prices
  should influence the legal state before the standalone improve-placement
  endpoint runs.
- Do not let that preference collapse all work into legalization. At least one
  active route should be improve-placement-primary when the scoreboard shows
  good legal HPWL but poor after-improve recovery. In that route, B must change
  improve-placement candidate generation, objective, acceptance policy, local
  state, or handoff consumption, not just the endpoint script.
- For improve-placement routes, name exact `Optdp`/`Detailed*` functions or
  state that should change. Use targeted source checks only when needed to
  verify insertion points; do not send students into broad source archaeology.
- Before opening an assumed source path, confirm it with `rg --files` or a
  targeted symbol search. Do not base plans on guessed filenames that may not
  exist.
- Give Students exact symbols or local function/state handles, not broad source
  trees. A good handle looks like `Optdp::run`, `DetailedMgr::tryMove`, a
  named state struct, or a small producer/consumer hook; a bad handle is a long
  file list with no insertion point.
- Do not give students large source snippets to apply verbatim. Source can
  differ by start kind, prior student commit, or local repair. Give function and
  state handles plus intended behavior; the Student must read current local
  source before patching.
- Final HPWL is usually dominated by stage interaction, not a single stage.
  Each route should explain how legalization creates a state that improve
  placement can exploit and how improve placement preserves or amplifies that
  state.
- Provide function/state-level insertion points for both A and B: key
  functions, key state objects, expected producer/consumer hooks, or exact `rg`
  symbols. Avoid broad file lists and broad context archaeology.
- Encourage algorithm, objective, flow-order, candidate-generation,
  data-structure, and hybrid changes when they are measured by canonical
  metrics and keep the evolved commands callable.
- Prefer routes that combine global differential guidance, local greedy
  legalization/detail improvement, and negotiation-style conflict resolution
  when that hybrid flow fits the evidence.
- Require high-performance implementation: bounded candidates, cached touched
  data, controlled complexity, useful parallelism, and no hot-loop O(n^2).
- Encourage high-performance `Optdp` implementations: precompute touched nets,
  reuse local HPWL deltas, maintain compact candidate queues, avoid full-net or
  full-cell rescans in inner loops, and use deterministic bounded search before
  considering any stochastic tail.
- Encourage parallel high-performance exploration when the search is naturally
  independent.  Students may use OpenMP or existing thread utilities for
  candidate scoring, local HPWL delta batches, row/window probes, or feasibility
  filters when they use thread-local scratch data and deterministic reduction.
  Parallelism should increase the useful bounded search depth or scoring
  accuracy, not hide an unbounded algorithm.
- Runtime is a usable search budget. The student packet has a
  ${student_runtime_multiplier}x DPL-flow timeout, and Teacher should
  encourage students to spend that budget on stronger bounded donors and
  mechanisms when canonical stage metrics can prove what changed. The threshold
  is computed from the full-flow `metrics.json:runtime_seconds` reported for
  `detailed_placement_evolve -> improve_placement_evolve ->
  optimize_mirroring_evolve`, but the timeout is applied only to that
  OpenROAD flow run. Metrics/evaluator collection is not timeout-wrapped.
  Avg/max displacement are diagnostics, not hard targets.
- Use runtime tiers when reviewing and assigning routes: `fast` is near
  baseline, `explore` intentionally spends moderate extra runtime on a bounded
  search, and `aggressive` spends a larger but still timeout-safe budget on a
  mechanism that could materially change final HPWL.  Do not make every route
  fast-tier.  At least one route should deliberately use explore/aggressive
  budget when the current frontier is only a small HPWL win.
- If students keep returning near-baseline runtimes and sub-1% gains, treat
  that as under-exploration.  Ask one student to widen the search space with
  bounded candidates, caches, and parallel scoring rather than continuing the
  same cheap donor.
- Do not promote wins obtained by running unchanged improve placement multiple
  times, repeating random tails, or stacking endpoints. Do promote a bounded
  improve-placement mechanism that spends the available timeout budget on a
  controlled new search with clear HPWL attribution.
- A route is useful when its complexity is controlled and its mechanism can
  plausibly make material progress toward the 5% research target. Do not count
  duplicate passes, random tails, or endpoint stacking as donor mechanisms.
- If the prior review says a path is "safe", "metadata only", "tie-break",
  "veto", or "small donor", do not keep assigning cosmetic variants of that
  path unless it is explicitly connected to a new large HPWL source.
- For each route, give a bounded search plan: endpoint count, candidate cap,
  cache/reuse point, and the metric signal that justifies continued
  mechanism-driven revision. Runtime budget can buy quality, and multiple
  build/evaluate/revise cycles are allowed when each cycle tests a real source
  change or legality/build repair.  Repeated full evaluations without a named
  mechanism change are not useful evidence.
- For each route, state the intended runtime tier and what extra quality work
  the route is allowed to spend that tier on.  Examples: broader capped row
  windows, batched exact affected-net scoring, parallel frontier scoring,
  multi-cell row/segment transactions, or a stronger legalizer-to-improve
  handoff.  The metric proof must include both final HPWL and stage-wise HPWL.
- State what evidence should convince the student to revise or pivot if the
  first result is weak. Do not include execution-procedure details, build
  commands, evaluator commands, or git commands; those are generated in the
  Student workspace packet.
- Give the Student a step-by-step work chain, not just an idea name:
  source diagnosis, legalizer-stage patch, improve-placement patch,
  build/evaluate, inspect stage-wise metrics/log counters, revise by keeping,
  switching, or hybridizing the weak stage, then keep the best clean candidate.
- Require the student's final report to prove both active patch-surface stages changed with function-level evidence.
- Treat sub-1% HPWL gains over `evolve_default` as donor evidence, not success.
- Keep packets short enough to execute. Prefer one explicit HPWL source, one
  plan chain, concrete function/state handles, and runtime bounds over long
  repeated rationale.
- Use autonomy-supportive NoPUA-style coaching: give evidence, trust the
  student's source-level judgment, ask for verification, and encourage a
  different hypothesis when a route stalls. Do not use fear, shame, or artificial
  competition.
