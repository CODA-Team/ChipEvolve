# priority_escape_telemetry_first

This is a repair/polish research artifact, not a robust-base parent and not a
diamond-first fallback wrapper.

The patch records structured `findBestLocation` outcomes first, then allows a
small bounded escape only when telemetry shows a real stuck/no-valid condition.
Normal cases should emit the counters and keep `escape_attempted == 0`.

## Source-of-truth type

- Type: `research_patch_artifact`
- Patch: `research_patches/priority_escape_telemetry_first_no_diamond.patch`
- Base source: `src/dpl_evolve/src/NegotiationLegalizer.{h,cpp}` from an
  OpenROAD repository root.
- Consumption: apply only in an isolated variant checkout after the
  telemetry-only and real stuck/no-valid gates are selected.

## Contract

- Do not call `diamondDPL()` or `diamondRecovery()` before priority escape.
- Keep escape disabled unless structured stats show no-valid candidates or a
  repeated returned-current streak.
- Report find-best/stuck counters even when no escape is attempted.
- Bound escape by candidate cap, displacement guard, and rollback-safe legality
  checks.

## Blockers

- Needs a real or synthetic stuck/no-valid case before promotion.
- Needs normal-case zero-trigger proof on `aes_nangate45` and `jpeg_nangate45`.
- Needs large-case stress only after the parent negotiation path is runtime-safe.
