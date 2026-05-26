# Mechanism Reconstruction Roadmap

## Agent Use

- Role: direct Teacher/Student reconstruction core after Teacher selects a
  blueprint from `case_type_quality_mechanism_priority.md`.
- Open only the selected blueprint section during ordinary routing.
- These are implementation roadmaps, not fixed recipes.  Student may redesign
  local details after inspecting current source, but must preserve the complete
  producer-handoff-consumer logic and prove liveness with counters.
- Strong routes are cumulative.  Reconstruct the stack, not the last guard or
  last small patch.

## Shared Source Anchors

Use these anchors inside the private `dpl_evolve` source prepared for the
Student workspace.

- Flow composition: `src/StudentAlgorithm.cpp` and
  `Opendp::runStudentAlgorithm` for legalizer/improve/mirror sequencing.
- Top-level state: `src/Opendp.cpp` and `include/dpl_evolve/Opendp.h` for
  persistent handoff fields, target arrays, displacement limits, and metrics.
- LEGALM/differential producer: `src/LegalmGuidance.cpp`,
  `src/DifferentialGuidance.cpp`, `src/LegalmFullLegalization.cpp`, and
  `src/LegalmRowAssignment.cpp` for target shaping, current-net anchors,
  target-miss state, and recoverable frontier production.
- Negotiation producer: `src/EvolveNegotiationRepair.cpp`,
  `src/NegotiationLegalizer.cpp`, `src/NegotiationLegalizerPass.cpp`, and
  `src/NegotiationLegalizer.h` for resource/conflict closure, endpoint/source
  recoverability scoring, and displacement/slack damping.
- Improve-placement schedule: `src/Optdp.cpp::Opendp::improvePlacement` for
  exact-DPO pass order and producer-handoff-consumer imports.
- Exact consumers: `src/optimization/detailed_global.{h,cxx}`,
  `src/optimization/detailed_reorder.{h,cxx}`,
  `src/optimization/detailed_vertical.{h,cxx}`,
  `src/optimization/detailed_manager.{h,cxx}`,
  `src/optimization/detailed_random.{h,cxx}`, and
  `src/objective/detailed_hpwl.{h,cxx}`.
- Diamond/source-edge producer: `src/Place.cpp`, `src/Opendp.cpp`,
  `include/dpl_evolve/Opendp.h`, and source-edge hooks in the exact global
  swap implementation.
- Native state: prefer `Node*`, `Edge*`, segment ids, row ids, accepted journal
  records, manager masks, touched-net lists, and target arrays.  Avoid
  string-keyed handoff maps or bulky coordinate logs when native ids can carry
  the state.

Every route should log compact counters: producer count, handoff produced and
consumed, exact probes/scores, exact accepts, accepted HPWL gain or delta,
rollback/reject count, pass runtime, and accepted gain per runtime.

## Blueprint A: Runtime-Balanced Critical-Frontier Exact DPO Stack

Use when final HPWL is DPO-dominant: improve placement recovers a large stage
loss, source-topK/global-swap exact accepts are plausible, and the legalizer
state exposes a recoverable critical frontier.  This is the runtime-balanced
strong route for row-rich/control/datapath and wrapper-fragmented cases when the
main residue is accepted-node/hot-critical frontier rather than a pure
endpoint/source negotiation payload.

### Start Basin

- Start from `evolved_diamond` when source-topK or exact DPO already executes
  and the missing work is downstream frontier closure.
- Start from `framework` when the route needs producer/frontier payload from
  LEGALM, differential guidance, or row assignment before the exact consumer can
  score useful candidates.
- Do not start from negotiation for this blueprint unless current evidence says
  negotiation is the useful producer; in that case use Blueprint B as a separate
  hypothesis.

### Cumulative Mechanism Chain

1. Keep exact source-topK/global-swap live in the normal improve flow.  Do not
   let density/intensity heuristics silently fall back to weak legacy DPO when
   source-topK, source-edge, or critical-net residue is visible.
