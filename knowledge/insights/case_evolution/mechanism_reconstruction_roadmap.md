# Mechanism Reconstruction Roadmap

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

Use when a Diamond-compatible legal basin is stable but detailed improvement
leaves source-edge or bbox-edge residue.

### Implementation Order

1. Start from `evolved_diamond` or `diamond` when the legalizer state is already
   stable.  Do not replace the primary legalizer before the exact DPO kernel is
   live.
2. In `src/Optdp.cpp`, ensure the enhanced global-swap/DPO path executes in the
   normal improve-placement flow.  Avoid a silent fallback to legacy global
   swap when the intensity score is low.
3. In `src/optimization/detailed_global.h`, add exact-source-edge state to
   `DetailedGlobalSwap`: a temporary `DetailedHPWL*`, `last_move_from_source_edge_`,
   `last_move_exact_delta_`, and counters for cells, locations, proxy skips,
   move scores, swap scores, replays, commits, rejects, nonpositive bests,
   best-delta sum, and committed-delta sum.
4. In `DetailedGlobalSwap::globalSwap`, construct a `DetailedHPWL` object for
   the pass, set the temporary pointer before candidate generation, and restore
   it afterward.  Use `DetailedHPWL::delta(mgr_->getJournal())` as the
   acceptance truth and call `DetailedHPWL::accept()` only for committed moves.
5. In `DetailedGlobalSwap::generateWirelengthOptimalMove`, replace weak
   median-box-only or random fallback targeting with a bounded source-edge
   target generator.  Candidate coordinates should come from median pin
   coordinates, bbox edges excluding the source cell, current row/position,
   nearby legal rows, and available segments.
6. For each target, compute a cheap source-edge proxy to discard obviously bad
   candidates, then exact-score both direct move and swap variants through the
   journal.  Reject trial moves immediately after scoring, retain the best
   exact-positive candidate, replay it, and commit only if the replay succeeds.
7. Tie-break by exact HPWL delta first, then proxy delta, support score, and
   distance.  Never commit a nonpositive exact delta.
8. After the source-edge kernel is live, optional selected-segment tail or
   basin kick can amplify it.  Those are secondary; they do not replace this
   exact source-edge consumer.

### Required Counters

- source-edge cells, locations, proxy skips, move exact scores, swap exact
  scores, replays, commits, rejects, nonpositive bests, average best delta, and
  average committed delta;
- low replay reject rate; high replay rejects usually mean target replay,
  legality, or journal rollback is wrong;
- stage tuple showing movement in `HPWLimprove` and final HPWL.

### Partial Routes To Demote

- Diamond frontier records with no exact source-edge consumer;
- source-edge telemetry without changing `generateWirelengthOptimalMove`;
- proxy-positive acceptance without exact affected-net scoring;
- basin kick or mirror work before source-edge exact commits are live.

### Validated Large Row-Rich Diamond-DPO Route

When the current design has many movable cells, a stable legal basin, and large
source-topK accepted delta, reconstruct the complete Diamond-DPO chain before
guarding it:

1. Use `evolved_diamond` as the source basin and keep the legalizer stable.
2. In `src/LegalmRowAssignment.cpp`, add a micro-start producer that reshapes
   the frontier into high-impact row/segment seeds; log frontier cells,
   segments, probes, accepts, appended nodes, and adjusted gain.
3. In `src/optimization/detailed_reorder.cxx`, consume that frontier with
   critical-net chain assignment, exact local closure, and bounded multi-row
   residual transactions.  Each substage must exact-score with rollback and
   emit accepts plus accepted gain.
4. Add only a small segment-local residual swap or polish after the multi-row
   consumer is live.  If residual swaps accept only tiny gain, change the move
   family or frontier payload rather than retuning priority order.
5. Required liveness pattern: source-topK accepts and accepted delta are large;
   micro-start, chain, exact closure, and multi-row counters are all nonzero;
   final HPWL improves with controlled runtime.

## Blueprint B: Negotiation-Start Hot-Segment Exact Consumer Stack

Use when a negotiation-compatible legal basin is legal but not HPWL-optimal and
downstream DPO can recover a large portion of the damage.

### Row-Rich Low/Medium-Utilization Strong-Quality Reconstruction

Use this reconstruction when the design is row-rich, has moderate utilization,
shows a legal final result from the default flow, and still has substantial
recoverable source-edge or bbox-edge residue after legalization.  A small
negotiation or residual donor is not enough for this case type: if the current
donor only gives a weak final-HPWL move after one repair, assign at least one
Student to rebuild the complete chain below and at least one Student to test an
alternate start basin.

Recommended starts:

- Primary start: `evolved_diamond` or `diamond` when the legal placement is
  stable and source-edge residue is the likely HPWL source.
- Secondary start: `evolved_negotiation` or `default_negotiation` only when
  conflict/resource closure gives a clearly useful legal basin.  In that route,
  negotiation is the closure producer; the quality mechanism must still be the
  exact DPO consumer stack.

Complete chain to reconstruct:

1. Preserve a stable legal basin instead of chasing legalization HPWL alone.
   The legalizer may leave `HPWLlg` higher than `HPWLg` if it creates a state
   that DPO can recover.  Avoid early guidance that destroys source-edge order
   or bbox-edge locality before DPO sees it.
