# Insight: LEGALM Paper-Style Displacement Cost Fix

## What Changed

The first self-legal LEGALM closure was legal and fast, but JPEG quality was
poor because the row free-segment assignment used an overly hard same-row
preference.  The cost effectively made one row of vertical movement more
expensive than crossing the whole row horizontally.

The assignment objective was changed to a paper-aligned displacement cost:

- row movement is converted to site-equivalent distance using
  `row_height / site_width`,
- each segment evaluates projected candidates near desired, original, and
  midpoint locations,
- the score combines desired-target distance, original-placement displacement,
  and a max-displacement tail penalty,
- telemetry records the row-equivalent site scale and max-displacement
  threshold.

This is still not a full LEGALM 2.0 reproduction.  It is a targeted correction
of the Stage1/closure objective so it follows the paper's displacement and
max-displacement-tail idea more closely.

## Evidence

All runs used:

```tcl
detailed_placement_evolve
```

and 10 OpenROAD threads.

### JPEG Nangate45

Run tag: `legalm_paper_cost_20260426_jpeg`

- result: `LEGALM full legalization placed 58513 / 58513 cells without diamond`
- LEGALM stage runtime: 208 ms
- legalize command elapsed time: 5.80 s
- average displacement: 1.8 um
- max displacement: 40.2 um
- legalized HPWL: 520866.4 um
- HPWL delta: 19%
- strict check: passed

Compared with the previous `legalm_stage3_20260426_jpeg` milestone:

- average displacement improved from about 10.0 um to 1.8 um,
- max displacement improved from about 325.1 um to 40.2 um,
- HPWL delta improved from 220% to 19%,
- runtime stayed within the JPEG legalize gate.

### AES Nangate45

Run tag: `legalm_paper_cost_20260426_aes`

- result: `LEGALM full legalization placed 14265 / 14265 cells without diamond`
- LEGALM stage runtime: 29 ms
- legalize command elapsed time: 1.48 s
- average displacement: 0.6 um
- max displacement: 3.5 um
- HPWL delta: 2%
- strict check: passed

### Ariane133 Nangate45

Run tag: `legalm_paper_cost_20260426_ariane133`

- result: `LEGALM full legalization placed 156702 / 156702 cells without diamond`
- LEGALM stage runtime: 1131 ms
- legalize command elapsed time: 17.54 s
- average displacement: 0.7 um
- max displacement: 23.2 um
- HPWL delta: 1%
- strict check: passed

## Updated Interpretation

The previous poor JPEG result was not mainly because LEGALM closure was
inherently weak.  It was because the closure objective had a hidden hard
same-row bias that contradicted the paper's displacement objective.

The current implementation is now a much better starting point for evolving a
paper-faithful LEGALM path:

- legality is self-contained,
- JPEG is below the 10-second legalize threshold,
- displacement tail is controlled,
- HPWL is near the diamond-order baseline rather than catastrophically worse.

This is still not promotion evidence for the active case loop.  Treat the
paper-cost path as a strong donor and ablation unless the complete strict flow
beats both `openroad_dpl_flow` and the best-so-far evolved artifact.  Legalizer
HPWL and displacement improvements explain the handoff quality, but they do not
replace final strict metrics.

## Next Paper-Faithful Work

Do not freeze the current details as final.  The algorithmic flow is still open.
Promising next changes are:

- replace the greedy segment pass with a local min-cost/bucketed scanline
  assignment,
- add BGD partition scheduling instead of a single global greedy closure,
- add connectivity/local-optimum escape only when convergence stalls,
- let Stage3 use no-overflow HPWL/displacement refinement, not only same-row
  displacement refinement,
- keep stage telemetry lightweight and emitted by each stage itself.

## Follow-Up: Bounded Stage3 No-Overflow Refinement

After the first paper-cost fix, Stage3 was changed from same-row-only
displacement polish into a bounded no-overflow refinement:

- cells are ordered by full site-equivalent displacement, including row
  displacement,
- only the largest displacement outliers are refined,
- each candidate must fit existing free intervals and pass placement checks,
- accepted moves may change rows, but only if original displacement decreases,
- the stage reports moved cells, row moves, and candidate evaluations.

This is closer to the paper's Stage Three idea: refine displacement without
introducing overflow.  It is still a CPU-bounded approximation, not the full
GPU BGD/TP engine from the paper.

Observed evidence:

