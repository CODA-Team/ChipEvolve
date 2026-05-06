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
- Diamond reference baseline: `$openroad_diamond`
- negotiation donor: `$openroad_negotiation_nblg`
- Abacus donor: `$dreamplace_abacus`
- evolved legalizer patch catalog: `$evolved_legalizers_readme`
- evolved legalizer manifest: `$evolved_legalizers_manifest`
- evolved legalizer validation: `$evolved_legalizers_validation`
- dense evolved-legalizer routing insight: `$dense_legalizer_routing_insight`
- Teacher coaching skill: `$teacher_coaching_skill`

Use these paths as search handles only when they help identify concrete
function/state insertion points. Do not require broad donor-tree reading.

## Objective And Boundaries

- canonical metric: `metrics.json:hpwl` from OpenROAD/DPL pin-based logs;
  ignore `hpwl_proxy` for promotion
- stage metrics: report `HPWLg`, `delta HPWLlg`, `delta HPWLip`,
  `delta HPWL final`, and final HPWL when available
- research belief: clean canonical HPWL at least 5% below the best clean line is
  achievable; 5% is not a hard gate and not a ceiling
- per-round stance: preserve best donors as guardrails, but assign at least one
  route that can attack a larger HPWL source when wins are tiny or plateaued
- callable flow: `detailed_placement_evolve -> improve_placement_evolve ->
  optimize_mirroring_evolve`
- editable patch surface: source-level detailed placement/legalization and
  improve placement, including their internal flow, candidate generation,
  objective, parameterization, state, and handoff
- locked surface: external evaluator/ORFS/workspace helper scripts; downstream
  optimize-mirroring code stays evaluation-only unless a future task reopens it
- final HPWL is judged as legalization/improve-placement interaction; useful
  routes should create legal states that improve placement can consume

## Runtime And Performance

- report runtime for the full evaluated flow above; do not call it pure
  algorithm-internal time
- the generated runner kills only the OpenROAD flow at
  `${student_runtime_multiplier}x` the canonical `openroad_dpl_flow`
  `metrics.json:runtime_seconds`; metrics/evaluator collection is not
  timeout-wrapped
- runtime is usable budget, not a penalty. Spend it on bounded stronger
  mechanisms: deeper legalizer scoring, broader capped candidates, donor
  hybridization, parallel candidate evaluation, or better legalizer/improve
  handoff
- runtime tiers: `fast` preserves a donor, `explore` spends moderate extra
  time on bounded search, and `aggressive` spends larger timeout-safe budget on
  a mechanism that could materially change final HPWL
- do not buy quality through endpoint stacking, repeated random tails, broad
  rescans, or repeated unchanged improve-placement runs
- high-performance exploration may use OpenMP, thread-local scratch buffers,
  cached touched data, and deterministic reductions for independent probes

## Donors And Starts

- compare `openroad_dpl_flow`, `openroad_dpl_negotiation`, and
  `evolve_default` together; all three are legitimate evidence and
  donor/start-point choices
- evolved legalizers under `patches/evolved_legalizers/` are active donor
  starts, not stale backups: `evolved_diamond`, `evolved_legalm`, and
  `evolved_negotiation`
- prior evidence makes `evolved_legalm` a strong first-round route on dense
  high-utilization standard-cell cases with large legalization HPWL inflation;
  still test Diamond and negotiation families when stage evidence supports them
- patch base matters: `*_from_clean.patch` applies to the clean OpenROAD anchor
  in `metadata/anchors.json`; `*_framework_delta.patch` applies only after the
  base/framework patches
- Student private source trees are normally materialized seed sources; do not
  make Students manually apply OpenROAD-root patches unless that is the route

## Execution Context

- ordinary Student skills: `skills/patch_rules.md`,
  `skills/source_git_workflow.md`, `skills/build_openroad.md`,
  `skills/evaluate_run.md`, and `skills/trace_logging.md` when counters/logs
  are needed
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

## Scoreboard

$scoreboard

## Elite Continuation

$elite_text

## Packets

- baseline artifacts: `$baseline_artifacts_path`
- peer learning: `$peer_learning_path`

## Prior Context

$prior_context

## Teacher Boundary

- output insight and per-student plans only
- do not ask students to chase optional reports that may not exist
- do not include memory citations, shell/build/eval/git command blocks, or long
  file inventories; the Student workspace packet owns execution procedure
