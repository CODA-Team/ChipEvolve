# Mechanism Reconstruction Roadmap

## Agent Use

- Role: direct Teacher/Student reconstruction core after Teacher selects a
  blueprint from `case_type_quality_mechanism_priority.md`.
- Open only the selected blueprint section during ordinary routing.
- These are implementation roadmaps, not fixed recipes.  Student may redesign
  local details after inspecting the current source, but must preserve the
  complete producer-handoff-consumer logic and prove liveness with counters.
- Strong routes are usually cumulative: several accepted mechanisms from earlier
  iterations work together.  Reconstruct the stack, not the final guard or the
  last small patch.

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
evidence specifically points to the negotiation endpoint/source stack or the
low-residual LEGALM target-miss stack.

### Start Basin

- Start from `evolved_diamond` when source-topK exact DPO already executes and
  the missing work is downstream frontier closure.
- Start from `framework` when the current route needs a producer/frontier
  payload from LEGALM, differential guidance, or row assignment.
- Do not start from negotiation unless current evidence proves negotiation is
  the useful producer; otherwise use Blueprint B only as a separate hypothesis.

### Cumulative Mechanism Chain

1. Keep exact source-topK/global-swap live in the normal improve flow.  Do not
   let density/intensity heuristics silently fall back to legacy DPO when
   source-topK, source-edge, or critical-net residue is visible.
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
  neighbor rows, legal segment centers, and source-edge candidates
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

- `src/optimization/detailed_global.cxx`: exact source-topK/global-swap
  candidate generation, scoring, replay, accepted-node capture, hot-segment and
  critical-frontier export, and source-topK counters.
- `src/optimization/detailed_manager.{h,cxx}`: accepted-node, hot-segment,
  critical-frontier, and source-topK native state.
- `src/Optdp.cpp::Opendp::improvePlacement`: schedule the source-topK pass and
  the post-DPO chain; log HPWL before/after each link.
- `src/LegalmRowAssignment.cpp`: critical-row micro-start or producer reshape
  only when evidence says the DPO consumer needs a better frontier.
- `src/optimization/detailed_reorder.cxx`: critical-net chain assignment, exact
  local closure, multi-row residual transaction, and segment-local residual
  swap.
- `src/Place.cpp`: Diamond/source-edge ordering and exact source-edge producer
  behavior when the selected start basin already uses Diamond-style DPO.

### Required Counters

- source-topK/global-swap candidates, exact scores, replays, accepts, accepted
  delta, replay rejects, and hot/critical segments exported;
- critical-frontier nodes/segments and merged frontier nodes/segments;
- micro-start probes/accepts/gain and risk-filtered candidates;
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

## Blueprint B: Negotiation Recoverability Plus Endpoint/Source Exact Consumer Stack

Use when endpoint/source residue and top-net imbalance are visible and a
negotiation-like legal basin is the useful producer.  The strong form is a
multi-round cumulative chain.  Negotiation alone, endpoint caps alone, or a late
guard alone should not be promoted.

### Start Basin

- Start from `default_negotiation` for a clean negotiation/resource-closure
  producer.
- Start from `evolved_negotiation` only if it preserves the same recoverability
  producer behavior and the exact consumers can still import its payload.
- If continuing an existing donor, preserve the complete accepted-window replay
  chain rather than restarting from a guard or attribution commit.

### Cumulative Mechanism Chain

1. First make the DPO consumer live on the negotiation basin: exact source-edge
   global swap must rank source-edge/boundary cells, enumerate row/segment
   targets, exact-score with a journal, rollback probes, replay positive moves,
   and export hot segments/source-edge cell masks.
2. Run hot-segment selected reorder.  Expand the accepted hot segments to
   neighboring row segments, use a larger hot window than the generic reorder,
   exact-score windows, and track accepted delta.
3. Run hot micro-pack over the same accepted frontier.  Use compact windows,
   shifts, and permutations around source-edge or endpoint cells; prioritize
   boundary source-edge windows because they preserve the accepted DPO footprint.
4. Add the negotiation recoverability producer.  Rank high-span/top-impact nets,
   mark endpoint/source cells, add a bounded location bonus during `findBest`,
   damp by displacement growth and local slack, and log selected/reverted
   recoverability decisions.  The producer is useful only if downstream exact
   consumers consume the payload.
5. Replay accepted windows.  Store accepted hot/micro-pack windows as seeds,
   replay local residual reorder with exact scoring, then run a second cascade
   pass around accepted seeds.  Strong seeds may use a larger halo and shift
   budget; flat or low-conversion seeds should be rejected, not just counted.
