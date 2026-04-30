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
5. `case_evolution/micro_gain_trap_and_elite_donors.md`
6. Relevant LEGALM card under `legalm/` only when changing legalization.

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
- `case_evolution/micro_gain_trap_and_elite_donors.md`: why tiny HPWL wins are
  donors, not proof of a strategic algorithmic improvement.
- `case_evolution/full_flow_timeout_and_target_selection.md`: full-flow timeout
  and discovery-target selection policy.

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
