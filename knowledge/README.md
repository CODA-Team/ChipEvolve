# Knowledge Base

This directory now contains only compact paper and algorithm reference material
for the constrained `detailed_placement_evolve` framework.

Default reading order:

1. `../README.md`
2. `../AGENTS.md`
3. `EVIDENCE_POLICY.md`
4. `../baseline/canonical_lines.yaml`
5. `../family_variants/REFERENCE_INDEX.yaml`
6. `index/skill_cards.jsonl` through `../scripts/query_knowledge.py` when selecting stage mechanisms
7. `insights/case_evolution/strategy_inspiration_by_design_feature.md` when
   translating design features into mechanism inspiration
8. `insights/case_evolution/runtime_light_final_hpwl_mechanism_priority.md`
   when choosing final-HPWL-proven mechanisms with runtime kept as a visible
   cost
9. `insights/case_evolution/evidence_weighted_mechanism_priority.md` when
   choosing which prior mechanism families deserve active search budget
10. `insights/case_evolution/case_type_quality_mechanism_priority.md` when
   mapping current case features to blueprint route choices without turning old
   programs into benchmark-name rules
11. `insights/case_evolution/mechanism_reconstruction_roadmap.md` after a
   case-type blueprint is selected and Teacher needs source anchors, counters,
   and implementation order for Student guidance
12. `insights/dpo/source_level_mechanisms.md` when planning improve-placement
   source mechanisms
13. `insights/dpo/exact_source_edge_recoverability_consumer.md` when a legal
   but not HPWL-optimal state may have a large DPO-recoverable basin
14. `insights/dpo/openroad_native_handoff.md` when passing legalization
   frontier state into improve placement
15. `insights/dpo/lightweight_post_dpo_basin.md` when a stable legalizer still
    leaves post-DPO HPWL residue
16. `skills/case/legalizer_dpo_handoff_triage.md` when stage evidence is
   ambiguous and Teacher must decide whether to repair legalizer output,
   strengthen DPO, or improve handoff
17. `insights/dpo/frontier_guided_basin_consumer.md` when a producer frontier
    should be consumed by exact basin search
18. `insights/legalization/algorithm_role_liveness_basics.md` before routing
   Diamond, negotiation, LEGALM, or Differential Guidance families
19. `skills/legalization/differential_guidance_stop_target.md` when using
   LEGALM/differential guidance as a seed/frontier instead of a full legalizer
20. one relevant file under `algorithm_cards/` or `insights/`
21. paper PDFs and source notes under `reference/` only if needed

Current compact algorithm cards:

- `CONTEXT_AUDIT.md`
- `EVIDENCE_POLICY.md`
- `insights/README.md`
- `insights/workflow/teacher_child_case_evolution.md`
- `insights/workflow/cross_case_experiment_design.md`
- `insights/workflow/metric_contract.md`
- `insights/case_evolution/fixed_source_replay_transfer_evidence.md`
- `insights/case_evolution/score_based_case_strategy_routing.md`
- `insights/case_evolution/strategy_inspiration_by_design_feature.md`
- `insights/case_evolution/runtime_light_final_hpwl_mechanism_priority.md`
- `insights/case_evolution/evidence_weighted_mechanism_priority.md`
- `insights/case_evolution/case_type_quality_mechanism_priority.md`
- `insights/case_evolution/mechanism_reconstruction_roadmap.md`
- `insights/case_evolution/micro_gain_trap_and_elite_donors.md`
- `insights/case_evolution/full_flow_timeout_and_target_selection.md`
- `skills/case/legalizer_dpo_handoff_triage.md`
- `insights/dpo/source_level_mechanisms.md`
- `insights/dpo/exact_source_edge_recoverability_consumer.md`
- `insights/dpo/openroad_native_handoff.md`
- `insights/dpo/lightweight_post_dpo_basin.md`
- `insights/dpo/aggressive_basin_schedule.md`
- `insights/dpo/frontier_guided_basin_consumer.md`
- `insights/legalization/algorithm_role_liveness_basics.md`
- `index/skill_cards.jsonl` and `skills/README.md`
- `insights/legalm/paper_faithful_legalization_integration.md`
- `insights/legalm/legalm_self_legal_closure.md`
- `insights/legalm/legalm_paper_cost_tuning.md`
- `insights/legalm/legalm_large_case_runtime.md`
- `algorithm_cards/README.md`
- `algorithm_cards/legalization/README.md`
- `algorithm_cards/legalization/local_order_and_cluster.md`
- `algorithm_cards/legalization/resource_allocation_and_flow.md`
- `algorithm_cards/legalization/alm_and_exact_repair.md`
- `algorithm_cards/legalization/constraints_and_parallelism.md`
- `algorithm_cards/dpo_refinement/README.md`
- `algorithm_cards/dpo_refinement/classic_hpwl_descent.md`
- `algorithm_cards/dpo_refinement/incremental_and_timing.md`
- `algorithm_cards/dpo_refinement/handoff_and_runtime.md`
- `algorithm_cards/dpo_refinement/refinement_extensions.md`
- `algorithm_cards/dpo_refinement/gpu_dpo_lsmc.md`
- `algorithm_cards/context/README.md`
- `algorithm_cards/context/openroad_dpl.md`
- `algorithm_cards/context/nblg.md`
- `algorithm_cards/context/legalm2.md`
- `algorithm_cards/context/dreamplace_abacus.md`
- `skills/legalization/differential_guidance_stop_target.md`

