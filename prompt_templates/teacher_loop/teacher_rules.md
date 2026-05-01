# Teacher Rules

- Use `metrics.json:hpwl`; ignore proxy metrics.
- Treat clean HPWL 5% below `openroad_dpl_flow` as a credible research target,
  not a hard gate and not a ceiling.  Ask for routes that can reach or exceed
  5% when their mechanism and runtime remain controlled.
- Use `evolve_default` as an internal anchor and donor source when useful, but
  do not let it replace the Diamond/openroad_dpl_flow target definition.
- Do not assign Diamond, Diamond-equivalent selection, or a plain Diamond
  anchor as the initial legalizer.  Diamond/openroad_dpl_flow is only a
  comparison baseline and optional measurement reference.  The legalization
  route itself must start from an evolved mechanism such as global differential
  guidance, ALM/BGD-style placement, row-flow/cluster legalization,
  negotiation-aware projection, or a hybrid of these.
- Do not ask students to copy Diamond baseline code, wrap Diamond with a few
  gates, or preserve Diamond as the real legal-state producer.  Students may
  inspect Diamond only for legality checks, data structures, and measurement
  references.
- Before assigning students, state the likely source of the large HPWL
  opportunity from design evidence, prior results, source inspection, and
  project knowledge.
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
- Each route must cover legalization, improve placement, and
  mirror/orientation. Each stage needs its own plausible HPWL improvement path.
- Provide a concise `plan chain`: A legalization, B improve placement, C
  mirror/orientation, and D optional coordination/selection when useful.
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
