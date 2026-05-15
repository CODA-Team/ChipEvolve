# Insights Index

This directory stores compact lessons that guide DPL-Evolve agents.  Keep
source-of-truth scripts and raw run artifacts outside this directory; insight
cards should summarize what changed, what was measured, and how future agents
should act on it.

## Reading Order

1. `workflow/teacher_child_case_evolution.md`
2. `workflow/cross_case_experiment_design.md`
3. `workflow/metric_contract.md`
4. `case_evolution/cross_case_transfer_matrix.md`
5. `case_evolution/strategy_inspiration_by_design_feature.md`
6. `case_evolution/score_based_case_strategy_routing.md`
7. `case_evolution/dense_evolved_legalizer_routing.md`
8. `case_evolution/optdp_stage_cooptimization.md`
9. `legalization/algorithm_role_liveness_basics.md`
10. `dpo/source_level_mechanisms.md`
11. `dpo/lightweight_post_dpo_basin.md`
12. `dpo/frontier_guided_basin_consumer.md`
13. `dpo/openroad_native_handoff.md`
14. `case_evolution/micro_gain_trap_and_elite_donors.md`
15. Relevant LEGALM card under `legalm/` only when changing legalization.

## Workflow

- `workflow/teacher_child_case_evolution.md`: Teacher/Student loop contract,
  promotion rules, peer learning, and elite preservation.
- `workflow/cross_case_experiment_design.md`: outer matrix design for testing
  one generated program across many cases and utilization points.
- `workflow/metric_contract.md`: canonical HPWL source, comparable experiment
  classes, and reporting requirements.

## Case Evolution Evidence

- `case_evolution/cross_case_transfer_matrix.md`: fixed-source transfer matrix
  synthesis across utilization classes, design scales, and technology settings.
- `case_evolution/score_based_case_strategy_routing.md`: feature-level `G_HR`
  routing guidance distilled from single-design evolution, fixed-source replay,
  and multi-design legalizer-line evaluation; use it to distinguish score
  elites from HPWL donors.
- `case_evolution/strategy_inspiration_by_design_feature.md`: feature-level
  mechanism inspiration for staged source hybrids.  Use this before route
  assignment to avoid turning empirical lessons into benchmark-name selectors.
- `case_evolution/dense_evolved_legalizer_routing.md`: dense-case evidence for
  using `evolved_legalm` as a stage-level legalizer prior, plus Teacher policy
  for first-round diversification and later route switching/hybridization.  This
  card is subordinate to current full-flow score evidence when they disagree.
- `case_evolution/optdp_stage_cooptimization.md`: useful and harmful
  mechanisms for legalization, `Optdp`, and their source-level handoff.
- `case_evolution/micro_gain_trap_and_elite_donors.md`: why tiny HPWL wins are
  donors, not proof of a strategic algorithmic improvement.
- `case_evolution/full_flow_timeout_and_target_selection.md`: full-flow timeout
  discovery-target selection, bad execution patterns, and the configured
  baseline-runtime promotion gate.

## DPO And Handoff Notes

- `dpo/source_level_mechanisms.md`: source-level improve-placement mechanisms
  to reimplement directly in current `Optdp`/`Detailed*` code.
- `dpo/lightweight_post_dpo_basin.md`: when a stable legalizer still leaves
  local DPO residue and one bounded basin cleanup pass is a good donor.
- `dpo/aggressive_basin_schedule.md`: when a validated light basin donor should
  spend more runtime under control for stronger exact local search.
- `dpo/frontier_guided_basin_consumer.md`: handoff-aware DPO consumer pattern
  that uses producer frontiers to rank and probe exact basin candidates.
- `dpo/openroad_native_handoff.md`: efficient OpenROAD-native producer/consumer
  data structures for legalization-to-DPO frontier handoff.

## Legalization Role Notes

- `legalization/algorithm_role_liveness_basics.md`: baseline roles for Diamond,
  negotiation, LEGALM-style full legalization, and Differential Guidance.  Use
  it to distinguish primary legalizers from heuristic producers and to choose
  liveness counters before implementing a route.

## LEGALM Notes

- `legalm/paper_code_alignment.md`: formula/pseudocode-to-code map for
  checking that LEGALM edits preserve the paper flow.
- `legalm/paper_faithful_legalization_integration.md`: separation between
  paper-faithful legalizer work and full-flow integration.
- `legalm/legalm_self_legal_closure.md`: LEGALM self-legal closure milestone and
  remaining quality warning.
- `legalm/legalm_paper_cost_tuning.md`: paper-detail tuning history and
  evidence.  This is a long reference, not a default prompt payload.
- `legalm/legalm_large_case_runtime.md`: large-case runtime bottleneck notes.
- `legalm/search_space_and_hpwl_objective.md`: why larger candidate stencils
  can saturate, and when to switch to bounded local HPWL-aware candidate
  scoring.

## Hygiene Rules

- Do not add dates to filenames unless the date is part of an external artifact
  id that cannot be renamed.
- Do not duplicate raw logs here.  Link or summarize artifact paths instead.
- Mark observations as evidence, hypothesis, or policy.  Do not write measured
  results as universal rules.
- Prefer one concise card per insight theme.  If a file grows into a run log,
  split it into an artifact and a summary.