2. Rank cells by affected-net HPWL, bbox-edge contribution, fanout-normalized
   span, displacement risk, and recent DPO movement.  Generate bounded row/site
   and swap targets from medians, bbox edges, current row, nearby rows, legal
   segment centers, and source-edge candidates.
3. Exact-score every trial with `DetailedHPWL` or a touched-net journal.  Roll
   back all probes and replay only positive candidates.
4. Convert accepted DPO moves into native manager state: accepted nodes, touched
   nets, source/topK cells, hot segments, and critical-frontier nodes.  This
   native handoff is the producer payload for the post-DPO chain.
5. Merge accepted DPO nodes with critical-net endpoints and hot segments.  If
   producer shaping is needed, add only cells/segments that later consumers will
   exact-score.
6. In `Opendp::improvePlacement`, run the post-DPO chain in this order:
   critical-row micro-start, critical-net chain assignment, exact local closure,
   multi-row residual transactions, and segment-local residual swaps.
7. Exact-score each closure link with rollback.  The residual swap or guard pass
   is not the mechanism unless the earlier source-topK, accepted-node handoff,
   micro-start/chain, and multi-row links are live.

### Reconstruction Sketch

```text
source_topk_exact_pass():
  rank movable cells by affected-net HPWL, edge contribution, span, displacement,
  and recent movement
  generate bounded target rows/sites/swaps from medians, bbox edges, legal
  segment centers, current/nearby rows, and source-edge hints
  exact-score each trial; rollback; replay the best positive trial
  record accepted nodes, touched nets, source/topK cells, hot segments, and
  accepted delta in DetailedMgr

critical_frontier_stack():
  merge accepted-DPO nodes with critical-net endpoints and hot segments
  micro-start high-value frontier cells into recoverable legal anchors
  chain each accepted move to newly exposed critical endpoints
  close touched segments with exact reorder/shift
  run bounded multi-row residual transactions over connected touched-net
  components
  finish with small segment-local swaps around the accepted footprint
```

### Source Handles

- `src/optimization/detailed_global.cxx`: source-topK/global-swap candidate
  generation, exact scoring, rollback/replay, accepted-node capture, hot-segment
  export, source-topK counters.
- `src/optimization/detailed_manager.{h,cxx}`: accepted nodes, hot segments,
  critical-frontier nodes, source/topK masks, and native handoff lifetime.
- `src/Optdp.cpp::Opendp::improvePlacement`: schedule source-topK and the
  post-DPO chain; log HPWL before/after each link.
- `src/LegalmRowAssignment.cpp`: critical-row micro-start or producer reshape
  when the exact consumer needs a better frontier.
- `src/optimization/detailed_reorder.cxx`: critical-net chain assignment, exact
  local closure, multi-row residual transaction, and segment-local residual
  swap.
- `src/Place.cpp`: Diamond/source-edge ordering only when the selected start
  basin already uses Diamond-style producer behavior.

### Required Counters

- source-topK/global-swap candidates, exact scores, rollbacks, replays, accepts,
  accepted delta, replay rejects, and hot/critical segments exported;
- accepted-node, hot-segment, critical-frontier, and merged-frontier counts;
- micro-start probes/accepts/gain and risk-filtered candidates;
- chain assignment probes/accepts/gain;
- exact closure windows/probes/accepts/gain;
- multi-row residual probes/accepts/gain;
- segment-local residual swap probes/accepts/gain;
- final full-flow HPWL, legality, displacement, and runtime.

### Self-Diagnosis And Repair

- Producer live but consumer accepts zero: repair native handoff state or exact
  candidate generation before changing weights.
- Exact accepts live but final HPWL flat: repair candidate quality, transaction
  granularity, or canonical replay/restore; do not only widen caps.
- Residual swaps tiny: change move family or transaction shape around the merged
  frontier; do not retune seed priority inside the same saturated set.
