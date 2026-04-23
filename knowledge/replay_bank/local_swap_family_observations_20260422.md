# Localized Swap Family Observations (2026-04-22)

## Scope

This family replaced the previous full-group `cellSwap()` behavior with a
localized swap algorithm:

- small same-shape groups still use full pair enumeration
- large same-shape groups use a hotset of high-displacement / high-pin-count
  seed cells
- each seed only considers nearby same-shape cells in a local spatial window

This was stacked on top of:

- HPWL-aware `placementObjective`
- selective refinement budget
- wide escape refinement on a smaller subset

Target surface:

- `NegotiationLegalizer::cellSwap`
- supporting efficiency paths in `greedyImprove`

## Why this family was opened

The previous family had a clear structural bottleneck on larger cases:

- `cellSwap()` still compared all pairs inside each same-shape group
- large single-height libraries created very large groups
- runtime rose too quickly once the design size increased

So this family was intended to keep the good HPWL behavior while removing the
worst quadratic blow-up in post-optimization.

## Concrete evidence

### `ariane133_nangate45`

Strict negotiation baseline:

- runtime: `80.236 s`
- HPWL delta: `96300.188`
- setup WNS: `-0.577436`
- setup TNS: `-1191.57`

Localized-swap family:

- runtime: `129.928 s`
- HPWL delta: `-32219.902`
- setup WNS: `-0.579907`
- setup TNS: `-1210.03`

Interpretation:

- HPWL improved very strongly
- runtime remained above baseline, but was much more controlled than the
  previous always-wide / full-swap style family
- timing did **not** improve with the same patch; WNS and TNS both regressed
  slightly

This means the localized swap family is a real quality/runtime improvement
relative to the previous heavy postopt family, but it is **not yet** a
promoted cross-metric winner for `ariane133`.

## Implementation review findings

After the first localized-swap run, the implementation itself was reviewed and
several low-value costs were removed:

- cached per-cell pin counts instead of repeatedly asking the network
- removed the quadratic `std::find` pattern in `greedyImprove` budget fill
- cached current per-cell placement objective inside `cellSwap`

These changes improved the implementation quality, but they did **not**
materially change the end-to-end `ariane133` result:

- localized-swap v1 runtime: `129.928 s`
- localized-swap v2 runtime: `129.08 s`
- HPWL / WNS / TNS were effectively unchanged

So the dominant remaining cost is algorithmic, not a trivial implementation
bug.

## Main lesson

Localized swap is worth keeping as a base family because it:

- preserves the strong HPWL behavior of the net-aware objective
- controls the worst postopt combinational explosion better than full-group swap

But it still needs another stacked algorithmic change to become large-case
useful:

- a timing-friendlier main-pass objective
- a differentiable-style smooth anchor term
- or a stronger stuck-cell / local-optimum escape policy

## Next direction

Do **not** throw away this family.

Use it as a base and stack one of the following on top:

- differentiable-style anchor objective in `placementObjective`
- explicit stuck-cell escape in `findBestLocation` / `negotiationIter`
- timing-sensitive objective gating for pin-rich / small-net cells
