# Mechanism Reconstruction Roadmap

## Agent Use

- Role: direct Teacher/Student reconstruction core after Teacher selects a
  blueprint from `case_type_quality_mechanism_priority.md`.
- Open only the selected blueprint section during ordinary routing.
- These are implementation roadmaps, not fixed recipes.  Student may redesign
  local details after inspecting the current source, but must preserve the
  complete producer-handoff-consumer logic and prove liveness with counters.

## Shared Source Anchors

Use these anchors inside the private `dpl_evolve` source prepared for the
Student workspace.

- Flow composition: `src/StudentAlgorithm.cpp` and
  `Opendp::runStudentAlgorithm` for the legalizer/improve/mirror sequence.
- Top-level state: `src/Opendp.cpp` and `include/dpl_evolve/Opendp.h` for
  persistent handoff fields, target arrays, displacement limits, and metrics.
- LEGALM/differential producer: `src/LegalmGuidance.cpp`,
  `src/DifferentialGuidance.cpp`, `src/LegalmFullLegalization.cpp`, and
  `src/LegalmRowAssignment.cpp` for target shaping, pressure, target release,
  and recoverable frontier production.
- Negotiation producer: `src/EvolveNegotiationRepair.cpp`,
  `src/NegotiationLegalizer.cpp`, `src/NegotiationLegalizerPass.cpp`, and
  `src/NegotiationLegalizer.h` for resource/conflict closure and endpoint
  recoverability scoring.
- Improve-placement schedule: `src/Optdp.cpp::Opendp::improvePlacement` for
  exact-DPO pass order and handoff import.
- Exact consumers: `src/optimization/detailed_global.{h,cxx}`,
  `src/optimization/detailed_reorder.{h,cxx}`,
  `src/optimization/detailed_vertical.{h,cxx}`,
  `src/optimization/detailed_manager.{h,cxx}`,
  `src/optimization/detailed_random.{h,cxx}`, and
  `src/objective/detailed_hpwl.{h,cxx}`.
- Native state: prefer `Node*`, `Edge*`, segment ids, row ids, accepted journal
  records, manager masks, and touched-net lists.  Avoid string-keyed handoff
  maps or bulky coordinate logs when native ids can carry the state.

Every route should log compact counters: producer count, handoff produced and
consumed, exact probes/scores, exact accepts, accepted HPWL gain or delta,
rollback/reject count, pass runtime, and enough fields to compute accepted gain
per runtime.

## Blueprint A: Runtime-Balanced Critical-Frontier Exact DPO Stack

Use when final HPWL is DPO-dominant: improve placement recovers a large stage
loss, the legalizer state is recoverable, and exact source-topK or hot/critical
frontier consumers can operate.  This route is the default strong route for
row-rich/control/datapath, wrapper-fragmented, and runtime-sensitive cases unless
evidence specifically points to negotiation or low-residual LEGALM target-miss
behavior.

### Start Basin

- Start from `framework` when the current route needs a producer/frontier
  payload from LEGALM, differential guidance, or row assignment.
- Start from `evolved_diamond` when source-topK exact DPO already executes and
  the missing work is downstream frontier closure.
- Do not start from negotiation unless current evidence proves negotiation is
  the useful producer; otherwise use Blueprint B only as a separate hypothesis.

### Mechanism Chain

1. Keep the exact source-topK/global-swap path live in the normal improve flow.
   Do not let density/intensity heuristics silently fall back to legacy DPO when
   source-topK or critical-net residue is visible.
2. Exact-score candidate moves/swaps with `DetailedHPWL` or a touched-net
   journal.  Roll back every probe and replay only exact-positive candidates.
3. Convert accepted DPO moves into native manager state: accepted nodes, touched
   nets, source/topK cells, and hot or critical segments.
4. Build a merged frontier from accepted DPO nodes plus critical-net endpoint
   nodes.  If producer shaping is needed, append only cells/segments that the
   exact consumer can later score.
5. In `Opendp::improvePlacement`, run the post-DPO chain in this order:
   critical-row micro-start, critical-net chain assignment, exact local closure,
   multi-row residual transactions, and segment-local residual swaps.