2. Force the improve-placement path to execute the enhanced DPO consumer rather
   than silently falling back to a legacy or low-util fast path.  The Student
   should verify the dispatch point in `src/Optdp.cpp` and the global-swap run
   path before tuning thresholds.
3. Rebuild exact source-edge / bbox-edge descent in
   `src/optimization/detailed_global.cxx` or the active global-swap file:
   collect source-edge cells, derive candidate rows/sites from bbox interval
   centers and edges, score a bounded top-K by cheap interval proxy, then exact
   replay only the best touched-net/journal-positive move or swap.
4. Reject non-positive candidates before replay when possible.  Exact replay
   should have low reject volume: high replay rejects usually mean candidate
   replay, legality restore, or journal scoring is wrong.
5. Keep the search bounded but not timid.  A healthy route spends runtime on
   exact candidates with accepted delta, using top-K caps, touched-net caches,
   gain-rate stops, and per-pass candidate limits.  If runtime is high, compress
   the candidate pool and cache scoring before abandoning the chain.
6. Pass accepted global-swap evidence forward.  Mark touched cells, affected
   nets, source-edge cells, and hot/edge-critical segments in native DPL manager
   state; do not create passive metadata that no downstream pass consumes.
7. Consume that evidence with selected-segment reorder and bounded local polish:
   selected hot segments first, exact reorder windows around accepted segments,
   then pair/endpoint/post-reorder polish only after upstream exact accepts are
   live.  Mirror work is only a final protection hook for accepted DPO changes,
   not the main mechanism.
8. If the full chain is live but the final gain is weak, repair the missing
   link rather than guarding the donor: change the start basin, candidate
   objective, source-edge target derivation, handoff payload, or post-consumer
   exact window.  Multiple Students may work on this same promising chain if
   they test distinct reconstruction hypotheses.

Required proof for this reconstruction:

- `HPWLlg`, `HPWLimprove`, and `HPWLfinal` move in a way consistent with a
  producer-consumer flow, not a legalize-only win;
- exact source-edge/global-swap cells, candidate locations, proxy skips,
  exact move/swap scores, replays, commits, rejects, nonpositive bests, and
  accepted delta are reported;
- selected hot segments or edge-critical segments are produced and consumed;
- post-reorder/pair/endpoint polish reports accepted candidates only after the
  upstream exact consumer has nonzero accepts;
- final HPWL, not only improve-stage HPWL, improves under the hard runtime gate.

Demote these partial hits:

- negotiation or residual reorder gives a small final move but exact source-edge
  commits are zero or absent;
- source-edge telemetry exists but dispatch still bypasses the enhanced DPO
  path;
- exact DPO accepts are live but no accepted evidence is passed to reorder or
  post-consumer repair;
- the elite route is preserved unchanged for multiple rounds instead of being
  expanded toward a larger final-HPWL source.

### Validated Row-Rich Stdcell Top-Net Endpoint/Source Route

This route is for row-rich stdcell cases where legal HPWL can inflate but the
improve-placement consumer can recover a large basin.  Do not reject the route
only because `HPWLlg` is worse than `HPWLg`; the quality source is the DPO
consumer chain.

1. Keep a negotiation-compatible legal basin that already leaves useful
   source-edge/hot-frontier evidence.  The complete upstream chain is:
   negotiation producer -> exact source-edge global-swap -> hot-segment reorder
   -> hot-frontier micro-pack -> accepted-window residual replay.
2. In `src/Optdp.cpp::Opendp::improvePlacement`, run a bounded post-reorder
   exact consumer after the hot reorder/micro-pack/replay evidence exists.  A
   useful form is a second `gs` pass with a handoff flag, not another passive
   metadata writer.
3. In `src/optimization/detailed_global.{h,cxx}`, snapshot incoming hot
   segments and source-edge hot cells before manager state is cleared.  Rank
   high-HPWL nets touching this frontier by edge HPWL, frontier pin count,
   endpoint-frontier pins, and source-edge bonus.
4. Generate endpoint/source targets only for movable stdcells on the ranked
   nets.  For a unique bbox endpoint pin, derive target coordinates toward the
   second min/max bbox coordinate, clamp to nearby legal rows/segments, and add
   these as exact-scored targets next to ordinary bbox-center/edge targets.
5. Use existing journal or affected-net exact HPWL as the acceptance truth.
   Commit only positive moves, and count endpoint-target accepts separately.
6. Required liveness pattern: `DPL-0926` exact/source-edge accepts remain live,
   `DPL-0931` hot reorder and micro-pack accepted delta remain live,
   `DPL-0937` accepted-window replay is nonzero, then `DPL-0938 handoff=on`
   reports frontier segments, source cells, top nets, endpoint targets,
   endpoint accepts, and endpoint gain.
7. First repair rules:
   if `DPL-0938 handoff=off` or frontier counts are zero, repair handoff
   lifetime/id mapping; if targets are high but accepts are zero, repair target
   quality or exact replay; if accepts are high but final HPWL is flat, move to
   pair/k-exchange or multi-cell top-net transactions instead of only widening
   caps.

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
   target-correction anchors.
3. In `src/Optdp.cpp`, import a bounded residual payload into improve placement
   and enable the enhanced DPO path.  Prove the import with focus-cell,
   focus-net, backfill, and priority counters.
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
   pair/endpoint or move/swap probes.  Required proof: upstream assignment
   counters stay live, boundary probes exact-score, accepts are nonzero, and
   final HPWL improves.
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