6. Run post-reorder endpoint/source repair.  Import the incoming hot segments
   and source-edge masks before they are cleared, rank top nets touching that
   frontier, derive endpoint hints from first/second extrema on each net, build
   endpoint/source targets, exact-score them, and commit only replay-positive
   moves.
7. If single-cell endpoint repair is live but final HPWL is flat, add bounded
   endpoint/source pair or small-cluster exact transactions over the same
   frontier, scored as a unit with rollback.
8. Preserve accepted-window value through canonical downstream passes.  Generic
   random, broad GS, mirror, or reorder passes should not wash out accepted
   footprint unless their exact gain is positive.

### Reconstruction Sketch

```text
negotiation_endpoint_stack():
  run exact source-edge/global-swap on the negotiation legal state
  export accepted nodes, source-edge hot cells, and hot segments
  run hot-segment reorder, then hot micro-pack over accepted segments
  add recoverability producer only after a consumer path exists:
    rank high-span nets and endpoint/source cells
    bias legal target selection with bounded bonus
    damp bonus by displacement growth and local slack
  store accepted reorder/micro-pack windows as replay seeds
  run exact residual replay and cascade around accepted seeds
  import incoming handoff before clearing hot state
  rank top nets touching frontier and build endpoint-derived targets
  exact-score endpoint/source moves, then pair/small-cluster transactions if
  single-cell endpoint accepts do not move final HPWL
  preserve accepted footprint unless a later pass proves exact positive gain
```

### Source Handles

- `src/optimization/detailed_global.{h,cxx}`: exact source-edge/global-swap,
  handoff import, endpoint target generation, post-reorder endpoint/source
  repair, and optional pair/small-cluster transaction entry.
- `src/optimization/detailed_manager.{h,cxx}`: hot-segment storage,
  source-edge hot-cell masks, accepted nodes, and incoming handoff lifetime.
- `src/optimization/detailed_reorder.{h,cxx}`: hot-segment selected reorder,
  hot micro-pack, accepted-window residual replay, replay cascade, and connected
  endpoint/source local transactions.
- `src/NegotiationLegalizer.cpp`, `src/NegotiationLegalizerPass.cpp`, and
  `src/NegotiationLegalizer.h`: recoverability producer, endpoint/source target
  identification, local slack, displacement damping, and producer counters.
- `src/Optdp.cpp::Opendp::improvePlacement`: pass order and preservation of
  incoming handoff through source-edge GS, reorder, micro-pack, replay, endpoint
  repair, and canonical cleanup.
- `src/objective/detailed_hpwl.{h,cxx}`: exact/journal HPWL scoring helpers for
  affected nets and accepted windows.

### Required Counters

- exact source-edge/global-swap candidates, exact scores, source-edge cells,
  accepts, accepted delta, hot segments, and source-edge hot masks;
- hot-segment reorder segments/windows/probes/accepts/accepted delta;
- hot micro-pack segments/windows/probes/source-edge windows/boundary endpoint
  windows/accepts/accepted delta;
- negotiation recoverability top nets, candidate cells, scored candidates,
  bonus candidates, damped candidates, selected/reverted locations, selected
  slack, and selected bonus;
- accepted-window replay seeds, hot seeds, micro-pack seeds, pass1 accepts,
  cascade seeds, expanded cascade seeds, pass2 accepts, rollback rejects,
  low-conversion rejects, and accepted delta;
- post-reorder endpoint/source repair: handoff on/off, frontier segments,
  frontier source cells, prioritized cells, endpoint hints, endpoint targets,
  endpoint accepts, and endpoint gain;
- pair/small-cluster transactions: candidates, legal transactions, accepts,
  exact transaction gain, replay rejects, and gain per runtime;
- final full-flow HPWL, legality, avg/max displacement, and runtime.

### Self-Diagnosis And Repair

- Source-edge accepts zero: repair exact source-edge candidate generation and
  journal replay before touching negotiation weights.
- Hot reorder/micro-pack accepts zero: repair hot-segment export/import and
  boundary source-edge window selection before adding new producer scores.
- Recoverability producer live but downstream accepts flat: producer payload is
  not being consumed; repair handoff lifetime or target generation first.
- Replay seeds live but low conversion: add cascade around accepted windows or
  change transaction shape; do not just widen seed caps.
- Endpoint accepts live but final HPWL flat: add pair/small-cluster exact
  transactions and preservation over the same top-net frontier.
- Displacement tail grows sharply: damp recoverability bonus and reject endpoint
  extensions unless exact gain is strong.

## Blueprint C: Low-Residual Current-Net / Vertical-Frontier Consumer

Use when the design is dense/high-utilization and legalization creates large HPWL
inflation but also exposes target-miss, current-net, or stage3 exact handoff
cells that downstream selected segments or vertical moves can consume.  This
route is narrow: it is strong for low-residual target-miss cases and should not
be used as the default for generic DPO-recoverable row-rich cases.

