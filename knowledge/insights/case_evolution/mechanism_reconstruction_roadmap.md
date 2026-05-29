# Mechanism Reconstruction Roadmap

## Agent Use

This file is the implementation roadmap after Teacher has selected a blueprint
from `case_type_quality_mechanism_priority.md`.  Read only the selected blueprint
section during normal work.  Each blueprint is a producer-handoff-consumer
mechanism: preserve the mechanism shape, adapt local implementation details to
current source evidence, and prove liveness with counters.

## Shared Contracts

- Source layout is the private `dpl_evolve` tree prepared for the Student.
- Use native OpenROAD state (`Node*`, `Edge*`, segment ids, row ids, journals,
  masks, target arrays) rather than logs, strings, files, or benchmark names as
  handoff payload.
- Exact consumers score with `DetailedHPWL` or a journal/touched-net delta,
  roll back probes, and replay only positive transactions.
- Every route reports: producer count, handoff produced/consumed, exact probes,
  exact accepts, accepted HPWL gain/delta, rejects/rollbacks, pass runtime, and
  final full-flow HPWL/legality/displacement/runtime.

## Shared Source Anchors

- Flow sequence: `src/StudentAlgorithm.cpp`, `Opendp::runStudentAlgorithm`.
- Top-level state and improve schedule: `src/Optdp.cpp`,
  `include/dpl_evolve/Opendp.h`.
- Exact DPO consumers: `src/optimization/detailed_global.{h,cxx}`,
  `src/optimization/detailed_reorder.{h,cxx}`,
  `src/optimization/detailed_vertical.{h,cxx}`,
  `src/optimization/detailed_manager.{h,cxx}`,
  `src/objective/detailed_hpwl.{h,cxx}`.
- LEGALM/current-net producer: `src/LegalmGuidance.cpp`,
  `src/DifferentialGuidance.cpp`, `src/LegalmFullLegalization.cpp`,
  `src/LegalmRowAssignment.cpp`.
- Negotiation producer: `src/EvolveNegotiationRepair.cpp`,
  `src/NegotiationLegalizer.cpp`, `src/NegotiationLegalizerPass.cpp`,
  `src/NegotiationLegalizer.h`.
- Diamond/source-edge producer: `src/Place.cpp`, `src/Opendp.cpp`,
  source-edge hooks in exact global-swap code.


## Blueprint D+A: One-Student Diamond Critical-Frontier Warm-Up

### Use When

Use Blueprint D+A for large row-rich/control/datapath cases with little true
macro evidence, moderate utilization, fast clean Diamond legalization, and a
large improve-placement recovery opportunity.  The strong one-shot version does
not depend on improving legal HPWL first: Diamond legalization may raise legal
HPWL slightly, then exact DPO recovers the quality through a broad sourceTopK
producer and selected-segment consumer.  This is the single-Student warm-up
method for this case type: do not split Blueprint D producer activation and
Blueprint A consumers across separate Students when only one Student is assigned
or when the goal is a one-shot strong-chain reconstruction.

### Start Basin

- Start from `diamond` for the first reconstruction when this blueprint is
  selected.  The intended first state is a fast clean Diamond-style legal basin;
  legal HPWL may rise modestly, and that is acceptable when improve placement
  has enough recoverable DPO opportunity.
- Do not spend the first one-student attempt on `Place.cpp` legalizer scoring
  simply because `HPWLlg` is above `HPWLg`.  In the validated one-shot shape the
  legalizer remained essentially Diamond; the quality source was exact global
  swap sourceTopK plus selected-segment reorder.
- Repair the legalizer only after logs prove the DPO producer, hot-segment
  handoff, and selected reorder are live and the remaining failure is explicitly
  legal-basin damage or displacement-tail damage.
- Do not use `default_negotiation` unless endpoint/source residue is the named
  payload.  Do not use `framework` unless target-miss/current-net anchors are
  the named payload.

### One-Student Mechanism Chain

Implement the core strong chain first, then add continuation consumers only
after the core producer/handoff/consumer link builds and evaluates.  The
one-student reproduction target is not "write every downstream idea before the
first compile"; it is to make the validated HPWL-moving chain executable in one
workspace:

1. Preserve the normal `diamond` legalization command path and focus the first
   patch on DPO consumption.  The validated Ariane-like one-shot shape had a
   small global-to-legal HPWL rise but then a very large improve-placement drop;
   it did not need a first-pass `Place.cpp` rewrite.  Do not replace this route
   with LEGALM, negotiation, mirror, guard, or telemetry work.
2. In `Opendp::improvePlacement`, make the enhanced exact global-swap lane
   reachable from the regular detailed-placement script.  For this blueprint,
   `extra_dpl_enabled` must force the exact `gs` path; do not let a zero density
   or intensity score return to legacy `gs`.  Use a bounded low-intensity floor
   for exact HPWL search, and log the forced exact-path dispatch.
3. In `DetailedGlobalSwap`, keep the normal full shuffled
   `mgr_->getSingleHeightCells()` loop.  The strong chain is a broad exact
   sourceTopK producer, not a tiny globally admitted source sampler.  Runtime is
   controlled by small per-source target pools, per-source top-K exact probes,
   move-before-swap replay, and pass-level elapsed/gain guards; it is not
   controlled by admitting only a few thousand sources and leaving most cells
   unscored.  Profiling may restore its moves afterward, but the profiling pass
   should still exercise the same sourceTopK machinery enough to prove candidate
   supply and HPWL value.
