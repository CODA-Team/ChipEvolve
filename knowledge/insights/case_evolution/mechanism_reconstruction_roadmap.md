# Mechanism Reconstruction Roadmap

## Agent Use

- Role: direct Teacher/Student reconstruction core after a blueprint is selected.
- Open only the selected blueprint section or generated focused packet; do not broad-read all blueprints during ordinary routing.
- Use these roadmaps to give source handles, implementation order, liveness counters, and demotion tests.


This card contains implementation roadmaps for case-type mechanisms selected by
`case_type_quality_mechanism_priority.md`.  Teacher should not ask Students to
read every section.  Select the matching blueprint, then copy the relevant
source handles, implementation order, counters, and first repair rule into the
Student packet.

The roadmaps are mechanism blueprints, not fixed recipes.  Students may redesign
details when source evidence suggests a better implementation, but the report
must prove which links are live and which link blocks final HPWL movement.

## Shared Source Anchors

Use these anchors inside the private `dpl_evolve` source prepared in each
Student workspace.

- Flow composition: `src/StudentAlgorithm.cpp`, especially
  `Opendp::runStudentAlgorithm`, when changing the order or coupling of
  guidance, legal closure, handoff, and improve-placement preparation.
- Top-level DPL state: `src/Opendp.cpp` and `include/dpl_evolve/Opendp.h` for
  `EvolveContext`, max-displacement defaults, `reportEvolvePlacementMetrics`,
  target arrays, `network_`, `arch_`, `grid_`, and persistent handoff fields.
- LEGALM/Differential producer: `src/LegalmGuidance.cpp`,
  `src/DifferentialGuidance.cpp`, and `src/LegalmFullLegalization.cpp` for
  target objectives, target release, overflow handling, high-pressure handling,
  residual state, and guidance stop points.
- Negotiation closure: `src/EvolveNegotiationRepair.cpp`,
  `src/NegotiationLegalizer.cpp`, `src/NegotiationLegalizerPass.cpp`, and
  `src/NegotiationLegalizer.h` for conflict/resource legalization, history
  cost, location scoring, and residual/conflict counters.
- Improve-placement schedule: `src/Optdp.cpp` for internal detailed-improvement
  pass order, source-internal parameters, and handoff import into DPO.
- Exact DPO consumers: `src/optimization/detailed_global.cxx`,
  `src/optimization/detailed_global_legacy.cxx`,
  `src/optimization/detailed_reorder.cxx`,
  `src/optimization/detailed_manager.{h,cxx}`,
  `src/optimization/detailed_random.{h,cxx}`, and
  `src/objective/detailed_hpwl.{h,cxx}` for candidate generation,
  affected-net scoring, journal delta, accept/rollback, selected-segment
  reorder, and basin escape.
- Native data: prefer `Node`, `Edge`, `Pin`, `Group`, `Network`,
  `Architecture`, `Grid`, segment ids, row ids, and journal state.  Avoid bulky
  coordinate logs and string-keyed hot-path maps when native ids or objects can
  carry the state.

Every route should emit compact counters: produced frontier count,
consumed/probed count, exact accepts, accepted HPWL gain or accepted delta,
rollback/reject count, runtime for each bounded pass, and
`accepted_delta_per_runtime` or enough accepted-delta/runtime fields to compute
it.

## Blueprint A: Diamond-Basin Source-Edge Exact DPO

Use when a Diamond-compatible legal basin is stable and detailed improvement
leaves source-edge or bbox-edge residue.  This is a source-local DPO route, not
a legalize-only route: preserve the legal basin, force the enhanced global-swap
consumer to execute, exact-score source-edge move/swap candidates, and repair
canonical replay if internal gain does not reach the final flow.

### Source-Edge Producer Plus Exact Consumer Variant

Use this variant when the start basin is Diamond-compatible and the legalizer
still controls enough local order to expose DPO-friendly source-edge cells.  The
producer is not a separate legalizer win; it only marks and preserves a
recoverable local order for the exact DPO consumer.

1. Before or during legal closure, rank movable cells by source-edge hotness:
   high-HPWL nets with bounded pin count, bbox-edge endpoint contribution,
   fanout-normalized span, and cells that block another hot source-edge cell.
2. Store hotness on native cell/`Node` state or a bounded id vector.  Clear or
   restore the hints after the pass so stale hotness cannot bias unrelated
   later work.
3. In legal candidate selection, use the hotness only as a bounded bonus.  The
   selected location must remain legal and displacement-aware.  Dampen the bonus
   when it grows max displacement, extends an already high-displacement cell, or
   offers no net-aware margin.
4. If a hot source-edge cell is blocked by a small number of lower-value cells,
   try a bounded vacancy/eviction transaction: snapshot all touched cells,
   attempt the hot move plus blocker repair, exact-score the touched nets, and
   rollback all cells unless the bundle remains legal and positive.
5. Feed accepted hot cells or vacancy commits into the same exact source-edge
   DPO route below.  The producer is useful only if DPO later reports exact
   scores, replays, accepts, and final-flow HPWL movement.

Required producer counters:

- source-edge hot cells, guided legal cells, guided candidates, guided
  reranked cells, guided estimated bonus;
- vacancy attempts, commits, rollbacks, evicted cells, and accepted/estimated
  vacancy gain;
- DPO consumer counters tied to those hot cells.  If producer counters are live
  but consumer accepts are zero, repair the handoff or candidate quality before
  tuning producer weights.

### Implementation Order

1. Start from `evolved_diamond`, `diamond`, or a current Diamond-compatible
   basin donor.  If the donor has a useful basin kick or shell/edge producer,
   preserve it; the first quality patch should make DPO consume the residue.
2. In `src/Optdp.cpp::Opendp::improvePlacement`, make sure the enhanced
   global-swap/DPO path executes in the normal improve-placement flow.
   Low-utilization or low-intensity cases must not silently fall back to legacy
   global swap before exact source-edge candidates are scored.  If the default
   heuristic computes a low intensity despite visible source-edge residue, add a
   hotspot/rescue intensity path that activates the exact consumer and then
   stops by accepted gain, not by raw utilization alone.
