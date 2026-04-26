# LEGALM bp_quad Runtime Insight

## Context

`bp_quad_nangate45` is large enough that algorithmic constant factors dominate
the evolved LEGALM path.  The useful timing target is the legalizer stage first;
full strict metrics can be much heavier because writing/reloading the large ODB
and placement parasitic estimation are separate costs.

## Observed Bottleneck

The slow path was not primarily Stage3 polish.  The old bp_quad run showed:

- `detailed_placement_evolve`: about 62 seconds.
- LEGALM Stage3 attempted about 4.25M candidate evaluations but moved 0 cells.
- After skipping large-case Stage3, `detailed_placement_evolve` dropped to about
  53 seconds and `stage3 evals` became 0.

The remaining dominant bottleneck was row/interval assignment inside
`runLegalmFullLegalization`.  The original row search created a fresh
near-all-row vector per cell and scanned all free intervals in candidate rows.
On bp_quad, that means millions of avoidable allocations/probes as rows become
fragmented.

## Effective Fix

Two changes were high value:

- Replace per-cell `row_offsets()` vector construction with direct nearest-row
  iteration.
- Replace full row interval scans with bounded nearest-interval probes around
  desired/original/midpoint targets; fall back to the full scan only if bounded
  probes find no legal site.

The second change is the big win.  On the measured bp_quad legalizer-only run:

- `student_algorithm`: about 45.7 seconds -> about 11.7 seconds.
- `detailed_placement_evolve`: about 53 seconds -> about 19 seconds.
- LEGALM still placed all 1,436,995 cells, and OpenROAD DPL precheck reported
  0 wrong-region, row-alignment, site-alignment, and adjacent-overlap issues
  before the run was intentionally stopped during later improvement work.

## Guidance For Future Agents

For large cases, do not scan full rows or build per-cell row-order vectors in
inner loops.  Use row-id keyed vectors, sorted interval arrays, `lower_bound`,
bounded neighbor probes, and correctness-preserving fallbacks.

If quality regresses, add better target scoring or local rollback around the
bounded probes before returning to full scans.  Full scans should be diagnostic
or fallback behavior, not the normal path.