4. For each visited source cell, compute the HPWL median/bbox range with
   `getRange`, clip it by displacement limits, and skip cells already inside the
   range.  Build a compact per-source target set from the target row nearest the
   bbox center, adjacent target rows, and bbox-left/center/right anchors aligned
   to legal segments.  Rank candidates by outside-bbox distance reduction,
   distance to bbox center, and move distance before exact scoring.  The cap is
   per source and per pass; if a global source-admission list exists, it must be
   large enough that the pass still behaves like a broad all-cell sourceTopK
   producer.
5. Exact-score move and swap probes with `DetailedHPWL::delta` only for each
   source's ranked top candidates and only within per-source and per-pass
   budgets.  For each candidate,
   try the legal move first; try a swap only if the move cannot be formed or if
   the implementation deliberately marks that candidate as swap-only.  Do not
   exact-score both move and swap for every candidate.  Roll back every probe,
   keep only the best positive transaction for that source, replay it, re-score
   the replay, and reject nonpositive or illegal replay.  If profiling itself
   times out or consumes the flow budget before downstream stages, the producer
   is overbuilt even if the exact path is live.
   A broad exact-GS implementation that accepts many weak center/bbox moves is
   not enough.  If accepted count and accepted delta are large but improve-stage
   recovery is weak, the failure is producer quality/accepted-delta washout:
   repair per-source target-row/anchor ranking before widening consumers.  For
   large row-rich cases, high-quality sourceTopK prefers sources outside their
   bbox/median band and target rows with clear legal segment feasibility.  A
   source whose score is mainly "many possible anchors" but does not reduce
   outside-bbox distance is low quality.  Rank by expected HPWL reduction per
   exact probe, displacement headroom, target-row legality, and
   accepted-delta-per-runtime; use accept count only as liveness evidence.
6. Accept the replay through the existing budget/objective path, not through a
   separate post-hoc copy of the placement state.  When a sourceTopK replay is
   accepted, collect old/new segment ids directly from the live journal before
   `acceptMove()` clears it.  Moved `Node*` ids and accepted-delta density are
   useful continuation payloads, but the minimal one-shot handoff is the
   cumulative hot-segment frontier from accepted journals.
7. Export native handoff state into `DetailedMgr`: append or merge old/new hot
   segment ids from every accepted sourceTopK transaction, dedupe them, and keep
   them alive until selected reorder consumes them.  Do not overwrite the
   frontier with only the last accepted move.  Accepted-node masks,
   critical-frontier nodes, and accepted-delta-ranked footprints are stronger
   continuation payloads after the hot-segment handoff is proven live.
8. Immediately run selected-segment reorder over the hot segments: prioritize
   hot segments first and use only bounded fallback after the hot-frontier budget
   has been spent.  A broad fallback that processes most of the design while the
   accepted frontier is tiny is a failed handoff/consumer reconstruction, even
   if reorder accept counters are nonzero.  Log hot
   frontier/windows/accepts/gain separately from fallback windows/accepts/gain.
9. If the core sourceTopK -> hot-segment reorder chain builds and evaluates
   cleanly, optionally add exact local closure over accepted nodes and hot
   segments in the same `improvePlacement` call.  Generate small exact reorder
   windows, exact-score affected-net HPWL, roll back failed windows, and keep
   only accepted windows.
10. Optional continuation consumers over the same native footprint are
    critical-row micro-start, critical-net chain assignment, multi-row residual
    transactions, and segment-local residual swaps.  These are extensions; do
    not delay the first build/evaluation of sourceTopK plus selected reorder to
    implement all of them at once.
11. Log HPWL before/after the producer, selected reorder, and any optional exact
    closure or residual consumers.  Clear accepted/hot/critical state only after
    all invoked consumers finish.

### SourceTopK Producer Shape

This blueprint depends on a high-throughput exact producer.  The strongest
implementation is not a small ranked-source sampler.  Reconstruct the producer
with these source-level choices:

- In `Opendp::improvePlacement`, set the manager's extra-DPL path on for this
  route and keep the normal detailed script structure so `gs` runs before `ro`.
  The intended order is still the native detailed flow: `mis`, enhanced `gs`,
  `vs`, focused `ro`, then default/random cleanup.  A log line that says the
  exact path fell back to legacy `gs` is a failed implementation of this
  blueprint, even if final HPWL is close to baseline.
- In `DetailedGlobalSwap::globalSwap`, start from the full shuffled
  single-height-cell list in both profiling and applied passes.  Reset
  sourceTopK counters at pass start and maintain separate counters for
  `sources_seen`, `candidates_generated`, `exact_scored`, `replay_attempts`,
  `replay_failures`, `rollbacks`, `accepts`, and `accepted_delta`.  A tiny
  `sources_admitted` pool is a common failed reconstruction; if such a pool is
  used for runtime control, it must be large enough that the pass still covers
  broad row-rich source residue.
- In `generateWirelengthOptimalMove`, use the cell's median/bbox range and
  displacement box to derive target rows and x anchors.  Compute cheap
  per-source ranking features before journal probes, build the legal candidate
  pool for that source, and exact-probe only the first few ranked candidates.
  Probe `tryMove` first and use `trySwap` only as a fallback for occupied or
  otherwise move-infeasible target positions, so exact scoring stays bounded
  enough for vertical swap, reorder, mirror, and final reporting.
- Use top-K as a per-source cap and also enforce per-pass elapsed/gain-rate
  guards.  A good reconstruction scans the full source list, builds only a small
  ranked candidate pool per source, exact-scores only the first few candidates,
  and replays only the best positive candidate.  Runtime control comes from
  target-row segment pruning, candidate dedupe, trying move before swap,
  gain-rate early stop, and a bounded intensity floor; it does not come from
  disabling the exact producer, routing back to legacy `gs`, or shrinking the
  source list until only a small sample is scored.
- Record sourceTopK accepts only after the replay is accepted by the same
  `currHpwl`, budget, and combined-profit logic used by global swap.  Do not
  count probe-only deltas as accepted gain.
