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
rollback/reject count, and runtime for each bounded pass.

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

### Implementation Order

1. Start from the source basin that already exposes the strongest residual
   signal: `evolved_legalm` for residual target/guidance state or
   `evolved_diamond` for stable endpoint geometry.
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

- residual replay focus cells/nets, rounds, accepts or accepted buckets, stop
  reason, and HPWL gain;
- row-window candidates, probes, accepted windows, rollback windows, changed
  cells/nets, best gain, and HPWL gain;
- mirror handoff replay-priority and row-window-priority counts if mirror is
  used;
- final HPWL improvement after the full flow.

### Partial Routes To Demote

- compact handoff or mirror attribution as a standalone mechanism;
- broad replay without exact-positive gain;
- net-heavy mirror priority when cell-only accepted-window handoff is the live
  signal;
- broadening a dead endpoint-pair producer instead of repairing why it is zero.

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
   meaningfully better than the reference.
2. Send other Students to a different source mechanism: producer policy,
   handoff payload and remapping, DPO move family, exact scoring objective,
   transaction acceptance, or post-consumer polish.
3. Use current-run peer packets and Student mechanism cards first; use this
   roadmap to choose a different mechanism family only after naming the observed
   failure mode.
4. Require new counters proving a different path executed and a stage tuple that
   differs from the plateau family.

### Required Counters

- the new mechanism's producer/consumer/acceptance counters;
- stage-wise HPWL movement different from the plateau family;
- final HPWL improvement or clear classification as stage donor, implementation
  bug, consumer failure, or low ROI.

### Partial Routes To Demote

- repeated threshold or queue-depth edits;
- preservation-only best route;
- different names for the same DPO or legalizer family;
- runtime-only improvement without a quality mechanism.

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
