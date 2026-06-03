# Context Audit

This audit recalibrates the default agent context after the project pivot from
family-tree tuning to a constrained `detailed_placement_evolve` framework.

## Current Mainline

- The evolved command remains `detailed_placement_evolve`.
- The active source patch is `patches/openroad_dpl_evolve_framework.patch`.
- Prepared start branches preserve active donor/source parents:
  `framework`, `diamond`, and `default_negotiation` need case-specific
  validation.
- `EvolveLegalizer` is a stage scaffold, not a fixed final algorithm.
- Student experiments use private `dpl_evolve` source trees plus lightweight
  variant relink.
- The default LEGALM-style implementation reference is
  `family_variants/legalm_guidance/`; its code is split by stage, with
  `LegalmGuidance.cpp`, `LegalmRowAssignment.cpp`,
  `LegalmFullLegalization.cpp`, repair handoff, and pipeline composition kept
  separate.

## Calibrated Baselines And Donors

- OpenROAD DPL flow is the current strict-track comparison anchor:
  `detailed_placement`, `improve_placement`, `optimize_mirroring`.
- Strict HPWL comparisons use OpenROAD/DPL pin-based log HPWL in
  `metrics.json:hpwl`.  The legacy bbox proxy is a debug field only.
- OpenROAD diamond remains a local-search donor and prepass reference, not a
  standalone canonical baseline runner in the current harness.
- The `framework`, `diamond`, and `default_negotiation` prepared start branches
  are active route-specific donor starts. Teacher must use current case
  evidence to justify the selected source parent.
- OpenROAD negotiation/NBLG is a repair and mechanism donor. It should not be
  promoted as the primary path without case evidence against the current
  OpenROAD DPL flow anchor.
- `default_negotiation` is the negotiation-primary source parent. It may consume
  guidance from earlier stages, but the normal successful route must execute
  negotiation/resource allocation and must not silently return from full LEGALM
  legalization.
- Differential guidance can be used as a route-internal seed/frontier stage.
  Its target objective, stopping point, and consumer are open mechanism choices;
  they should be tested by stage-wise and final full-flow metrics rather than
  treated as fixed LEGALM behavior.
- Selected threaded-frontier mechanisms from earlier negotiation experiments
  live under
  `family_variants/openroad_negotiation_nblg/mechanism_deltas/`.
- LEGALM is a paper-faithful source reference: keep Stage 1 projection,
  Stage 2 ALM/BGD-style overflow reduction, and Stage 3 no-overflow refinement
  semantically clean. Extra HPWL, negotiation, or flow-level ideas must be
  explicit outer stages, not hidden inside LEGALM.
- DREAMPlace/Abacus remain source and idea donors for separate experiments.

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

- generated build, variant, and experiment state.
- optional cached paper PDFs for reading.

They are useful locally but should not be read by default prompt generation or
committed as source-of-truth.
