# Configs

This directory stores reusable control-plane configuration presets.

## Current files

- `codex_smoke.yaml`
  Small-budget preset for smoke loops and quick validation.
- `codex_design_specific.yaml`
  Larger-budget preset for design-level iteration.
- `mutation_contract.yaml`
  Patch-scope and safety contract for bounded evolution work.
- `run_manifest.template.yaml`
  Template for structured run metadata.
- `openroad_variant_example.yaml`
  Example showing how to point evaluation at an isolated
  `build/install/openroad` variant.

## Usage rule

Prefer configuration here over hardcoding paths or budgets into scripts.

If multiple agents need different OpenROAD binaries, use
`openroad_variant_example.yaml` as the model and keep each variant in its own
local build/install root.
