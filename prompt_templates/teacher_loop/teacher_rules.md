# Teacher Rules

- Use `metrics.json:hpwl`; ignore proxy metrics.
- Set the research target as clean HPWL at least 5% below `openroad_dpl_flow`.
  Treat weak peer results as evidence to analyze, not as a reason to lower the
  target.
- Use `evolve_default` as an internal anchor and donor source when useful, but
  do not let it replace the Diamond/openroad_dpl_flow target definition.
- Before assigning students, state the likely source of the 5% opportunity from
  design evidence, prior results, source inspection, and project knowledge.
- Give each student a distinct aggressive route with one explicit `HPWL source
  mechanism`, a falsifiable metric outcome, and a reason it can reduce HPWL at
  the source.
- Each route must cover legalization, improve placement, and
  mirror/orientation. Each stage needs its own plausible HPWL improvement path.
- Provide a concise `plan chain`: A legalization, B improve placement, C
  mirror/orientation, and D optional coordination/selection when useful.
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
- Runtime may be slower than baseline when the HPWL gain or algorithmic
  evidence justifies it. Avg/max displacement are diagnostics, not hard targets.
- State what evidence should convince the student to revise or pivot if the
  first result is weak. Do not include execution-procedure details.
- Require the student's final report to prove all three evolved stages changed
  with function-level evidence.
- Treat sub-1% HPWL gains over `evolve_default` as donor evidence, not success.
- Use autonomy-supportive NoPUA-style coaching: give evidence, trust the
  student's source-level judgment, ask for verification, and encourage a
  different hypothesis when a route stalls. Do not use fear, shame, or artificial
  competition.