6. Each consumer must exact-score with rollback and accept only positive deltas.
   A residual swap or guard pass is not the mechanism unless the earlier links
   are live.

### Reconstruction Sketch

```text
source_topk_exact_pass():
  rank movable cells by affected-net HPWL, bbox-edge contribution,
  fanout-normalized span, displacement risk, and recent DPO movement
  generate bounded row/site/swap targets from medians, bbox edges, current row,
  neighbor rows, and legal segment centers
  exact-score each trial, rollback, replay the best positive trial, and record
  accepted node/touched-net/segment/delta state in DetailedMgr

critical_frontier_stack():
  merge accepted-DPO nodes with critical-net endpoints and hot segments
  micro-start high-value frontier cells into recoverable legal anchors
  chain from each accepted move to newly exposed critical endpoints
  close touched segments with exact reorder/shift
  run bounded multi-row residual transactions over connected touched-net
  components
  finish with small segment-local swaps only around the accepted footprint
```

### Source Handles

- `src/Optdp.cpp::Opendp::improvePlacement`: schedule the source-topK pass and
  the post-DPO chain; log per-link metrics.
- `src/optimization/detailed_global.cxx`: exact source-topK/global-swap
  candidate generation, scoring, replay, and `DPL-0926`-style counters.
- `src/optimization/detailed_manager.{h,cxx}`: accepted-node, hot-segment,
  critical-frontier, and source-topK native state.
- `src/optimization/detailed_reorder.cxx`: critical-row micro-start,
  critical-net chain assignment, exact local closure, multi-row residual
  transaction, and segment-local residual swap.
- `src/LegalmRowAssignment.cpp` or producer code only when current evidence says
  producer/frontier shaping is missing.

### Required Counters

- source-topK/global-swap candidates, exact scores, replays, accepts, accepted
  delta, and replay rejects;
- critical-frontier nodes/segments and merged frontier nodes/segments;
- micro-start probes/accepts/gain;
- chain assignment probes/accepts/gain;
- exact closure windows/probes/accepts/gain;
- multi-row residual probes/accepts/gain;
- segment-local residual swap probes/accepts/gain;
- final HPWL and runtime after canonical full-flow evaluation.

### Self-Diagnosis And Repair

- Producer live but consumer accepts zero: repair native handoff state or exact
  candidate generation before changing weights.
- Exact accepts live but final HPWL flat: repair candidate quality, transaction
  granularity, or canonical replay/restore; do not only widen caps.
- Residual swaps tiny: change move family or transaction shape around the merged
  frontier; do not retune seed priority inside the same saturated set.
- Runtime too high without accepted gain: cache affected-net deltas, prune by
  gain rate, or narrow frontier while keeping the full mechanism chain.

## Blueprint B: Endpoint-Source Handoff Exact Consumer Stack

Use when endpoint/source residue and top-net imbalance are visible and
negotiation/resource closure is the useful legal producer.  This is a high-HPWL
quality route for short or medium cases with enough runtime headroom.  It is not
a generic response to large improve-stage recovery; if negotiation is not the
producer, use Blueprint A.

### Start Basin

- Start from `default_negotiation` or `evolved_negotiation` when current stage
  evidence shows negotiation/resource closure leaves a better recoverable legal
  basin.
- If continuing an existing donor, preserve the complete accepted-window replay
  chain rather than restarting from a guard or attribution commit.

### Mechanism Chain

1. In negotiation, rank top high-HPWL nets and endpoint/source cells.  Add a
   bounded recoverability bonus to legal location scoring, damped by
   displacement and legality risk.
2. Preserve the produced source-edge/hot-cell information in native manager
   state through legal closure and into improve placement.
3. Run exact source-edge/global-swap.  It must score direct moves and swaps with
   exact journal/touched-net HPWL, rollback probes, and replay only positive
   candidates.
4. Convert exact DPO accepts into hot segments and accepted windows.
5. Run hot-segment selected reorder, micro-pack, and accepted-window replay
   over the accepted footprint.