- Treat accept count and raw accepted delta as liveness, not quality proof.  A
  live producer whose accepted transactions are too broad can feed a hot
  reorder frontier and still worsen final HPWL.  In that case the next repair is
  the ranked per-source producer: bbox-left/center/right anchors, target-row
  feasibility, outside-bbox distance reduction, move-before-swap replay, and
  accepted-delta-per-runtime filtering.
- Record the accepted footprint as pass-local cumulative state before the move
  journal is cleared.  If many replays are accepted but exported
  `accepted_nodes` or `hot_segments` remain near one or two, the producer is
  live but the native handoff is still broken; repair append/merge lifetime
  before adding unrelated consumers.
- Sanity check after one run: on a large row-rich case, a live producer should
  show high-throughput generated/exact-scored/replay/accept counters and large
  accepted delta, and the accepted-node/hot-segment frontier should scale with
  accepted transactions after dedupe.  If only a few thousand sources or exact
  probes are considered, the source enumeration was probably narrowed too much
  or the enhanced `gs` path was only partially connected.

### Runtime-Bounded Exact Replay Contract

The sourceTopK mechanism is quality-oriented, but it must leave enough time for
handoff consumers and final reporting.  A reconstruction that times out inside
exact GS profiling is not a completed warm-up method.  Use this structure:

1. Profiling pass: scan the broad shuffled source list, build the same ranked
   per-source bbox/median candidate pool, exact-score only a few candidates per
   source, replay the best positive candidate through the normal accept path,
   then undo the profiling journal to restore the initial state before the
   applied pass.
2. Applied exact pass: rerun the broad sourceTopK loop under the budgeted
   objective.  Use per-source top-K, pass elapsed/gain-rate guards,
   rollback/replay counters, and accepted-delta-per-runtime logs.  If a global
   admission stage is added, it is a runtime optimization only and must not
   reduce the producer to a small sampler.
3. Budgeted refinement: use the profiling optimum to set a budget and optionally
   taper congestion/random exploration.  The exact sourceTopK lane remains live
   even when congestion/random exploration is off.
4. Handoff and consumers: after accepted replays appear, immediately export
   cumulative hot segments and run selected reorder.  The export must accumulate
   all accepted transactions from the pass, not just the last replay journal.
   Do not spend all runtime proving producer liveness while starving the first
   consumer.  Accepted-node export and exact local closure are optional
   continuation repairs after the hot-segment reorder path is live.
5. If the exact path is live but stalls before the first counter block or before
   vertical/reorder/final stages, the next repair is runtime structure: cheaper
   per-source candidate construction, target-row/segment pruning, elapsed-time
   guard, and gain-rate stop.  Do not pivot to guard work or add continuation
   consumers before the core flow completes.

### Acceptance-Critical SourceTopK Details

The common failed reconstruction is a producer that visits many cells but never
creates a positive replay.  Avoid that shape.  SourceTopK means "rank a compact
candidate set per source, then exact-score the best few"; it does not mean
"take the first few legal positions found while scanning row segments".

For each source cell:

1. Use `getRange` to build the source's median/bbox target range and compute
   whether the current cell center is outside that target range.  Skip only
   cells already inside the range.
2. Clip the bbox by max displacement, but keep the target direction.  Build
   target rows around the closest target row, not only around the current row:
   target row, one row above/below, and optionally two rows above/below when
   the route intentionally spends more quality runtime.
3. Build x anchors from bbox-left, bbox-center, and bbox-right converted to
   legal cell-left positions.  Use `DetailedMgr::alignPos` against the chosen
   segment limits; do not just clamp the anchor to a segment boundary.  Drop
   anchors that violate displacement or preserve the exact current placement.
4. Before exact scoring, attach cheap ranking features to each candidate:
   reduction in outside-bbox Manhattan distance, distance to bbox center, and
   move distance.  Deduplicate candidates by row, segment, bottom, and aligned
   left.  Sort by larger outside-bbox-distance reduction first, then smaller
   center distance, then smaller move distance.
5. Exact-score only the first per-source top-K candidates after that ranking.
   A typical first reconstruction uses a small top-K and a slightly larger
   pre-ranked candidate pool, but it must still repeat this process for the
   full shuffled single-height-cell list.
6. Probe `tryMove` first.  Only if the move fails or the candidate is explicitly
   swap-only, probe `trySwap` into the same candidate position.  Score the
   current journal with the same `DetailedHPWL` object owned by the current
   global-swap pass.  Roll back every probe immediately after scoring.
7. Replay the best positive candidate by rerunning the same `tryMove`/`trySwap`
   probe from the current placement, not by treating probe-only data as an
   accepted result.  Re-score the replay; only then mark the move as a
   sourceTopK replay and allow the normal global-swap accept path to accept or
   reject it.

Pseudocode for the intended producer core:

```text
for source in shuffled single-height cells:
  cheap = bbox/median pressure + row feasibility + displacement headroom
  record cheap_profiled(source, cheap)
  if profiling_pass and not small_sample_slot: continue
  if not admit_source(cheap, source_budget, elapsed_budget, gain_rate): continue
  bbox = median target range excluding source
  if source center inside bbox: continue
  bbox = bbox clipped by max displacement
  candidates = []
  for row in admitted_target_rows(source, bbox):
    for segment in nearby_legal_segments(row, bbox anchors):
      for anchor in [bbox_left, bbox_center, bbox_right]:
        aligned_left = alignPos(source, anchor - source_width/2, segment)
        if displacement/legal/current-placement filters pass:
          rank = outside_bbox_distance_reduction, center_distance, move_distance
          candidates.push(row, segment, aligned_left, rank)
  sort/dedup candidates by rank
  for candidate in first topK while exact_probe_budget remains:
    if tryMove succeeds:
      delta = pass_hpwl.delta(journal)
      rejectMove()
      remember best positive move delta
    else if trySwap succeeds:
      delta = pass_hpwl.delta(journal)
      rejectMove()
      remember best positive swap delta
  if best positive exists:
    rerun the same move or swap candidate
    replay_delta = pass_hpwl.delta(journal)
    if replay_delta > 0:
      mark the replay as sourceTopK and let the normal accept path decide
      if the accept path accepts:
        append moved nodes, old/new segments, and replay_delta to pass frontier
        update cumulative accepted-node/hot-segment masks and delta totals
    else:
      rejectMove()
```