3. In `src/optimization/detailed_global.h`, add or verify exact-source-edge
   state in `DetailedGlobalSwap`: a temporary exact HPWL scorer, a flag/delta
   for source-edge moves, and counters for cells, candidate locations, proxy
   skips, exact move/swap scores, replays, commits, replay rejects, nonpositive
   bests, best-delta sum, and committed-delta sum.
4. In `DetailedGlobalSwap::globalSwap`, construct the exact HPWL scorer for
   the pass, set it before candidate generation, and restore it afterward.  Use
   journal or touched-net exact HPWL as the acceptance truth; call the HPWL
   accept/update only for committed moves.
5. In `DetailedGlobalSwap::generateWirelengthOptimalMove`, replace weak
   median-box-only or random fallback targeting with a bounded source-edge
   generator.  Candidate rows/sites should come from median pin coordinates,
   bbox interval centers, bbox edges excluding the source cell, current
   row/position, nearby legal rows, and available legal segments under
   displacement limits.
6. Use a cheap source-edge/interval proxy only to filter or rank.  Exact-score
   direct move and swap variants through the journal, rollback immediately,
   retain the best exact-positive candidate, replay it once, and commit only if
   replay still has positive exact delta.  Tie-break by exact delta first, then
   proxy/support/distance.
   A concrete reconstruction should look like this:
   - build the active source list from bbox-edge contributors, high affected-net
     HPWL cells, cells on long two-pin or sparse nets, and recently moved DPO
     cells; skip fixed cells and candidates that cannot remain legal under the
     displacement limits;
   - for each source, form a bounded target set from its current site, net median
     row/site, bbox interval centers, bbox min/max edge projections excluding
     the source, nearby legal rows, and legal-segment centers/endpoints;
   - for each target, try direct move first, then same-height legal swap around
     the target segment; exact-score with the same journal or touched-net HPWL
     object that will be used for replay, and rollback every trial;
   - replay the best exact-positive candidate on the live placement, recompute
     the affected nets, and update accepted-source, accepted-target, affected
     segment, and accepted-delta state only after replay remains positive.
   - record accepted moved nodes, touched nets, touched segments, and accepted
     delta in `DetailedMgr`; downstream reorder or pair/endpoint polish should
     consume this native state rather than re-discovering it from logs.
7. If accepted gain is visible in internal counters but not in canonical final
   HPWL, repair the basin contract before widening search: snapshot and restore
   location, placed state, segment assignment, and orientation; accept basin
   candidates by canonical legal HPWL, not only an internal pass score.
   The snapshot must cover cell left/bottom, orient, placed flag, row/segment
   assignment, and any manager occupancy touched by the trial.  After restore,
   recompute canonical OpenDB/DPL HPWL and reject internal-only wins.  If the
   canonical value does not match the restored state, fix snapshot or manager
   synchronization before adding more candidates.
8. Only after source-edge commits and canonical preservation are live, add
   selected-segment, pair, endpoint, or mirror-dependent consumers.  They extend
   accepted exact DPO moves; they are not substitutes for this route.
   A good downstream extension is: post-DPO selected reorder over focused/hot
   segments, then same-segment assignment-boundary polish, touched-pair polish,
   and touched-endpoint polish.  Each extension must be anchored on accepted
   source-edge or assignment state and report its own exact accepted delta.

### Required Counters

- enhanced DPO dispatch in the normal improve-placement flow;
- source-edge producer hotness/vacancy counters when the producer variant is
  used;
- source-edge cells, candidate locations, proxy skips, exact move/swap scores,
  replays, commits, replay rejects, nonpositive bests, average best delta, and
  average committed delta;
- focused nodes/segments, hot-segment seeds, same-segment assignment candidates,
  assignment-boundary probes/accepts, and post-consumer exact/pair/endpoint
  accepted delta when downstream consumers are enabled;
- low replay reject rate or a concrete replay/legality/journal repair;
- `HPWLimprove` movement and final HPWL movement after canonical replay/restore;
- any selected-segment, endpoint, pair, or mirror work identified as downstream
  of accepted source-edge moves.

### Partial Routes To Demote

- Diamond frontier records with no exact source-edge consumer;
- source-edge or endpoint telemetry without changing the exact candidate
  generator and acceptance path;
- exact candidates that are scored but never replayed or committed;
- proxy-positive moves accepted without journal/touched-net exact scoring;
- mirror ordering, guard, basin kick, or runtime trimming before source-edge
  exact commits are live;
- internal HPWL wins that cannot be restored to the canonical DB state.

### Validated Large Row-Rich Critical-Frontier Diamond-DPO Route

Use this route when the design is large and row-rich, legality is stable, and
most quality comes from a broad improve-placement recovery.  The mechanism is a
cumulative chain; a later guard or tiny residual-swap commit is not the source
of the win.

1. Start from `evolved_diamond` and keep the legal basin stable.
2. In the active global-swap path, keep exact source-topK scoring live even when
   a density/intensity heuristic would otherwise reduce the route to legacy
   behavior.  Exact-score candidate moves/swaps with journal HPWL and commit
   only positive deltas.
3. Convert accepted global-swap evidence into native handoff state: hot
   segments from accepted move journals and critical frontier nodes from cells
   or nets with large accepted delta.  Store this in `DetailedMgr` as segment
   ids and `Node*` frontier state, not as passive text logs.
4. In `src/Optdp.cpp::Opendp::improvePlacement`, run the post-DPO consumer chain
   in this order: critical-row micro-start, frontier attribution, critical-net
   chain assignment, exact local closure, multi-row residual transactions, and a
   small segment-local residual swap/polish.
5. In `src/optimization/detailed_reorder.cxx`, each consumer should exact-score
   with rollback and accept only positive journal/touched-net deltas.  The
   chain should use the merged accepted-move and critical-frontier state rather
   than scanning every row as an undifferentiated tail.
