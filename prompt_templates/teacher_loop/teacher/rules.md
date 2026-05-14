# Teacher Rules

## Evidence And Objective

- Use `metrics.json:hpwl`; ignore proxy metrics.
- Keep the research target as canonical HPWL reduction. Use
  `G_HR = 100 * (HPWL_ref - HPWL_sol) / HPWL_ref - P(runtime_sol / runtime_ref), where P(r)=0 for r <= 1.10 and P(2.0)=1.0 percentage point`
  versus the OpenROAD DPL default-flow (`openroad_dpl_flow`,
  Diamond-search) reference only as an experiment-analysis and runtime-value
  metric. Do not use `G_HR` as the optimization target, promotion target, or
  elite/default-parent selector.
  Do not promote a faster but worse-final-HPWL candidate over a clean lower-HPWL
  candidate as the headline elite. Keep the faster candidate as runtime/control
  evidence unless the lower-HPWL candidate violates legality, artifact gates, or
  the hard timeout budget.
  The runtime term has a deadband: runtime improvements and <=1.10x
  runtime noise receive no bonus; 2x runtime needs 1.0 percentage point of
  reference-normalized final-HPWL gain to break even.
- Treat clean HPWL 5% below the OpenROAD DPL default-flow reference as a credible
  research target, not a hard gate and not a ceiling. Keep useful below-5%
  mechanisms as donor evidence, but do not let sub-1% gains define success.
- Show `openroad_dpl_flow`, `openroad_dpl_negotiation`, and `evolve_default`
  together before assigning routes. All three are legitimate evidence and
  donor/start-point choices.
- Before assigning students, state the likely large HPWL source using design
  evidence, prior results, targeted source checks, and project knowledge.
- Use the LEGO-lite skill index when a route needs a reusable mechanism. Query
  by stage and bottleneck, then select only the relevant skill ids; do not dump
  skill notes into every Student prompt.
- When selecting a new mechanism, inspect the relevant algorithm/pseudocode
  card after the skill query: `algorithm_cards/legalization/` for legalizer
  mechanisms, `algorithm_cards/dpo_refinement/` for improve-placement or
  handoff mechanisms, and `algorithm_cards/context/` only for background.
  Use those cards to find a mechanism, pseudocode skeleton, liveness counters,
  and failure mode; do not treat them as mandatory code.
- Do stage-wise attribution before choosing routes. Separate final HPWL donors
  from legalization-stage donors, improve-placement donors, runtime-only
  quality signals, non-executed mechanisms, and negative evidence.
- Use Student log/efficiency diagnoses as first-class evidence: DPL counters,
  timeout/failure cause, zero-counter mechanisms, stale binary/source mismatch,
  acceptance bottlenecks, legality rejects, fallback domination, broad rescans,
  and duplicated endpoint work should change the next route.
- If the best lineage repeats, plateaus, or wins by a tiny delta, keep it as a
  regression guard but assign at least one route to a different large HPWL
  source: objective, legal frontier, candidate generator, transaction, exact
  affected-net scorer, data structure, or legalizer/improve handoff.

## Donor And Start Strategy

- Treat `evolved_diamond`, `evolved_legalm`, and `evolved_negotiation` as prior
  evolved start-point families. Dense high-utilization standard-cell cases with
  large legalization HPWL inflation should usually include an `evolved_legalm`
  route; macro/row-rich or local-closure-heavy cases should still test Diamond
  and negotiation evidence.
- Treat the best current donor as a regression anchor and evidence source, not
  the default parent for exploratory routes. Exploration routes should choose
  the parent that best tests their HPWL source mechanism.
- When assigning a start kind, be explicit: say "use the prepared start branch
  `<kind>`" for `framework`, `diamond`, `evolved_diamond`, `evolved_legalm`,
  or `evolved_negotiation`. Student start-point switches are branch-only; the
  Student then commits local source edits on the iteration branch.
- Assign DPO work as source-level mechanism design in the current tree after
  inspecting active `Optdp`/`Detailed*` code and logs. Implement the selected
  mechanism directly in the current source.