6. Add a post-reorder `gs` pass that explicitly consumes handoff state.  It
   ranks high-HPWL nets touching the frontier, prioritizes endpoint/source
   cells, builds endpoint-derived targets, exact-scores them, and commits only
   replay-positive moves.
7. If this route plateaus, replace the last single-cell endpoint repair with a
   bounded pair or small-cluster exact transaction over the same handed-off
   top-net frontier.

### Reconstruction Sketch

```text
negotiation_recoverability_producer():
  identify high-span/top-impact nets and their endpoint/source cells
  add bounded location bonus only when the candidate remains legal,
  displacement-controlled, and closer to a recoverable endpoint/source basin
  store selected endpoint/source cells and affected segments as native handoff

endpoint_source_consumer():
  before first exact GS, import source-edge hot cells from manager state
  exact-score source-edge move/swap targets and record accepted nodes/segments
  run selected hot reorder and micro-pack on accepted segments
  replay accepted windows with exact positive checks
  after reorder, run handoff-aware exact GS over top nets touching the frontier
  and endpoint-derived targets
```

### Source Handles

- `src/NegotiationLegalizer.cpp`, `src/NegotiationLegalizerPass.cpp`, and
  `src/NegotiationLegalizer.h`: recoverability scores, endpoint/source target
  identification, displacement damping, and producer counters.
- `src/optimization/detailed_global.{h,cxx}`: handoff import, exact
  source-edge/global-swap, endpoint target generation, and handoff-aware post
  reorder pass.
- `src/optimization/detailed_manager.{h,cxx}`: source-edge hot-cell mask,
  accepted nodes, and hot segment storage.
- `src/optimization/detailed_reorder.{h,cxx}`: selected hot reorder,
  micro-pack, and accepted-window replay.
- `src/Optdp.cpp::Opendp::improvePlacement`: pass order, including the
  post-reorder handoff-aware exact consumer.

### Required Counters

- negotiation recoverability top nets, candidate cells, scored candidates,
  selected cells, selected bonus, damped/reverted candidates;
- exact source-edge/global-swap candidates, exact scores, accepts, source-edge
  accepts, accepted delta, replay rejects;
- hot-segment reorder and micro-pack segments, probes, accepts, accepted delta;
- accepted-window replay windows/probes/accepts/accepted delta;
- handoff-aware endpoint/source repair: handoff on/off, frontier segments,
  source cells, prioritized cells, endpoint targets, endpoint accepts, endpoint
  gain;
- final full-flow HPWL, legality, avg/max displacement, and runtime.

### Self-Diagnosis And Repair

- Negotiation counters live but source-edge accepts zero: handoff was lost or
  candidate targets are weak; repair manager state lifetime and target
  generation first.
- Source-edge accepts live but post-reorder endpoint repair zero: confirm the
  post-reorder pass imports the incoming hot/source-edge state instead of
  clearing it.
- Endpoint accepts live but final HPWL flat: switch to pair/small-cluster exact
  transactions over the same top-net frontier; do not only widen endpoint caps.
- Displacement tail grows sharply: damp recoverability bonus and make endpoint
  repair reject high-displacement extensions unless exact gain is strong.

## Blueprint C: Low-Residual Current-Net / Vertical-Frontier Consumer

Use when the design is extremely dense/high-utilization and legalization creates
large HPWL inflation but also exposes target-miss, current-net, or stage3 exact
handoff cells that downstream selected segments or vertical moves can consume.
This route is narrow: it is strong for low-residual target-miss cases and should
not be used as the default for generic DPO-recoverable row-rich cases.

### Start Basin

- Start from `framework` so the current LEGALM/full-guidance path can produce
  target rows/sites/valid flags and stage3 exact handoff state.
- Do not route to this blueprint only because density is high.  Require
  target-miss/current-net/low-residual evidence or use Blueprint A as the safer
  DPO-consumer route.

### Mechanism Chain

1. Run LEGALM/full guidance as a recoverable producer, not as a legalize-only
   objective.
2. Add stage3 exact/current-net refinement: use target rows/sites, current-net
   anchors, target-miss cells, and displacement-aware legality checks to move
   only exact-positive cells.