Diagnostic rule: if a run shows high generated/exact-scored counts but
`replay_attempts`, `accepts`, and `accepted_delta` stay at zero, the producer is
not yet reconstructed.  Repair candidate ranking, target-row/anchor selection,
`alignPos`, move/swap replay, or delta sign before adding consumers.  Do not
call selected reorder or residual closure the main mechanism when the producer
has no accepted replay payload.

### Handoff And Consumer Shape

- While each accepted sourceTopK journal is still live, collect moved nodes and
  old/new segment ids from every `MoveCellAction`.  Append or merge these records
  into a pass-local frontier instead of replacing the previous frontier.  Sort,
  deduplicate, and rank the accumulated frontier before storing or exposing it
  in `DetailedMgr`.
- Store hot segments separately from critical-frontier nodes.  Critical nodes
  are the high-delta moved nodes; hot segments are the old/new segments touched
  by accepted sourceTopK transactions.  Consumers should be able to use either
  one without losing the other.
- Focused reorder should prioritize hot segments first and use only a bounded
  fallback after the hot-frontier budget.  Cap reorder window size to a small
  exact window and log hot-frontier windows separately from fallback windows.
  If accepted producer counters are high but hot-frontier windows are tiny,
  repair handoff lifetime before tuning reorder constants.
- Exact local closure is the first required post-DPO consumer after hot-segment
  reorder.  It operates on producer-created accepted nodes and hot segments; it
  should not become a broad all-design closure if the sourceTopK producer is
  weak.
- Critical-row, critical-net, multi-row, and residual-swap consumers are
  continuation consumers.  Add them only after the core sourceTopK -> native
  handoff -> selected reorder -> exact local closure chain is live, or when the
  current source already has a clean implementation surface.  They must use the
  same accepted/hot/critical footprint and exact rollback/replay.

### Source Handles And First Edits

- `src/Optdp.cpp::Opendp::improvePlacement`: schedule exact GS and selected
  reorder first; force the exact `gs` path for this route; own route-level
  counters and HPWL checkpoints.  Add exact local closure, micro-start, chain,
  multi-row residual, and segment-local residual only as continuation passes
  after the core sourceTopK -> hot-segment reorder chain works.
- `src/optimization/detailed_global.{h,cxx}`: exact sourceTopK/source-edge
  producer, intensity/legacy fallback repair, full single-height-cell pass
  iteration, per-source top-K exact scoring, rollback/replay, and hot-segment
  export from accepted journals.
- `src/optimization/detailed_manager.{h,cxx}`: native storage and clear/get/append
  APIs for hot segments first; accepted nodes, critical-frontier nodes, optional
  touched nets, and accepted delta are continuation payloads.
- `src/optimization/detailed_reorder.{h,cxx}`: selected hot-segment reorder is
  the required first consumer.  Exact local closure, critical-row micro-start,
  critical-net chain assignment, multi-row residual transactions, and
  segment-local residual swaps are continuation consumers over the same
  footprint.
- `src/objective/detailed_hpwl.{h,cxx}`: exact affected-net delta hygiene and
  cache reset for repeated journal probes.
- `src/optimization/detailed.cxx`: confirm the normal `gs`/`ro` script path calls
  the enhanced producer and hot-frontier reorder rather than bypassing it.

### Minimum Implementation Contract

A Student has not implemented this warm-up method unless all of these are true:

- Start branch is `diamond` for first reconstruction.  A modest legal-stage
  HPWL rise is compatible with this warm-up method when legality is clean and
  improve placement has a large recoverable basin.
- SourceTopK/global-swap exact producer runs with nonzero generated,
  exact-scored, accepted, accepted-delta, replay-failure/rollback, and
  hot-segment counters.
- Hot-segment counters reflect the cumulative accepted footprint after dedupe,
  not just the final accepted journal.  Many accepted replays with only one or
  two surviving segments means the producer is live but the handoff lifetime is
  wrong.  Accepted-node counters are useful but not required for the first
  sourceTopK + selected-reorder reproduction.
- Runtime stays bounded enough for the full detailed-placement flow to finish.
  A trial that proves exact GS dispatch or sourceTopK liveness but times out in
  profiling, before vertical swap, before reorder, before mirror, or before final
  reporting is only negative/runtime evidence, not a completed strong-chain
  reconstruction.  Repair per-source candidate construction, exact-probe caps,
  target-segment pruning, and gain-rate stop before adding consumers.
- Large sourceTopK accept counts and large accepted delta are not sufficient.
  If accepted nodes/hot segments scale and focused reorder consumes them, but
  `HPWLimprove` is worse than OpenROAD or final HPWL regresses, the missing link
  is high-quality sourceTopK producer ranking rather than handoff liveness.
  Rebuild per-source target rows and bbox-left/center/right anchors, rank by
  outside-bbox-distance reduction before exact scoring, and accept fewer
  higher-quality transactions before adding continuation consumers.
- Selected reorder consumes hot segments from the exact producer and reports
  hot-frontier effort separately from bounded fallback effort.
