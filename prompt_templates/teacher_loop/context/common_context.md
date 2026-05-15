# Round Context

- case: `$case_id`
- flow_variant: `$flow_variant`
- threads: `$threads`
- start_kind: `$start_kind`
- round_id: `$round_id`
- iteration: `$iteration_name`
- packet: `$packet_path`

## Sources

- evolved source: `$dpl_evolve_src`
- LEGALM reference: `$legalm_guidance`
- OpenROAD DPL default-flow reference: `$openroad_diamond`
- negotiation donor: `$openroad_negotiation_nblg`
- Abacus donor: `$dreamplace_abacus`
- dense evolved-legalizer routing insight: `$dense_legalizer_routing_insight`
- feature-to-mechanism strategy insight: `$strategy_inspiration_insight`
- DPO mechanism insight: `$dpo_source_mechanisms_insight`
- OpenROAD-native handoff insight: `$openroad_native_handoff_insight`
- LEGO-lite skill index: `$skill_index`
- LEGO-lite skill query helper: `$skill_query_script`
- LEGO-lite skill notes: `$skill_cards_dir`
- algorithm/pseudocode cards: `$algorithm_cards_dir`
- Teacher coaching skill: `$teacher_coaching_skill`

Use these paths as search handles only when they help identify concrete
function/state insertion points. Do not require broad donor-tree reading.

## LEGO-lite Skill Lookup

- Use the skill index as the first-stage knowledge database. Query it before
  assigning a route when the needed legalizer, DPO, handoff, or diagnosis
  mechanism is not obvious from the metrics.
- Fast command pattern:
  `python3 $skill_query_script --stage <stage> --q "<bottleneck or mechanism>"`
- Stage names: `case_diagnosis`, `start_selection`, `legalization`,
  `improve_placement`, `handoff`, `build_eval_log_diagnosis`, and
  `teacher_review`.
- A selected skill is guidance, not a cage. Teacher should name the skill id,
  expected stage transition, done criteria, and log signals; Student may refine
  the mechanism when current source evidence contradicts the card.
- Treat strategy cards as design-feature inspiration, not case-level algorithm
  selectors.  Teacher should translate them into a staged source mechanism and
  require liveness counters rather than assigning a fixed route by name.
- For mechanism inspiration, Teacher should query the skill index first and
  then open the smallest relevant card under `$algorithm_cards_dir`, especially
  `legalization/` for legalizer routes and `dpo_refinement/` for improve
  placement or handoff routes. Pseudocode cards are idea contracts, not fixed
  recipes.

## Objective And Boundaries

- canonical metric: `metrics.json:hpwl` from OpenROAD/DPL pin-based logs;
  ignore `hpwl_proxy` for promotion
- primary research target remains canonical HPWL reduction. Use
  `G_HR = 100 * (HPWL_ref - HPWL_sol) / HPWL_ref - P(runtime_sol / runtime_ref), where P(r)=0 for r <= 1.10 and P(2.0)=1.0 percentage point`
  against the OpenROAD DPL default-flow (`openroad_dpl_flow`, Diamond-search)
  reference as an analysis metric only. The evolve optimization target,
  promotion target, and elite/default-parent selector are legal final HPWL under
  the hard runtime budget. Use `G_HR` only to explain whether the HPWL gain needs
  runtime repair.
  A faster but worse-final-HPWL result is runtime/control evidence, not the
  headline elite, unless the lower-HPWL result fails legality, artifact gates, or
  the hard timeout budget.
  The runtime term has a deadband: runtime improvements and <=1.10x
  runtime noise receive no bonus; 2x runtime needs 1.0 percentage point of
  reference-normalized final-HPWL gain to break even.
- stage metrics: report `HPWLg`, `delta HPWLlg`, `delta HPWLip`,
  `delta HPWL final`, and final HPWL when available
- research belief: clean canonical HPWL at least 5% below the OpenROAD DPL
  default-flow reference is achievable; 5% is not a hard gate and not a ceiling
- algorithmic prior: global/differential guidance followed by source-level
  detailed repair should be able to outperform pure greedy legalization when
  the handoff and refinement are implemented correctly; weak final HPWL should
  trigger handoff/improve-placement diagnosis, not immediate abandonment of the
  global route
- hybrid-source prior: useful hybrids are staged algorithms inside one
  candidate implementation, such as lightweight global guidance, native legal
  closure, local HPWL repair, and a DPO consumer.  Do not implement hybrid as a
  case-level selector among complete legalizers.
- per-round stance: preserve best donors as guardrails, but assign at least one
  route that can attack a larger HPWL source when wins are tiny or plateaued
- callable flow: `detailed_placement_evolve -> improve_placement_evolve ->
  optimize_mirroring_evolve`
- editable patch surface: source-level detailed placement/legalization and
  improve placement, including their internal flow, candidate generation,
  objective, parameterization, state, and handoff
- locked surface: external evaluator/ORFS/workspace helper scripts; downstream
  optimize-mirroring code stays evaluation-only unless a future task reopens it
- parameter search is allowed only as source-level implementation work: change
  constants, heuristic thresholds, scoring weights, pass schedules,
  data-dependent policies, or small internal config structs inside
  `private_dpl_evolve_source`, then rebuild and evaluate the binary. Do not
  route parameter tuning through Tcl command options, ORFS flow scripts,
  evaluator scripts, or repeated external endpoint invocation.
