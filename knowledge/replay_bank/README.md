# Replay Bank

This folder stores concrete observations from real dpl_evolve runs.

Use it for:
- keeping successful and rejected mutation patterns tied to real cases
- recording which symbols changed and why
- avoiding repeated exploration of already-rejected directions

Each note should stay grounded in actual artifacts such as:
- evaluator JSON files under `evolve_agent/checkpoints/operations/*`
- `metrics.json` files under `flow/reports/...`
- the exact source files and functions that changed

When a direction improves HPWL/WNS/TNS but causes a large runtime increase,
the runtime tradeoff must be written down explicitly. Runtime is a first-class
gate for large-case sweeps, not a secondary note.

Current notable notes:

- `multi_case_negotiation_observations_20260422.md`
- `selective_refinement_budget_observations_20260422.md`
- `local_swap_family_observations_20260422.md`
- `legalm_engine_integration_20260422.md`

Read them only after checking `family_components/*.yaml` and
`family_registry.yaml`:

- initializer / variant-engine path:
  - `legalm_engine_integration_20260422.md`
- runtime-aware negotiation starts:
  - `multi_case_negotiation_observations_20260422.md`
  - `selective_refinement_budget_observations_20260422.md`
- stacked large-case escape work:
  - `local_swap_family_observations_20260422.md`
  - `priority_escape_family_observations_20260422.md`

Use `family_registry.yaml` first when you need a compact answer. Use the
individual observation notes only when you need deeper case-specific context.

When starting on a fresh case:

1. read the baseline `metrics.json`
2. run `scripts/recommend_initial_family.py`
3. use `family_components/initial_patch_paths.yaml` plus `family_registry.yaml`
   to choose the first reusable base rather than guessing from old notes