- The first one-student reproduction may stop after sourceTopK + selected
  reorder if it builds, evaluates, and gives a material final HPWL drop.  If the
  drop is weak, repair the sourceTopK producer or hot-segment handoff quality
  before adding optional exact local closure or residual consumers.
- The implementation does not stop at cap widening, selected reorder only,
  telemetry, or local closure without a live sourceTopK accepted payload.  Those
  are partial links, not the warm-up method.
- The final report includes per-link counters and HPWL checkpoints so Teacher can
  locate whether the miss is producer quality, handoff lifetime, consumer
  candidate quality, transaction granularity, accepted-delta washout, or final
  preservation.

### Required Counters And Diagnosis

Report these counters in logs and in the final card:

- `source_topk_sources_seen`, optional `source_topk_sources_admitted` only when
  a broad admission/ranking stage is actually implemented,
  `source_topk_generated`,
  `source_topk_exact_scored`, `source_topk_replay_attempts`,
  `source_topk_replay_failures`, `source_topk_rollbacks`,
  `source_topk_accepts`, `source_topk_accepted_delta`,
  `source_topk_elapsed_ms`, `source_topk_gain_per_runtime`, `hot_segments`, and
  optional `accepted_nodes` when a node-footprint handoff is implemented.
- `selected_reorder_frontier`, `selected_reorder_windows`,
  `selected_reorder_accepts`, `selected_reorder_gain`, plus hot-frontier versus
  fallback windows/accepts/gain when the implementation has fallback work.
- Optional `exact_closure_windows/accepts/gain` when exact closure is implemented.
- For optional continuation consumers when implemented:
  `critical_micro_start_probes/accepts/gain`,
  `critical_net_chain_probes/accepts/gain`,
  `multi_row_residual_probes/accepts/gain`,
  `segment_residual_swap_probes/accepts/gain`.
- HPWL checkpoints before exact GS, after exact GS, after selected reorder, after
  each residual consumer, and after mirror/final.

Self-diagnose from those counters:

- Producer counters zero or tiny: repair `gs` dispatch, intensity fallback, and
  sourceTopK candidate generation before touching consumers.
- Exact GS dispatch is live but profiling times out or no final report appears:
  the producer is overbuilt.  Make candidate construction cheaper, cap exact
  probes per source/pass, prune target rows/segments, and add
  accepted-delta-per-runtime/gain-rate stop before changing route.
- Legal HPWL rises modestly but sourceTopK/reorder final HPWL improves strongly:
  keep the route on DPO producer/handoff/consumer; do not pivot to legalizer
  repair just to lower `HPWLlg`.
- Legal HPWL rises badly or displacement tails grow and the DPO chain is already
  live but cannot recover: keep the live DPO chain as a regression check, then
  consider a bounded legal-basin repair.  The proof target is lower final HPWL,
  not lower `HPWLlg` alone.
- Producer counters live but only a small global source pool was visited: remove
  the global source cap and restore all-cell pass iteration with per-source
  top-K bounds.
- Producer counters live but runtime times out before downstream stages: keep
  the same mechanism, but repair exact scoring cost.  Use move-before-swap
  probing, small pre-ranked candidate pools, gain-rate stop, and accepted-delta
  density to preserve quality while allowing selected reorder and residual
  consumers to run.
- Producer generated/exact-scored counts are high but replay attempts or accepts
  are zero: the route is live but the candidate ordering or replay semantics are
  wrong.  Rebuild the ranked per-source target rows/anchors, `alignPos`, exact
  move/swap probe, rollback, and positive replay path before touching handoff or
  consumers.
- Producer accepts large but final HPWL small: do not repeat cap widening; repair
  cumulative accepted-frontier export, consumer transaction granularity, hot
  consumer scope, or final preservation.
- Producer accepts and accepted delta are large, accepted-node/hot-segment
  handoff scales, and hot-frontier reorder is dominant, but final HPWL is flat
  or worse: this is accepted-delta washout from a low-quality producer, not a
  handoff or consumer-liveness failure.  Keep the dispatch/handoff/reorder
  chain, but replace broad source enumeration with ranked per-source sourceTopK:
  target rows around the bbox/median direction, bbox-left/center/right anchors
  aligned to legal segments, outside-bbox reduction ranking, move-before-swap
  exact replay, and accepted-delta-per-runtime stop.
- Selected reorder consumes few hot segments: repair accepted journal capture and
  `DetailedMgr` lifetime.  Broad fallback reorder is not proof of D+A consumer
  success when hot-frontier windows are tiny.
- Consumer accepts are sparse: rank by accepted-delta density, critical-net span,
  bbox-edge cells, and displaced frontier cells; use multi-row or chain
  transactions rather than single-cell local closure only.
- Runtime grows without final HPWL: reduce low-yield windows but keep the
  strongest exact transaction families; runtime repair is only useful if it
  preserves quality search.

### Reconstruction Sketch

```text
improvePlacement:
  importDb/initGrid/ShiftLegalizer as usual
  run Detailed script with enhanced exact sourceTopK/global-swap enabled
    for every shuffled single-height source cell in each pass:
      get median/bbox range and clip by displacement
      generate a small per-source set of row/segment/bbox anchors
      exact-score move/swap probes with DetailedHPWL::delta and journal rollback
      replay best positive transaction through the normal accept path
      export accepted nodes, old/new segments, hot segments, accepted delta
  selectedSegmentReorder(hot_segments)
  criticalRowMicroStart(critical_frontier, hot_segments)
  criticalNetChainAssignment(critical_frontier, touched_nets)
  exactLocalClosure(accepted_nodes + critical_frontier, hot_segments)
  multiRowResidualTransactions(critical_frontier, nearby rows)
  segmentLocalResidualSwaps(accepted/critical footprint)
  updateDbInstLocations and report final HPWL
```

