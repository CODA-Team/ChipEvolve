# Context Audit

This audit recalibrates the default agent context after the project pivot from
family-tree tuning to a constrained `detailed_placement_evolve` framework.

## Current Mainline

- The evolved command remains `detailed_placement_evolve`.
- The active source patch is `patches/openroad_dpl_evolve_framework.patch`.
- `EvolveLegalizer` is a stage scaffold, not a fixed final algorithm.
- Student experiments use private `dpl_evolve` source trees plus lightweight
  variant relink.
- The default LEGALM-style implementation reference is
  `family_variants/legalm_guidance/`.

## Calibrated Baselines And Donors

- OpenROAD DPL flow is the current strict-track comparison anchor:
  `detailed_placement`, `improve_placement`, `optimize_mirroring`.
- OpenROAD diamond remains a local-search donor and prepass reference, not a
  standalone canonical baseline runner in the current harness.
- OpenROAD negotiation/NBLG is a repair and mechanism donor. It should not be
  promoted as the primary path without case evidence against the current
  OpenROAD DPL flow anchor.
- Selected threaded-frontier mechanisms from earlier negotiation experiments
  live under
  `family_variants/openroad_negotiation_nblg/mechanism_deltas/`.
- LEGALM and DREAMPlace/Abacus are source and idea donors. Their objectives,
  stage order, and data structures are not fixed project requirements.

## Default Context Hygiene

Checked default tracked context:

- `README.md`
- `AGENTS.md`
- `baseline/`
- `family_variants/`
- `knowledge/`
- `patches/`
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
are excluded from default tracked context unless a task explicitly asks for
forensic review.

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

## Ignored Runtime Notes

Ignored runtime directories may exist:

- `.dpl_evolve_state/`: builds, variants, experiments.
- `knowledge/reference/papers/pdf_cache/`: optional paper PDFs for reading.

They are useful locally but should not be read by default prompt generation or
committed as source-of-truth.
