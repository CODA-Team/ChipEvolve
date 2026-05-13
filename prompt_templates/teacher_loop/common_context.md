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
- evolved legalizer patch catalog: `$evolved_legalizers_readme`
- evolved legalizer manifest: `$evolved_legalizers_manifest`
- evolved legalizer validation: `$evolved_legalizers_validation`
- dense evolved-legalizer routing insight: `$dense_legalizer_routing_insight`
- evolved DPO patch catalog: `$evolved_dpo_readme`
- evolved DPO manifest: `$evolved_dpo_manifest`
- evolved DPO validation: `$evolved_dpo_validation`
- DPO runtime/quality insight: `$dpo_runtime_quality_insight`
- cross-legalizer DPO donor insight: `$dpo_cross_legalizer_insight`
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
- For mechanism inspiration, Teacher should query the skill index first and
  then open the smallest relevant card under `$algorithm_cards_dir`, especially
  `legalization/` for legalizer routes and `dpo_refinement/` for improve
  placement or handoff routes. Pseudocode cards are idea contracts, not fixed
  recipes.

## Objective And Boundaries

- canonical metric: `metrics.json:hpwl` from OpenROAD/DPL pin-based logs;
  ignore `hpwl_proxy` for promotion
- primary research target remains canonical HPWL reduction. Use
  `G_HR = 100 * (HPWL_ref - HPWL_sol) / HPWL_global - 2 * (sqrt(runtime_sol / runtime_ref) - 1) / (sqrt(2) - 1)`
  against the OpenROAD DPL default-flow (`openroad_dpl_flow`, Diamond-search)
  reference to judge whether the HPWL gain is worth the runtime. Higher
  `G_HR` is better and the reference is 0. Use HPWL first for research
  direction and `G_HR` as the value check; preserve strong HPWL-only donors as
  repair routes instead of discarding them.
  The runtime penalty is intentionally light: about 2x runtime needs roughly
  2 percentage points of final-HPWL gain to break even.
- stage metrics: report `HPWLg`, `delta HPWLlg`, `delta HPWLip`,
  `delta HPWL final`, and final HPWL when available
- research belief: clean canonical HPWL at least 5% below the OpenROAD DPL
  default-flow reference is achievable; 5% is not a hard gate and not a ceiling
- algorithmic prior: global/differential guidance followed by source-level
  detailed repair should be able to outperform pure greedy legalization when
  the handoff and refinement are implemented correctly; weak final HPWL should
  trigger handoff/improve-placement diagnosis, not immediate abandonment of the
  global route
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
- runtime is a usable `${student_runtime_multiplier}x`-tolerant budget and
  also part of `G_HR`. Spend it on
  bounded stronger mechanisms: deeper legalizer scoring, broader capped
  candidates, donor hybridization, parallel candidate evaluation, or better
  legalizer/improve handoff. Do not waste it on repeated unchanged passes.
- `bounded` means complexity-controlled and measurable, not small-scope; use
  caps, caches, thread-local scoring, and deterministic reductions to make
  larger searches practical
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

## DPO / Improve-Placement Donors

- evolved DPO patches under `patches/evolved_dpo/` are source-root
  improve-placement donor patches for private `dpl_evolve` trees. They are
  meant to stack on the selected legalizer seed, not replace the legalizer.
- `src_dpo_neg017b_algo1_src_cache_runtime.patch` is the recommended first
  DPO donor when both final HPWL and runtime matter. It keeps Algorithm-1
  source-edge cached scoring and bounded runtime behavior.
- `src_dpo_neg014_hybrid_quality.patch` is the quality-ceiling donor. It can
  be more expensive, but it is useful when the route intentionally spends
  bounded runtime on stronger improve-placement quality.
- Teacher should use DPO donors when the legalizer creates a useful stage
  donor but improve placement fails to preserve or consume it. Assign DPO work
  as a source-level `Optdp`/`Detailed*` mechanism, not as repeated endpoint
  execution.
- DPO patch base matters: these are private-source-root patches. Students
  should normally use prepared local branches such as
  `start/evolved_legalm_dpo_neg017b` or `start/evolved_diamond_dpo_neg014`
  when Teacher wants a clean legalizer+DPO donor start. For continuation
  sources, Students can use the generated DPO helper from the workspace packet
  with `--check-only` first. Do not make them hand-write `git apply` commands.

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