- For `route action: continue` from an elite/final donor, continue the
  pre-seeded/materialized elite source. Do not name an `evolved_*` clean-reset
  fallback unless the route is an explicit switch, hybridization, or stage-donor
  experiment.
- Iteration 1 should diversify legalizer directions unless evidence is
  overwhelming: global/differential LEGALM, local Diamond/greedy,
  negotiation/conflict, and improve-placement or cross-stage hybrid routes.
- Treat global/differential legalization followed by source-level detailed
  repair as a high-potential route that should be able to beat pure local
  greedy when the guidance-to-refinement handoff is correct. If a global route
  has legal-stage signal but weak final HPWL, first diagnose the detailed
  repair/handoff consumer before discarding the global mechanism.
- From iteration 2 onward, label each route `continue`, `switch`, or
  `hybridize`, justified by stage-wise HPWL, runtime, and trace counters.
- Prefer hybrid flows when evidence supports them: global differential
  guidance, local greedy legalization/detail improvement, and negotiation-style
  conflict resolution can be combined as a staged source-level algorithm.
- Hybrid does not mean choosing one complete legalizer by case through an
  `if/else` selector.  It means composing algorithmic mechanisms inside one
  candidate source flow, for example lightweight global/differential guidance,
  native legality closure, local HPWL repair, and a bounded DPO consumer.
- Treat design-feature strategy cards as inspiration for source mechanisms, not
  as a routing table.  Ask Students to adapt the idea after inspecting the
  current code, and require counters that prove the staged mechanism ran.

## Route Requirements

- Give each student one explicit `HPWL source mechanism`, a falsifiable metric
  outcome, and a reason it can attack a materially larger gap than donor
  polishing.
- Name selected stage skills when useful: one for legalization, one for improve
  placement, and one handoff/diagnosis skill when that is the route's active
  uncertainty. Include the expected state transition and done criteria for each
  selected skill.
- Every route must declare primary emphasis: `legalizer-emphasis`,
  `DPO-emphasis`, or `co-optimization-emphasis`. This is a priority label, not
  a one-stage-only license. Students should analyze both legalization and
  improve placement and should patch both when there is a coherent,
  high-quality mechanism. If the secondary stage is not patched, Teacher must
  state why a cosmetic edit would be worse than diagnosis/handoff evidence.
- Provide a concise plan chain: A legalization/detailed placement, B improve
  placement, and C co-optimization/handoff. Each route should include a
  meaningful plan for A and B: either a source change, a handoff/consumer
  change, or a concrete diagnostic proving why that stage should be preserved
  this round.
- Parameter tuning is a valid route only when it is implemented inside the
  `dpl_evolve` source as mechanism parameters: constants, thresholds,
  scoring weights, pass schedules, adaptive policies, or compact internal
  config structs. Do not assign Tcl/flow-script knob sweeps. If Teacher wants
  a parameter route, name the source file/function where the parameter lives
  and the liveness counter or stage metric that proves it affected HPWL.
- For hybrid routes, describe the staged source flow: first legalizer family,
  residual/frontier handoff, second legalizer or repair family, and
  improve-placement consumer. This is internal algorithm sequencing, not
  repeated endpoint execution and not case-level selection among unrelated
  legalizers.
- Preserve stage-donor repair routes. If one stage improves but a later stage
  erases the gain, keep the useful stage mechanism and assign a repair of the
  handoff/consumer instead of discarding the line.
- Preserve active mechanism workbenches for at least one focused repair when
  they have nonzero counters, clean legality, controlled runtime, and either a
  stage-local gain or a diagnosed final-loss reason.
- Distinguish continuation parents: `final donor`, `stage donor`, and
  `mechanism workbench`. Use the parent that matches the route.
- If legal HPWL improves but final HPWL is weak, repair the improve-placement
  consumer. If final HPWL improves while legal HPWL is unchanged, ask how
  legalization can create a better frontier for that consumer.
- Prefer plans where improve-placement knowledge enters legalization through
  local HPWL deltas, residual-net queues, row/segment conflict prices, or
  handoff state. Do not collapse all work into legalization; assign
  improve-placement-primary routes when after-improve recovery is the gap.

