# legalm_r6_relaxed_scanline_alm

This is the Worker C source-of-truth artifact for the next LEGALM structural
base.  It is scoped to the materialized `legalm_engine` family and must not be
counted as fallback-to-diamond/default OpenDP evidence.

## Base Contract

- Start from `../legalm_engine/dpl_evolve.patch`.
- Apply or preserve `../legalm_engine/research_patches/legalm_counterfix_r4.patch`.
- Do not use `../legalm_engine/research_patches/legalm_stage1_quality_guard_r5.patch`
  as the base.
- Keep the strict LEGALM entrypoint contract:
  `detailed_placement_evolve -use_legalm`.

R4 is required because it fixes the stale maintained-overflow counter after
Stage1 clears the grid.  R5 is excluded because it is a scalar guard/weight
change that only slightly improved JPEG HPWL while worsening displacement, so it
does not address the structural Stage1 failure mode.

## R6 Mechanism

R6 changes Stage1 from greedy "must be fully legal now" placement into relaxed
static-constraint placement:

- Stage1 candidates must satisfy core bounds, rail alignment, region/fence
  constraints, static invalid-site checks, fixed blockage checks, and site
  orientation.
- Stage1 candidates may overlap already placed movable cells.  That overlap is
  recorded in the maintained overflow grid and becomes ALM work for Stage2/3.
- Candidate search is scanline/bounded: same-row, nearby-row, and plate-projected
  candidates are capped per cell rather than full-core scanned.
- Stage1 scoring remains structural: displacement, movable-overflow pressure,
  and component pressure.  It does not inherit the R5 default `alpha_max`,
  `alpha_anchor`, or `alpha_hpwl` scalar bumps.
- Stage2 and Stage3 remain responsible for resolving residual movable overflow
  and must finish with zero placement violations for promotion.

The intended effect is to avoid the R4/R5 long-displacement tail created by
greedy one-cell-at-a-time legal placement.  Stage1 should preserve locality even
when nearby legal slots are temporarily over-subscribed, then let ALM pressure
repair only the hot overflow frontier.

## Patch Artifact

Source of truth type:
`research_patch_after_legalm_engine_plus_r4_counterfix`.

Patch file:
`research_patches/legalm_r6_relaxed_scanline_alm.patch`.

This is a concrete implementation delta for materialization review.  It is not
compile-validated in this workspace turn because shared materialization/build
scripts are outside Worker C's scope.

## Telemetry Plan

Log these counters in the LEGALM telemetry stream before considering promotion:

- Stage1 cells visited and candidates evaluated.
- Stage1 candidate cap hits.
- Stage1 static-constraint rejects.
- Stage1 selected relaxed-overflow sites.
- Stage1 max selected candidate overflow.
- Stage1 final maintained overflow after all cells are added.
- Stage2 initial and final overflow.
- Stage3 final overflow.
- Existing R4 false-return/success logs around Stage1, Stage2, Stage3, and
  writeback.

Required gates before promotion:

- `aes_nangate45` strict same entrypoint, no fallback.
- `jpeg_nangate45` strict same entrypoint, no fallback.
- `bp_quad_nangate45` strict same entrypoint, no fallback.
- Report HPWL delta, average displacement, max displacement, runtime, RSS,
  timing proxy, placement violations, LEGALM entry logs, and the R6 counters
  above.

## Materialization Status

Ready for materialization review, not yet build-validated.