- `legalm_stage3_budget_20260426_jpeg`: strict pass, 58513/58513 placed
  without diamond, legalize 6.19s, LEGALM stage 335ms, avg/max displacement
  1.7/40.2um, HPWL delta 19%, Stage3 moved 2695 cells with 1203 row moves.
- `legalm_stage3_budget_20260426_aes`: strict pass, 14265/14265 placed
  without diamond, legalize 1.56s, avg/max displacement 0.6/2.5um, HPWL
  delta 2%.
- `legalm_stage3_budget_20260426_ariane133`: strict pass, 156702/156702
  placed without diamond, legalize 18.42s, LEGALM stage 1518ms, avg/max
  displacement 0.7/23.2um, HPWL delta 1%.

Open issue: Stage3 still performs many candidate checks on larger designs
(`ariane133` reported about 36.9M candidate evaluations).  Runtime is currently
acceptable, but the next version should use row-local candidate indexes or
partitioned refinement to avoid scaling this linearly with too many intervals.

## Follow-Up: Bounded GD-Style Candidate Projection

The next refinement changed Stage3 candidate generation to better match the
paper's GD/BGD neighborhood idea.  Instead of scanning every free interval in a
row, Stage3 now enumerates a bounded horizontal stencil around the original,
midpoint, and current locations, then projects each target only to the nearest
few free intervals.

This keeps the no-overflow guard but makes the CPU implementation scale more
like a fixed candidate stencil than an interval-scan pass.

Observed evidence:

- `legalm_stage3_stencil_20260426_jpeg`: strict pass, 58513/58513 placed
  without diamond, legalize 6.01s, LEGALM stage 404ms, avg/max displacement
  1.7/40.2um, HPWL delta 19%, Stage3 candidate evaluations reduced from about
  7.6M to 4.8M compared with the previous budgeted Stage3.
- `legalm_stage3_stencil_20260426_ariane133`: strict pass, 156702/156702
  placed without diamond, legalize 18.06s, LEGALM stage 1446ms, avg/max
  displacement 0.7/23.2um, HPWL delta 1%, Stage3 candidate evaluations reduced
  from about 36.9M to 10.0M.
- `legalm_stage3_stencil_20260426_aes`: strict pass, 14265/14265 placed
  without diamond, legalize 1.55s, avg/max displacement 0.6/2.5um, HPWL
  delta 2%.

The quality stayed effectively unchanged while candidate evaluations dropped
substantially on large cases.  This should be the preferred current Stage3
implementation before testing `bp_quad`.

## Follow-Up: Paper-Style 2D ALM/BGD Guidance

Stage A was changed from a same-row horizontal target nudge into a
paper-style 2D ALM/BGD guidance pass:

- each GD update evaluates a fixed 245-candidate stencil, matching the
  LEGALM 2.0 Fig. 5 candidate-count structure,
- candidate positions include horizontal and vertical row offsets,
- the ALM bin cost now uses the paper-style `lambda_j * max(1 + sigma * g_j,
  0)` gradient term instead of a simple positive-overflow penalty,
- multiplier updates use the clipped violation form from Eq. 23,
- candidate scoring removes the current cell from its footprint before
  evaluating a candidate, matching Algorithm 2's remove/evaluate/place flow,
- displacement cost is row-aware and includes the `delta_threshold = 3H`
  maximum-displacement tail idea.

This still does not claim full paper reproduction.  Missing paper features are:

- true triplefold partition scheduling,
- partition-local sequential updates sorted by demand,
- connectivity-based local-optimum escape,
- GPU-style parallel reduction over candidate positions.

Observed evidence:

- `legalm_2d_bgd_tail_20260426_jpeg`: strict pass, 58513/58513 placed without
  diamond, legalize 6.13s, LEGALM stage 436ms, avg/max displacement
  1.7/46.9um, HPWL delta 20%, 245-candidate 2D guidance moved 21888 cells with
  18879 row moves.
- `legalm_2d_bgd_tail_20260426_aes`: strict pass, 14265/14265 placed without
  diamond, legalize 1.57s, LEGALM stage 109ms, avg/max displacement
  0.6/2.5um, HPWL delta 2%.
- `legalm_2d_bgd_tail_20260426_ariane133`: strict pass, 156702/156702 placed
  without diamond, legalize 18.08s, LEGALM stage 1370ms, avg/max displacement
  0.7/23.2um, HPWL delta 1%.