6. If the residual-swap stage accepts only tiny gain, do not keep retuning seed
   priority.  Change the move family, the frontier payload, or the transaction
   shape, while preserving the upstream source-topK and critical-frontier links.

Concrete reconstruction sketch:

- source-topK pass: rank cells by affected-net HPWL, bbox-edge contribution,
  fanout-normalized net span, and source-edge residue; exact-score a bounded
  move/swap set and commit only positive journal deltas;
- frontier handoff: build `active_frontier` from accepted DPO move nodes and
  critical net endpoint nodes; build hot segment masks from accepted journals,
  moved rows, and segments that repeatedly bound high-span nets;
- micro-start: for each frontier node, generate anchors from critical-net bbox
  edge projections, net medians, current row, neighbor rows, and legal segment
  centers; score each trial as exact HPWL delta adjusted by legality risk and
  displacement pressure, with preference for targets that shorten critical nets;
- chain assignment: when one accepted move exposes another high-impact endpoint
  or segment, enqueue it as the next chain node instead of returning to a global
  scan; each chain step must exact-score and rollback independently;
- exact closure: after the chain, run row-local exact reorder/shift around the
  touched segments and only then a bounded multi-row residual transaction over
  the remaining connected touched-net component;
- residual swap/polish: use this as the last small cleanup around the accepted
  footprint; if it is the first or only live stage, the route is incomplete.

Required liveness pattern:

- `DPL-0926` source-topK stats report candidates, exact scores, replays,
  accepts, and accepted delta;
- `DPL-0927` or equivalent critical-frontier stats report frontier nodes and
  hot segments;
- micro-start logs report frontier cells/segments, probes, accepts, appended
  nodes/segments, and adjusted gain;
- chain assignment, exact closure, multi-row transactions, and residual swaps
  each report probes, accepts, rollbacks, accepted gain, and before/after HPWL;
- final HPWL improves with controlled runtime.  If only counters move, repair
  candidate quality or canonical preservation before adding another guard.

Demote these partial hits:

- source-topK exact accepts with no hot/critical handoff consumer;
- critical-frontier logs that are never consumed by reorder/closure;
- micro-start or chain counters that are live but do not change final HPWL and
  are only guarded in later rounds;
- residual-swap or mirror work presented as the whole mechanism.

## Blueprint B: Negotiation-Start Hot-Segment Exact Consumer Stack

Use when a negotiation-compatible legal basin is legal but not HPWL-optimal and
downstream DPO can recover a large portion of the damage.

### Validated Negotiation/Hot-Segment Exact Consumer Stack

Use this reconstruction when a negotiation-compatible legal basin or row-rich
legal state is recoverable by DPO.  The strong route is not negotiation alone
and not endpoint polish alone: it is a source/edge exact consumer that creates
hot or edge-critical segments, then a selected reorder and post-reorder exact
consumer that actually uses them.

1. Choose the start basin by evidence.  Use `evolved_negotiation` or
   `default_negotiation` when conflict/resource closure is primary and leaves a
   recoverable legal state.  Use `evolved_diamond` or `diamond` when the same
   source-edge residue exists without a negotiation advantage.
2. If negotiation is the start basin, add a recoverability producer inside
   `src/NegotiationLegalizer*.cpp` before DPO.  Rank high-HPWL nets, identify
   endpoint cells on those nets, and give those cells a bounded preferred
   location bonus when a candidate location improves their DPO recoverability.
   The bonus must be damped by displacement growth and must revert to the normal
   cost when it only moves a cell farther from the allowed displacement budget.
3. In `src/Optdp.cpp`, keep the improve-placement schedule explicit.  A useful
   schedule runs exact global-swap/source-edge search, optional targeted
   vertical probes when vertical residue exists, selected-segment reorder, and
   only then post-reorder exact/pair/endpoint polish.  Broad random tails should
   be light and should not replace the exact consumers.
4. In `src/optimization/detailed_global_legacy.cxx` or the active global-swap
   file, generate both base and edge/source candidates.  Rank candidate sites by
   bbox/edge relevance, exact-score with journal or touched-net HPWL, accept
   only positive deltas, and record edge-critical segments or cells from
   accepted moves.  When the negotiation producer is live, run the exact
   consumer in handoff mode: seed target hints from incoming hot segments,
   source-edge hot cells, top endpoint nets, and endpoint pins on the current
   bbox boundary.
5. In `src/optimization/detailed_manager.{h,cxx}`, carry the accepted segment
   and edge-critical state as native segment/node/edge ids.  The handoff is only
   useful if reorder or polish consumes it in the same flow.
6. In `src/optimization/detailed_reorder.cxx`, select hot or edge-critical
   segments first, then run exact reorder windows.  Record queued segments,
   selected segments, edge-selected segments, processed segments, accepts,
   shift failures, accepted delta, and edge accepted delta.
7. Post-reorder exact, pair, and endpoint polish should be anchored on reorder
   touched nodes/edges.  Each probe is exact-scored, rolled back on nonpositive
   delta, replayed once, and counted separately.  Endpoint polish is a late
   consumer of touched edges, not an independent route.
8. If runtime grows with flat final HPWL, repair selectivity or gain-rate first:
   candidate quality, accepted-delta per runtime, touched-edge preservation, or
   canonical replay.  Do not widen endpoint/pair caps without evidence that the
   current consumer is under-covered rather than saturated.

Concrete reconstruction sketch:

- first stage exact GS/source-edge: produce accepted moves and record the source
  node, target segment, touched nets, exact accepted delta, and replay status;
- negotiation recoverability producer: count top nets, candidate endpoint
  cells, scored candidates, preferred-location bonuses, damped bonuses,
  selected cells, and preferred-location reverts; keep the producer only if the
  handoff consumer later accepts exact positive moves;
- optional vertical probe: run only when the accepted footprint or stage metrics
  show vertical residue; exact-score adjacent-row or multi-row probes and keep a
  separate accepted-delta counter so it cannot mask a dead GS route;
