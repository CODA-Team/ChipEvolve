# Insight: LEGALM Self-Legal Closure First Milestone

## Status

The current `detailed_placement_evolve` implementation now has a LEGALM-style
self-legal closure stage.  It is no longer merely a guidance hook followed by
diamond when the `legalm_full` stage succeeds.

The implemented sequence is:

1. relaxed/static target guidance,
2. coarse ALM multiplier update with bounded BGD-like stencil,
3. seed row-assignment guidance,
4. row free-segment capacity assignment that places all movable stdcells,
5. Stage3 no-overflow refinement that only moves cells inside available free
   intervals.

Diamond remains compiled and available as a fallback path, but successful
`legalm_full` runs return before diamond.

## Observed Evidence

All of these runs used 10 OpenROAD threads and the same evolved command:

```tcl
detailed_placement_evolve
```

AES:

- run tag: `legalm_full_20260426_aes`
- result: `LEGALM full legalization placed 14265 / 14265 cells without diamond`
- strict status: passed
- legalize runtime: about 2.0 seconds

JPEG:

- run tag: `legalm_stage3_20260426_jpeg`
- result: `LEGALM full legalization placed 58513 / 58513 cells without diamond`
- Stage3 moved cells: 434
- strict status: passed
- legalize runtime: about 5.7 seconds

Ariane133:

- run tag: `legalm_fastseg_20260426_ariane133`
- result: `LEGALM full legalization placed 156702 / 156702 cells without diamond`
- strict status: passed
- legalize runtime: about 17.6 seconds

## What This Proves

This proves that this LEGALM-style path can produce a site-aligned,
row-aligned, non-overlapping placement on tested Nangate45 AES/JPEG/Ariane
cases without relying on diamond for legality.

It does **not** prove quality competitiveness.

## Main Quality Problem

JPEG is legal and fast enough for the current 10-second legalize gate, but its
HPWL and displacement are poor.  The main cause is not legality failure.  It is
the greedy row free-segment assignment objective:

- it prioritizes finding capacity over preserving local wirelength,
- it sorts large/scarce cells early,
- dense rows can push cells far horizontally,
- Stage3 currently only performs same-row displacement refinement.

The next quality work should therefore focus on assignment objective and
partition strategy, not legality closure.

## Next Implementation Targets

Keep these as paper-faithful algorithm work, not hidden flow policy:

- replace greedy capacity assignment with bucketed scanline or min-cost local
  row assignment,
- add partition/local-optimum escape based on overflow or displacement
  stagnation,
- improve BGD candidate stencil so targets are less horizontally destructive,
- make Stage3 refine HPWL or displacement under no-overflow constraints,
- add per-stage convergence traces to distinguish objective failure from
  legality failure.

## Important Guardrail

Do not call this final quality-ready LEGALM.  It is a self-legal closure
milestone.  The legality path is now real enough to evolve, but the objective
and partitioning are still immature.

This path is a donor or ablation until the complete strict flow beats the
active case baseline and the best-so-far evolved artifact.  A later student
should not promote full LEGALM self-legalization merely because it avoids
diamond or reports clean legality.