- Runtime high without accepted gain: cache affected-net deltas, prune by gain
  rate, or narrow the frontier while keeping the full chain alive.

## Blueprint B: Negotiation Recoverability Plus Endpoint/Source Exact Consumer Stack

Use when endpoint/source residue and top-net imbalance are visible and a
negotiation-like legal basin can produce recoverable endpoint/source payload.
The strong form is a multi-round cumulative chain: negotiation producer,
source-edge exact consumer, hot reorder, hot micro-pack, accepted-window replay,
endpoint/source repair, and optional small transactions.  Negotiation alone,
endpoint caps alone, or a late guard alone should not be promoted.

### Start Basin

- Start from `default_negotiation` for a clean negotiation/resource-closure
  producer.
- Start from `evolved_negotiation` only if it preserves the same recoverability
  producer behavior and the exact consumers can still import its payload.
- If continuing an existing donor, preserve the complete accepted-window replay
  chain.  Do not restart from a guard, attribution commit, or isolated cap
  change.

### Cumulative Mechanism Chain

1. Make the DPO consumer live on the negotiation basin.  Exact source-edge/global
   swap ranks source-edge and boundary cells, enumerates row/segment targets,
   exact-scores with a journal, rolls back probes, replays positive moves, and
   exports accepted nodes, source-edge hot-cell masks, and hot segments.
2. Run hot-segment selected reorder.  Expand accepted hot segments to nearby row
   segments, use a larger hot window than generic reorder, exact-score windows,
   and track accepted delta.
3. Run hot micro-pack over the same accepted frontier.  Use compact windows,
   shifts, and permutations around source-edge or endpoint cells; prioritize
   boundary source-edge windows because they preserve the accepted DPO footprint.
4. Add the recoverability producer in negotiation.  Rank high-span/top-impact
   nets, identify first/second extrema endpoint/source cells, apply a bounded
   location bonus during `findBest`, and damp the bonus by displacement growth
   and local slack.  Log selected and reverted recoverability decisions.
5. Store accepted reorder/micro-pack windows as replay seeds.  Replay local
   residual reorder with exact scoring, then run a second cascade pass around
   accepted seeds.  Strong seeds may use a larger halo; flat or low-conversion
   seeds should be rejected, not merely counted.
6. Run post-reorder endpoint/source repair.  Import incoming hot segments and
   source-edge masks before they are cleared, rank top nets touching that
   frontier, derive endpoint hints from first/second extrema, build endpoint and
   source targets, exact-score them, and commit only replay-positive moves.
7. If single-cell endpoint repair is live but final HPWL is flat, add bounded
   endpoint/source pair or small-cluster exact transactions over the same
   frontier, scored as a unit with rollback.  This is a follow-up repair, not a
   replacement for the source-edge/replay stack.
8. Preserve accepted-window value through canonical downstream passes.  Generic
   random, broad GS, mirror, or reorder passes should not wash out the accepted
   footprint unless their exact gain is positive.

### Reconstruction Sketch

```text
negotiation_endpoint_stack():
  run exact source-edge/global-swap on the negotiation legal state
  export accepted nodes, source-edge hot cells, and hot segments
  run hot-segment reorder, then hot micro-pack over accepted segments
  add recoverability producer only after a consumer path exists:
    rank high-span nets and endpoint/source cells
    bias legal target selection with bounded recoverability bonus
    damp bonus by displacement growth and local slack
  store accepted reorder/micro-pack windows as replay seeds
  run exact residual replay and cascade around accepted seeds
  import incoming handoff before clearing hot state
  rank top nets touching frontier and build endpoint-derived targets
  exact-score endpoint/source moves
  add pair/small-cluster exact transactions only if single-cell endpoint accepts
  do not move final HPWL
  preserve accepted footprint unless a later pass proves exact positive gain
```

### Source Handles