Interpretation:

- This version is more faithful to LEGALM 2.0 Stage Two than the previous
  horizontal-only guidance, especially around 2D GD candidates, clipped ALM
  updates, restart-style early iterations, and row-aware displacement.
- JPEG quality regressed slightly from the best Stage3-stencil version
  (`19%` HPWL delta to `20%`), but legality and runtime stayed within the gate.
  Keep this as a paper-faithful Stage A donor/ablation, not as the final
  quality optimum or the automatic next-round parent.
- The next paper-faithful improvement should be triplefold-style partitioned
  BGD scheduling.  That should reduce update interference from simultaneous
  all-cell moves without falling back to serial full-design passes.

## Paper-Fidelity Gap List

This is the current ordered checklist for making the implementation respect
LEGALM 2.0 more closely while keeping CPU performance explicit:

1. Stage Two BGD scheduling should follow Algorithm 3: partition cells into
   subregions, rotate three shifted partition schemes, sort partition cells by
   descending demand `d_i(x)`, and process partitions in parallel.
2. Stage Two cell updates should update local overflow after each accepted
   cell move within a partition.  The current CPU version still evaluates most
   candidate costs against a snapshot occupancy.
3. Stage One should become scanline/plate-based relaxed initial legalization:
   direct rounded placement plus projection to region/blockage plates, allowing
   movable overlap rather than doing an immediate greedy no-overlap closure.
4. Local-optimum escape should be added only when overflow stagnates, using
   connected plate components and moving the most congested cells from small
   isolated components to larger overflow-free components.
5. Stage Three should cycle through the three partition schemes for roughly 10
   rounds and use a strict no-overflow candidate check, equivalent to
   `lambda = +infinity` in the paper.
6. Routability/technology penalties from Eq. 35 are still absent except for
   existing OpenDP legality checks; they should be added only when we can
   compute them cheaply.
7. Mixed-height/P-G alignment details are mostly delegated to OpenDP
   `canBePlaced`; a more faithful implementation should expose the paper's
   parity handling directly in the candidate generator.

## Follow-Up: Triplefold-Style Partitioned BGD

Stage A now uses a CPU version of the paper's triplefold partition idea:

- three shifted partition schemes rotate by ALM iteration,
- cells must fit completely inside the current subregion to be updated,
- cells in each partition are sorted by descending demand `d_i(x)` before GD,
- partitions execute in parallel across CPU threads,
- candidate positions are constrained to remain inside the assigned subregion.

This removes the largest mismatch in the previous Stage A, which updated all
eligible cells simultaneously from one global snapshot.  It is still not a full
GPU Algorithm 3 reproduction because local overflow is not yet incrementally
updated after each accepted cell inside a partition.

Observed evidence:

- `legalm_tp_bgd_20260426_jpeg`: strict pass, 58513/58513 placed without
  diamond, legalize 6.30s, LEGALM stage 437ms, avg/max displacement
  1.7/42.7um, HPWL delta 20%, Stage A 298ms.
- `legalm_tp_bgd_20260426_aes`: strict pass, 14265/14265 placed without
  diamond, legalize 1.60s, LEGALM stage 113ms, avg/max displacement
  0.6/2.5um, HPWL delta 2%.
- `legalm_tp_bgd_20260426_ariane133`: strict pass, 156702/156702 placed
  without diamond, legalize 18.32s, LEGALM stage 1391ms, avg/max displacement
  0.7/23.2um, HPWL delta 1%, Stage A 821ms.

Interpretation:

- The implementation is now structurally closer to Algorithm 3 than the
  previous 2D snapshot update.
- Runtime remains acceptable on JPEG and Ariane.  Stage A got heavier because
  partition construction and demand sorting are now real work; that is the
  expected CPU cost of respecting the paper's BGD scheduling.
- The next implementation target is local per-partition overflow update during
  sequential cell moves.  That should improve convergence fidelity before
  adding connectivity-based local-optimum escape.

## Follow-Up: Partition-Local Overflow Delta

The next pass made partition-local sequential moves more faithful to Algorithm
2 and Algorithm 3:

- every worker keeps a private occupancy-delta buffer for the partition it is
  processing,
- after a cell move is accepted, its old footprint is removed and its new
  footprint is added to the local overflow estimate,
- later cells in the same partition therefore see the updated overflow state,
- the max-displacement tail coefficient in Stage A now follows the paper's
  `alpha_max = 1.5` relationship to the base displacement weight.

