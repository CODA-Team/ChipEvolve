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
- focused matched blueprint packet: `$matched_blueprint_packet`
- secondary inspiration only, not direct route maps:
  - dense evolved-legalizer note: `$dense_legalizer_routing_insight`
  - feature-to-mechanism strategy note: `$strategy_inspiration_insight`
- DPO mechanism insight: `$dpo_source_mechanisms_insight`
- OpenROAD-native handoff insight: `$openroad_native_handoff_insight`
- LEGO-lite skill index: `$skill_index`
- LEGO-lite skill query helper: `$skill_query_script`
- LEGO-lite skill notes: `$skill_cards_dir`
- algorithm/pseudocode cards: `$algorithm_cards_dir`
- Teacher coaching skill: `$teacher_coaching_skill`

Use these paths as search handles only when they help identify concrete
function/state insertion points. Do not require broad donor-tree reading.

Only the focused matched blueprint packet is the direct case-feature route map.
It is generated from `case_type_quality_mechanism_priority.md` and
`mechanism_reconstruction_roadmap.md`. Other insight files are support material:
use them only after a blueprint or bottleneck is selected, and never as a
parallel route selector.

## First-Round Evidence-Driven Route Scan

In the first Teacher planning round, build the route map from observed case
evidence first. Most knowledge cards are vocabulary, inspiration, and prior
evidence. The focused matched blueprint packet is different: it is the first
case-feature route map filtered for this case. If it contains a matching
blueprint, use that blueprint as the route prior, use the included roadmap
section for implementation details, then diversify only through compatible
mechanism variants or a clearly justified alternative blueprint.

- Read the design characteristics and stage metrics first.
- First reaction: decide whether this case matches one or more known case types
  with verified mechanism chains. Base that classification on concrete case
  features: size/runtime scale, density/utilization, legalization HPWL movement,
  DPO/improve-placement recovery, true macro/SRAM/large-blockage/hierarchy or
  row-fragmentation evidence, and live source-level counters. Fixed instance
  count alone is not macro evidence; macro means a physically large instance.
  If yes, assign Students across the matching packets or compatible
  combinations, then use the remaining Students for complementary or
  exploratory routes.
- After naming the dominant bottleneck, query the skill index only to sharpen
  the selected blueprint, check a known failure mode, or diagnose low ROI. Do
  not query broad secondary cards to replace the blueprint map.
- When selecting a feature-matched start kind or route, open the focused
  matched blueprint packet first. If it contains a matching blueprint, assign
  at least one Student to reconstruct or strengthen the route with the included
  implementation order, source handles, liveness counters, and
  partial-implementation failure tests; use strategy cards and algorithm cards
  only to refine the mechanism or check risk.
- Short route digest for first-round matching:
  large row-rich or datapath-like recoverable basin with strong improve-stage
  recovery, nontrivial default runtime, and final HPWL dominated by DPO accepts
  rather than legalize-only HPWL -> assign one cumulative producer/closure/DPO
  chain before pure local-consumer routes.  The producer may be the current
  Diamond basin, negotiation/resource closure, or framework guidance only when
  stage evidence supports it.  The strong route is the complete chain:
  recoverable producer or stable basin -> exact source-edge/global-swap
  consumer -> edge-critical or selected-segment reorder -> bounded
  post-reorder exact/pair/endpoint polish.
  low-util or Diamond-stable local residue with large improve-stage
  recoverability -> assign one complete Diamond-basin source-edge exact descent
  route: preserve a Diamond-compatible legal basin, force the enhanced DPO path,
  and implement the `DetailedGlobalSwap` exact source-edge kernel described in
  the focused matched blueprint packet or mechanism reconstruction roadmap:
  bounded source-edge target generation,
  exact move/swap scoring with `DetailedHPWL::delta`, replay through
  journal/rollback, and source-edge
  cells/locations/exact-scores/replays/commits/rejects counters.
  Diamond-native frontier records alone do not count as this route; dense
  recoverable pressure -> recoverable producer plus hot-segment/exact DPO
  consumer; large row-rich recoverable basin -> producer/handoff plus exact DPO
  or row-window transactions; high-utilization with large legalizer inflation
  and incomplete DPO recovery -> include one high-impact-net target/source
  repair plus bounded mirror-dependency hybrid route. Mirror work is valid there
  only as the final step of a producer/DPO/critical-net chain, not as a
  standalone route.
