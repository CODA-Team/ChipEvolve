# Knowledge Base

This directory now contains only compact paper and algorithm reference material
for the constrained `detailed_placement_evolve` framework.

Default reading order:

1. `../README.md`
2. `../AGENTS.md`
3. `EVIDENCE_POLICY.md`
4. `../baseline/canonical_lines.yaml`
5. `../family_variants/REFERENCE_INDEX.yaml`
6. one relevant file under `algorithm_cards/`
7. paper PDFs and source notes under `reference/` only if needed

Current compact algorithm cards:

- `CONTEXT_AUDIT.md`
- `EVIDENCE_POLICY.md`
- `insights/README.md`
- `insights/workflow/teacher_child_case_evolution.md`
- `insights/workflow/cross_case_experiment_design.md`
- `insights/workflow/metric_contract.md`
- `insights/case_evolution/cross_case_transfer_matrix.md`
- `insights/case_evolution/micro_gain_trap_and_elite_donors.md`
- `insights/case_evolution/full_flow_timeout_and_target_selection.md`
- `insights/legalm/paper_faithful_legalization_integration.md`
- `insights/legalm/legalm_self_legal_closure.md`
- `insights/legalm/legalm_paper_cost_tuning.md`
- `insights/legalm/legalm_large_case_runtime.md`
- `algorithm_cards/openroad_dpl.md`
- `algorithm_cards/nblg.md`
- `algorithm_cards/legalm2.md`
- `algorithm_cards/dreamplace_abacus.md`

The previous family-tree knowledge base is not part of default tracked context.
Do not broad-read external archives during normal framework patching.  They are
useful only when a task explicitly asks for old algobank or family-evidence
forensics.

Knowledge cards are not all equal. Use `EVIDENCE_POLICY.md` to distinguish
hard contracts from measured observations, working hypotheses, and reference
donors.  Use `insights/README.md` to pick only the insight cards relevant to
the current task.