## Source Handles And Student Scope

- Give function/state-level handles, not broad source trees. Good handles look
  like `Optdp::run`, `DetailedMgr::tryMove`, a named state struct, or a small
  producer/consumer hook.
- Before relying on a path, confirm it with `rg --files` or targeted symbol
  search. Do not base plans on guessed filenames.
- Do not give large source snippets to apply verbatim. Source differs by start
  kind and student workspace; give intended behavior plus insertion handles.
- For improve-placement routes, name exact `Optdp`/`Detailed*` functions or
  state to change. B must alter source-level candidate generation, objective,
  acceptance, local state, endpoint policy, or handoff consumption.
- Assign only relevant skills for ordinary source edits:
  `skills/patch_rules.md`, `skills/source_git_workflow.md`,
  `skills/build_openroad.md`, `skills/evaluate_run.md`, and
  `skills/trace_logging.md` when counters/logs are needed.
- Treat the generated packet as self-contained. Do not open memories, rollout
  summaries, child event logs, session archives, or old checkpoint transcripts
  while planning.

## Runtime And Implementation Expectations

- Runtime is a usable search budget. State the intended tier: `fast`,
  `explore`, or `aggressive`, and what extra bounded work that tier buys.
- `Bounded` means complexity-controlled, measurable, and timeout-safe; it does
  not mean small-scope. Prefer large search spaces made tractable by candidate
  caps, caches, parallel scoring, and deterministic reductions.
- Encourage explore/aggressive routes when near-baseline runtime keeps
  producing only sub-1% gains. Budget should buy capped row/window search,
  batched transactions, exact affected-net scoring, parallel frontier scoring,
  or stronger legalizer/improve handoff.
- Require high-performance implementation: bounded candidates, cached touched
  data, compact queues, controlled complexity, useful parallelism, and no
  hot-loop full rescans or avoidable `O(n^2)`.
- Encourage OpenMP or existing thread utilities for independent scoring/probing
  loops with thread-local scratch data and deterministic reduction.
- When assigning broader search, also assign what log evidence should prove it
  is efficient: candidate cap, accepted/attempted ratio, reject reasons,
  touched-net/cache reuse, parallel scoring count, and elapsed pass/runtime
  signal. A quality clue with poor runtime should become a rewrite-for-efficiency
  route, not be discarded automatically.
- Do not promote wins from unchanged repeated improve-placement runs, random
  tails, duplicate passes, endpoint stacking, or uninstrumented broad rescans.
  Distill any quality signal into one bounded mechanism.

## Review-To-Plan Discipline

- If a route returns weak final HPWL but active counters, ask for targeted
  repair of liveness, objective, acceptance, persistence, handoff,
  final-safe survival scoring, or runtime implementation before declaring it
  exhausted.
- If a path is only "safe", "metadata", "tie-break", "veto", or "small donor",
  do not assign cosmetic variants unless they connect to a new large HPWL
  source.
- Give the Student a step chain, not just an idea name: source diagnosis,
  legalizer patch, improve-placement patch, build/evaluate, inspect stage
  metrics/log counters, revise the weak stage, then keep the best clean
  candidate.
- Ask the Student to prove each selected skill with function/state-level source
  evidence, stage-wise metrics, and the skill's log signals. If the source
  evidence contradicts a selected skill, the Student should pivot and report the
  better mechanism.
- Require the final report to prove every patched stage with function-level
  evidence and stage-wise metrics. If only one stage changed, require a
  specific explanation of how the other stage preserved, consumed, or erased
  the gain, and what would be the next high-quality change there.
- Require the final report/knowledge card to include log-derived diagnosis:
  key DPL counter lines, runtime bottleneck classification, implementation
  error evidence if any, and the exact repair that should guide the next plan.
- Keep packets executable: one HPWL source, one plan chain, exact
  function/state handles, runtime tier, and metric proof.
- Use autonomy-supportive NoPUA-style coaching: give evidence, trust the
  student's source-level judgment, ask for verification, and invite a different
  hypothesis when a route stalls.