Observed evidence:

- `legalm_tp_local_delta_alphamax_20260426_jpeg`: strict pass, 58513/58513
  placed without diamond, legalize 6.25s, LEGALM stage 439ms, avg/max
  displacement 1.8/57.3um, HPWL delta 20%, final Stage A overflow sites
  reduced to about 13314.
- `legalm_tp_local_delta_20260426_aes`: strict pass, 14265/14265 placed without
  diamond, legalize 1.61s, LEGALM stage 112ms, avg/max displacement 0.6/2.5um,
  HPWL delta 2%.
- `legalm_tp_local_delta_alphamax_20260426_ariane133`: strict pass,
  156702/156702 placed without diamond, legalize 18.41s, LEGALM stage 1456ms,
  avg/max displacement 0.7/23.2um, HPWL delta 1%.

Interpretation:

- Local occupancy updates made the ALM guidance much more convergent on JPEG:
  overflow sites dropped far more aggressively than the snapshot TP version.
- JPEG max displacement worsened despite the paper-aligned `alpha_max = 1.5`
  tail, suggesting the remaining displacement tail is dominated by the greedy
  no-overlap closure and available free intervals, not by the Stage A tail
  scalar alone.
- The next structural task should be Stage One scanline/plate relaxed
  projection or a less greedy Stage Two assignment.  Further scalar tuning of
  Stage A is unlikely to recover the JPEG displacement tail by itself.

## Follow-Up: Stage One Relaxed Projection, Stage Three Loop, and Escape Hook

The implementation was reviewed again against the LEGALM 2.0 paper and then
updated in several paper-fidelity steps rather than one isolated tweak:

1. Stage One now performs a scanline/free-plate relaxed projection before
   ALM/BGD.  It builds static free intervals from fixed blockages, invalid
   sites, padding reservations, and region pixels, then projects each eligible
   movable cell to the nearest static-valid site while still allowing movable
   overlap.
2. Stage Three no-overflow refinement now runs up to 10 rounds, closer to the
   paper's repeated no-overflow BGD refinement stage instead of one outlier
   sweep.
3. Algorithm 2 skip/demand logic now uses footprint-level overflow rather than
   the lower-left bin density.  This better matches the paper's remove-cell /
   update-overflow / evaluate-candidate semantics.
4. A conservative connectivity/local-optimum escape hook now exists.  It only
   triggers when overflow improvement stalls across recent ALM iterations, so
   normal descending cases do not widen search accidentally.

Observed evidence for the final `legalm_escape_ready_20260426_*` code:

- `legalm_escape_ready_20260426_aes`: strict pass, 14265/14265 placed without
  diamond, legalize 1.99s, LEGALM stage 431ms, avg/max displacement 0.6/2.5um,
  HPWL delta 2%.
- `legalm_escape_ready_20260426_jpeg`: strict pass, 58513/58513 placed without
  diamond, legalize 8.06s, LEGALM stage 1971ms, avg/max displacement
  1.7/56.1um, HPWL delta 20%.
- `legalm_escape_ready_20260426_ariane133`: strict pass, 156702/156702 placed
  without diamond, legalize 20.60s, LEGALM stage 2808ms, avg/max displacement
  0.7/23.2um, HPWL delta 1%.

Interpretation:

- The implementation now respects the paper's high-level staged algorithm much
  more closely: relaxed static projection, ALM/BGD with TP-style partitioning,
  footprint overflow updates, repeated no-overflow refinement, and a guarded
  local-optimum escape path are all present.
- JPEG remains legal and under the 10-second legalize gate, but Stage Three's
  10-round CPU approximation is visibly heavier.  If future work needs more
  speed, optimize the Stage Three candidate kernel before reducing the paper
  structure.
- The remaining non-exact parts are implementation-level approximations rather
  than missing stages: plate connectivity is represented through static row
  intervals instead of a full 2D plate graph, Eq. 35 technology/routability
  penalties are mostly represented through OpenDP static checks plus a bounded
  net-anchor proxy, and mixed-height/P-G parity is delegated to `canBePlaced`
  for most cases.

## Follow-Up: Plate Component Graph and Hot-Loop Technology Guards

The next review focused on places where the CPU implementation was still more
"works in practice" than "close to the paper's constrained search space."  The
goal was not to add slow callbacks, but to make the BGD candidate kernel reject
invalid candidates using precomputed, cache-friendly data.