- hot queue: convert accepted journals into segment weights and edge-critical
  weights; selected reorder must pull from this queue before any broad row scan;
- selected reorder: snapshot each selected segment/window, exact-score reorder
  candidates, rollback nonpositive windows, and report accepted edge and normal
  segment gains separately;
- post-reorder exact, pair, endpoint: anchor all three on reorder-touched nodes
  or accepted source-edge nodes, run them in that order, and require each stage
  to show exact-positive accepted delta before it is expanded.

Required liveness pattern:

- exact global/source-edge stats include generated candidates, exact-scored
  candidates, accepts, replay failures, and accepted delta;
- negotiation recoverability stats, when enabled, show nonzero selected
  endpoint/source cells and bounded displacement-damped bonuses;
- edge-critical or hot-segment queues are nonzero and consumed by reorder;
- selected reorder reports accepted delta and edge accepted delta;
- post-reorder exact/pair/endpoint stages report probes, accepts, replay
  failures, accepted delta, and pass runtime;
- final HPWL moves after the complete chain, not just after legalization.

Demote these partial hits:

- negotiation/resource closure that is legal but has no DPO consumer accepts;
- vertical or edge handoff whose selected segment count stays zero;
- endpoint or pair polish with no upstream exact accepts;
- post-reorder endpoint work that creates overlaps or legality failures;
- gain-rate or runtime edits that preserve a weak donor without changing the
  quality mechanism.

### Source-Edge/Endpoint Saturation Escape

Use this rule when source-edge, pair, or endpoint counters are live across
several rounds but final HPWL keeps returning to the same basin.

1. Keep one continuation only if it changes objective, transaction granularity,
   or preservation contract.
2. Send other Students to a different HPWL source: alternate start basin, new
   critical-frontier payload, row-window/component transaction, top-net
   target/source repair, or canonical replay/restore repair.
3. Required proof for the new route is a different producer-consumer stage tuple,
   not just larger counts in the same endpoint/source family.

### Implementation Order

1. Start from `evolved_negotiation` or `default_negotiation` when conflict or
   resource closure is the useful basin.  Prove the negotiation path is primary
   before tuning its cost.
2. Add or retain bounded exact global-swap frontier search in
   `src/optimization/detailed_global_legacy.cxx`: candidate rows around bbox
   center/edges, ranked segments, top-K exact-score caps, and affected-net
   rollback scoring.
3. When vertical residue exists, add bounded multi-row or high-degree vertical
   probes in `src/optimization/detailed_vertical.cxx`.  Require legal probes
   and positive accepted-delta counters.
4. In `src/optimization/detailed_manager.{h,cxx}`, add hot-segment state:
   functions equivalent to marking hot segments from accepted journals, keeping
   segment weights and edge-critical weights, returning ordered hot segments,
   and clearing them after consumption.
5. In `src/optimization/detailed_reorder.cxx`, consume the hot segments or
   edge-critical cells created by exact global-swap.  Selected-segment reorder
   should use those segments first; it should not disguise a broad all-row
   scan.
6. Fuse edge-critical global-swap evidence into reorder: edge/frontier
   candidates not fully consumed by global-swap become selected reorder
   segments.
7. Add post-reorder polish only after selected-segment reorder is live:
   exact local polish around touched nodes, pair-swap polish around touched
   edges, and endpoint move polish around high-distance endpoint cells.  Each
   stage exact-scores with rollback and commits only positive candidates.
8. Keep exact affected-net or journal delta as the acceptance truth across the
   stack.

### Required Counters

- exact global/frontier generated candidates, top-K candidates, exact-scored
  candidates, accepted sites, replay failures, and accepted delta;
- hot segment count, selected segments, selected edge segments, processed
  segments, accepted segments, accepted edge segments, and reorder accepted
  delta;
- post-reorder exact, pair, and endpoint probes, duplicates, nonpositive
  candidates, accepts, replay failures, and accepted delta;
- final HPWL movement after the full flow.

### Partial Routes To Demote

- endpoint or pair polish on top of a weak upstream consumer;
- final preservation commits treated as the mechanism while omitting global,
  vertical, hot-reorder, or post-reorder links;
- broad reorder windows with zero selected-segment accepts;
- mirror-only work before exact DPO consumers are saturated.

## Blueprint C: Wrapper/Macro Row-Window Replay And Handoff

Use when macro, memory, hierarchy, blockage, or wrapper structure fragments
standard-cell logic into repeated row-window basins.

### Cross-Case Validated Wrapper Routes

For wrapper-like cases, the first plan should not be only a guard or a small
mirror/reorder tweak.  Two mechanism chains have the strongest evidence for
this feature class.  Teacher can assign both in parallel when the stage metrics
show both residual/window structure and source-edge residue.

Route C1: residual-window producer plus row-window consumer.

1. Start from `framework` when the legalizer exposes residual target misses,
   stage3-repaired cells, or compact residual cells/nets after legalization.
2. In the legalizer/guidance code, keep a recoverable producer live rather than
   optimizing `HPWLlg` alone.  Useful producer payloads are target-miss cells,
   stage3-repaired cells, residual nets, compact components, and current-net or
   target-correction anchors.  A strong producer shape is frontier target
   release: compute the desired row/site, then clamp it to a recoverable
   row/site shift that relieves the source basin without over-growing
   displacement.  Log frontier target cells, clamped target cells, cells
   released back toward source, recoverable row-clamp count, released cells,
   tail-filtered cells, and average release distance.
3. In `src/Optdp.cpp`, import a bounded residual payload into improve placement
   and enable the enhanced DPO path.  Prove the import with focus-cell,
   focus-net, backfill, and priority counters.  Convert legalizer target
   residuals into handoff specs with current row/site, target row/site,
   residual rows/sites, target segment, and priority; clear stale state after
   import.
4. Consume the payload with residual-focus replay first.  Then add residual
   diversity or bucketed replay only if the focus route has exact-positive
   accepts.  Bucket actions should be keep/reject by exact HPWL gain, not by
   marker count.