- `src/optimization/detailed_global.{h,cxx}`: exact source-edge/global-swap,
  handoff import, endpoint target generation, post-reorder endpoint/source
  repair, and optional pair/small-cluster transaction entry as later repair.
- `src/optimization/detailed_manager.{h,cxx}`: hot-segment storage,
  source-edge hot-cell masks, accepted nodes, incoming handoff lifetime.
- `src/optimization/detailed_reorder.{h,cxx}`: hot-segment selected reorder,
  hot micro-pack, accepted-window residual replay, replay cascade, connected
  endpoint/source local transactions.
- `src/NegotiationLegalizer.cpp`, `src/NegotiationLegalizerPass.cpp`, and
  `src/NegotiationLegalizer.h`: recoverability producer, endpoint/source target
  identification, local slack, displacement damping, producer counters.
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
  not being consumed; repair handoff lifetime or endpoint/source target
  generation first.
- Replay seeds live but low conversion: add cascade around accepted windows or
  change transaction shape; do not just widen seed caps.
- Endpoint accepts live but final HPWL flat: add pair/small-cluster exact
  transactions and preservation over the same top-net frontier.
- Displacement tail grows sharply: damp recoverability bonus and reject endpoint
  extensions unless exact gain is strong.

## Blueprint C: Low-Residual Current-Net / Vertical-Frontier Consumer

Use when the design is dense/high-utilization and legalization creates large
HPWL movement but also exposes target-miss, current-net, exact-anchor, or stage3
handoff cells that downstream selected segments or vertical moves can consume.
This route is narrow: it is strong for low-residual target-miss/current-net
cases and should not be used as the default for generic DPO-recoverable cases.

### Start Basin

- Start from `framework` so the current LEGALM/full-guidance path can produce
  target rows/sites/valid flags and stage3 exact handoff state.
- First inspect whether current source already publishes target-miss,
  current-net, exact-anchor, and stage3 handoff state.  If not, rebuild those
  producer hooks before widening the DPO consumer.
- Do not route to this blueprint only because density is high.  Require
  low-residual target-miss/current-net/vertical-frontier evidence or use
  Blueprint A as the safer DPO-consumer route.

### Cumulative Mechanism Chain

1. Run LEGALM/full guidance as a recoverable producer, not as a legalize-only
   objective.
2. Add stage3 exact/current-net refinement.  Use target rows/sites,
   current-net anchors, target-miss cells, and displacement-aware legality
   checks to move only exact-positive cells.
3. Expand current-net anchors in a bounded way: adjacent row, near-target, and
   toward-target candidates are useful only when they preserve exact gain and do
   not inflate displacement risk.
4. Publish target rows, target sites, valid flags, moved/stage3 handoff cells,
   target-miss counts, and exact-anchor flags in `Opendp` state.
5. In `Opendp::improvePlacement`, build a compact frontier from moved cells,
   residual target-miss cells, exact anchors, dirty segments, row-miss cells,
   and same-row residual cells.  Balance row-miss and same-row queues so one
   does not starve the other.
6. Run targeted exact global and vertical wrappers over this frontier.  Score
   with `DetailedHPWL`, rollback every non-improving probe, and commit only
   positive moves.
7. Rank residual segments by exact-anchor count and residual magnitude, then run
   selected-segment exact reorder and optional local transactions only on those
   segments.
8. Protect exact scoring by clearing stale affected-net state at the beginning
   of each `DetailedHPWL::delta` call.

### Reconstruction Sketch

```text
legalm_stage3_producer():
  for candidate cells near target-miss/current-net anchors:
    generate legal row/site candidates from target row/site, current row,
    nearby rows, current-net anchors, adjacent rows, and toward-target sites
    exact-score legal candidates; commit only positive/refined moves
    mark target valid, exact-anchor, target miss, stage3 handoff, and
    current-net counters

low_residual_frontier_consumer():
  read legalm target rows/sites/valid flags from Opendp
  split candidates into moved cells, row-miss cells, same-row residual cells,
  exact anchors, dirty segment neighbors, and target-miss cells
  rank by exact-anchor flag, target miss, site residual, current-net gain,
  net span, and displacement risk
  run targeted global and vertical exact wrappers
  run selected-segment reorder on ranked residual segments
  log candidates, exact scores, accepts, and exact gain for every link
```

