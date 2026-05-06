# Teacher Rules

## Evidence And Objective

- Use `metrics.json:hpwl`; ignore proxy metrics.
- Treat clean HPWL 5% below the best clean canonical line as a credible
  research target, not a hard gate and not a ceiling. Keep useful below-5%
  mechanisms as donor evidence, but do not let sub-1% gains define success.
- Show `openroad_dpl_flow`, `openroad_dpl_negotiation`, and `evolve_default`
  together before assigning routes. All three are legitimate evidence and
  donor/start-point choices.
- Before assigning students, state the likely large HPWL source using design
  evidence, prior results, targeted source checks, and project knowledge.
- Do stage-wise attribution before choosing routes. Separate final HPWL donors
  from legalization-stage donors, improve-placement donors, runtime-only
  quality signals, non-executed mechanisms, and negative evidence.
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
  `<kind>`" for `framework`, `evolved_diamond`, `evolved_legalm`, or
  `evolved_negotiation`. Use `*_framework_delta.patch` only when intentionally
  stacking that donor delta on the current framework source.
- For `route action: continue` from an elite/final donor, continue the
  pre-seeded/materialized elite source. Do not name an `evolved_*` clean-reset
  fallback unless the route is an explicit switch, hybridization, or stage-donor
  experiment.
- Iteration 1 should diversify legalizer directions unless evidence is
  overwhelming: global/differential LEGALM, local Diamond/greedy,
  negotiation/conflict, and improve-placement or cross-stage hybrid routes.
- From iteration 2 onward, label each route `continue`, `switch`, or
  `hybridize`, justified by stage-wise HPWL, runtime, and trace counters.
- Prefer hybrid flows when evidence supports them: global differential
  guidance, local greedy legalization/detail improvement, and negotiation-style
  conflict resolution can be combined as a staged source-level algorithm.

## Route Requirements

- Give each student one explicit `HPWL source mechanism`, a falsifiable metric
  outcome, and a reason it can attack a materially larger gap than donor
  polishing.
- Every route must cover both active responsibilities: A
  legalization/detailed placement and B improve placement. Each stage needs its
  own plausible HPWL path.
- Provide a concise plan chain: A legalization/detailed placement, B improve
  placement, and C co-optimization/handoff. Identify the canonical line or
  evolved family used as evidence or start for each active stage.
- For hybrid routes, describe the staged source flow: first legalizer family,
  residual/frontier handoff, second legalizer or repair family, and
  improve-placement consumer. This is internal algorithm sequencing, not
  repeated endpoint execution.
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
- Require the final report to prove both active stages changed with
  function-level evidence and stage-wise metrics.
- Keep packets executable: one HPWL source, one plan chain, exact
  function/state handles, runtime tier, and metric proof.
- Use autonomy-supportive NoPUA-style coaching: give evidence, trust the
  student's source-level judgment, ask for verification, and invite a different
  hypothesis when a route stalls.
