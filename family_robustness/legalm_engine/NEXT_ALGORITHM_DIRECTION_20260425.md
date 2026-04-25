# LEGALM next algorithm direction - 2026-04-25

## Boundary

This note is limited to the materialized `legalm_engine` family.  It does not
promote fallback-to-diamond, fallback-to-default OpenDP, or a full-core/full-grid
scan as family success.  The flow contract remains the common
`detailed_placement_evolve` evaluator line; matrix variants route the existing
`-use_negotiation` command into the private LEGALM implementation.

## Evidence Read

- R4 result: `family_robustness/legalm_engine/WORKER_RESULT_R4_20260425.md`
- R5 result: `family_robustness/legalm_engine/WORKER_RESULT_R5_20260425.md`
- Gate rule: `family_robustness/legalm_engine/ROBUSTNESS_GATE_20260425.md`
- R4 backup source/logs: raw runtime evidence archived locally and intentionally
  not committed.
- R5 backup source/logs: raw runtime evidence archived locally and intentionally
  not committed.
- Fallback gate evidence: raw runtime evidence archived locally and intentionally
  not committed.

## R4 Diagnosis

`legalm_counterfix_r4` is a real legality repair, not a quality solution.

- Root cause fixed: Stage1 cleared the grid but the maintained overflow counter
  still carried pre-Stage1 overflow.  R4 resets `total_overflow_` and
  `component_overflow_` after `grid_.clear()`, so Stage2 correctly early-exits
  when Stage1 is legal.
- Positive evidence: strict `aes_nangate45` and `jpeg_nangate45` pass through
  the same evolve command with LEGALM active.
- Remaining blocker: JPEG quality is poor.  R4 reports JPEG HPWL delta
  `204464.2755`, average displacement `3.721085`, and max displacement
  `118.790389`.  That is not acceptable as a base-family result.
- Coverage gap: R4 has no `bp_quad_nangate45` pass evidence.

The durable R4 patch artifact was regenerated from the backup source because the
previous file was byte-identical to the R5 patch and did not represent the R4
counterfix evidence.

## R5 Diagnosis

`legalm_stage1_quality_guard_r5` is also not a base candidate.

- Mechanism tried: keep R4's counterfix, raise `alpha_max`, add anchor and HPWL
  terms, and score Stage1 window candidates with `evaluateCandidateCost`.
- Local result: JPEG HPWL improves only slightly versus R4, from `204464.2755`
  to `199934.3355`.
- Regression: JPEG displacement worsens versus R4, from average `3.721085` to
  `4.040428`, and max `118.790389` to `121.440046`.
- Baseline gap: versus the clean evolve baseline noted in the R5 result, JPEG
  remains `+21.88%` HPWL delta, `+131.08%` average displacement, and
  `+469.44%` max displacement.
- Coverage gap: R5 also has no `bp_quad_nangate45` gate.

The R5 patch artifact is now the small incremental diff from R4 to R5.  It is
useful evidence for why parameter-only Stage1 quality scoring is insufficient.

## Fallback Is Not Family Success

The `large_design_diamond_fallback` evidence is intentionally excluded from
LEGALM success accounting.

- It uses a runtime-safe fallback binary, not a LEGALM algorithm improvement.
- It passes `jpeg_nangate45` with clean-evolve-like quality, but that result is
  a fallback result, not a LEGALM result.
- `bp_quad_nangate45` timed out at 360 seconds in the first fallback gate.  A
  retry produced metrics at 900 seconds, but it is still fallback evidence and
  cannot promote LEGALM.

## Next Algorithm-Level Direction

The next real LEGALM step should be an R6 row-segment batch assignment engine,
not another scalar weight tweak.

Core idea:

- Replace greedy one-cell-at-a-time Stage1 placement with bounded row-segment
  reservation and batch assignment inside each plate/component.
- Build a per-plate free-interval index from rows and fixed blockages.  This
  gives Stage1 legal slot candidates without scanning the full core.
- Bucket cells by original row band, plate/component, height, and coarse net
  anchor.  Keep bucket sizes capped; spill large buckets into deterministic
  stripes rather than using a fallback legalizer.
- Generate a bounded candidate frontier per cell: home snapped slot, nearest
  same-row slots, nearby row-band slots, low-fanout net-anchor slots, and a few
  displacement-guarded escape slots.  The frontier must be capped per cell.
- Solve each bucket as a small min-cost assignment or auction between cells and
  row slots.  The objective should combine displacement outlier penalty,
  low-fanout HPWL proxy, same-component pressure, and slot fragmentation cost.
- Feed only unresolved overflow or high-cost outliers into Stage2/Stage3.  The
  later stages should become repair/refinement over a hot frontier, not the
  mechanism that rescues a bad Stage1 global ordering.

Why this is the right next jump:

- R4 proves LEGALM can be made legal when Stage1 has a consistent overflow
  invariant.
- R5 proves local candidate scoring alone cannot recover JPEG quality because
  the greedy order still creates long-displacement tail choices.
- JPEG and BP need a Stage1 allocation model that reserves local row capacity
  before cells consume slots greedily.
- The row-segment/bucket structure gives a clear complexity budget: no full-core
  search, no full-cell x full-slot matching, and no large-design fallback.

## Required Next Gate

The next candidate must run these gates before any promotion language:

- Build/materialize gate for `legalm_r6_row_segment_batch_assignment`.
- Strict `aes_nangate45` through the same detailed-placement evolve line.
- Strict `jpeg_nangate45` with no fallback; reject if JPEG HPWL/displacement is
  worse than the clean evolve baseline or if max displacement remains in the
  R4/R5 tail regime.
- Strict `bp_quad_nangate45` with no fallback; report timeout, RSS, HPWL delta,
  average displacement, max displacement, and timing proxy.
- Log check that the run entered LEGALM and did not use diamond/default fallback.
- Complexity telemetry: Stage1 bucket count, max bucket size, candidate cap hit
  count, assignment iterations, Stage2/Stage3 hotset sizes, and elapsed time by
  stage.
