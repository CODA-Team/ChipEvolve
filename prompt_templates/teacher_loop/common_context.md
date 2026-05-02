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
- Teacher coaching skill: `$teacher_coaching_skill`

## Objective

- canonical metric: `metrics.json:hpwl` from OpenROAD/DPL pin-based logs
- ignore `hpwl_proxy` for promotion
- research belief: clean canonical HPWL at least 5% below the strongest clean
  canonical line is achievable, but 5% is not a hard gate and not a ceiling
- Teacher stance: assume there is real optimization space at and beyond 5%
  until the evidence proves otherwise. Explain where that space may come from
  before assigning students.
- plateau stance: when the best result repeats or only improves by a tiny
  amount, do not overfit the next round to that donor's local repair knobs.
  Keep the donor as a guardrail, but deliberately search for a new large HPWL
  source in the stage interaction, objective, candidate generator, or data
  structure.
- per-iteration target: discover mechanisms that move toward or beyond that 5%
  research target;
  compare `openroad_dpl_flow`, `openroad_dpl_negotiation`, and
  `evolve_default` together, and treat sub-1% wins as donor evidence rather
  than success
- runtime does not need to match baseline, but student evaluations are killed
  at ${student_runtime_multiplier}x the canonical `openroad_dpl_flow` baseline runtime.  Avoid unbounded
  scans and uncontrolled complexity.
- high-performance requirement: do not pursue tiny incremental wins through
  endpoint stacking, repeated random tails, or broad rescans.  Prefer bounded
  structural mechanisms that can plausibly reach or exceed the 5% research
  target.
- runtime budget is a resource to allocate, not a baseline-matching target.
  If legalization and mirror/orientation are cheap, spend the remaining
  timeout budget on one deeper bounded improve-placement mechanism with a clear
  HPWL source, cache plan, and stop condition.
- high-performance exploration may use parallel candidate evaluation, OpenMP,
  thread-local scratch buffers, and deterministic reductions when the work is
  independent and the result remains reproducible. Spend threads on deeper
  bounded search or more accurate local HPWL scoring, not on repeated unchanged
  endpoint runs.
- editable flow: `detailed_placement_evolve -> improve_placement_evolve -> optimize_mirroring_evolve`
- every valid student attempt should change legalization, improve placement,
  and mirror/orientation
- final HPWL depends on the interaction of these stages.  Useful changes should
  create, consume, and preserve stage handoff state rather than betting all
  quality on one isolated stage.
- Diamond/openroad_dpl_flow, negotiation, and evolve_default are all valid
  donor/start-point evidence. Students may explore any of them, but should
  explain the source behavior they reuse or change. Do not buy quality by
  rerunning unchanged improve placement; improve placement itself is an
  editable research stage.

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
- do not ask students to chase optional reports that may not exist; use the
  generated packets, canonical `metrics.json:hpwl`, DPL logs, and artifacts
  listed in the packets
