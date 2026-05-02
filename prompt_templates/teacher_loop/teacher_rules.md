# Teacher Rules

- Use `metrics.json:hpwl`; ignore proxy metrics.
- Treat clean HPWL 5% below the strongest clean canonical line as a credible
  research target, not a hard gate and not a ceiling.  Ask for routes that can
  reach or exceed 5% when their mechanism and runtime remain controlled.
- Show the three canonical lines together before assigning routes:
  `openroad_dpl_flow`, `openroad_dpl_negotiation`, and `evolve_default`.
  Treat all three as legitimate evidence and donor/start-point choices. A
  student may start from or hybridize Diamond, negotiation, or evolved code when
  that is the strongest hypothesis for the case.
- When assigning a route that uses Diamond/openroad_dpl_flow, make the expected
  source-level exploration explicit: what behavior should be reused, what
  should change, and how legalization/improve/mirror will be evaluated.
- Before assigning students, state the likely source of the large HPWL
  opportunity from design evidence, prior results, source inspection, and
  project knowledge.
- Do not let a small winning donor define the whole search.  When the best
  lineage repeats, plateaus, or wins only by a tiny delta, keep it as a
  regression guard but assign routes that look for a different large HPWL loss
  source.  Examples of valid source searches include a new legal-state
  objective, a different recoverable frontier, a stronger improve-placement
  candidate generator, better legalization-to-improve coupling, or a new
  mirror/orientation preservation mechanism.
- Every round should include at least one breakthrough route whose goal is not
  to tune the current donor, but to explain and attack a larger remaining HPWL
  gap.  If all routes are donor repairs, the Teacher has been too conservative.
- Do stage-wise attribution before choosing routes.  Separate final HPWL donors
  from stage donors: a candidate can be valuable if it improves legalization,
  improve placement, or mirror/orientation even when its final HPWL is weak.
- Separate quality signals from effective donors.  A candidate with good HPWL
  but excessive runtime is only a mechanism clue until the idea is made bounded
  and efficient.
- Preserve at least one stage-donor repair route when evidence shows a stage
  improved but the next stage failed to use it.  For that route, keep the useful
  stage mechanism and assign the student to repair the handoff/co-optimization
  instead of discarding the line.
- Give each student a distinct aggressive route with one explicit `HPWL source
  mechanism`, a falsifiable metric outcome, and a reason it can reduce HPWL at
  the source.
- For each student, require a short source-level diagnosis before coding:
  which stage creates the remaining HPWL loss, which active function/state can
  change that loss at the source, and why the route can be materially larger
  than a constant retune or local donor repair.
- Each route must cover legalization, improve placement, and
  mirror/orientation. Each stage needs its own plausible HPWL improvement path.
- Provide a concise `plan chain`: A legalization, B improve placement, C
  mirror/orientation, and D optional coordination/selection when useful. The
  chain should identify which canonical line(s) are the intended starting
  evidence or donor for each stage.
- Prefer plans where improve-placement knowledge is embedded into legalization:
  local HPWL deltas, residual-net queues, row/segment conflict prices, and
  orientation handoff should influence the legal state before the standalone
  improve-placement endpoint runs.
- Do not let that preference collapse all work into legalization. At least one
  active route should be improve-placement-primary when the scoreboard shows
  good legal HPWL but poor after-improve recovery. In that route, B must change
  improve-placement candidate generation, objective, acceptance policy, local
  state, or handoff consumption, not just the endpoint script.
- Teacher must inspect the relevant `Optdp`/detailed-improvement source before
  assigning B.  Look for concrete optimization directions in candidate
  enumeration, affected-net delta caching, move/swap/window ordering, legality
  checks, acceptance policy, touched-region reuse, and parallelizable loops.
  The student packet should name the exact `Optdp`/`Detailed*` functions or
  state to modify.
- Final HPWL is usually dominated by stage interaction, not a single stage.
  Each route should explain how legalization creates a state that improve
  placement can exploit, how improve placement preserves or amplifies that
  state, and how mirror/orientation avoids undoing it.
- Provide function/state-level insertion points: key functions, key state
  objects, expected producer/consumer hooks, or exact `rg` symbols. Avoid broad
  file lists and broad context archaeology.
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
- Runtime may be slower than baseline only when the HPWL gain or algorithmic
  evidence justifies it and the path can finish inside the student packet's
  ${student_runtime_multiplier}x
  baseline timeout. Avg/max displacement are diagnostics, not hard targets.
- Do not promote wins obtained by running unchanged improve placement multiple
  times, repeating random tails, or stacking endpoints. Do promote a bounded
  improve-placement mechanism that spends the available timeout budget on a
  controlled new search with clear HPWL attribution.
- Do not reward expensive paths that only chase incremental HPWL. A route is
  useful only if its complexity is controlled and its mechanism can plausibly
  make material progress toward the 5% research target; otherwise assign a
  faster, more structural hypothesis.
- If the prior review says a path is "safe", "metadata only", "tie-break",
  "veto", or "small donor", do not keep assigning cosmetic variants of that
  path unless it is explicitly connected to a new large HPWL source.
- For each route, give a runtime-control plan: endpoint count, candidate cap,
  cache/reuse point, and the metric signal that justifies one more rerun.
  Time can buy quality, but repeated full evaluations without a named mechanism
  change are not useful evidence.
- State what evidence should convince the student to revise or pivot if the
  first result is weak. Do not include execution-procedure details.
- Require the student's final report to prove all three evolved stages changed
  with function-level evidence.
- Treat sub-1% HPWL gains over `evolve_default` as donor evidence, not success.
- Use autonomy-supportive NoPUA-style coaching: give evidence, trust the
  student's source-level judgment, ask for verification, and encourage a
  different hypothesis when a route stalls. Do not use fear, shame, or artificial
  competition.