### Source Handles

- `src/StudentAlgorithm.cpp`: reset and publish LEGALM/stage3 handoff counters;
  keep legalizer/improve sequence consistent.
- `src/LegalmFullLegalization.cpp`: stage3 exact refinement, target-miss
  frontier, current-net anchor generation, exact scoring, and producer counters.
- `include/dpl_evolve/Opendp.h`: target rows/sites/valid flags, stage3 exact
  handoff counts, exact-anchor flags, and target-miss state.
- `src/Optdp.cpp::Opendp::improvePlacement`: frontier construction, row-miss
  and same-row queues, targeted global/vertical exact wrappers, selected-segment
  reorder schedule, and liveness logs.
- `src/optimization/detailed_vertical.{h,cxx}`: targeted vertical candidate
  generation and exact rollback.
- `src/optimization/detailed_reorder.{h,cxx}`: selected-segment exact reorder
  and anchor-local transactions.
- `src/optimization/detailed_global.{h,cxx}` and
  `src/objective/detailed_hpwl.{h,cxx}`: exact global moves and safe affected-net
  delta.

### Required Counters

- stage3 exact refinement enabled/frontier/frontier-before-cap/attempted/scored;
- target misses, target-gain sites, current-net anchor terms/candidates/scored,
  current-net anchor moves, exact calls avoided, full-net scans, legal/static
  rejects, and displacement/tail rejects;
- inherited stage3 handoff cells and target misses in improve placement;
- frontier size, exact-anchor cells, target-miss cells, vertical/global
  candidates, scored moves, accepts, vertical/global accepts, exact HPWL gain;
- selected residual segments, anchor cells, exact windows/transactions, accepts,
  and accepted gain;
- final full-flow HPWL, legality, displacement, and runtime.

### Self-Diagnosis And Repair

- Stage3 producer counters zero: repair target-valid/current-net publication
  before editing DPO.
- Producer live but frontier consumer sees no cells: repair `Opendp` handoff
  lifetime and id mapping.
- Frontier moves score but accept zero: improve candidate quality or exact
  objective; do not only increase caps.
- Vertical moves accept but final HPWL flat: add selected-segment reorder around
  exact anchors and preserve accepted footprint.
- Legal HPWL improves but final worsens: treat the legalizer as producing a
  bad basin; repair downstream consumability rather than promoting `HPWLlg`.

## Blueprint D: Diamond Source-Edge Ordered-Pair And Endpoint-Escape Exact DPO

Use when Diamond/source-edge placement already provides high-span boundary or
source-edge hot-cell signal, but improve placement underuses it because low
intensity falls back to weak legacy search or only single-cell exact moves are
tried.  This route is source-edge exact DPO, not LEGALM and not negotiation.

### Start Basin

- Start from `diamond` when the plain Diamond producer creates the source-edge
  hot tags and legal state.
- Start from `evolved_diamond` only when it keeps the same source-edge hot-cell
  producer while adding useful exact-DPO infrastructure.
- Do not use this blueprint when the main evidence is negotiation
  endpoint/source recoverability; use Blueprint B for that.

### Cumulative Mechanism Chain

1. In placement/legal closure, identify source-edge hot cells from high-span nets
   and bbox-edge contribution before detailed global swap runs.
2. Preserve source-edge hot tags through placement and legalization state reset.
   Expose compact counters for hot cells, guided legal candidates, reranked
   candidates, and optional vacancy attempts.
3. In detailed global swap, prevent low-intensity settings from disabling the
   exact source-edge path.  An HPWL-only exact mode should still use exact
   affected-net scoring and rollback.