## Blueprint A: Runtime-Balanced Critical-Frontier Exact DPO Stack

### Use When

Use Blueprint A when sourceTopK/global-swap exact accepts or another producer has
created a recoverable accepted-node/hot-critical frontier, and final HPWL is
DPO/post-DPO-frontier dominated.  For one-student first-shot reconstruction on
large row-rich Diamond-friendly cases, use Blueprint D+A instead of assigning
Blueprint A separately.  This is the continuation/value-consumer stack
for large row-rich/control/datapath and wrapper-fragmented cases.  It is not the
first activation path for a missing sourceTopK producer; use Blueprint D+A when sourceTopK/global-swap counters are absent, gated, or tiny and the Student must reconstruct the full warm-up chain.  Use standalone Blueprint D only when the task is explicitly scoped to producer activation.

### Start Basin

- `diamond` or a current live Diamond donor when sourceTopK/global-swap
  exact DPO and selected reorder are already live.
- `framework` only when LEGALM/differential/row-assignment producer payload is
  explicitly the missing frontier and the exact consumer is planned.
- Avoid negotiation starts unless endpoint/source recoverability is the useful
  payload; that is Blueprint B.

### Mechanism Chain

1. Keep the exact sourceTopK/global-swap or equivalent producer live in the
   normal improve-placement flow.
2. Export accepted moves before journal cleanup: accepted nodes, touched nets if
   available, source/topK cells, old/new hot segments, accepted delta, and
   critical-frontier nodes.
3. Store the payload in `DetailedMgr` using native ids and de-dup masks.
4. Run selected-segment reorder over hot segments.
5. Run the post-DPO critical-frontier stack in `Opendp::improvePlacement`:
   critical-row micro-start -> critical-net chain assignment -> exact local
   closure -> multi-row residual transactions -> segment-local residual swaps.
6. Log HPWL before/after each link and clear hot/critical state only after the
   late links finish.

### Implementation Checklist

- `DetailedGlobalSwap`: while accepted sourceTopK moves are still in the
  journal, collect moved nodes, touched nets if available, old/new segment ids,
  and exact accepted delta.  Sort high-delta moved nodes into a critical
  frontier, set hot segments from old/new segments, and append both to
  `DetailedMgr`.
- `DetailedMgr`: provide clear/get/append APIs for accepted move nodes,
  critical-frontier nodes, and hot segments.  Keep masks for de-duplication and
  preserve lifetime through all post-DPO consumers.
- `runCriticalRowMicroStart`: consume critical frontier and hot segments; choose
  displaced single-height frontier cells; target bbox/median anchors in current
  or nearby rows; exact-score each trial through the placement journal; apply
  only positive adjusted deltas; append affected nodes/segments back into the
  native frontier.
- `criticalNetChainAssignment`: build exact two- or three-step chains as one
  transaction: seed toward bbox/median target, local partner into seed vacancy,
  optional follower into partner vacancy.  Reject nonpositive replay.
- `exactLocalClosure`: merge accepted and critical nodes, generate small reorder
  windows over hot/frontier segments, prioritize displaced and edge-touching
  windows, exact-score with rollback, and attribute gain to base versus
  micro-start/critical segments.
- `multiRowResidualTransactions`: search bounded current/nearby-row
  transactions with local partners and exact transaction replay.
- `segmentLocalResidualSwaps`: try only local neighbors around the accepted or
  critical footprint to preserve and extend earlier DPO gains.

### Counters And Diagnosis

- Required counters: sourceTopK/global-swap generated/exact-scored/replayed/
  accepted/accepted-delta; accepted nodes; hot segments; critical frontier;
  selected reorder windows/accepts/gain; micro-start probes/accepts/gain;
  chain probes/accepts/gain; exact closure windows/accepts/gain; multi-row
  probes/accepts/gain; residual swap probes/accepts/gain.
- If producer counters are absent, repair Blueprint D or the producer first.
- If producer is live but consumer accepts are zero, repair native handoff
  lifetime or candidate generation.
- If accepts are live but final HPWL is flat, repair transaction granularity,
  candidate quality, or canonical replay/preservation rather than widening caps
  only.
- If only sourceTopK, selected reorder, or local closure exists, Blueprint A is
  only partially reconstructed; the full mechanism is the post-DPO
  critical-frontier stack above.

### Reconstruction Sketch

```text
source_topk_or_live_producer:
  exact-score bounded move/swap candidates
  replay only positive transactions
  export accepted nodes, touched nets, hot segments, critical nodes

critical_frontier_stack:
  selected-segment reorder on hot segments
  micro-start displaced frontier cells toward bbox/median anchors
  apply exact multi-step critical-net chains
  close merged frontier with exact local windows
  apply multi-row residual transactions
  finish with local residual swaps around accepted/critical footprint
```

## Blueprint B: Negotiation Recoverability Plus Endpoint/Source Exact Consumer Stack

### Use When

Use Blueprint B when endpoint/source residue, top-net imbalance, or
fragmented/wrapper-style legal pressure indicates that a negotiation-like legal
basin can create recoverable endpoint/source payload.  The mechanism is not a
negotiation-weight tweak: negotiation must produce a payload that exact DPO,
reorder, replay, and endpoint/source repair consume.

### Start Basin

- `default_negotiation` for first reconstruction of the resource/endpoint
  producer.
- Start from `default_negotiation` and rebuild the recoverability producer plus
  exact consumer/replay chain in the current source.
- Keep large row-rich cases eligible when endpoint/source residue is visible;
  size alone should not demote this route.

### Mechanism Chain