5. Add transactional row-window replay around the accepted residual cells/nets:
   generate bounded row windows, exact-score swap/move/shift probes, commit
   only positive windows, and report accepted windows, changed cells/nets,
   best gain, total gain, and rollback count.
6. Mirror or later endpoint handling may consume only accepted replay/window
   cells.  Do not make mirror priority the primary optimizer.

Concrete reconstruction sketch:

- producer payload: store bounded native ids for target-miss cells,
  stage3-repaired cells, residual nets, dirty rows, and compact components; keep
  the payload small enough that DPO can consume it in the same flow;
- frontier release: publish only target residuals that still have recoverable
  row/site movement after clamp; filter cells whose target is effectively
  unchanged or whose tail move would create a DPO-hostile displacement tail;
- handoff import: remap payload cells/nets to detailed-placement `Node`/`Edge`
  objects after legal closure, drop stale entries, and log produced, remapped,
  consumed, and dropped counts;
- row-window transaction: for each anchor component, build one or more legal
  row windows around anchor rows and neighbor rows, try move/swap/shift bundles,
  exact-score affected nets, and rollback the full window on nonpositive gain;
- framework-to-DPO bridge: when residual specs are live, seed exact global or
  pair/row-window consumers from those specs before broad scan; if exact
  accepts remain zero, repair the remap from legalizer cell ids to DPO
  `Node`/segment ids before widening the payload;
- component replay: if row-window accepts are live but final HPWL is still flat,
  group accepted-window cells by shared residual nets and try bounded
  component/beam transactions rather than widening an all-cell queue.

Route C2: endpoint/source-edge exact consumer stack.

1. Start from `evolved_diamond` or `diamond` when the legal basin is stable and
   the remaining HPWL looks like endpoint, source-edge, or bbox-edge residue.
2. In `src/Optdp.cpp`, force the enhanced improve-placement path to execute;
   do not silently bypass it through a low-utilization or legacy fallback.
3. In `src/optimization/detailed_global.cxx` or the active global-swap source,
   collect source-edge/frontier cells, generate candidate rows/sites from bbox
   interval centers and edges, exact-score a bounded top-K of move and swap
   trials with journal or affected-net HPWL, and replay only positive bests.
4. Convert accepted exact moves into hot or edge-critical segments in native
   detailed-placement state.
5. In `src/optimization/detailed_reorder.cxx`, consume selected segments first,
   then run bounded post-reorder exact polish, pair polish, and endpoint polish
   around touched nodes/edges.  Each tail must exact-score and commit only
   positive candidates.
6. If a run has many candidates but weak final movement, repair candidate
   quality or accepted-delta preservation before widening the queue.

The two routes can be stacked only when counters show both producers are live.
If C1 creates residual payload but C2-style exact consumers have zero accepts,
the failure is consumer mapping or candidate quality.  If C2 accepts moves but
final HPWL is flat, the failure is final-flow preservation, selected-segment
consumption, or accepted-delta-per-runtime.

Route C3: late broad exact capture plus component/beam replay.

Use this when a wrapper or hierarchy-heavy design has a useful framework
frontier but early row-window or mirror protection moves only weakly.  This
route spends controlled runtime after a live DPO footprint exists.

1. Start from `framework` when LEGALM/guidance exposes frontier records,
   anchors, residual target misses, or stage3-repaired cells.  Keep the
   legalizer as a producer; do not optimize legal HPWL alone.
2. Import frontier anchors into DPO and run a late broad global capture over
   accepted exact DPO footprint cells/nets.  The capture should report touched
   cells, touched nets, shifted sites/rows, accepted transactions, and exact
   accepted delta.
3. Build connected components or beam groups from the accepted footprint, not
   from all cells.  Score bounded component/beam candidates with exact HPWL,
   cache affected-net deltas, and commit only positive bundles.
4. Add beam polish, pair polish, or endpoint polish only after component replay
   has positive accepts.  Keep caps explicit: component count, trials, depth,
   cache hits, bundle probes, pair probes, accepts, and accepted delta.
5. If runtime becomes high without final movement, compress candidate coverage
   and cache scoring.  Do not replace this route with mirror-only protection.

Route C4: focused pair/endpoint replay on accepted DPO footprint.

Use this when exact source-edge/global-swap is already the main producer and
the missing link is after the accepted DPO footprint.

1. Preserve the legal basin and existing global-swap acceptance path.
2. In `src/optimization/detailed_global.cxx`, hand accepted moved cells and
   small affected nets into manager state as focused anchors/frontier nodes.
3. In `src/optimization/detailed_random.{h,cxx}`, generate bounded touched-pair
   and touched-endpoint probes around that focused set.  Score with exact HPWL
   and rollback.
4. In `src/Optdp.cpp`, place the focused pass immediately after the producing
   `gs`; optionally refresh accepted focused-move anchors and run a second
   bounded replay after the generic random DPO pass.
5. Promote only if the focused replay has accepted gain and final HPWL moves.
   If the replay accepts only tiny gain, pivot to changed-net/local-cluster
   transactions or a richer producer payload.

### Implementation Order

1. Start from the source basin that already exposes the strongest residual
   signal: `framework` for residual target/frontier state or `evolved_diamond`
   for stable endpoint geometry.
2. In `src/Optdp.cpp`, collect compact residual cells and nets from legalizer or
   DPO output.  Run a few residual-focus replay rounds and stop by exact
   positive gain.
3. Add diversity or bucketed replay only after the first replay accepts moves.
   Track focus cells/nets, accepted buckets, rejected buckets, exact-positive
   rounds, and best bucket gain.
4. Add transactional row-window replay.  Generate windows around anchor cells,
   exact-score swap/move/shift probes, keep only accepted windows, and report
   changed cells/nets plus HPWL gain.
5. If final mirroring is part of the remaining HPWL gap, pass only compact
   accepted-window or replay-priority cells to mirror.  Cell-only handoff is
   often safer than net-heavy handoff when fanout dilutes the signal.