4. Generate source-edge target probes from bbox-edge medians, left/right edge
   targets, current/nearby rows, segment centers, and source-edge partner cells.
5. Add ordered-pair transactions: exact-score the first move, cache its affected
   nets, then exact-score a coupled second move/swap over overlapping source-edge
   nets before replaying the pair as a unit.
6. Add endpoint-escape partners: find high-impact nets where a source-edge cell
   is trapped at an endpoint, generate escape partners/rows/sites, exact-score
   the coupled move, and accept only positive unit deltas.
7. Cache affected-net deltas for runtime, but keep an audit gap counter so cached
   decisions cannot silently diverge from exact `DetailedHPWL` scoring.
8. Runtime guards may reuse scratch buffers or skip zero-weight bookkeeping only
   after the exact source-edge/ordered-pair/endpoint-escape accepts remain
   semantically identical.

### Reconstruction Sketch

```text
source_edge_producer():
  rank movable cells by high-span net bbox-edge contribution and endpoint/source
  hotness
  store source-edge hot tags on native nodes/instances
  optionally use guided legal candidate ordering or vacancy probes for hot cells,
  but keep this bounded and rollback-safe

source_edge_exact_consumer():
  force exact HPWL-only source-edge GS when source-edge hot tags are present
  for each hot cell:
    generate edge, row, segment, and partner probes
    exact-score single-cell move; rollback
    build ordered-pair candidates from overlapping affected nets
    exact-score the pair as one transaction; rollback
    build endpoint-escape partners for trapped endpoints
    exact-score the escape transaction; rollback
  replay only positive single/pair/escape transactions
  log accepted deltas and audit gap for cached scoring
```

### Source Handles

- `src/Place.cpp`: source-edge hot-cell marking, guided legal candidate ordering,
  bounded vacancy probe behavior, and producer counters.
- `include/dpl_evolve/Opendp.h` and `src/Opendp.cpp`: source-edge hot-cell state,
  guided/vacancy counters, reset/report/metric plumbing.
- `src/optimization/detailed_global.{h,cxx}`: exact HPWL-only source-edge path,
  ordered-pair transaction generation, endpoint-escape partner generation,
  rollback/replay, and accepted counters.
- `src/objective/detailed_hpwl.{h,cxx}`: affected-net delta cache, cache replay,
  and audit gap comparison.
- `src/optimization/detailed.cxx` and `src/Optdp.cpp`: ensure pass selection and
  intensity do not bypass the source-edge exact consumer when hot tags exist.

### Required Counters

- source-edge producer hot cells, guided cells, guided legal candidates,
  reranked candidates, vacancy attempts/commits/rollbacks, and vacancy bonus;
- exact source-edge cells, raw candidates, generated candidates, exact scored,
  accepted moves, accepted delta, hot generated, hot accepted, and hot accepted
  delta;
- ordered-pair stage1 exact probes, pair candidates, scored pairs, cached
  overlap edges, promoted pairs, accepted pairs, accepted delta, and audit gap;
- endpoint-escape edges, partners, candidates, scored, cached overlap edges,
  promoted escapes, accepted escapes, accepted delta, and audit gap;
- runtime of exact source-edge pass and final full-flow HPWL.

### Self-Diagnosis And Repair

- Hot tags zero: repair `Place.cpp` source-edge producer and state reset before
  editing detailed global swap.
- Hot tags live but exact scored zero: repair pass scheduling/intensity fallback
  and exact-source-edge candidate generation.
- Single-cell exact accepts live but final HPWL flat: add ordered-pair and
  endpoint-escape unit transactions, not another single-cell cap increase.
- Cached scoring improves runtime but changes HPWL: fix audit gap before keeping
  the cache.
- Vacancy/guided producer raises displacement or hurts final HPWL: make it a
  bounded producer hint; the exact consumer must decide promotion.
