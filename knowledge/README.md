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
8. `insights/dpo/source_level_mechanisms.md` when planning improve-placement
   source mechanisms
9. `insights/dpo/openroad_native_handoff.md` when passing legalization
   frontier state into improve placement
10. `skills/legalization/differential_guidance_stop_target.md` when using
   LEGALM/differential guidance as a seed/frontier instead of a full legalizer
11. one relevant file under `algorithm_cards/` or `insights/`
12. paper PDFs and source notes under `reference/` only if needed

Current compact algorithm cards:

- `CONTEXT_AUDIT.md`
- `EVIDENCE_POLICY.md`
- `insights/README.md`
- `insights/workflow/teacher_child_case_evolution.md`
- `insights/workflow/cross_case_experiment_design.md`
- `insights/workflow/metric_contract.md`
- `insights/case_evolution/cross_case_transfer_matrix.md`
- `insights/case_evolution/score_based_case_strategy_routing.md`
- `insights/case_evolution/strategy_inspiration_by_design_feature.md`
- `insights/case_evolution/micro_gain_trap_and_elite_donors.md`
- `insights/case_evolution/full_flow_timeout_and_target_selection.md`
- `insights/dpo/source_level_mechanisms.md`
- `insights/dpo/openroad_native_handoff.md`
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

For `evolved_negotiation`, verify the negotiation-primary route signal before
using it as a donor.  The intended mechanism is resource-allocation/conflict
resolution; full LEGALM legalization must not be the successful primary path
inside this start kind.

Differential/LEGALM-style guidance can still be valuable in a non-LEGALM route
when it stops early and produces a bounded seed/frontier for the downstream
legalizer or DPO consumer.  Treat the guidance objective, stop point, handoff
payload, and consumer as mechanism-level search variables, then promote only by
full-flow final HPWL, legality, displacement, and runtime evidence.

## Legalizer Algorithm Flow Review

- `knowledge/insights/legalization/legalizer_algorithm_flow_review.md`: mandatory review card for path-pure legalizer evolution. Teacher and Student should consult it before planning LEGALM, NEGOTIATION, or DIAMOND iterations and cite the mapped paper/card idea in reports.

## Paper-to-Pseudocode Cards

- `algorithm_cards/legalization_paper_pseudocode.md`: compatibility index for legalization paper mechanisms.  The implementation-ready cards are split under `algorithm_cards/legalization/`.
- `algorithm_cards/dpo_paper_pseudocode.md`: compatibility index for DPO/refinement paper mechanisms.  The implementation-ready cards are split under `algorithm_cards/dpo_refinement/`.
- `algorithm_cards/context/`: background cards for OpenROAD DPL, LEGALM, NBLG, and DREAMPlace/Abacus references.  These are context, not direct fallback instructions.
- `reference/papers/researched_paper_index.md`: source handles and the correction that the OpenDP-named committed reference is a fence-region-aware mixed-height legalization paper, not OpenROAD OpenDP engine documentation.

Teacher should cite one of these cards when giving mechanism-level legalizer or DPO guidance. Student should copy the relevant pseudo code into its plan and state which counters prove liveness.
