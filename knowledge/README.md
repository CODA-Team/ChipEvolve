# Knowledge Base

This folder is the working knowledge base for `dpl_evolve`.

It is meant to support three things:

- bounded patch design
- family-level experiment tracking
- case-aware interpretation of `metrics.json`

## Current high-value entry points

- [`algorithm_cards/base_family_cards.yaml`](./algorithm_cards/base_family_cards.yaml)
  Compact first-read cards for robust base-family selection, scale rules, and
  next evolve directions. Prefer this before long replay logs.
- [`algorithm_cards/algobank50_findings_20260425.yaml`](./algorithm_cards/algobank50_findings_20260425.yaml)
  Structured evidence from the 50-way Nangate45 algorithm matrix. Read this
  before proposing a new negotiation, net-aware, priority, or localized-polish
  variant; it records which mechanisms helped and which repeatedly failed.
- [`algorithm_cards/netaware_objective_card.yaml`](./algorithm_cards/netaware_objective_card.yaml)
  Current net-aware repair status, why `netaware12` is usable evidence but not
  a hard base, and the next `netaware14` mechanism direction.
- [`algorithm_cards/legalm_engine_card.yaml`](./algorithm_cards/legalm_engine_card.yaml)
  LEGALM legality-repair evidence and the next structural row-segment
  assignment direction. Read before touching LEGALM.
- [`algorithm_cards/priority_localized_card.yaml`](./algorithm_cards/priority_localized_card.yaml)
  Priority/localized status: priority requires real stuck telemetry;
  localized swap is opt-in polish after a legal parent only.
- [`../family_robustness/ROBUST_BASE_DECISION_20260425.md`](../family_robustness/ROBUST_BASE_DECISION_20260425.md)
  Compact first-read decision note for robust base-family selection and scale
  rules. Prefer this before long replay logs.
- [`family_components/effective_families.yaml`](./family_components/effective_families.yaml)
  Effective-only summary of the current reusable starts, donor-only families,
  and noise to ignore.
- [`family_components/initial_patch_paths.yaml`](./family_components/initial_patch_paths.yaml)
  The current initial evolve paths to consider after a baseline run.
- [`stage_context/detail_place_stack.yaml`](./stage_context/detail_place_stack.yaml)
  Current ORFS/OpenROAD placement-stage context.
- [`delta_ledger/nblg_to_openroad.yaml`](./delta_ledger/nblg_to_openroad.yaml)
  Primary mapping from NBLG concepts to the current negotiation engine.
- [`delta_ledger/legalm_to_openroad.yaml`](./delta_ledger/legalm_to_openroad.yaml)
  Secondary mapping for overflow modeling, escape, and refinement ideas.
- [`replay_bank/family_registry.yaml`](./replay_bank/family_registry.yaml)
  Structured registry of active, superseded, and stackable patch families.
- [`../baseline/canonical_lines.yaml`](../baseline/canonical_lines.yaml)
  The canonical baseline/evolve lines. Read this before reasoning about wrappers.
- [`family_components/legalm_engine.yaml`](./family_components/legalm_engine.yaml)
  Active description of the `LEGALM` family variant and how to use it.
- [`replay_bank/README.md`](./replay_bank/README.md)
  Human-readable replay bank index and observation notes.

## Directory guide

- `algorithm_cards/`
  Background algorithm cards and stage-12 seed material.
- `code_atlas/`
  File/function/runtime switch maps for the repo.
- `delta_ledger/`
  Paper-to-implementation deltas and idea donors.
- `design_profiles/`
  Case-aware objective priorities and regime hints.
- `failure_taxonomy/`
  Common failure modes and recovery directions.
- `family_components/`
  Reusable long-term algorithm components and stack recipes.
- `../family_variants/`
  Materialized-family manifests and family-specific `dpl_evolve` patch assets.
- `accepted_patches/`
  Saved patch artifacts for promising or promoted families.
- `mutation_playbooks/`
  Family-oriented patch ideas.
- `packets/`
  Current compact context for the agent plus packet templates.
- `replay_bank/`
  The most important current experiment memory.
- `seam_design/`
  Candidate patch seams and runtime-safe refactor surfaces.
- `stage_context/`
  True flow context for strict vs reduced-flow interpretation.
- `symbol_cards/`
  Symbol-level patch guidance.

## Recommended reading order

1. `../README.md`
2. `../AGENTS.md`
3. `stage_context/detail_place_stack.yaml`
4. `delta_ledger/nblg_to_openroad.yaml`
5. `delta_ledger/legalm_to_openroad.yaml`
6. `../baseline/canonical_lines.yaml`
7. `algorithm_cards/base_family_cards.yaml`
8. `algorithm_cards/algobank50_findings_20260425.yaml`
9. family-specific cards under `algorithm_cards/*_card.yaml` when assigned to
   that family
10. `family_components/effective_families.yaml`
11. `family_components/initial_patch_paths.yaml`
12. `family_components/legalm_engine.yaml`
13. `replay_bank/family_registry.yaml`
14. `packets/current_run_packet.md`
15. `packets/README.md`

## Background reference only

- `reference/OpenDP.pdf`
- `reference/commands.txt`

These are still useful, but they are no longer the primary entry point for day-to-day family evolution.

## Packet note

`packets/current_run_packet.md` and `packets/current_run_packet.json` are
generated files. They are the latest compact context, but not the canonical
place to make durable edits. For that distinction, see:

- `packets/README.md`