3. Publish target rows, target sites, valid flags, stage3 handoff cells, and
   target-miss counts in `Opendp` state for improve placement.
4. In `Opendp::improvePlacement`, build a compact frontier from row-miss cells
   and same-row residual cells.  Balance both queues so same-row residual cells
   are not starved by row-miss cells.
5. Run targeted exact global and vertical wrappers over this frontier.  Score
   with `DetailedHPWL`, rollback every non-improving probe, and commit only
   positive moves.
6. Run selected-segment reorder or residual segment closure on the remaining
   touched frontier.
7. Protect exact scoring by clearing stale affected-net state at the beginning
   of each `DetailedHPWL::delta` call.

### Reconstruction Sketch

```text
legalm_stage3_producer():
  for candidate cells near target-miss/current-net anchors:
    generate legal row/site candidates from target row/site, current row,
    nearby rows, current-net anchors, and displacement-safe positions
    exact-score legal candidates, commit only positive/refined moves
    mark target valid, target miss, stage3 handoff, and current-net counters

low_residual_frontier_consumer():
  read legalm_target_rows/sites/valid from Opendp
  split candidates into row-miss and same-row residual queues
  rank by target miss, site residual, exact-anchor flag, net span, and
  displacement risk
  build a compact balanced frontier
  run targeted global and vertical exact wrappers, then selected-segment reorder
  log vertical/global candidates, exact scores, accepts, and exact gain
```

### Source Handles

- `src/LegalmFullLegalization.cpp`: stage3 exact refinement, current-net anchor
  expansion, target-miss/frontier counters, target rows/sites/valid flags.
- `include/dpl_evolve/Opendp.h`: target arrays and stage3 handoff counters.
- `src/Optdp.cpp::Opendp::improvePlacement`: inherit stage3 handoff, build the
  low-residual frontier, call targeted global/vertical consumers, and run
  selected-segment closure.
- `src/optimization/detailed_global.{h,cxx}` and
  `src/optimization/detailed_vertical.{h,cxx}`: targeted one-off exact move
  wrappers.
- `src/optimization/detailed_reorder.{h,cxx}`: selected-segment residual
  consumer.
- `src/objective/detailed_hpwl.cxx`: clear affected-edge state before each
  exact delta calculation.

### Required Counters

- LEGALM stage3 exact refinement: frontier, attempted, scored, moved,
  target-miss count, current-net candidate/scored/move counters, exact HPWL
  gain, displacement gain;
- inherited handoff in improve placement: stage3 handoff cells and target-miss
  cells;
- low-residual frontier: row-miss count, same-row residual count, exact-anchor
  count, selected frontier size;
- targeted global/vertical: candidates, exact scores, accepts split by global
  and vertical, exact gain;
- selected-segment closure: segments, scored windows, accepts, exact gain;
- final HPWL, legality, avg/max displacement, and runtime.

### Self-Diagnosis And Repair

- Stage3 producer live but improve consumer sees zero frontier: repair target
  arrays, valid flags, or state lifetime before changing LEGALM weights.
- Frontier live but global/vertical accepts zero: rebalance row-miss versus
  same-row residual queues and inspect exact target generation; do not add a
  broad random tail.
- Vertical accepts live but final HPWL flat: tighten selected-segment closure or
  redesign producer anchors to create same-row/global residual signal.
- LEGALM lowers `HPWLlg` but final worsens: demote legalize-only tuning and
  switch one Student to Blueprint A or B depending on current evidence.

## Complete-Chain Check

A Student implementation is incomplete if it only does one of these:

- logs a producer without a consumer;
- adds passive handoff state that no DPO pass reads;
- preserves a donor with a guard-only diff;
- changes caps or constants without changing candidate generation, scoring,
  transaction shape, handoff lifetime, or preservation contract;
- reports exact accepts but no accepted delta/gain or no final full-flow HPWL;
- improves `HPWLlg` while final HPWL and displacement are worse.

Before finalization, the Student must run build/evaluate, inspect logs, diagnose
which link is missing, make one strengthened repair or controlled pivot, and
record the next repair direction for Teacher if the route still underperforms.