- When dense recoverable pressure and large row-rich recoverability both match,
  and negotiation-style evidence shows strong DPO recovery but poor final
  closure, assign one Student to the cumulative stack from the focused
  blueprint packet or mechanism roadmap: recoverable producer or
  negotiation-compatible legal closure -> exact source-edge/global-swap
  consumer -> edge-critical/selected reorder -> bounded post-reorder
  exact/pair/endpoint polish. Use framework guidance only when it creates a
  consumed payload; do not assume it is the primary route.
- For a strong retained route, route from the cumulative mechanism chain. Do not
  assign only the final preservation, telemetry, or attribution diff as if it
  were the quality mechanism.
- Open the smallest useful algorithm/pseudocode card only when it provides a
  concrete mechanism, liveness counter, or failure mode relevant to the observed
  bottleneck.
- Classify donors as either `general donor` or `feature-matched donor`.
  General donors are safe regression guards or broadly useful kernels.
  Feature-matched donors are hypotheses tied to design features such as dense
  row pressure, low-util slack, fragmented rows, macro/edge pressure, high
  conflict pressure, or weak DPO recoverability.
- Assign the first-round Students across distinct route families. Do not put
  every Student on the current start seed or the same donor-polish path unless
  the evidence leaves no other credible mechanism.
- The objective is extreme per-case HPWL optimization under the runtime gate.
  Universal transferability is useful evidence, but it is not required for a
  case-specific winner.

## LEGO-lite Skill Lookup

- Use the skill index as a targeted evidence database after the stage metrics
  and logs identify a bottleneck. Do not choose a route just because a card
  exists.
- Fast command pattern:
  `python3 $skill_query_script --stage <stage> --q "<bottleneck or mechanism>"`
- Stage names: `case_diagnosis`, `start_selection`, `legalization`,
  `improve_placement`, `handoff`, `build_eval_log_diagnosis`, and
  `teacher_review`.
- A selected skill is guidance, not a cage. Teacher should name the skill id,
  expected stage transition, done criteria, and log signals; Student should
  adapt or reject the mechanism when current source evidence contradicts the
  card.
- Keep skill selection small: one primary mechanism skill, one auxiliary
  handoff/objective skill, and one optional diagnosis skill is the normal upper
  bound for a Student route.
- Treat strategy cards as design-feature inspiration, not case-level algorithm
  selectors.  Teacher should translate them into a staged source mechanism and
  require liveness counters rather than assigning a fixed route by name.
- When mixing Diamond, negotiation, LEGALM, or Differential Guidance, first
  query `--stage legalization --q "diamond negotiation differential guidance liveness"`
  and name the route role: primary legalizer, guidance producer,
  repair/polish stage, or handoff consumer.
- Weak-gain / over-cost escalation is a Teacher judgment, not an automatic
  controller rule.
  If current-run legal candidates show tiny HPWL movement, repeat one family,
  or incur runtime cost without proportional HPWL, do not only polish the current
  donor. Use one broader stage/mechanism query or card only to find a different
  source-level hypothesis that matches the current evidence, then give at least
  one Student a stronger within-run route. If the case-type outline has a
  matching blueprint, prefer the full mechanism chain from the focused packet
  over another same-basin threshold/queue edit. Current-run
  kept/rejected refs may be repaired with `25_trial_source.sh begin --from-ref
  <ref>`.
  Query `--stage teacher_review --q "mechanism priority telemetry grouped window exact consumer"`
  when deciding which donor families to promote, preserve as fallback, or demote.
  Query `--stage teacher_review --q "runtime light final HPWL mechanism priority"`
  before spending a route on a heavy donor.

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
- research belief: assume every case still has a plausible path to at least 5%
  clean canonical HPWL reduction versus the OpenROAD DPL default-flow
  reference. 5% is a search-ambition prior for plan scale, not a promotion gate
  and not a ceiling. If current candidates are far below that, Teacher should
  plan mechanism-level changes, not incremental polish.
- algorithmic prior: global/differential guidance followed by source-level
  detailed repair should be able to outperform pure greedy legalization when
  the handoff and refinement are implemented correctly; weak final HPWL should
  trigger handoff/improve-placement diagnosis, not immediate abandonment of the
  global route
