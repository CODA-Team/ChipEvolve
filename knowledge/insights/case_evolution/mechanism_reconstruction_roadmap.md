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
- Before coding a selected blueprint, write a compact completeness audit:
  chosen start basin, required producer payload, handoff state, exact consumer,
  post-consumer closure, counters, which links already exist in the current
  source, and which links this iteration will implement or repair.  A route
  that implements only the final polish link is partial evidence, not a full
  blueprint hit.

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

- Start from `diamond` when the main missing link is that a Diamond-style legal
  basin exists but the source-topK/exact global-swap kernel is disabled by
  dispatch, density, or intensity gating.
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
   let dispatch, density, or intensity heuristics silently fall back to weak
   legacy DPO when source-topK, source-edge, or critical-net residue is
   visible.  If the log says an exact path was enabled but intensity is zero and
   legacy global swap was used, the mechanism did not execute.
2. Rank cells by affected-net HPWL, bbox-edge contribution, fanout-normalized
   span, displacement risk, and recent DPO movement.  Generate bounded row/site
   and swap targets from medians, bbox edges, current row, nearby rows, legal
   segment centers, and source-edge candidates.
3. Exact-score every trial with `DetailedHPWL` or a touched-net journal.  Roll
   back all probes and replay only positive candidates.  Clear per-probe
   affected-net state before each exact delta so rejected probes cannot pollute
   later scoring.
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

### Reconstruction Tuning Profile

This blueprint is easy to underbuild.  A useful reconstruction should preserve
the following concrete structure before inventing new move families:

- Keep the exact global-swap producer reachable even on low or uneven density.
  A small exact-lane intensity floor is acceptable for this route; random
  exploration should remain conservative.  Export only the top critical
  accepted footprint, for example a bounded few hundred critical nodes plus
  old/new hot segments.
- `DetailedMgr` should own the native handoff: accepted DPO nodes,
  hot segments, critical-frontier nodes, and masks for de-duplication.  Do not
  rebuild this state from logs or names.
- In `improvePlacement`, the order matters: run the normal DPO script, then
  critical-row micro-start, critical-net chain assignment, exact local closure,
  multi-row residual transactions, and segment-local residual swaps before
  clearing the handoff.
- Critical-row micro-start should rank critical-frontier nodes first and fall
  back to accepted nodes only when no critical frontier exists.  It should only
  use currently hot segments, skip fixed/multi-height/non-single-segment cells,
  rank by displacement, try current/adjacent rows and left/center/right bbox
  anchors, and accept only exact-positive journal deltas after a risk penalty.
  A proven bounded profile is roughly 48 seeds, four candidates per seed, an
  early stop around 192 exact scores with no accepts, row-risk around hundreds
  of dbu, a much larger hot-only segment penalty, a smaller source-escape bonus,
  and a critical-target preference slack so a near-tied critical target wins.
  Accepted micro-start moves should append affected nodes and segments back into
  the native frontier.
- Exact local closure should run window-size-four reorder on windows touching
  accepted/critical nodes and hot segments.  Prioritize windows around displaced
  frontier cells, boost edge-touching windows, include hot-segment edge windows
  only as bounded fallback, cap total windows to a few hundred, and stop after a
  long no-accept streak rather than scanning the whole design.
- Critical-net chain assignment should not be a pair-only swap.  Build
  rollback-safe two- or three-step chains: seed to bbox/median target, local
  partner to seed vacancy, and optional follower to partner vacancy.  Keep a
  small number of move candidates, partners, followers, windows, and accepted
  moves per seed; reject nonpositive replay.
- Multi-row residual transactions should use the same exact-positive rule over
  current/nearby rows, bbox left/center/right anchors, and nearby partner cells.
  Segment-local residual swaps should then try only local neighbors around the
  accepted footprint.  These two late links are quality links, not guard links.

### Complete-Chain Reconstruction Checklist

Treat Blueprint A as live only when the implementation has all of these links:

- exact source-topK/global-swap is reachable from `improvePlacement` and cannot
  silently fall back to weak legacy DPO when source/topK or critical-frontier
  residue is visible;
- exact accepted moves are captured before rollback/journal state is cleared
  and exported as native accepted nodes, touched nets, source/topK cells, hot
  segments, and critical-frontier nodes;
- any legalizer/frontier producer reshapes only payload that the exact consumer
  can later score, instead of optimizing legal HPWL in isolation;