6. For Diamond-compatible wrapper routes, legalizer-side producer work can be
   useful: frontier-strong producer ordering, slack-biased source ordering, and
   capped endpoint or critical-net preferences.  Prove each subpath with
   nonzero counters.

### Required Counters

- legalizer residual target-miss cells, stage3-repaired cells, residual cells,
  residual nets, compact components, and DPO focus handoff counts;
- frontier target, clamp, release, tail-filter, residual-handoff spec, and
  stale-drop counts when the framework producer is selected;
- residual replay focus cells/nets, rounds, accepts or accepted buckets,
  rejected buckets, stop reason, exact-positive rounds, and HPWL gain;
- row-window candidates, probes, accepted windows, rollback windows, changed
  cells/nets, best gain, and HPWL gain;
- source-edge or edge-critical generated candidates, top-K candidates,
  exact-scored candidates, accepts, replay failures, and accepted delta when
  the endpoint/source-edge route is selected;
- selected-segment reorder and post-reorder exact/pair/endpoint probes,
  accepts, replay failures, accepted delta, and pass runtime;
- mirror handoff replay-priority and row-window-priority counts if mirror is
  used;
- accepted delta per runtime for the bounded replay/exact stages;
- final HPWL improvement after the full flow.

### Partial Routes To Demote

- compact handoff or mirror attribution as a standalone mechanism;
- broad replay without exact-positive gain;
- net-heavy mirror priority when cell-only accepted-window handoff is the live
  signal;
- broadening a dead endpoint-pair producer instead of repairing why it is zero;
- preserving a weak wrapper donor unchanged after plateau instead of testing a
  residual-window chain, an endpoint/source-edge exact consumer chain, or a
  coherent stack of both.

## Blueprint D: Top-Net Target-Source Repair And Mirror-Dependency Hybrid

Use when final HPWL is dominated by high-impact nets, boundary-active net
groups, or dense/high-utilization legalizer inflation followed by incomplete
DPO recovery.

### Recoverable Target/Source Producer Variant

Use this variant when the legalizer produces target misses, low residual
overflow, or a small set of cells whose target rows/sites dominate final HPWL.
The aim is not to minimize legal-stage HPWL alone; it is to make the legal
endpoint easier for exact DPO to consume.

1. In the LEGALM/differential assignment code, build net-local HPWL terms for
   each candidate source cell from bounded-pin nets.  For each candidate
   row/site, estimate signed HPWL delta against current/source position and
   pressure/displacement relief.
2. Generate target sites from desired site, original site, midpoint,
   interval-feasible sites, and a bounded set of HPWL projection anchors from
   current-net pins.  De-duplicate targets before scoring.
3. Use a combined choice: exact/estimated HPWL delta first when residual is low
   and DPO can consume target changes; pressure/displacement relief first only
   when row pressure would otherwise break legality or max displacement.
4. Keep a tail guard: reject target repairs that create large displacement
   tails or worsen high-impact nets without a compensating DPO-consumable
   frontier.
5. Publish compact target-miss/frontier cells and stage3 exact-handoff cells to
   improve placement.  DPO must exact-score the resulting candidates; otherwise
   the legalizer target repair is only a stage donor.

Required target/source counters:

- row probes, anchor-row probes, interval candidate evaluations, duplicates,
  cap hits, maximum interval candidates, HPWL projection terms/sites, and
  projection accepts;
- target-row accepts, nearby-row accepts, pressure-escape accepts,
  HPWL-escape accepts, HPWL-over-pressure accepts/rejects, tail-guard rejects,
  pressure relief/deficit sites, and stage3 exact handoff cells/misses;
- DPO exact probes/accepts on the published target/source payload and final
  HPWL movement.

### Implementation Order

1. Add or verify exact top-K DPO in `src/Optdp.cpp` and
   `src/optimization/detailed_global.cxx`.  Rank high-impact cells by affected
   nets, source-edge residue, and boundary-active nets.
2. In `src/LegalmFullLegalization.cpp`, `src/Place.cpp`, and
   `include/dpl_evolve/Opendp.h`, track and repair high-impact target/source
   choices that DPO can consume.  Legal-stage HPWL movement alone is not enough.
3. Pass compact high-impact cells, nets, repaired targets, and critical
   segments into DPO with native ids or bounded vectors.
4. Add critical-net segment micro-repack only when candidate segments are
   nonzero and exact-scored.
5. Add bounded mirror-dependency batches only after upstream DPO or
   target-source repair is live.  Build dependency components over mirrored
   candidates that share important nets, cap component size, exact-score each
   batch, and commit only positive batches.

### Required Counters

- top-K ranked sources, exact-scored candidates, accepts, rejects, accepted
  gain, and final-flow movement;
- target/source selected high-impact sources, repaired misses, and DPO
  consumption;
- critical segment candidates, scored assignments, accepted packs, rollback
  count, and accepted HPWL gain;
- optional mirror dependency candidates, components, committed cells, exact
  batch gain, and before/after HPWL.

### Partial Routes To Demote

- copying only mirror-dependency or guard logic while omitting upstream exact
  top-K DPO, target-source repair, and critical-net micro-repack;
- high-impact-net logs with zero exact accepts;
- expanding mirror or multi-row batches before source ranking and critical
  segment candidates are live.

## Blueprint E: Recoverable Producer Plus Hot-Segment Exact Consumer

Use when dense row pressure creates a legal but not final-quality-optimal state
and final HPWL follows downstream DPO accepts more than legalize-only HPWL.

### Implementation Order

1. In `src/StudentAlgorithm.cpp`, make the flow explicit:
   guidance or negotiation-compatible producer -> primary legal closure ->
   improve-placement consumer.