Implemented changes:

1. Static free intervals are now also treated as row-interval plate components.
   Adjacent-row intervals with x-overlap are unioned into a component graph.
2. BGD candidate search now requires every candidate footprint to fit inside
   one static plate component before it is scored.  This is a cheap binary
   interval lookup plus component consistency check, not a full grid scan.
3. Local-optimum escape now uses the plate component graph and only jumps from
   a stuck source component into a different component with enough area.  This
   is closer to the LEGALM 2.0 connectivity-based escape idea than the earlier
   row-only scan.
4. BGD candidate search now performs an O(1) row/site compatibility guard using
   `Grid::getSiteOrientation(...)` before ALM scoring.  This makes technology
   row compatibility explicit without calling the heavier placement validator
   inside the 245-point stencil.

Observed evidence for `legalm_tech_constraint_20260426_*`:

- AES: strict pass, 14265/14265 placed without diamond, legalize 2.05s,
  LEGALM full stage 431.90ms, avg/max displacement 0.6/2.5um, HPWL delta 2%.
- JPEG: strict pass, 58513/58513 placed without diamond, legalize 8.69s,
  LEGALM full stage 2254.33ms, avg/max displacement 1.7/56.3um, HPWL delta
  20%.  This still satisfies the current JPEG <10s legalization gate with 10
  threads.
- Ariane133: strict pass, 156702/156702 placed without diamond, detailed
  placement command reported 6s, relaxed guidance 1973.37ms, LEGALM full stage
  2886.34ms, avg/max displacement 0.7/23.2um, HPWL delta 1%.

Interpretation:

- The implementation is now a useful high-performance CPU reference for the
  LEGALM-style pipeline: relaxed static projection, ALM/BGD with TP-style
  partitioning, local occupancy deltas, row-interval plate components,
  connectivity escape, and repeated no-overflow refinement are all present.
- The paper's exact GPU data structures and all technology/routability terms
  are still not copied verbatim.  In this repo, those details should remain
  evolvable: future agents can replace component construction, Stage Two
  assignment, or Stage Three refinement while preserving the same
  `detailed_placement_evolve` entrypoint and telemetry contract.

## Follow-Up: Performance Review and Stage Three Pruning

After the paper-fidelity pass, the main remaining runtime hotspot was not the
outer framework but redundant work inside the LEGALM-style CPU kernels:

1. BGD candidates were doing both a static interval scan and a plate-component
   lookup.  The component lookup already proves the full footprint fits in one
   static free component, so the duplicate interval scan was removed from the
   BGD hot loop and escape hot loop.
2. Bin capacities and inverse capacities are now precomputed once.  ALM density
   and overflow scoring no longer recompute capacity and division inside every
   bin visit.
3. Stage Three no-overflow refinement now prunes candidate rows whose vertical
   displacement alone cannot improve the current solution, skips duplicate row
   visits, and skips cells already at zero displacement before temporarily
   unplacing them.
4. A trial optimization that replaced Stage Three `canBePlaced` calls with a
   site-orientation fast path was rejected because it increased JPEG runtime in
   practice.  The final version keeps the authoritative placement validator in
   Stage Three and only uses safe pruning around it.

Observed evidence for `legalm_stage3_prune_20260426_*`:

- AES: strict pass, legalize 1.71s, LEGALM full stage 87.64ms, Stage Three
  candidate evals 696083, avg/max displacement 0.6/2.5um, HPWL delta 2%.
- JPEG: strict pass, legalize 8.01s, LEGALM full stage 1399.11ms, Stage Three
  candidate evals 9437556, avg/max displacement 1.7/56.3um, HPWL delta 20%.
- Ariane133: strict pass, detailed placement command reported 5s, LEGALM full
  stage 2061.46ms, Stage Three candidate evals 4428735, avg/max displacement
  0.7/23.2um, HPWL delta 1%.

Interpretation:

- This is a good example of the preferred evolve style: keep the staged LEGALM
  algorithm intact, then optimize the CPU implementation by removing redundant
  checks, precomputing repeated quantities, and pruning candidates with safe
  lower bounds.
- The fastest accepted change was not the most aggressive fast path.  The
  accepted optimization is conservative: it reduces Stage Three work while
  preserving the same legality authority and paper-like repeated no-overflow
  refinement structure.
