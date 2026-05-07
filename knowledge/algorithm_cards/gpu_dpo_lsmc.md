# GPU-DPO / LSMC Detailed Placement Card

Source paper:

- `knowledge/reference/papers/pdf_cache/UCSD_c425_Detailed_Placement_Optimization.pdf`
- Source URL recorded in `knowledge/reference/papers/paper_sources.yaml`

## What Codex should remember

GPU-DPO is a detailed-placement optimization donor, not a legalization donor.
The useful idea is to combine strong detailed-placement descent with a bounded
large-step escape mechanism:

1. run detailed-placement descent to reach a local optimum,
2. perturb the best legal placement with legal random swaps,
3. rerun descent from the perturbed state,
4. keep the new state only if the canonical cost improves,
5. stop after a bounded number of failed large-step attempts.

This is not the same as rerunning unchanged random tails.  The large step is a
controlled escape from a basin of attraction, and the descent must be strong
and efficient enough to recover quality after the perturbation.

## Paper knobs worth preserving

Treat these as reference defaults before doing case-specific tuning:

- reorder window size: `3`
- MIS problem size: `64`
- LSMC kick move ratio: `0.10`
- LSMC early-exit failure tolerance: `5`

## Donor mechanisms for this repo

### Parallel-friendly descent kernels

The paper optimizes the same family of detailed-placement kernels used by
OpenROAD DPO:

- maximum independent set matching,
- global swap,
- local reorder,
- flipping / orientation.

For this repo, a CPU-first version should first improve the serial data
structures and exact local HPWL deltas before attempting GPU work.  Candidate
scoring, affected-net bbox construction, and dry-run reorder costs are safe
parallelization targets; grid and segment commits should remain serialized or
explicitly conflict-checked.

### LSMC booster

The practical algorithm shape for `Optdp` evolution:

- start from the current legal placement,
- run a strong descent script once,
- snapshot the best legal state,
- apply a bounded number of legal kick swaps,
- rerun the same efficient descent from the kicked state,
- keep only canonical HPWL improvements,
- terminate after a small number of failed kicks.

The kick operator must be legality-preserving and bounded.  It should not
increase runtime by hiding many full random passes inside each iteration.

### Multi-row awareness

The paper explicitly treats movable and reorderable multi-row cells as part of
detailed placement.  For this repo, do not silently drop multi-row candidates
from broad candidate pools if the algorithm claims multi-row support.  Either
implement the multi-row move/reorder semantics or keep the candidate pool
single-height and report that limitation.

## Implementation targets in current Optdp code

High-value source areas:

- `src/Optdp.cpp`: stage script and possible LSMC top-level controller.
- `src/optimization/detailed_mis.cxx`: MIS problem construction, local HPWL
  cost, and problem-size control.
- `src/optimization/detailed_global.cxx`: median-region target generation and
  swap scoring.
- `src/optimization/detailed_reorder.cxx`: dry-run reorder cost and window
  selection.
- `src/optimization/detailed_random.cxx`: legal kick-swap generator should be
  separated from the normal random improver.
- `src/objective/detailed_hpwl.cxx` and `src/util/journal.h`: exact local HPWL
  delta and move journaling must be efficient enough to support repeated
  descent.

## What not to do

- Do not claim an LSMC implementation if it only runs random improvement more
  times.
- Do not use unbounded random kicks.  Kick count should be a documented ratio
  of movable cells and should have an early-exit policy.
- Do not use bbox proxy HPWL as the promotion metric.  Use canonical
  OpenROAD/DPL pin-based HPWL from the flow metrics/logs.
- Do not let LSMC hide weak descent quality.  If descent cannot recover from a
  small kick, optimize the descent kernels first.

## Suggested first CPU experiment

Before GPU work, try a small CPU-only LSMC prototype:

1. optimize hot-path HPWL delta and journal overhead,
2. add dry-run local reorder and multi-target global/vertical candidates,
3. run one descent to local optimum,
4. apply `0.02`, `0.05`, and `0.10` legal kick ratios,
5. rerun descent with a strict runtime cap,
6. compare stage-wise HPWL and runtime against the no-kick baseline.

Promote only if the improvement comes from better final HPWL under the runtime
cap, not from repeated unchanged random tails.

## Current Implementation Evidence

Recent source-only closure on a dense image-compression placement snapshot:

- Reorder dry-run/offset traversal with window size 5 is a useful source donor;
  it improves final HPWL versus the old evolve default without changing the
  endpoint script.
- Honoring the existing `-t 0.005` tolerance in MIS/GS/VS/reorder/random gives
  a smaller additional gain by allowing real extra descent passes that were
  previously blocked by a hard `0.01` floor.
- A median-region guided random generator was rejected.  It consumed the random
  tail, worsened final HPWL, and added runtime.  Do not reintroduce it as a
  hidden runtime switch.
- Full-net reorder scoring was rejected as a default.  It barely improved final
  HPWL while adding scoring work.
- Prior endpoint-script portfolio results show a near-Diamond ceiling, but that
  is only a donor clue.  The publishable path is to move that behavior into
  bounded source kernels and a real descent controller, not to expand
  `dtParams.script`.

Next CPU-DPO implementation target:

1. keep the endpoint script fixed,
2. build a reusable local HPWL extrema cache,
3. score GS/VS/Reorder candidates from a bounded source frontier,
4. serialize only exact legal commits,
5. use final-stage mirror effects only as diagnosis after after-improve HPWL is competitive; do not make downstream optimize-mirroring the active patch target.