The previous family-tree knowledge base is not part of default tracked context.
Do not broad-read external archives during normal framework patching.  They are
useful only when a task explicitly asks for old algobank or family-evidence
forensics.

Knowledge cards are not all equal. Use `EVIDENCE_POLICY.md` to distinguish
hard contracts from measured observations, working hypotheses, and reference
donors.  Use `insights/README.md` to pick only the insight cards relevant to
the current task.

Knowledge cards should describe reusable design features, failure modes, and
strategy guidance.  Do not put local experiment paths, result-table filenames,
or benchmark-specific result rows in default knowledge.  Keep those in external
experiment archives and translate only the reusable lesson back into knowledge.

Prepared evolved start branches are active donor inventory.
`evolved_diamond`, `evolved_legalm`, and `evolved_negotiation` are prior
iter30 legalizer donor seeds with measured wins on some design archetypes, not
universal defaults. Improve-placement knowledge should be expressed as
mechanism guidance: bounded source-edge scoring, exact top-K candidate
evaluation, transaction rollback, bounded staged descent, scoped LSMC basin
escape, and legalizer-to-DPO handoff consumers. Teacher should assign
those mechanisms directly in the current private source and validate them
against stage-wise evidence.

Do not give equal priority to every observed donor.  A mechanism is strong only
when the same-case final `metrics.json:hpwl` improves with clean legality and
source/log liveness.  The strongest repeated final-HPWL pattern is
legalizer-produced frontier/residual state consumed by exact DPO transactions or
grouped windows.  Stage-only legalizer wins, DPO-only tails, guard-only
preservation, telemetry-only edits, mirror-only ordering, and threshold/tie-break
polishing are lower-priority evidence unless the current stage metrics expose a
specific repair path.  See
`insights/case_evolution/runtime_light_final_hpwl_mechanism_priority.md` and
`insights/case_evolution/evidence_weighted_mechanism_priority.md`.

Use `insights/case_evolution/case_type_quality_mechanism_priority.md` when
Teacher needs a first case-type route prior.  After Teacher states the observed
stage pattern, the card suggests which prepared start kind is a good source
basin and which blueprint route to assign.  A design can match multiple
blueprints.  Dense recoverable basins should not receive only same-basin
retuning; row-local or edge-local residue favors source-edge or selected-segment
exact closure; conflict-heavy or fragmented-row layouts need primary
legalizer/resource-repair liveness; plateaued routes should change a real
producer, handoff, DPO move family, scoring objective, or transaction rule.

Use `insights/case_evolution/mechanism_reconstruction_roadmap.md` immediately
after selecting a case-type blueprint.  That file contains the detailed source
implementation order, source anchors, liveness counters, and partial-route
demotion rules needed for Student guidance.  Keep the route outline compact and
use the roadmap only for the selected blueprint, not as a broad reading task.

One high-value co-optimization pattern is a legalizer that slightly worsens
`HPWLlg` but preserves a DPO-recoverable basin, followed by exact
source-edge/global-swap consumers, edge-critical queues, selected-segment exact
reorder, and bounded post-reorder polish.  Treat this as a co-optimization
donor: the promotion evidence is clean final full-flow HPWL plus
producer/consumer liveness, not legalization-stage HPWL alone.  See
`insights/dpo/exact_source_edge_recoverability_consumer.md`.

For `evolved_negotiation`, verify the negotiation-primary route signal before
using it as a donor.  The intended mechanism is resource-allocation/conflict
resolution; full LEGALM legalization must not be the successful primary path
inside this start kind.

Differential/LEGALM-style guidance can still be valuable in a non-LEGALM route
when it stops early and produces a bounded seed/frontier for the downstream
legalizer or DPO consumer.  Treat the guidance objective, stop point, handoff
payload, and consumer as mechanism-level search variables, then promote only by
full-flow final HPWL, legality, displacement, and runtime evidence.

Use `insights/legalization/algorithm_role_liveness_basics.md` when an agent
needs to distinguish complete legalizers from heuristic producers.  In short:
Diamond and negotiation are primary legalizer families when their routes really
execute; Differential Guidance is usually a heuristic seed/frontier producer
that must be paired with a legalizer or DPO consumer and diagnosed through
producer/consumer log counters.

## Legalizer Algorithm Flow Review

- `knowledge/insights/legalization/legalizer_algorithm_flow_review.md`: mandatory review card for path-pure legalizer evolution. Teacher and Student should consult it before planning LEGALM, NEGOTIATION, or DIAMOND iterations and cite the mapped paper/card idea in reports.

## Paper-to-Pseudocode Cards

- `algorithm_cards/legalization_paper_pseudocode.md`: compatibility index for legalization paper mechanisms.  The implementation-ready cards are split under `algorithm_cards/legalization/`.
- `algorithm_cards/dpo_paper_pseudocode.md`: compatibility index for DPO/refinement paper mechanisms.  The implementation-ready cards are split under `algorithm_cards/dpo_refinement/`.
- `algorithm_cards/context/`: background cards for OpenROAD DPL, LEGALM, NBLG, and DREAMPlace/Abacus references.  These are context, not direct fallback instructions.
- `reference/papers/researched_paper_index.md`: source handles and the correction that the OpenDP-named committed reference is a fence-region-aware mixed-height legalization paper, not OpenROAD OpenDP engine documentation.

Teacher should cite one of these cards when giving mechanism-level legalizer or DPO guidance. Student should copy the relevant pseudo code into its plan and state which counters prove liveness.