- final HPWL is judged as legalization/improve-placement interaction; useful
  routes should create legal states that improve placement can consume
- route emphasis can be `legalizer-emphasis`, `DPO-emphasis`, or
  `co-optimization-emphasis`. This is not a mutually exclusive permission to
  ignore other stages. Student should inspect legalization, improve placement,
  and handoff together, and should improve multiple stages when the source
  evidence supports high-quality changes. The emphasis only names the primary
  HPWL source for the round.

## Runtime And Performance

- report runtime for the full evaluated flow above; do not call it pure
  algorithm-internal time
- the generated runner kills only the OpenROAD flow at
  `${student_runtime_multiplier}x` the canonical `openroad_dpl_flow`
  `metrics.json:runtime_seconds`; metrics/evaluator collection is not
  timeout-wrapped
- runtime is a usable `${student_runtime_multiplier}x` hard budget, not the
  objective. Spend it on
  bounded stronger mechanisms: deeper legalizer scoring, broader capped
  candidates, donor hybridization, parallel candidate evaluation, or better
  legalizer/improve handoff. Do not waste it on repeated unchanged passes.
- `bounded` means complexity-controlled and measurable, not small-scope; use
  caps, caches, thread-local scoring, and deterministic reductions to make
  larger searches practical
- runtime tiers: `fast` preserves a donor, `explore` spends moderate extra
  time on bounded search, and `aggressive` spends larger timeout-safe budget on
  a mechanism that could materially change final HPWL
- larger scans, repeated endpoint-like subpasses, and randomized perturbations
  are allowed only as controlled source mechanisms with scope, counters,
  early-stop or gain-rate evidence, and full-flow metrics; prefer
  handoff/frontier-guided targeting over blind random search
- high-performance exploration may use OpenMP, thread-local scratch buffers,
  cached touched data, and deterministic reductions for independent probes

## Donors And Starts

- compare `openroad_dpl_flow`, `openroad_dpl_negotiation`, and
  `evolve_default` together; all three are legitimate evidence and
  donor/start-point choices
- evolved donor seeds are materialized as prepared start branches:
  `evolved_diamond`, `evolved_legalm`, and `evolved_negotiation`
- prior evidence makes `evolved_legalm` a strong first-round route on dense
  high-utilization standard-cell cases with large legalization HPWL inflation;
  still test Diamond and negotiation families when stage evidence supports them
- Student private source trees use materialized seed sources and prepared git
  start branches. Student start-point switches are branch-only.

## DPO / Improve-Placement Mechanisms

- Improve-placement work should be implemented in the current source, especially
  `Optdp`/`Detailed*` candidate generation, objective, acceptance, transaction,
  local state, and handoff consumption.
- Useful mechanisms include source-edge cached scoring, bounded top-K exact
  candidate evaluation, transaction accept/rollback, bounded staged descent,
  and scoped LSMC basin escape.
- Scoped LSMC and staged descent can find better HPWL basins but are heavy. Use
  compact candidate sets, exact affected-net scoring, cached touched data,
  producer/consumer counters, and runtime/gain telemetry.
- Handoff state should stay OpenROAD-native and compact. Use
  `odb::dbInst*`, `odb::dbNet*`, `odb::dbGroup*`, `odb::dbRegion*`, dense ids,
  vectors, bitsets, and current detailed-placement mappings. Do not duplicate
  current coordinates or route hot state through files, logs, JSON, string-keyed
  hot maps, or public Tcl/SWIG ABI changes.

## Execution Context

- ordinary Student skills: `skills/patch_rules.md`,
  `skills/source_git_workflow.md`, `skills/build_openroad.md`,
  `skills/evaluate_run.md`, and `skills/trace_logging.md` when counters/logs
  are needed
- algorithm cards under `$algorithm_cards_dir` provide pseudocode and liveness
  contracts for the selected mechanism family; Students should read only the
  relevant card after Teacher names the stage/mechanism
- generated Student workspace scripts own prepare/build/evaluate/commit/diff
  commands; Teacher should not ask Students to reconstruct CMake, relink,
  evaluator, git, or diff commands
- this packet is self-contained. Do not open `~/.codex/memories`, rollout
  summaries, child event logs, or session archives during planning. Use this
  packet, listed knowledge/insight files, peer-learning packet, canonical
  metrics, and targeted source handles.

## Design Characteristics

$design_characteristics

Detailed packet: `$design_characteristics_path`

## Baseline Evidence

$metric_table

## Start Seed Calibration

- start-kind donor calibration packet: `$start_seed_calibration_path`
- If this packet contains rows, Teacher should use it as initial source-level
  donor evidence before assigning Student routes.  Compare `framework`,
  `evolved_diamond`, `evolved_legalm`, and `evolved_negotiation` stage-wise
  results, but do not treat the best initial seed as the only exploration
  parent.  A stage donor can still be useful when its final HPWL is not best.

## Scoreboard

$scoreboard

## Elite Continuation

$elite_text

## Packets

- baseline artifacts: `$baseline_artifacts_path`
- start seed calibration: `$start_seed_calibration_path`
- peer learning: `$peer_learning_path`

## Prior Context

$prior_context

## Teacher Boundary

- output insight and per-student plans only
- do not ask students to chase optional reports that may not exist
- do not include memory citations, shell/build/eval/git command blocks, or long
  file inventories; the Student workspace packet owns execution procedure