### Start Basin

- Start from `framework` so the current LEGALM/full-guidance path can produce
  target rows/sites/valid flags and stage3 exact handoff state.
- Do not route to this blueprint only because density is high.  Require
  target-miss/current-net/low-residual evidence or use Blueprint A as the safer
  DPO-consumer route.

### Cumulative Mechanism Chain

1. Run LEGALM/full guidance as a recoverable producer, not as a legalize-only
   objective.
2. Add stage3 exact/current-net refinement.  Use target rows/sites, current-net
   anchors, target-miss cells, and displacement-aware legality checks to move
   only exact-positive cells.
3. Expand current-net anchors in a bounded way: add adjacent row, near-target,
   and toward-target candidates only when they preserve exact gain and do not
   inflate displacement risk.
4. Publish target rows, target sites, valid flags, moved/stage3 handoff cells,
   target-miss counts, and exact-anchor flags in `Opendp` state.
5. In `Opendp::improvePlacement`, build a compact frontier from moved cells,
   residual target-miss cells, exact anchors, dirty segments, row-miss cells, and
   same-row residual cells.  Balance these queues so same-row residual cells are
   not starved by row-miss cells.
6. Run targeted exact global and vertical wrappers over this frontier.  Score
   with `DetailedHPWL`, rollback every non-improving probe, and commit only
   positive moves.
7. Rank residual segments by exact-anchor count and residual magnitude, then run
   selected-segment exact reorder over only those segments.
8. Protect exact scoring by clearing stale affected-net state at the beginning
   of each `DetailedHPWL::delta` call.

### Reconstruction Sketch

```text
legalm_stage3_producer():
  for candidate cells near target-miss/current-net anchors:
    generate legal row/site candidates from target row/site, current row,
    nearby rows, current-net anchors, adjacent rows, and toward-target sites
    exact-score legal candidates, commit only positive/refined moves
    mark target valid, exact-anchor, target miss, stage3 handoff, and current-net counters

low_residual_frontier_consumer():
  read legalm_target_rows/sites/valid from Opendp
  split candidates into moved cells, row-miss cells, same-row residual cells,
  exact anchors, and dirty segment neighbors
  rank by exact-anchor flag, target miss, site residual, current-net gain,
  net span, and displacement risk
  run targeted global and vertical exact wrappers
  run selected-segment reorder on the ranked residual segments
  log candidates, exact scores, accepts, and exact gain for every link
```

### Source Handles

- `src/LegalmFullLegalization.cpp`: stage3 exact refinement, current-net anchor
  expansion, target rows/sites/valid flags, exact-anchor marking, and current-net
  counters.
- `include/dpl_evolve/Opendp.h` and `src/Optdp.cpp`: persistent target arrays,
  moved/frontier handoff, low-residual frontier construction, selected-segment
  scheduling, and control counters.
- `src/optimization/detailed_global.{h,cxx}` and
  `src/optimization/detailed_vertical.{h,cxx}`: targeted global/vertical exact
  wrappers over the frontier.
- `src/optimization/detailed_reorder.{h,cxx}`: selected-segment residual reorder
  over exact-anchor and target-miss segments.
- `src/objective/detailed_hpwl.{h,cxx}`: affected-net exact scoring and stale
  state clearing.

### Required Counters

- stage3 current-net raw candidates, adjacent candidates, near-target
  candidates, exact-scored candidates, exact moves, exact HPWL gain,
  displacement gain, and full-net scans avoided;
- target rows/sites/valid counts, moved handoff cells, exact-anchor cells, and
  target-miss cells;
- low-residual frontier moved seeds, residual target-miss seeds, guided-miss
  seeds, touched neighbors, dirty segments, frontier before/after cap;
- targeted global/vertical candidates, generated moves, exact attempts, accepts,
  rejects, hot segments, and HPWL gain;
- selected residual segments, exact residual cells, scored windows, accepts, and
  exact HPWL gain;
- final full-flow HPWL, legality, avg/max displacement, and runtime.

### Self-Diagnosis And Repair

- Stage3 exact moves are zero: repair current-net anchor generation and target
  validity before widening DPO.
- Stage3 moves live but frontier empty: repair target-row/site/valid handoff and
  moved-cell marking.
- Frontier accepts live but final HPWL flat: fix selected-segment ranking,
  exact-anchor prioritization, or vertical/global transaction shape.
- Dense case has no target-miss/current-net evidence: demote Blueprint C and try
  Blueprint A instead of forcing LEGALM-specific repair.
- Runtime grows without accepted gain: cap the frontier by exact-anchor and
  residual score, then spend runtime on exact-positive selected segments rather
  than broad scans.
