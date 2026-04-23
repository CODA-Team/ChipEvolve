# Anchor Stack Observations (2026-04-22)

## Scope

This stack attempted to add a light smooth-anchor guidance layer on top of the
current runtime-aware net family:

- net-aware objective
- selective refinement
- localized swap
- smooth anchor candidate guidance

Target surface:

- `NegotiationLegalizer::findBestLocation`
- helper logic for connectivity-derived anchor targets

## What was attempted

The stack added:

- a smooth connectivity-derived anchor for high-displacement or pin-rich cells
- a small anchor neighborhood exploration
- a soft anchor-distance penalty in candidate cost

The intent was to recover some WNS/TNS on larger cases where `localized_swap`
already improved HPWL but still lost timing.

## Concrete evidence

On `ariane133_nangate45`:

Localized-swap family:

- runtime: `129.928 s`
- HPWL delta: `-32219.902`
- setup WNS: `-0.579907`
- setup TNS: `-1210.03`

Anchor stack:

- runtime: `132.843 s`
- HPWL delta: `-32219.902`
- setup WNS: `-0.579907`
- setup TNS: `-1210.03`

## Conclusion

This stack produced **no measurable quality improvement** on `ariane133` and
slightly worsened runtime.

So the current implementation should be treated as:

- a useful knowledge probe
- not a promoted family
- not worth keeping in the active target-plane code

## Interpretation

The likely issue is not that anchor ideas are useless.

The issue is that this specific implementation was too weak / too similar to
existing search neighborhoods to move the result:

- it did not change the chosen candidates enough
- it did not improve timing-sensitive cells enough to offset runtime cost

## Reuse guidance

If this direction is revisited, it should come back in a more structural form:

- tie anchor activation to stronger case selection or hot-cell selection
- combine with explicit stuck-cell escape or plate/region escape
- or use a timing-sensitive objective term instead of only a geometric anchor