- the post-DPO stack consumes that payload in order: critical-row micro-start,
  critical-net chain assignment, exact local closure, multi-row residual
  transaction, then segment-local residual swap;
- every link reports candidates, exact scores, accepts, accepted gain/delta,
  pass runtime, and final-flow stage movement.

Demote the route to partial if it only enables source-topK, only adds a
critical-frontier mask, only changes a cap, or only adds a residual/guard pass.
If first results are weak but counters show an early link live, the next repair
should fill the first missing downstream link rather than retune the same link.

### Reconstruction Sketch

```text
source_topk_exact_pass():
  make the exact global-swap kernel reachable even when density/intensity
  heuristics would otherwise choose legacy global swap
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
  generation, dispatch/intensity gating, exact scoring, rollback/replay,
  accepted-node capture, hot-segment export, source-topK counters.
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

- No source-topK/global-swap counter lines: repair pass selection, extra-DPL
  enablement, and intensity fallback first.  Do not score this as a low-ROI
  mechanism until the exact kernel is live.
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
- If continuing an existing implementation, preserve the complete accepted-window replay
  chain.  Do not restart from a guard, attribution-only change, or isolated cap
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
   source targets, exact-score them, and apply only replay-positive moves.
7. If single-cell endpoint repair is live but final HPWL is flat, add bounded
   endpoint/source pair or small-cluster exact transactions over the same
   frontier, scored as a unit with rollback.  This is a follow-up repair, not a
   replacement for the source-edge/replay stack.
8. Preserve accepted-window value through canonical downstream passes.  Generic
   random, broad GS, mirror, or reorder passes should not wash out the accepted
   footprint unless their exact gain is positive.

### Reconstruction Tuning Profile

This blueprint is not a negotiation-weight tweak.  A useful reconstruction
should rebuild the endpoint/source producer, then prove that DPO and reorder
consume it:

- Keep the legalizer producer focused on moderate-degree high-span nets.  Rank
  nets by current HPWL impact, ignore trivial and very high fanout nets, and
  mark cells that sit on first/second bbox extrema in x or y.  Accumulate a
  recoverability weight from net rank plus endpoint hits, then keep only the
  highest-value endpoint/source cells.
- Apply the producer as a bounded target-selection bonus inside
  `findBestLocation`, not as an unconditional displacement increase.  Compute
  local slack near the candidate site, scale the bonus by endpoint weight and
  slack, damp it when candidate displacement crosses the max-displacement
  threshold, and revert the biased choice when it grows displacement much more
  than the raw best location.  The expected log signature is nonzero scored
  recoverability candidates, selected cells, and some damped or reverted
  choices; zero reverts with large displacement tail is suspicious.
- Run source-edge/global-swap exact DPO after the negotiation legal state and
  before the hot reorder stack.  The pass should rank source-edge and accepted
  boundary cells, generate bbox-edge, median, current/nearby-row, segment, and
  swap probes, exact-score a small top set, rollback every probe, replay only
  positive candidates, and immediately export accepted nodes plus old/new hot
  segments into `DetailedMgr`.
- Preserve two native handoff masks until the post-DPO consumers finish:
  accepted hot segments and source-edge hot cells.  Do not rebuild these from
  string logs or top-net names.  Handoff must be imported before endpoint/source
  repair and cleared only after replay, cascade, and endpoint repair consume it.
- Hot selected-segment reorder should start from accepted hot segments, expand
  to adjacent segments only as a bounded fallback, and use a larger exact
  window than generic reorder.  It should store accepted windows as replay
  seeds with endpoint/source-edge counts and accepted delta, because those seeds
  are the payload for residual replay.
- Hot micro-pack is a local exact consumer, not a broad reorder.  Build compact
  windows around endpoint/source-edge cells, favor boundary source-edge windows,
  try small shifts/permutations, exact-score each window, and record accepted
  delta.  Its accepted windows should enter the same replay seed buffer with a
  micro-pack flag.
- Accepted-window replay should run in two phases.  First replay bounded local
  windows around the best hot and micro-pack seeds.  Then create cascade seeds
  from accepted replay windows and expand only strong seeds with a slightly
  larger halo/window.  Penalize displacement in the replay score and reject
  low-conversion windows instead of counting them as progress.
- Endpoint/source repair should import the still-live handoff, rank top nets
  touching frontier cells, derive first/second-extreme endpoint hints, and build
  a bounded target set from endpoint hints plus source-edge anchors.  Apply
  only exact-positive endpoint moves.  If single-cell endpoint accepts are live
  but final HPWL is flat, add pair/small-cluster transactions over the same
  touched-net frontier instead of widening single-cell caps.
- Runtime-heavy expansions are acceptable only when accepted gain per runtime
  rises.  Use cached touched-net or bbox summaries, compact top-net/frontier
  caps, and no-accept stops; do not replace the producer-consumer chain with
  global scans.

### Complete-Chain Reconstruction Checklist

Treat Blueprint B as live only when the implementation has all of these links:

- `default_negotiation` or compatible negotiation resource closure is the start
  basin, and the negotiation producer creates bounded endpoint/source
  recoverability pressure on high-span/top-impact nets with displacement and
  slack damping;
- exact source-edge/global-swap consumes the negotiation legal state, scores
  source-edge/boundary cells with rollback/replay, accepts positive moves, and
  exports accepted nodes, source-edge hot-cell masks, and hot segments;
- hot-segment selected reorder and hot micro-pack run over the accepted
  frontier, not over unrelated generic segments;
- accepted reorder/micro-pack windows are stored as replay seeds, then a
  residual replay and a second cascade pass exact-score neighborhoods around
  accepted seeds;
- post-reorder endpoint/source repair imports the incoming handoff before hot
  state is cleared, derives first/second-extreme endpoint targets on top nets,
  and exact-scores endpoint/source moves;
- if single-cell endpoint moves are live but final HPWL remains flat, bounded
  pair or small-cluster endpoint/source transactions score the whole unit with
  rollback instead of only widening single-cell caps;
- later cleanup preserves the accepted footprint unless it proves exact
  positive gain.

Demote the route to partial if it only changes negotiation weights, only adds
source-edge exact GS, only adds pair/cluster transactions, or only guards the
current implementation.  A partial pair/cluster implementation is especially easy to
misread: without recoverability producer, accepted hot handoff, replay/cascade,
and endpoint/source repair, it is not the strong Blueprint B route.

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
  do not let later generic passes erase final-HPWL gains unless they prove exact
  positive
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
   with `DetailedHPWL`, rollback every non-improving probe, and apply only
   positive moves.
7. Rank residual segments by exact-anchor count and residual magnitude, then run
   selected-segment exact reorder and optional local transactions only on those
   segments.
8. Protect exact scoring by clearing stale affected-net state at the beginning
   of each `DetailedHPWL::delta` call.

### Reconstruction Tuning Profile

This blueprint works when LEGALM/full guidance creates a low-residual target
field that detailed placement can consume.  A useful reconstruction should keep
the legalizer and DPO tied by native target state:

- In full legalization, distinguish low-residual overflow from high-pressure
  overflow.  For low-residual cases, keep target-row search narrow, spend
  effort on target correction/current-net anchors, and avoid broad legalizer
  moves that lower `HPWLlg` while destroying the final DPO basin.
- During assignment and stage2 handoff, store target row/site/valid state for
  each movable cell.  Include target-row, desired-site, original-site,
  midpoint, and a small number of HPWL projection anchors, but use maintained
  interval/free-site checks and `canBePlaced` before publishing a target.
- Stage3 exact refinement should build incident-net summaries with first and
  second bbox extrema, skip very high-fanout nets, and form a frontier from
  changed cells plus target-miss cells.  Rank by target distance, displacement,
  and HPWL regression risk; cap the frontier and stop after a long no-move
  streak rather than scanning all cells.
- Current-net anchors are the important quality source.  For each frontier
  cell, project bbox-extreme pins back inside the other pins' bbox, convert the
  projected pin center to a legal grid point, and also try a shadow point part
  way toward that projection.  Keep only a small number of anchors with positive
  projected gain, reject anchors that add displacement without target relief,
  and tag accepted target rows/sites as exact anchors.
- Candidate generation should mix target repair and current-net repair:
  current row/site, target row/site, original row/site, midpoints, nearby rows,
  anchor row/site, old row with anchor site, target row with anchor site,
  anchor row with old site, and a few adjacent/toward-target expansions.
  Exact-score only the best bounded candidates by proxy score.
- Acceptance must combine exact HPWL, displacement, and target recovery.  Accept
  moves that improve exact HPWL, recover displacement without HPWL loss, or
  recover target distance with bounded HPWL/tail cost.  Reject moves that grow
  max-displacement tail unless exact HPWL gain clearly pays for it.  After a
  move, update target row/site/valid, mark exact-anchor state, and recompute
  touched net summaries.
- Low-residual target correction/release is a supporting producer repair.  It
  should repair missed targets using free slots, swaps, and blocker release only
  when exact HPWL, displacement, and target-distance deltas stay bounded.  Track
  blockers, probes, exact-score caps, rejects, HPWL gain, displacement gain, and
  target gain separately so Teacher can see whether the producer became more
  consumable.
- In `improvePlacement`, split the imported target field into row-miss and
  same-row residual queues.  Give each queue quota so same-row residual cells
  with exact anchors are not starved by row-miss cells.  Score vertical moves
  first for row-miss cells, then targeted global moves; rollback all
  nonpositive probes.
- Selected-segment reorder should rank segments by exact-anchor count, weighted
  target residual, anchor count, and max residual.  Run a bounded selected
  reorder on those segments, then only arm pair/cycle transactions when
  stage3 exact handoff cells and exact residual anchor cells are both nonzero.
  Pairs should swap nearby same-width anchors; cycles should rotate a short
  local chain.  Guard-only vertical or selected-segment attribution is not the
  mechanism.
- Required liveness is the full chain: stage3 exact/current-net anchors produce
  exact-anchor target state; improve placement imports that state; targeted
  vertical/global accepts or selected-segment accepts are nonzero; final-flow
  HPWL moves in the same direction as accepted exact gain.

### Complete-Chain Reconstruction Checklist

Treat Blueprint C as live only when the implementation has all of these links:

- `framework` LEGALM/full-guidance code acts as a recoverable producer and
  publishes target rows, target sites, valid flags, exact-anchor flags,
  target-miss cells, and stage3 handoff cells;
- stage3 exact/current-net refinement uses target rows/sites, current-net
  anchors, target-miss cells, nearby rows, and displacement-aware legality to
  accept only exact-positive producer moves;
- `improvePlacement` imports the producer state and builds a compact frontier
  from moved cells, exact anchors, row-miss cells, same-row residual cells,
  dirty segments, and target-miss cells;
- targeted exact global and vertical wrappers consume that frontier with
  rollback/replay and report exact accepted gain;
- selected-segment reorder ranks residual segments by exact-anchor count and
  residual magnitude, then exact-scores local windows or transactions on those
  segments;
- affected-net delta state is reset per probe so stale scoring cannot create a
  false gain.

Demote the route to partial if it only changes LEGALM target costs, only lowers
`HPWLlg`, only adds vertical/frontier guards, or only preserves a previous
selected-segment state.  If legal HPWL improves but final flow worsens, repair
the current-net/target-miss consumer path before widening legalizer search.

### Reconstruction Sketch

```text
legalm_stage3_producer():
  for candidate cells near target-miss/current-net anchors:
    generate legal row/site candidates from target row/site, current row,
    nearby rows, current-net anchors, adjacent rows, and toward-target sites
    exact-score legal candidates; apply only positive/refined moves
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

