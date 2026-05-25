# Insights Index

This directory stores compact lessons that guide DPL-Evolve agents. Insight
cards are not equal. The routing contract below is the source of truth for what
can directly steer Teacher route assignment.

## Routing Contract

- Direct case-type route mapping uses only:
  - `case_evolution/case_type_quality_mechanism_priority.md`
  - `case_evolution/mechanism_reconstruction_roadmap.md`
  - the generated `matched_blueprint_packet.md`, which is filtered from those
    two files for the current case.
- Other files are inspiration, support, evidence archives, or workflow contracts.
  They can refine a selected blueprint, explain a failure mode, or provide a
  source-level mechanism, but they must not override the core blueprint map.
- Similar ideas should be treated as one mechanism family in the core roadmap:
  source-edge exact DPO, hot-segment exact consumer, row-window/component replay,
  top-net target/source repair, recoverable producer/consumer handoff,
  transactional basin escape, negotiation residual handoff, row-local exact
  closure, conflict-primary closure, and plateau redesign.
- Teacher should classify the current case by concrete features: size/runtime,
  utilization, legalization HPWL movement, DPO recovery, true macro/SRAM or
  large-blockage geometry, row fragmentation, live counters, and final HPWL.
  Benchmark names, old program ids, and raw result rows are not route selectors.
- Student should read only the assigned blueprint section or focused packet,
  then inspect current source/log evidence and implement a coherent mechanism.

## Reading Order

1. `workflow/metric_contract.md` for metric truth when reporting or comparing.
2. `workflow/teacher_child_case_evolution.md` for Teacher/Student loop rules.
3. `case_evolution/case_type_quality_mechanism_priority.md` for first route map.
4. `case_evolution/mechanism_reconstruction_roadmap.md` only for the selected
   blueprint, preferably through generated `matched_blueprint_packet.md`.
5. One relevant DPO, legalization, LEGALM, or case-evolution support card only
   after current evidence identifies the needed mechanism detail.

## File Roles

| file | role | direct route selector? |
| --- | --- | --- |
| `case_evolution/case_type_quality_mechanism_priority.md` | Core case-feature to blueprint map | yes |
| `case_evolution/mechanism_reconstruction_roadmap.md` | Core selected-blueprint implementation roadmap | yes, after blueprint selection |
| `case_evolution/cutrow_adversarial_legalization.md` | cutRow stress evidence and adversarial legality inspiration | no |
| `case_evolution/dense_evolved_legalizer_routing.md` | Dense legalizer producer inspiration and caution | no |
| `case_evolution/evidence_weighted_mechanism_priority.md` | Mechanism evidence/risk weighting after core route selection | no |
| `case_evolution/fixed_source_replay_transfer_evidence.md` | Transfer evidence archive and robustness lessons | no |
| `case_evolution/full_flow_timeout_and_target_selection.md` | Runtime/timeout policy and target-selection context | no |
| `case_evolution/micro_gain_trap_and_elite_donors.md` | Weak-gain/guard trap diagnosis | no |
| `case_evolution/optdp_stage_cooptimization.md` | Improve-placement/legalizer handoff mechanism notes | no |
| `case_evolution/runtime_light_final_hpwl_mechanism_priority.md` | Runtime-cost refinement after route choice | no |
| `case_evolution/score_based_case_strategy_routing.md` | G_HR and score interpretation, not HPWL promotion | no |
| `case_evolution/strategy_inspiration_by_design_feature.md` | Feature-to-mechanism inspiration after core classification | no |
| `dpo/aggressive_basin_schedule.md` | DPO runtime-spend support for a selected DPO route | no |
| `dpo/exact_source_edge_recoverability_consumer.md` | Exact source-edge DPO mechanism support | no |
| `dpo/frontier_guided_basin_consumer.md` | Frontier-to-DPO consumer support | no |
| `dpo/lightweight_post_dpo_basin.md` | Light post-DPO basin repair support | no |
| `dpo/openroad_native_handoff.md` | Native handoff data-structure support | no |
| `dpo/source_level_mechanisms.md` | Improve-placement source mechanism vocabulary | no |
| `legalization/algorithm_role_liveness_basics.md` | Legalizer role/liveness support | no |
| `legalization/legalizer_algorithm_flow_review.md` | Legalizer flow review support | no |
| `legalm/legalm_large_case_runtime.md` | LEGALM runtime support | no |
| `legalm/legalm_paper_cost_tuning.md` | LEGALM paper-cost tuning reference | no |
| `legalm/legalm_self_legal_closure.md` | LEGALM self-legal closure reference | no |
| `legalm/paper_code_alignment.md` | LEGALM paper/code alignment reference | no |
| `legalm/paper_faithful_legalization_integration.md` | LEGALM paper-faithful integration reference | no |
| `legalm/search_space_and_hpwl_objective.md` | LEGALM search-space support | no |
| `workflow/cross_case_experiment_design.md` | Cross-case experiment design workflow | no |
| `workflow/metric_contract.md` | Canonical metric contract | no |
| `workflow/teacher_child_case_evolution.md` | Teacher/Student workflow and evidence discipline | no |

## Hygiene Rules

- Do not add local experiment paths, run-state paths, old program ids, or raw
  benchmark result rows to default insights. Translate them into feature,
  mechanism, liveness signal, and failure-mode language.
- Keep route logic in the two core case-evolution files. If a support card
  repeats a route idea, collapse the route into the core blueprint and leave the
  support card as background evidence.
- Mark observations as evidence, hypothesis, or policy. Do not write measured
  results as universal rules.
- Prefer one concise card per support theme. If a card grows into a run log,
  move raw detail to an external archive and keep only the reusable lesson here.
