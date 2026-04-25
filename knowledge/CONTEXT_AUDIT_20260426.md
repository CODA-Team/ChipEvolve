# Context Audit 2026-04-26

This audit recalibrates the default agent context after the project pivot from
family-tree tuning to a constrained `detailed_placement_evolve` framework.

## Current Mainline

- The evolved command remains `detailed_placement_evolve`.
- The active source patch is `patches/openroad_dpl_evolve_framework.patch`.
- `EvolveLegalizer` is a stage scaffold, not a fixed final algorithm.
- The plugin fast path is intentional infrastructure for quick stage-policy
  experiments. Deeper data-structure changes should still use private relink.
- External LEGALM CPU work under
  `family_variants/reference_sources/legalm_cpu_reference/` is a reference
  implementation request, not an OpenROAD integration contract.

## Calibrated Baselines And Donors

- OpenROAD diamond is the current strict-track comparison anchor observed in
  this project. It is not a universal optimum claim.
- OpenROAD negotiation/NBLG is a repair and mechanism donor. It should not be
  promoted as the primary path without case evidence against the diamond anchor.
- LEGALM and DREAMPlace/Abacus are source and idea donors. Their objectives,
  stage order, and data structures are not fixed project requirements.
- `negotiation_parallel_frontier` is a compact historical delta to inspect and
  port selectively, not a direct apply patch.

## Default Context Hygiene

Checked default tracked context:

- `README.md`
- `AGENTS.md`
- `baseline/`
- `family_variants/`
- `knowledge/`
- `patches/`
- `plugins/`
- `adapters/science_codeevolve/`
- `scripts/`

Tracked context should contain only:

- active prepare patches,
- compact reference donors,
- current framework instructions,
- database/memory helpers,
- baseline/evaluator wrappers,
- explicit source-reference handoff packets.

Historical family matrices, raw robustness notes, and failed lineage patches
belong in ignored `local_backups/` unless a task explicitly asks for forensic
review.

## What Remains Open

These are intentionally not decided:

- exact relaxed/differentiable objective,
- whether LEGALM-style stages should run before, after, or instead of diamond,
- exact row/cluster assignment algorithm,
- exact repair trigger policy,
- final polish objective,
- case-specific routing between stage variants.

Agents should express new claims as:

- `observed`: what happened and where the metrics/logs are,
- `hypothesis`: why the behavior may have happened,
- `next_test`: the smallest experiment to validate or reject it.

Do not turn a single-case result into a global instruction.

## Local Directory Notes

Ignored local directories may exist:

- `.dpl_evolve_state/`: builds, plugin smoke outputs, variants, experiments.
- `local_backups/`: forensic material from older flows.
- `knowledge/reference/papers/pdf_cache/`: local paper PDFs for reading.

They are useful locally but should not be read by default prompt generation or
committed as source-of-truth.