## Blueprint D: Diamond Source-TopK/Source-Edge Exact DPO Activation

Use when a Diamond-style legal basin is clean but improve placement underuses
the available source/topK or source-edge cells because low density/intensity
falls back to weak legacy search.  Legal HPWL may be neutral or worse; the
quality source is exact global-swap acceptance and the selected-segment reorder
that consumes accepted hot segments.  Ordered-pair and endpoint-escape work are
repairs after the first exact lane is live, not prerequisites for the first win.
This route is exact DPO activation, not LEGALM and not negotiation.

### Start Basin

- Start from `diamond` when the plain Diamond legal basin is clean and the first
  missing link is an always-reachable exact source-topK/global-swap consumer.
- Start from `evolved_diamond` only when it keeps the same exact-DPO activation
  surface while adding useful frontier or hot-segment infrastructure.
- Do not use this blueprint when the main evidence is negotiation
  endpoint/source recoverability; use Blueprint B for that.

### Cumulative Mechanism Chain

1. Ensure the improve-placement schedule calls the exact global-swap
   implementation in the normal flow.  If a branch has an extra-DPL enable knob,
   the route must turn it on for this lane.
2. In detailed global swap, prevent low-density/intensity settings from
   disabling the exact path.  Use a small nonzero intensity floor or an explicit
   source-topK/source-edge override, but keep random exploration conservative.
   A log line that reports legacy global swap after intensity zero means this
   route failed to execute.