2. In `src/LegalmGuidance.cpp`, `src/DifferentialGuidance.cpp`,
   `src/LegalmFullLegalization.cpp`, `src/EvolveNegotiationRepair.cpp`, or
   `src/NegotiationLegalizer*.cpp`, produce a compact frontier: target misses,
   touched nets, dirty rows, conflict-resolved cells, boundary-active cells, or
   high-pressure cells.
3. Close legality without erasing that frontier.  Use negotiation-primary or
   negotiation-compatible closure when conflict/resource state is the useful
   basin.
4. In `src/Optdp.cpp`, import the compact frontier into improve placement
   without changing the top-level command contract.
5. In `src/optimization/detailed_global.cxx` or
   `src/optimization/detailed_global_legacy.cxx`, rank frontier/source-edge
   cells and exact-score a bounded top-K with affected-net HPWL and rollback.
6. In `src/optimization/detailed_manager.{h,cxx}` and
   `src/optimization/detailed_reorder.cxx`, convert accepted exact moves or
   high-potential edge-critical cells into hot segments or selected reorder
   windows.
7. Add bounded post-consumer exact/pair/endpoint polish only after the producer
   and exact consumer are live.  Stop by accepted-gain rate.

### Required Counters

- producer frontier count and class breakdown;
- handoff produced and consumed counts;
- exact/global candidates, exact-scored candidates, accepts, accepted delta,
  and replay failures;
- hot segment or edge-critical queue size;
- selected-segment reorder windows, accepts, and accepted delta;
- post-reorder exact/pair/endpoint attempts and accepts.

### Partial Routes To Demote

- guidance weight changes or target-release constants with no DPO accepts;
- selected-window reorder with zero hot-segment accepts;
- endpoint or pair polish without exact positive gain;
- legalizer-stage HPWL wins that are erased after improve placement.

## Blueprint F: Adaptive Transactional Basin Gain-Rate

Use when a legal endpoint is stable but repeated exact/reorder/DPO routes return
to the same local minimum.  This is controlled basin search, not a random tail.

### Implementation Order

1. In `src/Optdp.cpp`, run the normal improve-placement sequence first, then
   call a bounded basin consumer as an internal DPO stage.
2. In `src/optimization/detailed_manager.{h,cxx}`, expose or reuse a safe
   placement snapshot/journal path that can restore a legal endpoint after a
   failed trial.
3. In `src/optimization/detailed_random.{h,cxx}`, anchor candidate sets on
   residual nets, accepted exact moves, dirty rows, target misses, or
   high-pressure row windows.  Avoid broad random exploration.
4. Score each trial with affected-net or journal HPWL.  Commit only legal
   positive deltas and rollback otherwise.
5. Add coarse/fine behavior only after the simple loop is live: a coarse kick
   proposes a different basin, a fine recovery pass restores local legality and
   HPWL, and a restore-path segment rebuild repairs the path back to the best
   snapshot.
6. Stop by gain-rate, trial budget, and runtime budget.  Runtime repair should
   cache, cap, or parallelize the same mechanism so more quality search fits.

### Required Counters

- legal snapshots created and restored;
- basin trials, coarse kicks, fine recoveries, legal validations, and rollbacks;
- accepted basin moves, accepted gain, and best-snapshot HPWL;
- gain-rate stop reason and runtime per basin stage;
- final full-flow HPWL improvement.

### Partial Routes To Demote

- random moves without snapshot restore and legal replay;
- trial counters without accepted basin gain;
- runtime improvement by disabling quality search;
- repeating exact-source candidates already proven saturated.

## Blueprint G: Negotiation-Compatible Residual Transaction Handoff

Use when negotiation or resource-aware closure creates a better recoverable
basin than the current exact/reorder elite, but generic exact search misses or
destroys that basin.

### Implementation Order

1. In `src/EvolveNegotiationRepair.cpp`, `src/NegotiationLegalizer.cpp`,
   `src/NegotiationLegalizerPass.cpp`, and `src/NegotiationLegalizer.h`, keep
   negotiation primary until liveness is proven.
2. Record compact residual/conflict evidence: residual nets,
   conflict-resolved cells, row-window spans, high-cost history cells, or source
   cells.
3. Pass only bounded native ids or vectors through in-process state.  After DPO
   import, use `Node`, `Edge`, `Group`, `Network`, `Architecture`, `Grid`, row,
   and segment concepts rather than coordinate logs or stale object pointers.
4. In `src/Optdp.cpp`, feed the residual evidence into a specific DPO consumer.
   Do not turn it into another whole-flow replay.
5. In `src/optimization/detailed_global*.cxx`,
   `src/optimization/detailed_reorder.cxx`, and
   `src/objective/detailed_hpwl.cxx`, consume residual-net or row-window queues
   with journaled local transactions, exact affected-net scoring, and rollback.
6. Widen the frontier only after the first residual windows accept real HPWL
   gain.  If widening is flat or worse, repair candidate quality, not queue
   length.

### Required Counters

- negotiation-primary route signal and conflict/resource counters;
- residual nets/windows/frontier produced and consumed;
- exact probes, transaction attempts, accepts, rollbacks, and accepted gain;
- evidence that DPO consumes the negotiation basin rather than replacing it;
- final full-flow HPWL improvement.

### Partial Routes To Demote

- producer-only recoverability rerank that stock DPO erases;
- clean negotiation replay with no source diff;
- frontier widening with no additional accepted windows;
- stale handoff state that survives import incorrectly.

## Blueprint H: Row-Local Or Edge-Local Exact Closure

Use when the legalizer is stable and remaining HPWL is localized around dirty
rows, source-edge cells, selected row segments, boundary-active nets, or shifted
cells.

### Implementation Order

1. Preserve the stable legal basin, usually `evolved_diamond`, `diamond`, or the
   current best legal source.
2. Extract candidates from source-edge cells, shifted cells, dirty rows,
   selected row segments, and boundary-active nets.
3. Build small same-row or adjacent-row windows.
4. Exact-score reorder, pair swap, local swap, or endpoint polish with
   affected-net HPWL and rollback.
5. Commit only legal moves and stop by accepted-gain rate rather than fixed
   long tails.