1. Run negotiation/resource closure as the legalizer producer.
2. Inside negotiation, rank moderate-degree high-span/top-impact nets and mark
   first/second bbox-extrema endpoint/source cells.
3. Apply a bounded recoverability bonus in target selection, damped by
   displacement growth and local slack; log selected, damped, and reverted
   choices.
4. Run exact source-edge/global-swap after the negotiation legal state.  Rank
   source-edge/boundary cells, enumerate row/segment/bbox/median/swap targets,
   exact-score bounded candidates, rollback probes, replay positives, and export
   accepted nodes, source-edge hot-cell masks, and hot segments.
5. Run hot selected-segment reorder and hot micro-pack over accepted hot
   segments/source-edge cells.
6. Store accepted reorder/micro-pack windows as replay seeds; run residual
   replay, then a cascade pass around accepted seeds.
7. Run post-reorder endpoint/source repair.  Import incoming hot segments and
   source-edge masks before they are cleared, rank top nets touching the
   frontier, derive first/second-extreme endpoint targets, and exact-score
   endpoint/source moves.
8. When single-cell endpoint moves are live but too local, add bounded pair or
   small-cluster exact transactions over the same frontier.

### Implementation Checklist

- `NegotiationLegalizer*`: recoverability producer, endpoint/source target
  identification, local slack, displacement damping, and producer counters.
- `DetailedGlobalSwap`: exact source-edge/global-swap consumer and handoff export
  from the negotiation legal state.
- `DetailedMgr`: accepted nodes, hot segments, source-edge hot-cell masks, and
  incoming handoff lifetime through reorder/replay/repair.
- `DetailedReorderer`: hot-segment reorder, hot micro-pack, accepted-window
  replay, replay cascade, endpoint/source local transactions.
- `Optdp.cpp`: pass order and preservation of incoming handoff through
  source-edge GS, reorder, micro-pack, replay, endpoint repair, and cleanup.

### Counters And Diagnosis

- Required counters: negotiation recoverability top nets/cells/scored/selected/
  damped/reverted/slack; source-edge GS candidates/exact scores/accepts/delta;
  source-edge hot masks; hot reorder windows/accepts/gain; micro-pack windows/
  accepts/gain; replay seeds/pass1/cascade/pass2 accepts; endpoint targets/
  accepts/gain; pair/cluster candidates/accepts/gain.
- Source-edge accepts zero: repair source-edge candidate generation and exact
  replay before tuning negotiation weights.
- Hot reorder/micro-pack zero: repair hot-segment export/import.
- Producer live but endpoint accepts flat: repair handoff lifetime or endpoint
  target generation.
- Endpoint accepts live but final HPWL flat: use pair/small-cluster exact
  transactions over the same top-net frontier.
- Displacement tail grows sharply: damp recoverability bonus and reject endpoint
  extensions unless exact gain pays for them.

## Blueprint C: Low-Residual Current-Net / Vertical-Frontier Consumer

### Use When

Use Blueprint C for dense/high-utilization cases where LEGALM/full guidance
creates target-miss, current-net, exact-anchor, or stage3 handoff state that
downstream DPO can consume.  Density alone is not enough; require visible or
intentionally rebuilt low-residual target/current-net payload.

### Start Basin

- `framework`, because this route reconstructs the current LEGALM/full-guidance
  producer and its DPO consumer inside the current source.
- Do not select a separate non-current LEGALM start.
- If current-net/target-miss/vertical-frontier payload is absent, either rebuild
  that producer state or use another blueprint.

### Mechanism Chain

1. Run LEGALM/full guidance as a recoverable producer, not as a legalize-only
   objective.
2. Publish target rows, target sites, valid flags, exact-anchor flags,
   target-miss cells, moved/stage3 handoff cells, and current-net anchor state
   in `Opendp`.
3. Add stage3 exact/current-net refinement.  Use target rows/sites, current-net
   anchors, target-miss cells, nearby rows, and displacement-aware legality to
   apply only exact-positive producer moves.
4. In `improvePlacement`, import the target/current-net state and build compact
   row-miss, same-row residual, exact-anchor, dirty-segment, and target-miss
   frontiers.
5. Run targeted exact global and vertical wrappers over that frontier with
   rollback/replay.
6. Rank residual segments by exact-anchor count and residual magnitude; run
   selected-segment exact reorder and optional local transactions only on those
   segments.
7. Clear stale affected-net state before each `DetailedHPWL::delta` probe.

### Implementation Checklist

- `LegalmFullLegalization.cpp`: stage3 exact refinement, target-miss frontier,
  current-net anchor generation, exact scoring, producer counters.
- `Opendp.h`: target rows/sites/valid flags, exact-anchor flags, target-miss
  state, stage3 handoff counts.
- `Optdp.cpp`: imported frontier construction, row-miss and same-row queues,
  targeted global/vertical wrappers, selected-segment reorder schedule, logs.
- `detailed_vertical.{h,cxx}`: targeted vertical candidates and rollback.
- `detailed_global.{h,cxx}` and `detailed_hpwl.{h,cxx}`: targeted exact global
  moves and safe affected-net delta.
- `detailed_reorder.{h,cxx}`: selected-segment exact reorder and anchor-local
  transactions.

### Counters And Diagnosis

- Required counters: stage3 exact refinement enabled/frontier/scored/accepts;
  target misses; target-gain sites; current-net anchor terms/candidates/scored/
  moves; legal/static/displacement rejects; inherited handoff cells; imported
  frontier size; exact-anchor cells; target-miss cells; vertical/global scored
  moves/accepts/gain; selected residual segments/windows/transactions/accepts.
- Producer counters zero: repair target-valid/current-net publication.
- Producer live but frontier consumer sees no cells: repair `Opendp` handoff
  lifetime and id mapping.