3. Generate bounded source-topK probes for each movable source cell from
   median/bbox-edge anchors, projected source position, current/nearby rows,
   legal segment centers, and legal same-width swap partners.
4. Exact-score a small top-K set with `DetailedHPWL::delta` over the journal.
   Clear affected-edge state before each delta, rollback every probe, replay the
   best positive move/swap, and reject nonpositive replay.
5. On every accepted source-topK move, capture the moved node and old/new
   segments from the accepted journal before the journal is cleared.  Store them
   as native manager state: accepted nodes, hot segments, and optional
   source/topK masks.
6. Run selected-segment reorder immediately after global swap.  Consume the hot
   segments first, exact-score local reorder windows, and record windows,
   accepts, and gain.  This selected reorder is the first downstream consumer;
   without it, the source-topK pass is easy to wash out.
7. If single-cell exact accepts are live but final HPWL plateaus, add
   ordered-pair transactions over overlapping affected nets, then endpoint-escape
   partners.  Score each pair/escape as one rollback-safe transaction.
8. Runtime guards may reuse scratch buffers, cache affected-net deltas, or skip
   saturated cells only after the exact source-topK/source-edge accepts and
   selected-segment reorder remain semantically identical.

### Reconstruction Tuning Profile

This blueprint is a narrow Diamond/source-edge activation route.  It should not
be selected merely because a design is low-utilization; select it when the
source-edge or source-topK exact lane itself is the missing DPO source.  A
useful reconstruction should include these details:

- Source-edge hotness should be computed before Diamond legal placement from
  high-span, moderate-degree nets.  A proven bounded profile ignores very large
  nets, keeps only a small hot-cell set such as `max(64, cells/64)` capped at a
  few hundred cells, stores hotness directly on the native node/instance, and
  restores that native state before improve placement.
- Diamond producer guidance should be bounded: source-edge hot cells may choose
  among several legal candidate sites by estimated weighted HPWL gain minus a
  modest displacement penalty.  Vacancy probing is optional and must be small:
  a few blocked probes, at most a couple of blockers, reject cases where evicted
  blockers are comparably hot, and require a clear score margin after blocker
  displacement penalty.  This is only producer shaping; the exact DPO consumer
  decides quality.
- The exact source-edge/global-swap lane must run even when density-derived
  intensity is zero.  Low intensity should disable congestion/random extras, not
  fall back to legacy global swap.  Logs must explicitly show HPWL-only
  source-edge or sourceTopK exact scoring rather than legacy-only search.
- For each source cell, generate candidate rows from current row, bbox-center
  row, and bbox-edge rows, then cap to the nearest few rows.  Generate
  left-edge, center, and right-edge anchors and exact-score only a small top-K
  set, e.g. six probes.  Try move first, then same-width swap if needed.  Use
  `DetailedHPWL` journal delta/cache, rollback every probe, and replay only the
  best positive journal.
- Ordered-pair repair should be attached to a live single-cell exact probe, not
  run as a separate polish pass.  Rank same-net standard-cell partners by
  bounded pin degree and distance to the source vacancy, keep only a handful of
  partners, score a few partner probes into the source vacancy/current row, and
  promote the combined stage1+stage2 journal only when it beats the stage1
  profit.  Audit cached affected-net delta periodically and reject nonzero audit
  drift before trusting runtime gains.
- Endpoint-escape repair is a later, smaller fallback for hot source-edge
  anchors.  Rank one or a few positive-residual edges, one or a few endpoint
  partners, and one or a few probes; score the combined journal as a unit.  It
  should improve a live source-edge route, not replace the source-edge exact lane.
- Required liveness is stronger than counters existing: hot cells, generated
  exact probes, exact scores, accepted single-cell moves, accepted pair or
  escape transactions if enabled, zero or explained audit gap, and final-flow
  HPWL movement.

### Complete-Chain Reconstruction Checklist

Treat Blueprint D as live only when the implementation has all of these links:

- `diamond` is the start basin and source-edge/source-topK evidence is the
  intended DPO recovery source, not a LEGALM or negotiation producer;
- source-edge hot-cell marking or source-topK ranking produces bounded native
  hot tags/candidates before detailed global swap;
- detailed global swap explicitly prevents low-density/intensity fallback from
  bypassing the exact source-topK/source-edge path;
- bounded median, bbox-edge, current/nearby-row, segment-center, and swap
  probes are exact-scored with rollback and only positive trials are replayed;
- accepted nodes and old/new segments are captured before journal cleanup and
  preserved in manager state until selected-segment reorder consumes them;
- selected-segment reorder runs immediately on accepted hot segments and reports
  windows, accepts, and gain;