### Required Counters

- selected windows or candidates;
- exact-scored candidates;
- accepts, rollback count, accepted gain, and pass runtime;
- final HPWL improvement.

### Partial Routes To Demote

- ranking-only telemetry;
- broad whole-design exact search as the first local route;
- constants or thresholds that do not change candidate generation or exact
  acceptance.

### Validated Local Exact Variants

Use one of these when the route is already legal and the remaining HPWL source
is local.  These variants are warm starts for mechanism design; Student should
still diagnose which one matches the current counters.

1. Assignment-journal boundary consumer:
   when exact source-edge DPO has accepted assignment/journal state but final
   mirror or reorder loses some gain, record accepted assignment bounds in
   `src/optimization/detailed_manager.{h,cxx}` and consume them in
   `src/optimization/detailed_reorder.cxx` with same-row boundary-local
   pair/endpoint or move/swap probes.  A strong form ranks same-segment
   assignment candidates by accepted hot-segment hits, hot-segment score,
   sticky/protected neighbor support, fragility penalty, and exact HPWL delta;
   high exact delta may override a fragility penalty only after rollback-safe
   scoring.  Required proof: upstream assignment counters stay live, boundary
   probes exact-score, accepts are nonzero, accepted-delta is reported
   separately from reorder counts, and final HPWL improves.
2. Endpoint-escape ordered-pair route:
   when endpoint residue is localized and ordered-pair exact repair is already
   live, keep the move family but remove bookkeeping overhead only if exact
   counters and audit gaps remain equivalent.  Runtime repair is useful only to
   free budget for stronger exact search; it is not the quality mechanism.
3. Bounded staged sweep distillation:
   when a fallback reorder sweep is the real quality source, make it explicit:
   cap selected segments, snapshot each segment/window, exact-score touched
   edges, rollback nonpositive windows, and log selected/attempted/accepted/
   rejected/rollback windows, probes, permutation candidates, gain, and early
   stop.  Do not keep a crashing producer snapshot path if the bounded sweep
   already captures the quality signal.
4. Vertical-frontier / selected-segment control:
   when a low-residual, queue-sensitive image/control or local-residue design
   has a stable vertical/source-edge frontier donor, preserve queue breadth and
   frontier scope first.  Broad exact-preview reranking can increase activity
   while hurting final HPWL; only promote changes that keep vertical/frontier
   accepts, selected-segment accepts, and final HPWL aligned.

## Blueprint I: Conflict-Primary Legal Closure With DPO Consumer

Use when conflict repair, scarce rows, fragmented rows, or cut-row-like
constraints dominate legality and final quality.

### Implementation Order

1. Prefer `default_negotiation` or `evolved_negotiation` when conflict/resource
   counters match the bottleneck.
2. Ensure the conflict/resource legalizer is the primary legalizer for the
   route.  Prevent a guidance producer from making the placement fully legal
   before conflict repair can act.
3. Change negotiation/resource candidate generation, cost terms, or ordering
   only after primary-route liveness is proven.
4. Create compact conflict-frontier state from unresolved or recently resolved
   conflicts, touched nets, row spans, and source cells.
5. Remap that state to DPO dense ids and exact-score local repair moves around
   conflict-resolved cells and touched nets.

### Required Counters

- primary legalizer route signal;
- conflict queue, resolved conflicts, and legal closure counters;
- downstream DPO probes/accepts around conflict frontier;
- final HPWL and legality improvement together.

### Partial Routes To Demote

- tuning negotiation cost while negotiation is not actually primary;
- legality improvement with worse final HPWL and no handoff/consumer repair;
- differential guidance alone when the conflict route never executes.

## Blueprint J: Plateau Escape By Mechanism Redesign

Use when multiple Students return the same stage tuple, near-identical final
HPWL, or changes that are mostly thresholds, counters, preservation labels, or
passive metadata.

### Implementation Order

1. Keep one rollback-preserved elite-expansion route if the current best is
   meaningfully better than the reference, but do not freeze it as guard-only.
   Expand it with a stronger quality mechanism.
2. If runtime increased without proportional final-HPWL movement, assign at
   least one Student to rebuild the complete chain: producer creates an explicit
   component/window/frontier payload, handoff preserves payload lifetime through
   later passes, and DPO consumes it with a larger-grain exact transaction.
3. Send other Students to a different source mechanism: producer policy,
   handoff payload and remapping, DPO move family, exact scoring objective,
   transaction acceptance, or post-consumer polish.
4. Use current-run peer packets and Student mechanism cards first; use this
   roadmap to choose a different mechanism family only after naming the observed
   failure mode.
5. Require new counters proving a different path executed, the payload was
   produced and consumed, and the stage tuple differs from the plateau family.

### Required Counters

- the new mechanism's producer, payload-handoff, consumer, and acceptance
  counters;
- accepted delta, mechanism/pass runtime, and `accepted_delta_per_runtime`;
- stage-wise HPWL movement different from the plateau family;
- final HPWL improvement or clear classification as stage donor, implementation
  bug, consumer failure, or low ROI.

### Partial Routes To Demote

- repeated threshold or queue-depth edits;
- preservation-only best route;
- different names for the same DPO or legalizer family;
- runtime-only improvement without a quality mechanism;
- more accepts or raw accepted delta without final-flow preservation or
  gain-per-runtime diagnosis.

## Complete-Chain Check

When a route appears to match a strong blueprint, check the full chain:

- producer or legalizer policy creates a recoverable basin or compact frontier;
- handoff maps that state into native detailed-placement objects;
- DPO consumer probes a bounded but meaningful candidate set;
- exact scoring and rollback decide acceptance;
- post-consumer reorder, selected-segment polish, endpoint scoring, local
  closure, or basin escape extracts remaining HPWL when counters show residual
  opportunity.

If only a producer hint, frontier retune, or tiny tail consumer exists, classify
it as a partial-chain hit.  Name the missing link and complete or replace it
before declaring the mechanism family exhausted.