- Frontier moves score but accept zero: improve candidate quality or exact
  objective.
- Legal HPWL improves but final worsens: the legalizer produced a DPO-hostile
  basin; repair downstream consumability rather than promoting `HPWLlg`.

## Blueprint D: Diamond SourceTopK/Source-Edge Exact DPO Activation

### Use When

Use Blueprint D only when the assignment is explicitly scoped to activating the
Diamond-family exact DPO producer.  For one-student warm-up on large row-rich
cases, use Blueprint D+A instead so producer activation and post-DPO consumers
are implemented in one chain.  The typical signature is legal HPWL neutral or
worse, large potential recovery in `HPWLimprove`, and absent/gated/tiny
sourceTopK/global-swap counters.  D is a producer-reconstruction packet; it is
not the complete strong-chain route by itself.

### Start Basin

- `diamond` is the preferred basin when the target feature class is the large
  row-rich/control/datapath value route.  Preserve the fast clean Diamond
  legalizer and activate exact DPO first; a modest legal-HPWL rise is acceptable
  when the DPO producer has recoverable HPWL to consume.
- If exact DPO and selected reorder are already live but final HPWL still fails
  because legalization creates destructive displacement tails, then consider a
  bounded legal-basin repair.  Do not make legalizer scoring the first Blueprint
  D edit merely because `HPWLlg` is above `HPWLg`.
- Do not use `framework` unless a LEGALM/current-net producer is explicitly the
  selected payload.  Do not use negotiation unless endpoint/source
  recoverability is the selected payload.

### Mechanism Chain

1. In `Opendp::improvePlacement`, make the enhanced exact global-swap lane
   reachable from the normal DPO script.
2. Prevent density/intensity dispatch from falling back to weak legacy global
   swap.  A small exact-lane intensity floor is acceptable; random/congestion
   exploration may stay conservative.
3. In `DetailedGlobalSwap`, keep the all-cell global-swap pass over shuffled
   single-height cells.  Bound the per-source target list; do not cap the whole
   pass to a tiny ranked-source pool.
4. For each source cell, derive median/bbox targets with `getRange`, clip by
   displacement, and generate current/target/near-row bbox left/center/right
   anchors on legal segments.
5. Exact-score bounded per-source probes with `DetailedHPWL::delta()` on the
   current journal.  Try a legal move first; try same-width/same-height swap only
   as a fallback for a candidate that cannot be moved directly.  Roll back
   probes, replay only the best positive transaction, re-score the replay, and
   reject nonpositive or illegal replay.
6. Before accepted journal cleanup, export moved nodes, old/new segment ids, and
   accepted delta into `DetailedMgr` as native accepted-node/hot-segment state.
7. Run selected-segment reorder immediately after global swap over those hot
   segments and log frontier/windows/accepts/gain.
8. For large row-rich recoverable cases, do not stop at Blueprint D if one
   Student is responsible for the warm-up method.  Continue immediately into the
   Blueprint D+A post-DPO consumers over the same native footprint: critical-row
   micro-start, critical-net chain, exact closure, multi-row residual
   transactions, and segment-local residual swaps.  These consumers complement
   the producer; they do not replace it.

### Implementation Checklist

- `Optdp.cpp::Opendp::improvePlacement`: DPO script path, enhanced global-swap
  enablement, `DetailedMgr` setup, and handoff lifetime.
- `detailed_global.{h,cxx}`: route selection, intensity/legacy fallback,
  all-cell source iteration, per-source candidate generation, top-K exact
  scoring, rollback/replay, accepted counters, hot-segment export.
- `detailed_hpwl.{h,cxx}`: exact affected-net delta reset per probe.
- `detailed_manager.{h,cxx}`: native accepted-node and hot-segment append/clear
  APIs and lifetime until reorder consumes them.
- `detailed_reorder.{h,cxx}`: selected-segment reorder over hot segments and
  bounded residual windows.
- `detailed.cxx`: confirm the normal DPO script calls the global-swap
  implementation containing this sourceTopK kernel.

### Counters And Diagnosis

- Required stage tuple: `HPWLg`, `HPWLlg`, `HPWLimprove`, `HPWLfinal`, legality,
  runtime, avg/max displacement.
- Required producer counters: cells considered, generated candidates,
  exact-scored probes, replay attempts, replay failures, rollbacks, accepts,
  accepted delta.
- Required handoff/reorder counters: accepted nodes, hot segments generated,
  hot segments consumed, selected reorder frontier/windows/accepts/gain.
- A strong large-row-rich hit shows high-throughput producer liveness: many
  generated candidates, many exact scores, many positive accepts, large accepted
  delta, and most HPWL movement by `HPWLimprove` before mirror/final cleanup.
- No sourceTopK/exact-GS counters: repair pass selection, extra-DPL enablement,
  and intensity/legacy fallback.
- Candidates exist but exact scores are tiny: repair row/segment/bbox candidate
  enumeration and per-source top-K filtering.
- Counters are live but only thousands of generated probes appear on a large
  row-rich case: remove a global ranked-source cap and restore the normal
  all-cell pass.
- Exact scores large but accepts tiny: inspect exact delta reset, displacement
  limits, move-before-swap fallback, candidate target quality, and replay
  legality.
- Accepts live but final HPWL flat: add ordered-pair/source-edge repairs or move
  to Blueprint A residual frontier consumers over the same accepted footprint;
  do not only widen source caps.
- Selected reorder has no hot frontier: repair accepted-journal capture and
  `DetailedMgr` hot-segment lifetime.
- If most code changes are LEGALM, negotiation, mirror, telemetry, guard, or
  cap-only while sourceTopK counters remain absent/small, the implementation has
  drifted away from Blueprint D.