- source-search prior: the Teacher may optimize branch choice, mechanism
  ordering, differential/guidance objectives, heuristic weights, stop schedules,
  internal parameters, handoff payloads, and DPO scoring/acceptance policies.
  These are source-level search variables. Use logs and stage-wise evidence to
  decide what to change; promote only by legal full-flow final HPWL.
- hybrid-source prior: useful hybrids are staged algorithms inside one
  candidate implementation, such as lightweight global guidance, native legal
  closure, local HPWL repair, and a DPO consumer.  Do not implement hybrid as a
  case-level selector among complete legalizers.
- per-round stance: preserve best donors as rollback guardrails, but do not
  route the best line as a preservation task. The best line should be
  elite-expansion: use the donor as a parent and attack a larger HPWL source.
  Assign aggressive mechanism-level routes whenever wins are tiny, plateaued,
  or far from the 5% search ambition.
- plateau escape: when recent rounds repeat a donor with tiny gains, Teacher
  should assign a `mechanism-redesign` route that changes a deeper source
  mechanism under explicit complexity caps and liveness counters
- weak-gain / over-cost escalation: when the current run is tiny-gain,
  same-family, or too heavy for the HPWL gained, preserve useful donors as
  rollback refs but route the work as elite-expansion, repair, switch,
  hybridize, or mechanism-redesign. Assign aggressive routes that change the
  legalizer/DPO composition, repair a current-run ref, or test a different
  feature-matched mechanism hypothesis derived from the observed failure mode.
  Pseudocode cards may inspire the implementation, but they are not the reason
  for the route.
- low-ROI rule: when a mechanism is verified live/correct but still gives only
  extremely small full-flow HPWL movement after a meaningful repair attempt, preserve
  it as evidence and switch to a different HPWL source instead of stacking
  micro-variants
- callable flow: `detailed_placement_evolve -> improve_placement_evolve ->
  optimize_mirroring_evolve`
- editable patch surface: source-level detailed placement/legalization and
  improve placement, including their internal flow, candidate generation,
  objective, parameterization, state, and handoff
- locked surface: external evaluator/ORFS/workspace helper scripts and the
  top-level command interfaces. Optimize mirroring must stay callable and is
  normally evaluation/control evidence; edit its internals only if Teacher
  explicitly assigns a mirror mechanism with concrete source handles.
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
  ignore adjacent-stage compatibility. Student should understand how the
  emphasized mechanism interacts with legalization, improve placement, and
  handoff, but should not make cosmetic edits across all stages. The emphasis
  names the primary HPWL source for the round.

## Runtime And Performance

- report runtime for the full evaluated flow above; do not call it pure
  algorithm-internal time
- the generated runner kills only the OpenROAD flow at
  `${student_runtime_multiplier}x` the canonical `openroad_dpl_flow`
  `metrics.json:runtime_seconds`; metrics/evaluator collection is not
  timeout-wrapped
- runtime is a `${student_runtime_multiplier}x` hard budget and constrained
  cost, not the objective. Runtime optimization is useful because it frees
  budget for more complex quality search, not because runtime itself is the
  target. Extra runtime is justified for bounded stronger mechanisms: deeper
  legalizer scoring, broader capped candidates, donor hybridization, parallel
  candidate evaluation, or better legalizer/improve handoff. Do not waste it on
  repeated unchanged passes.
- `bounded` means complexity-controlled and measurable, not small-scope; use
  caps, caches, thread-local scoring, and deterministic reductions to make
  larger searches practical
- runtime tiers: `fast` preserves a donor, `explore` allows moderate bounded
  cost, and `aggressive` allows larger timeout-safe cost only for a mechanism
  that could materially change final HPWL
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
- donor taxonomy: distinguish `general donor` from `feature-matched donor` in
  Teacher output. A general donor is reusable across many cases or works as a
  rollback fallback. A feature-matched donor is plausible because the current
  design has matching stage/physical features; it can be aggressively optimized
  for this case even if it may not transfer universally.
- prepared start branches include `framework`, `diamond`,
  `default_negotiation`, `evolved_diamond`, and `evolved_negotiation`
- `framework` contains the current LEGALM-style producer/frontier base plus
  bounded DPO handoff support. Treat it as a normal editable source parent, not
  as proof that legalization-only changes are sufficient.
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
  `evolved_diamond`, and `evolved_negotiation` stage-wise
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