- only after single-cell exact accepts are live, ordered-pair and endpoint-escape
  transactions score overlapping affected-net units with audit-safe cached
  deltas.

Demote the route to partial if it only marks hot cells, only adds vacancy or
guided legal ordering, only changes the intensity floor, only optimizes the
cache, or only adds endpoint-escape guards.  If logs still show legacy global
swap, the blueprint did not execute regardless of final metrics.

### Reconstruction Sketch

```text
source_edge_producer():
  rank movable cells by high-span net bbox-edge contribution and endpoint/source
  hotness
  store source-edge hot tags on native nodes/instances
  optionally use guided legal candidate ordering or vacancy probes for hot cells,
  but keep this bounded and rollback-safe

source_edge_exact_consumer():
  force exact source-topK/source-edge GS to execute when the Diamond basin is
  clean and DPO recovery is the likely HPWL source
  for each movable source or hot cell:
    generate median, bbox-edge, current-row, nearby-row, segment-center, and
    swap probes
    exact-score bounded top-K single-cell move/swap trials; rollback each probe
    replay only the best positive trial
    record accepted node and old/new segments before clearing the journal
  run selected-segment reorder on accepted hot segments
  if single-cell exact accepts are live but flat:
    exact-score ordered-pair and endpoint-escape transactions as one unit
  log exact-scored probes, accepts, accepted_delta, hot segments, reorder
  windows/accepts, and audit gap for cached scoring
```

### Source Handles

- `src/Place.cpp`: source-edge hot-cell marking, guided legal candidate ordering,
  bounded vacancy probe behavior, and producer counters.
- `include/dpl_evolve/Opendp.h` and `src/Opendp.cpp`: source-edge hot-cell state,
  guided/vacancy counters, reset/report/metric plumbing.
- `src/optimization/detailed_global.{h,cxx}`: exact HPWL-only source-edge path,
  source-topK candidate generation, intensity/legacy fallback control,
  ordered-pair transaction generation, endpoint-escape partner generation,
  rollback/replay, and accepted counters.
- `src/optimization/detailed_manager.{h,cxx}`: accepted-node state, hot segment
  storage, optional source/topK masks, and handoff lifetime until reorder
  consumes it.
- `src/optimization/detailed_reorder.{h,cxx}`: selected-segment reorder over
  hot segments, accepted-window logging, and follow-up exact local windows.
- `src/objective/detailed_hpwl.{h,cxx}`: affected-net delta reset, optional
  cache replay, and audit gap comparison.
- `src/optimization/detailed.cxx` and `src/Optdp.cpp`: ensure pass selection and
  intensity do not bypass the source-edge exact consumer when hot tags exist.

### Required Counters

- source-edge producer hot cells, guided cells, guided legal candidates,
  reranked candidates, vacancy attempts/applies/rollbacks, and vacancy bonus;
- exact source/topK cells, raw candidates, generated candidates, exact scored,
  replays, replay failures, rollbacks, accepted moves, accepted delta, hot
  generated, hot accepted, and hot accepted delta;
- selected-segment reorder frontier segments, windows, accepts, and accepted
  gain;
- ordered-pair stage1 exact probes, pair candidates, scored pairs, cached
  overlap edges, promoted pairs, accepted pairs, accepted delta, and audit gap;
- endpoint-escape edges, partners, candidates, scored, cached overlap edges,
  promoted escapes, accepted escapes, accepted delta, and audit gap;
- runtime of exact source-edge pass and final full-flow HPWL.

### Self-Diagnosis And Repair

- Hot tags zero: repair `Place.cpp` source-edge producer and state reset before
  editing detailed global swap if this route relies on source-edge tags.  If
  the route is source-topK-first, hot tags may be zero, but source-topK
  candidates and exact-score counters must be nonzero.
- Hot tags live but exact scored zero: repair pass scheduling/intensity fallback
  and exact-source-edge candidate generation.
- Exact source-topK counters absent and the log reports legacy global swap:
  repair the extra-DPL enable path and intensity fallback; do not pivot to
  LEGALM, negotiation, or guard work.
- Single-cell exact accepts live but final HPWL flat: add ordered-pair and
  endpoint-escape unit transactions, not another single-cell cap increase.
- Cached scoring improves runtime but changes HPWL: fix audit gap before keeping
  the cache.
- Vacancy/guided producer raises displacement or hurts final HPWL: make it a
  bounded producer hint; the exact consumer must decide promotion.
