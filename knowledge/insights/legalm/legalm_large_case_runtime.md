# LEGALM Large-Case Runtime

## Context

Large placement instances expose constant-factor mistakes in the evolved
LEGALM path.  Optimize legalizer-stage runtime first; full strict metrics can
be much heavier because ODB write/read and downstream metric collection are
separate costs.

## Observed Bottleneck

The slow path was not primarily final no-overflow polish.  The dominant cost
was row/interval assignment inside full LEGALM legalization:

- per-cell construction of fresh row-order vectors,
- scanning many free intervals in candidate rows,
- millions of avoidable allocations and interval probes after rows become
  fragmented.

This pattern scales poorly on large, fragmented designs.

## Effective Fix

Two changes were high value:

- replace per-cell row-offset vector construction with direct nearest-row
  iteration,
- replace full row interval scans with bounded nearest-interval probes around
  desired, original, and midpoint targets; use full scans only as diagnostic or
  rare fallback behavior.

The bounded interval probe was the main win.  It preserved strict legality in
the measured large-case legalizer path while cutting legalizer-stage elapsed
time by a large factor.

## Guidance For Future Agents

For large cases:

- do not scan full rows in inner loops,
- do not allocate row-order vectors per cell,
- use row-id keyed vectors, sorted interval arrays, `lower_bound`, and bounded
  neighbor probes,
- keep candidate caps explicit in telemetry,
- only add richer scoring after the bounded probe path is already efficient.

If quality regresses, improve target scoring or commit criteria around bounded
probes.  Do not return full scans to the normal hot path.
