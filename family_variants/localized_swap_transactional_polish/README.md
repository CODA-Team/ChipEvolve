# localized_swap_transactional_polish

This is an opt-in polish artifact for an already legal parent.  It is not an
illegal-parent repair path and not a base family.

The patch replaces broad same-shape pair enumeration with a bounded,
transactional local swap polish.  It skips when the parent is illegal, caps
pair attempts, rolls back legality or displacement regressions, and emits
parent/post-polish telemetry.

## Source-of-truth type

- Type: `research_patch_artifact`
- Patch: `research_patches/localized_swap_legal_parent_transactional.patch`
- Base source: `src/dpl_evolve/src/NegotiationLegalizer.{h,cpp}` from an
  OpenROAD repository root.
- Consumption: apply only as an isolated post-legalization polish variant.

## Contract

- Parent must be legal before `cellSwap()` runs.
- Pair enumeration is window/hotset bounded and hard-capped.
- Every accepted pair is transactional: snapshot, attempt, validate, rollback
  on legality or displacement regression.
- Telemetry reports skip reason, parent/post violations, attempted pairs,
  accepted swaps, rollbacks, cap hits, and elapsed milliseconds.

## Blockers

- Needs legal-parent smoke evidence on `aes_nangate45` and `jpeg_nangate45`.
- Needs broader quality gate on legal parents before promotion.
- Needs `bp_quad` only after parent runtime is already under budget.
