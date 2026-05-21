# Case-Type Quality Mechanism Priority

This card maps observed detailed-placement case types to effective
optimization mechanisms.  Teacher should read the current stage metrics first,
classify the case type, then assign Students to reconstruct, combine, or
strengthen matching mechanism packets.  A design can match more than one
feature-level packet; use multiple packets as route hypotheses instead of
forcing a single selector.

Use this card with `runtime_light_final_hpwl_mechanism_priority.md`: this card
says which mechanism route matches the current case type, and the runtime-aware
card says which mechanisms should be tried first under a practical runtime
budget.

This card is not a numerical predictor.  Do not attach expected HPWL gains to a
route and do not route by benchmark name.  Its job is stronger than generic
inspiration: when the current case matches one or more observed case types
below, Teacher should treat the corresponding mechanism chains as
high-confidence route priors, then require same-case build, logs, legality,
runtime, and final-HPWL proof.  Packet mechanisms are not fixed recipes; they
name useful source-level directions, examples, liveness evidence, and risk
checks that Teacher and Student should adapt to the current code and logs.

When a retained source ends with a guard, telemetry, or reporting-only edit, do
not treat that last edit as the quality mechanism.  The useful evidence is the
sequence of source-level mechanism additions that changed final HPWL, not the
last branch label.

## First Insight For Teacher

After Teacher reads the current case's stage metrics and names the dominant
HPWL source, this is the first case-type insight to open when choosing a
feature-matched start kind or route.  It should answer four practical questions:

- which prepared start kind gives the most useful source basin for this feature
  pattern;
- which mechanism route to assign to Students;
- which source family or current-run peer ref contains concrete code to inspect;
- which counters and stage transitions prove the rebuilt mechanism is live.

Start-specific skill cards explain a branch such as `evolved_legalm`,
`evolved_diamond`, or `evolved_negotiation`.  This card decides whether that
branch family is a good route for the observed feature pattern.

## Case-Type Reconstruction Packets

Teacher can copy the matching packet language into a Student route.  These are
mechanism descriptions for reconstruction, not benchmark identifiers and not
result predictions.

## Source Implementation Anchors

Use these anchors to turn a route packet into a concrete Student task.  The
paths are relative to the private `dpl_evolve` source prepared in the Student
workspace.

- Pipeline composition: edit `src/StudentAlgorithm.cpp` when changing the
  order or coupling of guidance, primary legalizer, handoff, and DPO-facing
  preparation.  The normal evolved entry is `Opendp::runStudentAlgorithm`.
- Top-level legalization command context: inspect `src/Opendp.cpp` and
  `include/dpl_evolve/Opendp.h` for `Opendp::detailedPlacement`,
  `EvolveContext`, max-displacement defaults, `reportEvolvePlacementMetrics`,
  and private state such as `guided_initial_locations_`,
  `legalm_target_*`, `network_`, `arch_`, `grid_`, and `drc_engine_`.
- LEGALM/Differential guidance producer: edit `src/LegalmGuidance.cpp`,
  `src/DifferentialGuidance.cpp`, and sometimes
  `src/LegalmFullLegalization.cpp` when changing target objectives,
  target-release policy, overflow/high-pressure handling, or the stop point.
  The key functions are `Opendp::runDifferentialGuidance`,
  `Opendp::commitGuidedInitialLocationsToDb`, and
  `Opendp::runLegalmFullLegalization`.
- Negotiation-primary closure: edit `src/EvolveNegotiationRepair.cpp`,
  `src/NegotiationLegalizer.cpp`, `src/NegotiationLegalizerPass.cpp`, and
  `src/NegotiationLegalizer.h` when changing conflict/resource legalizer
  behavior.  The key functions are `Opendp::runEvolveNegotiationRepair`,
  `NegotiationLegalizer::runNegotiation`,
  `NegotiationLegalizer::findBestLocation`, and affected-net cache helpers.
- Detailed-improvement/DPO schedule: edit `src/Optdp.cpp` when changing the
  improve-placement script composition or internal parameters for `mis`, `gs`,
  `vs`, `ro`, or `default`.  Do not change the top-level Tcl command contract.
- Exact DPO consumer: edit `src/optimization/detailed_global.cxx`,
  `src/optimization/detailed_reorder.cxx`,
  `src/optimization/detailed_manager.cxx`, and
  `src/objective/detailed_hpwl.cxx` when changing candidate generation,
  affected-net exact scoring, accept/rollback, source-edge/global-swap,
  selected-segment reorder, or local closure.  Useful anchors include
  `DetailedGlobalSwap::run`, `DetailedGlobalSwap::globalSwap`,
  `DetailedGlobalSwap::generateWirelengthOptimalMove`,
  `DetailedReorderer::run`, `DetailedReorderer::reorder`,
  `DetailedHPWL::delta`, and `DetailedHPWL::accept`.
- Native grouping and handoff data: prefer existing `Node`, `Edge`, `Pin`,
  `Group`, `Network`, `Architecture`, `Grid`, segment, and journal structures.
  `Node::getId`, `Node::getPins`, `Pin::getEdge`, `Network::getEdges`,
  `Architecture::getRegions`, row ids, segment ids, and existing `Group`
  membership are sufficient for compact frontier queues.  Do not create bulky
  coordinate logs or string-keyed hot-path maps when ids or native objects can
  carry the state.
- Required liveness logs: every producer/consumer route should log at least
  produced frontier count, consumed/probed count, exact accepts, accepted HPWL
  gain or accepted delta, rollback/reject count, and runtime for the bounded
  pass.

## Cumulative Mechanism Routes

These routes describe source-level mechanism chains that have produced strong
final detailed-placement-flow HPWL.  They should be used as reproducible
mechanism plans, not as benchmark-name selectors.

### Route: Diamond-Basin Source-Edge Exact Descent

Use this route when the case is locally recoverable, Diamond-style legal output
is close enough to keep, and final HPWL still has source-edge or bbox-edge
residue that normal detailed improvement does not consume.  It is also a strong
route hypothesis for dense standard-cell or wrapper/macro-mixed cases whose
stage metrics show legal HPWL disruption but meaningful DPO recovery.

This packet is primarily a DPO-consumer route, not a Diamond-frontier handoff
route.  The core mechanism preserves a Diamond-compatible legal basin and then
changes the improve-placement/global-swap consumer so bbox-edge and source-edge
residue is exact-scored through the existing journal.  Its smallest useful
implementation footprint is `src/Optdp.cpp`,
`src/optimization/detailed_global.cxx`, and
`src/optimization/detailed_global.h`; a robust implementation may also touch
`src/objective/detailed_hpwl.cxx` for affected-edge bookkeeping and
`src/optimization/detailed_random.{h,cxx}` when adding the optional basin kick.

Feature signature that should trigger this packet:

- standard-cell utilization is low or moderate, but density/logs still show many
  local legal DPO opportunities;
- Diamond-style legalization is legal and does not badly damage the global
  placement basin;
- `HPWLlg` is close to `HPWLg` or only modestly worse, while `HPWLimprove`
  shows that exact DPO can recover a much larger basin;
- the current best routes are making small changes around LEGALM,
  negotiation, mirror, frontier thresholds, or telemetry but not changing the
  source-edge exact consumer;
- the default or current detailed-improvement path appears to leave many
  bbox-edge/source-edge candidates unconsumed.

In this signature, Teacher should assign at least one Student to this complete
chain in the first route map.  A partial assignment that only adds a frontier,
only changes mirror, or only tweaks a legalizer does not count as a hit.  The
Student plan should explicitly preserve a Diamond-compatible legal basin and
then rebuild the exact-positive source-edge DPO consumer.  If a Student proposes
only Diamond-native frontier records, changed-cell handoff metadata, or
coordinate-style producer logs without the `DetailedGlobalSwap` exact
source-edge kernel below, classify that as a partial control route rather than
the main quality route.

Evaluation signal for this packet:

- on a low-util standard-cell target, this mechanism reached
  `HPWLg=188569.2`, `HPWLlg=188051.6`, `HPWLimprove=171053.9`, and
  `HPWLfinal=168768.6`;
- relative to the OpenROAD default final HPWL `176845.1`, the final reduction
  was `-8076.5` or `-4.567%`, at about `2.745x` runtime;
- the useful mechanism was not a legalize-only win: legalization changed HPWL
  only slightly, while two source-edge exact DPO passes reported thousands of
  exact-positive commits and zero replay rejects.

Implementation fingerprint:

- source diff shape: `src/optimization/detailed_global.cxx` is the dominant
  change, with only a small `src/Optdp.cpp` dispatch change and a header update;
- the implementation should emit a log string equivalent to
  `Source-edge exact DPO: cells=...,
  locations=..., proxy_skips=..., move_scores=..., swap_scores=..., replays=...,
  commits=..., rejects=..., no_positive_best=..., avg_best_delta=...,
  avg_commit_delta=...`;
- if the current implementation produces `HPWLlg` close to the strong basin but
  `HPWLimprove` is still near the default DPO result, the legal basin is present
  but this exact DPO consumer has not been reproduced.

Start/source basin:

- start from `evolved_diamond` or a Diamond-compatible branch;
- if the current workspace start is not Diamond-compatible, use the prepared
  branch/ref management scripts to create a route branch from a Diamond-compatible
  source before implementing this mechanism;
- preserve the Diamond legalizer as the primary legalizer unless stage evidence
  proves it is the bottleneck.  Do not replace it with LEGALM or negotiation
  just because those starts are available;
- spend runtime in bounded exact DPO search before adding unrelated legalizer or
  mirror work.

Teacher route packet:

- Route label: `Diamond-compatible source-edge exact DPO consumer`.
- Primary HPWL source: post-legal source-edge and bbox-edge residue left by the
  default detailed improvement.
- Start kind: prefer `evolved_diamond`; use a Diamond-compatible branch when
  the current start is `evolved_legalm` or negotiation but stage metrics show a
  stable Diamond basin would be useful.
- Student objective: keep legalization stable, force the enhanced DPO path to
  execute, replace the median-box-only global-swap target with a bounded
  source-edge exact target generator, and accept only exact-positive journaled
  move/swap transactions.
- First files to inspect: `src/Optdp.cpp`,
  `src/optimization/detailed_global.h`, and
  `src/optimization/detailed_global.cxx`.
- Optional second-stage files after the exact DPO kernel is live:
  `src/objective/detailed_hpwl.cxx` for affected-edge state cleanup and
  `src/optimization/detailed_random.{h,cxx}` for a controlled basin kick.
- Stop/pivot rule: if source-edge counters stay zero, fix dispatch/liveness; if
  replays are high but commits are low, fix proxy filtering and replay target
  legality; if commits are high but final HPWL does not improve, add canonical
  basin snapshot acceptance or a selected-segment exact tail.

Important negative example:

- adding Diamond-native changed-cell/frontier records and importing them into
  DPO can be live and legal but still fail to improve final HPWL.  The typical
  failure is that `HPWLlg` matches a good Diamond basin while `HPWLimprove`
  stays weak because the consumer only ranks coarse cells.  Do not continue that
  path unless it is explicitly paired with the exact source-edge kernel and
  shows stronger `HPWLimprove`.

Cumulative reconstruction chain:

1. In `src/Optdp.cpp`, make the improve-placement path execute the enhanced
   DPO/global-swap consumer.  A small but critical dispatch change is to ensure
   the enhanced DPO path remains active even when low-utilization scoring would
   otherwise fall back to legacy global swap.  Do not spend the route on a new
   legalizer before this DPO kernel is live.
2. In `src/optimization/detailed_global.h`, add the exact-source-edge state used
   by `DetailedGlobalSwap`: a live `DetailedHPWL*` during global swap,
   `last_move_from_source_edge_`, `last_move_exact_delta_`, and counters for
   cells, locations, proxy skips, move exact scores, swap exact scores, replays,
   commits, rejects, nonpositive bests, best-delta sum, and committed-delta sum.
3. In `DetailedGlobalSwap::globalSwap`, construct a `DetailedHPWL hpwlObj`,
   assign it to the temporary member pointer before the candidate loop, and
   restore the previous pointer after the pass.  Around every generated move,
   use `hpwlObj.delta(mgr_->getJournal())` for acceptance and call
   `hpwlObj.accept()` only when the move is committed.  If the source-edge move
   is rejected, update the source-edge reject counter.
4. In `DetailedGlobalSwap::generateWirelengthOptimalMove`, replace the weak
   wirelength-optimal fallback with the exact source-edge candidate generator:
   build ranked x/y target candidates from median pin coordinates, bbox edges
   excluding the source cell, current row/position, nearby legal rows, and
   segment availability.  Keep this bounded, for example by pruning to a small
   top set such as `kMaxExactLocations = 8`.
5. For each target location, first compute a cheap source-edge proxy delta to
   discard clearly bad targets.  Then exact-score both direct move and swap
   variants through the existing journal path.  Immediately reject the trial
   move after scoring, retain the best exact-positive candidate, then replay and
   commit only that candidate.
6. Tie-break exact candidates by exact HPWL delta first, then proxy delta,
   support score, and distance.  Do not commit a move whose best exact delta is
   nonpositive.  A route that accepts by proxy delta alone is not this mechanism.
7. Print the source-edge exact DPO summary at the end of the run and require
   nonzero exact scores, replays, and commits.  Strong reproductions should have
   low replay rejects; a high reject rate points to a bad replay target or
   journal/rollback bug.
8. Optional basin kick or selected-segment tail can be added only after the
   source-edge exact kernel is live.  It is a secondary amplifier, not the core
   quality mechanism.
9. If adding basin search in `src/Optdp.cpp`, capture and restore left, bottom,
   placed state, and orientation for all movable nodes; call `adjustNodesOrient`
   before comparing internal and canonical HPWL; rebuild segment/grid state on
   restore; and accept a basin only when canonical HPWL improves under legality.
   This prevents an internally good basin from being erased by DB update or
   orientation mismatch.

Proof that the route is live:

- basin search has a legal snapshot, at least one meaningful kick attempt, and
  clean restore/accept behavior;
- logs show the enhanced DPO path is active even when the intensity score is
  low; a useful signal is a line equivalent to "source-edge HPWL mode" rather
  than a silent legacy fallback;
- source-edge exact scoring reports nonzero source cells, locations, exact
  scores, replays, and commits.  A strong implementation should have many
  exact-positive commits and low replay rejects;
- replay rejects stay low; a high reject rate means the exact replay path or
  candidate target mapping is wrong;
- final detailed-placement-flow HPWL improves, not only `HPWLimprove`.

Expected log shape:

- early broad source-edge scoring can show many replays but too many rejects;
  repair it with proxy filtering, exact-positive gating, and replay-target
  cleanup rather than accepting proxy-positive moves;
- a strong bounded implementation should report thousands of source-edge exact
  commits across the main passes, many nonpositive candidates filtered out, and
  near-zero replay rejects;
- if the source-edge counters are zero, the dispatch path is wrong or the
  generator is not connected to the active global-swap pass.

Common misleading reproductions:

- implementing only the basin kick without the source-edge exact consumer;
- adding source-edge telemetry, Diamond frontier records, or handoff counters
  without changing `generateWirelengthOptimalMove` and exact-scoring candidates;
- widening random moves instead of creating a bounded legal snapshot
  transaction;
- ranking only producer/frontier cells while leaving the legacy global-swap
  target generator unchanged;
- moving to mirror work before source-edge commits and final HPWL prove that the
  DPO basin is saturated.

### Route: Negotiation-Start Hot-Segment Exact Consumer Stack

Use this route when the start branch is negotiation-compatible, legalization is
legal but not HPWL-optimal, and downstream exact DPO can recover a large basin.
This route is especially relevant for large row-rich or wrapper-like designs
where `HPWLlg` can be worse than global while `HPWLimprove` drops sharply.

Start/source basin:

- start from `evolved_negotiation` or `default_negotiation` when conflict/legal
  closure is useful;
- keep the primary legalizer alive, but spend most new mechanism work in the
  DPO consumers that recover the legal basin;
- one Student can guard the best chain, but other Students should modify a
  different stage of the chain rather than only adding telemetry.

Cumulative reconstruction chain:

1. Add or retain bounded exact global-swap frontier search in
   `src/optimization/detailed_global_legacy.cxx`: candidate rows around bbox
   center/edges, ranked segments, small exact-score caps, and affected-net
   rollback scoring.
2. Add bounded multi-row/high-degree vertical probes in
   `src/optimization/detailed_vertical.cxx` when tall or high-degree cells create
   vertical HPWL residue.  Require accepted delta counters.
3. Add targeted hot-segment reorder in `src/optimization/detailed_reorder.cxx`
   and manager support in `src/optimization/detailed_manager.{h,cxx}`.  The
   reorderer should consume hot segments or edge-critical cells created by exact
   DPO, not scan broad rows blindly.
4. Fuse edge-critical global-swap evidence into the hot reorder consumer:
   edge/frontier candidates that exact global-swap could not fully consume
   should become selected reorder segments.
5. Add bounded post-reorder polish in stages only after the previous consumer is
   live: exact local polish, pair-swap polish, and endpoint move polish.  The
   endpoint polish should rank high-distance endpoint cells, probe nearby
   rows/segments, exact-score with journal rollback, and commit only positive
   moves.
6. Keep `src/objective/detailed_hpwl.cxx` exact affected-net delta as the
   acceptance truth.  Post-polish gains are valid only when exact accepts are
   nonzero and final HPWL improves.

Proof that the route is live:

- exact global/frontier search reports generated/top-K candidates, accepted
  sites, and accepted delta;
- vertical or multi-row probes, if present, report legal probes and positive
  accepted delta;
- selected-segment reorder has nonzero selected segments and accepts;
- post-reorder exact/pair/endpoint polish reports attempts, nonpositive count,
  accepts, replay failures, and accepted delta;
- final HPWL follows the DPO consumer chain.  A better `HPWLlg` alone is not a
  promotion reason.

Common misleading reproductions:

- implementing only endpoint or pair polish on top of a weak upstream consumer;
- treating a final guard commit as the mechanism while omitting earlier
  global-swap, vertical, and hot-reorder commits;
- broadening reorder windows with zero selected-segment accepts;
- using mirror-only work as the primary optimization before exact DPO consumers
  are saturated.

### Route: Wrapper/Macro Row-Window Replay And Handoff

Use this route when macro, memory, hierarchy, or blockage structure fragments
standard cells into repeated row-window basins.  This route is secondary to the
two exact-consumer routes above when those match, but it is useful when logs show
row-window replay, residual-focus replay, or mirror handoff are the only live
consumers.

Start/source basin:

- use `evolved_legalm` when residual target or guidance state is already the
  best producer;
- use `evolved_diamond` when Diamond legalizer producer telemetry and endpoint
  geometry are already live;
- keep runtime controlled.  If the default flow already takes hundreds of
  seconds, heavy replay is still allowed but must have caps, gain-rate stops,
  and accepted-gain proof.

Cumulative reconstruction chain:

1. Build residual-focus replay in `src/Optdp.cpp`: collect compact residual
   cells/nets from legalizer or DPO output, replay a few rounds, and stop by
   exact positive gain.
2. Add diversity or bucketed replay only when the first replay produces accepted
   moves.  The useful implementation selects a bounded set of focus nets/cells,
   tracks accepted buckets, rejected buckets, exact-positive rounds, and best
   bucket gain.
3. Add transactional row-window replay for fragmented local basins.  Generate
   windows around anchor cells, exact-score swap/move/shift probes, keep only
   accepted windows, and report changed cells/nets plus HPWL gain.
4. If final mirroring is part of the remaining HPWL gap, pass only compact
   accepted-window or replay-priority cells to `OptMirror`.  Cell-only mirror
   handoff can be better than net-heavy handoff when net fanout dilutes the
   signal.
5. For Diamond-compatible wrapper routes, legalizer-side producer work can be
   useful: frontier-strong producer, slack-biased Diamond source ordering, and
   capped endpoint/critical-net source preferences.  Do not claim a subpath is
   live unless its counters are nonzero; a final improvement can come from the
   producer ordering even if a proposed endpoint-pair subcounter stays dead.

Proof that the route is live:

- residual replay reports focus cells/nets, rounds, accepts or accepted buckets,
  stop reason, and HPWL gain;
- row-window replay reports candidate rows/windows, probes, accepted windows,
  rollback windows, changed cells/nets, best gain, and HPWL gain;
- mirror handoff reports replay-priority and row-window-priority candidates and
  mirrored counts separately;
- final HPWL improves after the complete flow.  Handoff counters alone are not a
  quality result.

Common misleading reproductions:

- treating compact handoff, mirror attribution, or telemetry as a standalone
  optimization mechanism;
- using broad replay without exact-positive gain;
- adding net-heavy mirror priority when the effective path is cell-only
  accepted-window handoff;
- broadening a dead endpoint-pair producer instead of repairing why the
  producer counter is zero.

### Route: Top-Net Target-Source Repair And Mirror-Dependency Hybrid

Use this route when final HPWL is dominated by a small set of high-impact nets
or boundary-active net groups, or when a dense/high-utilization case shows large
legalizer inflation followed by a strong but incomplete DPO recovery.  Baseline
mirroring does not need to be good yet: a strong implementation can first make
exact DPO, target/source repair, and critical-net micro-repack expose better
candidates, then let a bounded mirror-dependency batch preserve or improve
those accepted choices.  The useful signal is not "mirror work" by itself.  The
useful mechanism is the cumulative producer/DPO/mirror-dependency chain.

Start/source basin:

- start from a Diamond-compatible or already exact-DPO-live source when the
  stable legal basin is valuable;
- start from `evolved_legalm` only when target shaping or high-impact target
  source state is the missing producer;
- do not assign mirror-only work as the primary route.  Mirror-dependency work
  is valid only after exact DPO, top-net target/source repair, or critical-net
  micro-repack has produced a better candidate set to preserve.

Cumulative reconstruction chain:

1. Add or verify an exact top-K DPO consumer in `src/Optdp.cpp` and
   `src/optimization/detailed_global.cxx`.  Rank high-impact cells by affected
   nets, source-edge residue, and boundary-active nets; exact-score only a
   bounded candidate set with rollback.
2. Add recoverability-shaped legalizer target/source repair in
   `src/LegalmFullLegalization.cpp`, `src/Place.cpp`, and
   `include/dpl_evolve/Opendp.h`.  Track high-impact source candidates, target
   misses, source ordering, and repair outcomes.  The target/source repair is
   useful only when it changes final HPWL or creates DPO accepts; legal-stage
   improvement alone is weak evidence.
3. Add residual handoff from producer to DPO: compact high-impact nets,
   selected source cells, recently repaired cells, and critical segments.  Keep
   native ids and bounded vectors; do not write bulky coordinate logs.
4. Add critical-net segment micro-repack after the main DPO consumer.  Generate
   small segment-local assignments around high-impact nets, exact-score them,
   and commit only legal positive-gain packs.
5. Add a bounded mirror-dependency hybrid in `include/dpl_evolve/OptMirror.h`
   and `src/OptMirror.cpp` only after the preceding DPO/segment path is live.
   Build dependency components over mirrored candidates that share important
   nets, cap component size, exact-score each batch, and commit only positive
   batches.  This is a final-flow composition repair, not an independent mirror
   objective.

Proof that the route is live:

- exact top-K DPO reports nonzero ranked sources, exact-scored candidates,
  accepts, rejects, accepted gain, and final-flow movement;
- target/source repair reports high-impact candidates, selected sources,
  repaired misses, and whether DPO consumed the resulting cells;
- critical-net micro-repack reports candidate segments, scored assignments,
  accepted packs, rollback count, and accepted HPWL gain;
- mirror-dependency reports candidate mirrors, retained dependency components,
  conflict-filtered cells, committed cells, exact batch gain, and global HPWL
  before/after;
- final detailed-placement-flow HPWL improves.  A live mirror counter with no
  upstream exact-DPO or top-net repair gain is attribution, not promotion.

Common misleading reproductions:

- copying only the final mirror-dependency or guard diff while omitting earlier
  exact top-K DPO, target/source repair, and critical-net micro-repack;
- treating high-impact-net logs as proof when the exact consumer has zero
  accepts;
- expanding multi-row or mirror dependency batches before the top-K source
  ranking and critical segment candidates are live;
- promoting a route because mirroring changes HPWL even though the complete
  detailed-placement flow is worse.

### Packet: Large Row-Rich Recoverable Basin

Use this packet when the current design is large, row-rich, and shows a big
post-legalization recovery opportunity: `HPWLlg` is not convincing, but
`HPWLimprove` or prior logs show exact DPO can recover substantial HPWL.

Student route language:

Implement a recoverability-shaped legalizer-to-DPO chain.  Use the current
source to create a Differential/LEGALM-style guidance producer that builds a
target field or recoverability-biased hints, but do not treat the guidance as
the final legalizer.  Close legality with negotiation-primary or native legal
closure while preserving relative order, residual net neighborhoods, and cells
near high-pressure edges.  Pass only compact native frontier state to DPO:
touched nets, source-edge cells, dirty rows, recently moved cells, and
conflict-resolved cells.  In DPO, add an exact global-swap/source-edge consumer
that ranks this frontier, exact-scores affected nets with rollback, then feeds
accepted or high-potential cells into an edge-critical queue and
selected-segment exact reorder.  Finish with a bounded post-reorder exact/pair
or endpoint polish that stops by accepted-gain rate.

Required source orientation:

- start from `evolved_negotiation` if legal closure/conflict state is the
  anchor;
- start from `evolved_legalm` if target shaping/guidance is the anchor;
- inspect `src/LegalmGuidance.cpp`, `src/NegotiationLegalizer.cpp`,
  `src/StudentAlgorithm.cpp`, `src/Optdp.cpp`,
  `src/optimization/detailed_global.cxx`,
  `src/optimization/detailed_reorder.cxx`, and
  `src/objective/detailed_hpwl.cxx`.

Required proof:

- guidance target count, negotiation-primary/legal-closure route signal,
  compact frontier size, exact DPO probes, exact accepts, accepted delta,
  selected-segment accepts, rollback count, and runtime per bounded tail;
- final detailed-placement-flow HPWL improves.  Legalization-only HPWL is not
  sufficient and may be worse if the recovered basin is better.

### Packet: Macro-Mixed Row-Window Recoverable Basin

Use this packet when a hierarchical or macro/memory-mixed placement fragments
standard-cell logic into many local row-window basins.  The key signature is
not a specific benchmark name: macros, blockages, or hierarchy create
non-uniform local pressure; legalization may slightly disturb global HPWL; and
improve placement shows that downstream exact consumers can recover a
meaningful part of the loss but then plateau in repeated similar basins.

Typical stage and design signals:

- macro or memory cells occupy a noticeable part of the design and create
  macro-edge, blockage-edge, or row-window residual neighborhoods;
- standard-cell logic is still large enough that local exact search has many
  possible alternatives;
- `HPWLlg` is not the sole quality signal: a small legalization regression can
  be acceptable if `HPWLimprove` and final HPWL show recoverability;
- the default runtime is large enough that controlled quality spend is
  reasonable, but not so large that uncapped search should be added casually;
- early evolution can look flat because several Students only polish the same
  source-edge or DPO basin instead of changing the reachable local windows.

Student route language:

Design an evidence-targeted HPWL search mechanism for fragmented local basins.
Possible directions include node-anchored or row-window transactions,
source-edge/frontier exact consumers, selected-segment reorder, controlled
basin escape, macro-edge pressure repair, or another mechanism the Student can
justify from source and logs.  The route should explain which local/global
frontier is worth spending runtime on, how legality is protected, how accepted
moves are scored and rolled back, and how adjacent stages preserve or consume
the resulting placement state.

Do not treat this packet as a command to implement one fixed algorithm.  The
important behavior is to move beyond passive frontier telemetry and same-basin
small DPO polish.  One Student may deepen a live high-quality chain; other
Students should test different route hypotheses such as producer repair,
handoff/frontier redesign, a different DPO move family, or a runtime rewrite of
a heavy but promising mechanism.

Required source orientation:

- inspect `src/StudentAlgorithm.cpp` and `src/Optdp.cpp` for where the flow
  composes legalizer output with improve-placement work;
- inspect `src/optimization/detailed_manager.cxx`,
  `src/optimization/detailed_global.cxx`,
  `src/optimization/detailed_reorder.cxx`,
  `src/optimization/detailed_random.cxx`, and
  `src/objective/detailed_hpwl.cxx` for candidate generation, exact scoring,
  transactions, basin search, and reorder/polish hooks;
- inspect legalizer or handoff code only when the stage metrics indicate the
  producer state or compact frontier is the bottleneck.

Required proof:

- final HPWL improves against the default detailed-placement flow, with clean
  legality;
- logs show a live mechanism, not only a route label: candidate/probe counts,
  exact accepts or accepted gain, rollback/reject counts, and bounded runtime;
- if runtime is spent, the report states whether it bought a stronger HPWL
  search or exposed an efficiency bottleneck;
- if the route is live but plateaus, Teacher must decide whether to spend more
  controlled runtime on a different quality mechanism, repair implementation
  efficiency, or pivot to another matching packet.

### Packet: Dense Recoverable Standard-Cell Pressure

Use this packet when dense standard-cell pressure makes legalizer output
important, but the winning evidence comes from downstream recoverability rather
than legalize-only HPWL.

Typical stage signature:

- `HPWLlg` may be worse than global or worse than a legalize-only donor, while
  `HPWLimprove` drops sharply after the exact consumer runs;
- final HPWL tracks the DPO consumer's exact accepts and accepted delta more
  than the legalizer-stage number;
- a live but incomplete route often shows frontier/source-edge counters without
  enough selected-segment, edge-critical, or post-consumer accepts.

Student route language:

Implement a recoverability-preserving producer rather than a pure displacement
or legalize-only reducer.  Modify row assignment, target release, conflict
repair, or local closure so cells that affect high-fanout/touched nets keep
DPO-friendly relative order and nearby alternatives.  Emit a compact frontier
of touched nets, dirty rows, target misses, and boundary-active cells.  Pair the
producer with a bounded exact DPO consumer that probes top-ranked frontier
cells and commits only exact affected-net HPWL wins.

For datapath-like dense rows, rebuild the complete chain rather than only a
single source-edge tweak:

1. guidance or negotiation-compatible producer preserves recoverable relative
   order, target misses, touched nets, and high-pressure frontier cells;
2. primary legal closure makes the state legal without erasing the frontier;
3. exact global-swap/source-edge consumer probes the frontier with affected-net
   scoring and rollback;
4. edge-critical queue and selected-segment exact reorder consume remaining
   local residuals;
5. bounded pair, endpoint, or local closure extracts the tail and stops by
   accepted-gain rate.

If this packet also matches a large row-rich or datapath-like recoverable basin,
and stage metrics show that downstream DPO recovery is the main reason final
HPWL improves, do not route the case as only a Diamond-stable local-consumer
problem.  A pure Diamond/source-edge exact route can be useful as a complementary
guard, but the first quality route should reconstruct the cumulative mechanism
chain in one private source:

```
Differential/LEGALM-style guidance producer
  -> negotiation-primary or negotiation-compatible legal closure
  -> exact global-swap/source-edge DPO consumer
  -> edge-critical queue
  -> selected-segment exact reorder
  -> bounded post-reorder exact/pair/endpoint polish
```

This chain is a feature-matched route, not a benchmark-name rule.  It is most
appropriate when the case has enough row richness for DPO recovery, legalizer
output is recoverable but not final-quality-optimal, baseline runtime is large
enough to justify bounded exact consumers, and final HPWL follows exact DPO
accepts more than legalize-only HPWL.  Other Students should still cover
complementary mechanisms, but at least one route should try to make the complete
producer/closure/consumer/reorder/polish stack live and measurable.

Source-backed reconstruction routes with the strongest final-HPWL evidence:

#### Reconstruction route A: recoverable producer plus hot-segment exact consumer

Use this when a dense case shows a DPO-recoverable basin: `HPWLlg` may be worse
than global or worse than a stage-only donor, but `HPWLimprove` drops sharply and
final HPWL follows exact DPO accepts.  This route should be treated as a
high-confidence reconstruction packet, not just a vague inspiration.

For the dense-plus-row-rich signature above, route A should normally be the full
cumulative stack, not only a LEGALM frontier or a source-edge DPO patch.  The
minimum credible plan must name the producer, the primary legal closure, the
handoff payload, the exact DPO consumer, and the post-consumer tail.  If any of
those pieces is intentionally omitted, the Teacher should label the route as a
partial donor/control route rather than the main quality route.

Start/source basin:

- start from `evolved_legalm` when LEGALM/Differential target fields are already
  the best way to expose target misses or row pressure;
- start from `evolved_negotiation` or `default_negotiation` when conflict
  closure is the better primary legalizer, but keep the same consumer idea;
- keep at most one Diamond/local guard only if the default Diamond basin is
  already very close.

Minimum implementation steps:

1. In `src/StudentAlgorithm.cpp`, make the flow explicit:
   guidance or negotiation-compatible producer -> primary legal closure ->
   improve-placement consumer.  Do not let a guidance-only route silently become
   the legalizer.
2. In `src/LegalmGuidance.cpp`, `src/LegalmFullLegalization.cpp`,
   `src/EvolveNegotiationRepair.cpp`, or `src/NegotiationLegalizer.cpp`, preserve
   a compact producer frontier: target misses, touched nets, dirty rows,
   conflict-resolved cells, or high-pressure cells.  The payload should be stable
   ids or native object-derived queues, not coordinates or log parsing.
3. In `src/Optdp.cpp`, route the handoff into improve placement without changing
   the top-level Tcl command contract.
4. In `src/optimization/detailed_global.cxx` or
   `src/optimization/detailed_global_legacy.cxx`, rank frontier/source-edge cells
   and exact-score only a bounded top-K with affected-net HPWL and rollback.
5. In `src/optimization/detailed_reorder.cxx` and
   `src/objective/detailed_hpwl.cxx`, convert accepted exact moves into hot
   segments or edge-critical queues, then run targeted selected-segment reorder.
6. Add a bounded post-reorder tail only after the hot-segment consumer is live:
   exact local polish, pair-swap polish, endpoint move polish, or another
   Student-designed bounded consumer.  Stop by accepted-gain rate.

For the cumulative dense-plus-row-rich chain, the preferred first implementation
order is: expose target-miss/high-pressure frontier from Differential/LEGALM-style
guidance; close legality with negotiation-primary or negotiation-compatible
repair while preserving that frontier; import the frontier into `Optdp`; run a
bounded exact global-swap/source-edge consumer; convert accepted sources or
critical nets into selected segments; then run a bounded exact/pair/endpoint
tail.  The Student may redesign details, but the report must prove whether each
link is live.

Strong implementation skeleton observed in successful source variants:

- `src/Place.cpp` / `include/dpl_evolve/Opendp.h`: add a compact
  `recordRecoverableFrontier(...)` producer.  It should record row-cluster or
  recoverability frontier cells during legalizer/local placement activity and
  summarize produced cells, rows, and top edges.  This is a producer for DPO, not
  a log-only feature.
- `src/optimization/detailed_manager.{h,cxx}`: add a
  `reportRecoverableFrontierConsumerTelemetry()`-style bridge or equivalent
  in-manager state.  It should prove that the DPO-side manager imports or
  reconstructs the compact frontier after DB import.
- `src/optimization/detailed_reorder.cxx`: call the frontier telemetry near
  reorder startup and make the reorder consumer capable of using frontier/hot
  segment evidence.  A strong implementation reports many reorder probes and
  nonzero accepts, not just the presence of a frontier.
- `src/optimization/detailed_random.{h,cxx}`: add a
  `runPostReorderLargeStepEscape()`-style post-reorder exact repair.  It ranks
  frontier or residual sources, asks global-swap code for candidate targets,
  exact-scores with legality checks, commits only positive moves, and reports
  attempts, target probes, legal candidates, accepts, rejects, HPWL gain, and
  runtime.
- `src/optimization/detailed_global.{h,cxx}`: add
  `rankLargeStepTargets(...)` and `generateLargeStepMove(...)` or equivalent.
  The target policy should try a small set of meaningful large-step alternatives
  for a ranked source, such as median-box, bbox edge, current-row, and nearby-row
  targets.  Avoid logging once per probe; summarize the policy at the outer pass.
- `src/objective/detailed_hpwl.cxx`: keep exact affected-net or journal HPWL as
  the acceptance truth.  Cheap ranking may choose candidates, but exact positive
  delta decides commits.

Liveness counters that make this route credible:

- producer frontier count and class breakdown;
- exact/global candidates, exact-scored candidates, accepts, accepted delta, and
  rollback/replay failures;
- MIS or main-flow frontier consumer candidates, seeds, accepts, and rollbacks
  when the route feeds a MIS-style consumer;
- hot segment or edge-critical queue size;
- selected-segment reorder windows, accepts, and accepted delta;
- post-reorder exact/pair/endpoint attempts and accepts;
- final full-flow HPWL and runtime.

Partial implementations to demote:

- only changing guidance weights or target-release constants without DPO accepts;
- selected-window reorder that scans broad segments but has zero hot-segment
  accepts;
- endpoint or pair polish that runs without exact positive gain;
- legalizer-stage HPWL improvement that is erased after improve placement.
- an exact post-pass that creates `ranked` and `attempts` counters but no legal
  candidates or no accepts; repair candidate target generation before widening
  the pass.

#### Reconstruction route B: high-impact-net target-source plus mirror-dependency hybrid

Use this when a dense case has high-impact or boundary-active net residue, or
when high utilization creates a large legalizer inflation that DPO can recover
but not fully close.  Baseline mirroring may be neutral or even harmful; this
route is still worth one Student when the case likely needs high-impact-net
candidate generation before mirror dependency can help.  This is not a
mirror-only route.  The reconstruction chain is: exact top-K DPO consumer ->
high-impact target/source repair -> residual handoff or critical-net
micro-repack -> bounded mirror-dependency hybrid.

Start/source basin:

- start from a Diamond-compatible or exact-DPO-live source if stable local DPO is
  already the value path;
- start from `evolved_legalm` if the missing link is high-impact target/source
  repair or recoverability-shaped producer state;
- do not start from a final guard or mirror-only branch label.  Rebuild the
  cumulative producer/DPO/mirror-dependency chain.

Minimum implementation steps:

1. In `src/Optdp.cpp` and `src/optimization/detailed_global.cxx`, make exact
   top-K source ranking live for high-impact nets, source-edge residue, or
   boundary-active net groups.
2. In `src/LegalmFullLegalization.cpp`, `src/Place.cpp`, and
   `include/dpl_evolve/Opendp.h`, track and repair high-impact source/target
   choices that DPO can consume.
3. Pass compact high-impact cells, nets, repaired targets, and critical segments
   into the DPO consumer with native ids or bounded vectors.
4. Add critical-net segment micro-repack only when candidate segments are
   nonzero and exact-scored.
5. Add bounded `OptMirror` dependency batches only after upstream DPO or
   target-source repair is live.  Cap components, exact-score the batch, and
   commit only positive-gain batches.

Required proof:

- exact top-K DPO reports ranked sources, exact-scored candidates, accepts,
  rejects, accepted gain, and final-flow movement;
- target/source repair reports selected high-impact sources, repaired misses,
  and DPO consumption;
- critical-net micro-repack reports accepted packs or a clear zero-accept
  reason;
- mirror-dependency reports candidate mirrors, dependency components,
  committed cells, exact batch gain, and global HPWL before/after;
- final full-flow HPWL improves.  Mirror counters alone are attribution, not a
  winning mechanism.

Teacher routing rule:

- For dense/high-utilization cases with large legalizer inflation and strong
  DPO recovery, assign at least one Student to this route if no previous
  same-run evidence has already disproved high-impact-net target/source repair.
  Other Students should still cover the recoverable producer/hot-segment route,
  source-edge exact descent, and basin escape.  This route is the one that
  tests whether the missing win is a top-net/critical-net candidate-generation
  problem rather than another generic DPO tail.

#### Reconstruction route C: adaptive transactional basin gain-rate

Use this when the placement is already legal and repeated exact/reorder/DPO
routes converge to the same local minimum.  The goal is not a random tail.  The
goal is a bounded legal snapshot -> perturb -> recover -> exact-accept
transaction loop that can spend controlled runtime to escape a local HPWL basin.

Start/source basin:

- start from the current best legal final-HPWL donor in the same run;
- use `evolved_legalm`, `evolved_negotiation`, or Diamond only as the source
  basin that produced the best current legal endpoint;
- rebuild the mechanism in the current Student workspace rather than treating a
  complete program label as the mechanism.

Minimum implementation steps:

1. In `src/Optdp.cpp`, run the normal improve-placement sequence first and then
   call the basin consumer as an internal DPO stage under the same flow.
2. In `src/optimization/detailed_manager.cxx` and
   `src/optimization/detailed_manager.h`, expose or reuse a safe placement
   snapshot/journal path that can restore a legal endpoint after a failed trial.
3. In `src/optimization/detailed_random.cxx` and
   `src/optimization/detailed_random.h`, replace broad random exploration with
   candidate sets anchored on residual nets, accepted exact moves, dirty rows,
   target misses, or high-pressure row windows.
4. Score each trial with affected-net or journal HPWL through
   `src/objective/detailed_hpwl.cxx`; commit only legal positive deltas and
   rollback otherwise.
5. Add adaptive coarse/fine behavior only after the simple loop is live: a coarse
   kick proposes a different basin, a fine recovery pass restores legality and
   local HPWL, and a restore-path segment rebuild repairs the path back to the
   best snapshot.
6. Stop by gain-rate, trial budget, and runtime multiplier.  Runtime repair means
   cache/cap/parallelize the same mechanism so more quality search fits the
   budget; it is not a standalone faster-but-worse objective.

Liveness counters that make this route credible:

- legal snapshot created and restored;
- basin trials, coarse kicks, fine recoveries, legal validations, and rollbacks;
- accepted basin moves, accepted gain, and best-snapshot HPWL;
- gain-rate stop reason and runtime per basin stage;
- final full-flow HPWL improves after the complete flow.

Partial implementations to demote:

- random moves without snapshot restore and legal replay;
- trial counters without accepted basin gain;
- improving runtime by disabling quality search;
- repeating exact-source candidates already proven saturated.

#### Reconstruction route C: negotiation-compatible residual transaction handoff

Use this when negotiation or resource-aware closure creates a better recoverable
basin than the current exact/reorder elite, but generic exact search over-consumes
or destroys that basin.  This route is strongest when conflict or residual-net
structure is visible and the stock DPO recovers a large fraction after
negotiation.

Start/source basin:

- prefer `default_negotiation` or `evolved_negotiation`;
- verify negotiation-primary liveness before tuning: the negotiation route must
  be the actual legal closure, not a no-op after another legalizer already
  succeeded.

Minimum implementation steps:

1. Keep the negotiation producer intact until it is proven live.  In
   `src/EvolveNegotiationRepair.cpp`, `src/NegotiationLegalizer.cpp`,
   `src/NegotiationLegalizerPass.cpp`, and `src/NegotiationLegalizer.h`, record
   compact residual/conflict evidence: residual nets, conflict-resolved cells,
   row-window spans, or source cells.
2. Pass only bounded native ids or vectors through in-process state; use OpenROAD
   `Node`, `Edge`, `Group`, `Network`, `Architecture`, `Grid`, row, and segment
   concepts after DPO import instead of coordinate logs or string-keyed hot maps.
3. In `src/Optdp.cpp`, feed the residual evidence into a specific DPO consumer,
   not into another whole-flow replay.
4. In `src/optimization/detailed_global.cxx`,
   `src/optimization/detailed_global_legacy.cxx`,
   `src/optimization/detailed_reorder.cxx`, and
   `src/objective/detailed_hpwl.cxx`, consume residual-net or row-window queues
   with journaled local transactions, exact affected-net scoring, and rollback.
5. Widen the frontier only after counters show the first residual windows accept
   real HPWL gain.  If widening produces the same final HPWL or worse, the issue
   is candidate quality, not insufficient queue length.

Liveness counters that make this route credible:

- negotiation-primary route signal and conflict/resource counters;
- residual nets/windows/frontier produced and consumed;
- exact probes, transaction attempts, accepts, rollbacks, and accepted gain;
- evidence that DPO consumes the negotiation basin rather than replacing it;
- final full-flow HPWL improves.

Partial implementations to demote:

- producer-only recoverability rerank that stock DPO erases;
- cell-count frontier widening with no additional accepted windows;
- clean negotiation replay with no source diff;
- handoff state that changes ABI/layout unsafely or survives across imports as
  stale object pointers.

Feature-conditioned routing:

- If exact/global, vertical, selected-window, or accepted-edge evidence is live,
  assign at least one Student to route A.
- If legal endpoints are stable but all exact/reorder routes return to the same
  basin, assign at least one Student to route B.
- If negotiation or resource-aware closure is the best observed basin, assign at
  least one Student to route C.
- If the default runtime is already hundreds of seconds, routes A/B/C are still
  allowed, but every extra search component needs caps, gain-rate stops,
  multiplier awareness, and accepted-gain evidence.
- If legalizer output damages the global placement so much that DPO has zero
  accepted recovery, repair producer recoverability or handoff before spending
  runtime on downstream basin search.

Secondary routes and diagnostic donors:

- `guidance-anchor exact stage3`, `gain-ordered frontier reorder relay`,
  `residual-net objective-repair basin`, `mirror-aware multirow basin`, and
  `diamond residual frontier handoff` are useful repair components.  Use them
  when they fill a missing link of routes A/B/C or when current stage evidence
  makes a primary route impossible.  Do not promote them above routes A/B/C
  unless same-case final HPWL and liveness counters prove they are stronger.

Teacher guidance:

- send one Student to preserve and deepen the best live complete chain;
- send other Students to reconstruct at least one of routes A/B/C when the
  feature signature matches, not only to retune thresholds, guards, or queue
  depths;
- after a plateau, keep one guard but force the other Students to change a real
  link: producer objective, primary closure timing, handoff mapping, DPO move
  family, exact scoring objective, transaction acceptance, or post-consumer
  polish;
- require the Student's knowledge card to state which reconstruction route was
  attempted, which minimum implementation steps were completed, which counters
  are live, and which missing step blocks reproduction.

### Packet: Row-Local Or Edge-Local Residual

Use this packet when the legalizer is already stable and the remaining HPWL is
localized around dirty rows, source-edge cells, selected row segments,
boundary-active nets, or shifted cells.

Student route language:

Preserve the Diamond/local legalizer basin and add a small exact local closure
consumer.  Extract candidates from source-edge cells, shifted cells, dirty
rows, selected row segments, and boundary-active nets.  Build small same-row or
adjacent-row windows.  Exact-score reorder, pair swap, local swap, or endpoint
polish with affected-net HPWL and rollback.  Commit only legal moves and stop
by accepted-gain rate, not by a fixed long tail.

Required source orientation:

- start from `evolved_diamond` or `diamond`;
- inspect `src/Place.cpp`, `src/optimization/detailed_reorder.cxx`,
  `src/optimization/detailed_global.cxx`, `src/objective/detailed_hpwl.cxx`,
  and `knowledge/insights/dpo/lightweight_post_dpo_basin.md`.

Required proof:

- selected-window count, exact-scored count, accepts, rollback count, accepted
  gain, and final HPWL.  Ranking-only telemetry is not a mechanism.

### Packet: Conflict-Heavy Or Scarce-Row Legal Closure

Use this packet when row scarcity, fragmented rows, cut-row-like constraints,
or conflict repair dominates legality and final quality.

Student route language:

Make negotiation/resource-allocation closure the real primary legalizer.  Do
not let Differential/LEGALM guidance fully legalize the design before
negotiation runs.  Tune conflict/resource cost terms or candidate generation so
the primary legalizer resolves conflicts while preserving cells that remain
useful to DPO.  Convert unresolved or recently resolved conflicts into a compact
native frontier, then run exact local DPO around conflict-resolved cells and
touched nets.

Required source orientation:

- start from `default_negotiation` or `evolved_negotiation`;
- inspect `src/NegotiationLegalizer.cpp`, `src/EvolveNegotiationRepair.cpp`,
  `src/StudentAlgorithm.cpp`,
  `knowledge/insights/legalization/algorithm_role_liveness_basics.md`, and
  `knowledge/skills/legalization/differential_guidance_stop_target.md`.

Required proof:

- negotiation-primary route signal, conflict queue size, resolved-conflict
  count, final violation count, compact frontier consumed count, DPO
  probes/accepts, and final HPWL.

### Packet: Large Row-Rich Post-DPO Plateau

Use this packet when DPO already accepts some moves but final HPWL plateaus and
there are still row windows, boundary-active regions, residual nodes, or
touched-net basins.

Student route language:

Start from the best live legalizer route in the current run and add one deeper
bounded consumer.  Implement node-anchored or row-window transactions around
residual basins.  Generate candidates from touched nets, boundary-active
regions, high-residual rows, or frontier cells.  Exact-score transactions with
affected-net journals or caches, keep deterministic accept/rollback, and
parallelize independent scoring only when the commit order remains
deterministic.

Required source orientation:

- inspect `src/optimization/detailed_manager.cxx`,
  `src/optimization/detailed_global.cxx`,
  `src/objective/detailed_hpwl.cxx`, and
  `knowledge/insights/dpo/frontier_guided_basin_consumer.md`;
- use a current-run peer source ref if it contains a live compatible mechanism.

Required proof:

- candidate windows, exact transaction probes, accepts, rollback count,
  accepted gain, cache/cap counters, runtime per pass, and final HPWL.

### Packet: Low-Utilization Or Slack-Rich Local Closure

Use this packet when there is enough whitespace and the default/local basin is
already close.

Typical stage signature:

- global and legalizer-stage HPWL are already close enough that broad target
  reshaping is unnecessary;
- final residue is concentrated in local row windows, source-edge cells,
  selected segments, or a small set of touched nets;
- runtime-light exact accepts can beat heavier broad guidance, but a guard line
  may still spend bounded runtime on a real local quality mechanism.

Student route language:

Keep the stable legalizer.  Add source-edge top-K exact consumer or small
rollback-safe reorder.  Use cheap candidate ranking, exact-score only the top
local moves, and stop by accepted-gain rate.  Do not spend the first route on
heavy LSMC, restart, or broad global guidance unless local exact consumers are
live and plateaued.

The stronger local route is not mirror-only or telemetry-only.  It should
combine a stable legalizer basin with one concrete exact consumer: top-K
source-edge moves, selected-row reorder, adjacent-row pair swap, or endpoint
closure.  If a guard protects a good existing result, it should still test a
bounded quality-improving mechanism or a runtime rewrite of a live mechanism.

Required source orientation:

- start from `diamond` or `evolved_diamond`;
- use a negotiation-family start only when conflict/resource counters are live
  and the local closure consumes those recently resolved conflicts;
- inspect local closure, detailed reorder, source-edge candidate extraction,
  and affected-net scoring code.

Required proof:

- exact accepts and accepted gain are nonzero, final HPWL improves, and runtime
  remains controlled.
- if local accepts are live but low-ROI after one meaningful repair, preserve
  the branch as a guard and send non-guard Students to a different producer or
  DPO move family rather than repeating small constant edits.

## Mechanism Class Calibration

Use these classes to decide whether a matched case type needs a light local
repair, a balanced producer/consumer route, or a heavier quality donor.

- `Broad exact-consumer quality donors`: these often produce the strongest
  average final-HPWL reduction when they run on a compatible placement basin.
  They usually spend substantially more runtime.  Use them when stage metrics
  show a large recoverable DPO basin, then rewrite with affected-net caches,
  top-K candidate caps, or narrower frontier windows.
- `Balanced producer-consumer donors`: these combine legalizer-output shaping,
  compact frontier or source-edge signals, and exact DPO transactions.  They
  are the best default route family when Teacher needs both quality and
  controllable runtime.
- `Runtime-light local closure donors`: these can be excellent on placements
  whose remaining HPWL is row-local or edge-local.  They are not universal
  donors.  Use them when the current stage features match a localized residual
  HPWL source.

The key evidence is final detailed-placement-flow HPWL, not stage-local HPWL.
A legalizer may slightly worsen `HPWLlg` while preserving a basin that a later
exact DPO consumer can repair strongly.  Conversely, a legalizer-stage win is
weak evidence if after-improve or final HPWL does not improve.

### Complete-Chain Check

When a route appears to match a previously successful mechanism, check whether
the full chain is live, not only whether the names are similar:

- producer or legalizer policy creates a recoverable basin or compact frontier;
- handoff maps that state into native detailed-placement objects;
- DPO consumer probes a bounded but meaningful candidate set;
- exact scoring and rollback decide acceptance;
- post-consumer reorder, selected-segment polish, endpoint scoring, or local
  closure extracts the remaining HPWL when counters show residual opportunity.

If only a producer hint, frontier retune, or tiny tail consumer exists, classify
it as a partial-chain hit.  Name the missing link and complete or replace it
before declaring the mechanism family exhausted.

## Feature-Level Routing Map

Use this map after the same-case stage metrics are known.  The rows describe
design features and stage symptoms, not benchmark names.

| design/stage feature | evidence pattern | first mechanism route | mechanisms to delay or demote |
| --- | --- | --- | --- |
| Dense row pressure with recoverable local structure | `HPWLlg` worsens or stays high, but `HPWLimprove` can recover a large fraction when the basin is DPO-friendly | recoverability-shaped legalizer producer, compact frontier/residual handoff, exact top-K DPO consumer | legalize-only refinement, full global guidance with no DPO consumer, passive handoff |
| Locally recoverable near-default placement | baseline/Diamond is already close, final residue is concentrated in dirty rows, source-edge cells, or selected row segments | source-edge/frontier-ranked exact local consumer, selected-segment exact reorder, local exact closure | broad whole-design exact search, large endpoint portfolios, heavy LSMC as first route |
| Conflict-heavy or fragmented-row placement | legality/conflict repair dominates, negotiation/resource counters are meaningful, row scarcity or cut-row-like constraints appear | negotiation-primary or resource-allocation closure plus exact local DPO consumer; log primary-legalizer liveness | differential guidance alone, full LEGALM closure before negotiation can act, random perturbation tails |
| Large row-rich design with remaining post-DPO residue | DPO accepts some moves but final HPWL plateaus; row windows or boundary-active regions remain | node-anchored row-window transactions, residual-basin objective repair, deterministic parallel candidate scoring | whole-design exact rescans, unbounded multi-row enumeration, mirror-only priority |
| DPO-heavy winner with weak legalization explanation | best current result mainly comes from post-legal exact accepts while `HPWLlg` is not better | keep one DPO guard and add producer-side recoverability or handoff repair; stack producer frontier with exact consumer | routing all Students into more DPO tail polish |
| Stage-only legalizer win | `HPWLlg` improves but after-improve or final HPWL loses the gain | preserve as stage donor, then repair handoff/consumer compatibility | promoting the legalizer as complete-flow winner, more same-stage polish |
| Zero-accept or no-consumer frontier | producer/frontier counters are nonzero but DPO probes/accepts are zero | repair consumer liveness, remap ids, reduce payload to native compact state, add exact accept counters | adding more metadata, broadening the frontier, treating logs as mechanism success |

Teacher should use this table as the first case-type route map after it states
the observed failure mode.  If current evidence contradicts a row, current
evidence wins.

## Teacher Routing Defaults By Case Type

Classify the current case by stage evidence, then use these routing priors to
assign Students.  The table says which source basin and mechanism family should
be tested first for each feature pattern; it is not a benchmark-name selector
and not a claim that one complete program is universal.

| observed feature pattern | high-confidence start kind | first route to assign | source families to inspect |
| --- | --- | --- | --- |
| Dense pressure with a DPO-recoverable basin | `evolved_legalm` when guidance/closure is the anchor; `evolved_negotiation` when legal closure/conflict is the anchor | recoverability-shaped producer -> compact frontier -> exact DPO consumer | `src/LegalmGuidance.cpp`, `src/LegalmFullLegalization.cpp`, `src/StudentAlgorithm.cpp`, `src/Optdp.cpp`, `src/optimization/detailed_global.cxx` |
| Row-local or edge-local residue after a stable legalizer | `evolved_diamond` or `diamond` | local residue exact closure and selected-segment/source-edge reorder | `src/Place.cpp`, `src/optimization/detailed_reorder.cxx`, `src/optimization/detailed_global.cxx`, `src/objective/detailed_hpwl.cxx` |
| Conflict-heavy, fragmented-row, or scarce-row legality pressure | `default_negotiation` or `evolved_negotiation` | negotiation-primary conflict closure -> compact conflict frontier -> exact DPO repair | `src/NegotiationLegalizer.cpp`, `src/EvolveNegotiationRepair.cpp`, `src/StudentAlgorithm.cpp`, `include/dpl_evolve/Opendp.h`, `src/Optdp.cpp` |
| Large row-rich design with post-DPO plateau | best live legalizer route in the current run, plus one compatible current-run producer/consumer source if available | runtime-disciplined row-window or residual-basin transaction | `src/optimization/detailed_manager.cxx`, `src/optimization/detailed_global.cxx`, `src/objective/detailed_hpwl.cxx`, DPO exact-consumer cards |
| Same-family plateau across Students | one elite continuation plus different prepared starts matched to the observed failure mode | mechanism redesign: change producer policy, handoff mapping, DPO move family, objective, or transaction rule | current-run peer source refs, Student mechanism cards, then the relevant start-branch source family |

Teacher should include the start kind in the packet because it controls the
initial source basin, but the start kind is not a scope restriction.  Student
may modify any `dpl_evolve` source needed for the final detailed-placement-flow
HPWL objective, including legalizer, DPO, handoff, scoring, transaction, and
runtime-control code.

When a current-run peer source ref is available, Teacher may point Student to
that ref as concrete code evidence.  Otherwise, use the matching case-type
packet as mechanism language and let Student reconstruct the implementation in
the current private source.

## Route And Modification Playbook

These routes describe how Teacher should turn the feature map into a concrete
Student packet.  They are not fixed recipes; use the route whose evidence
matches the current case and modify the source mechanism coherently.

### Route: Recoverability-Shaped Producer Consumer Stack

Use when:

- legalization damages or reshapes the global basin, but DPO can recover
  strongly from a compatible legal state;
- final HPWL is better when exact DPO accepts are dense, even if `HPWLlg` is
  not the best stage-local number.

Modification idea:

- change the legalizer objective or closure policy from "make the placement
  legal with lowest local displacement" to "make it legal while preserving
  DPO-recoverable relative order, residual nets, and frontier cells";
- record only compact high-confidence producer state: touched nets, dirty rows,
  target misses, boundary-active cells, or residual conflict cells;
- consume that state with exact top-K DPO moves, not by blindly committing
  producer targets.

Recommended start and source handles:

- prefer `evolved_legalm` when stage evidence says guidance/closure can produce
  a better DPO basin;
- keep one `evolved_diamond` or `diamond` route only if the baseline basin is
  already competitive and needs protection;
- inspect `src/LegalmGuidance.cpp`, `src/LegalmFullLegalization.cpp`,
  `src/StudentAlgorithm.cpp`, `src/Optdp.cpp`, and
  `knowledge/insights/dpo/exact_source_edge_recoverability_consumer.md`.

Typical edit surfaces:

- legalizer row assignment, conflict repair, target release, or local closure;
- compact handoff state in existing OpenROAD/DPL structures;
- DPO candidate ranking, exact affected-net scoring, accept/rollback logic.

Validation:

- producer counters are nonzero;
- DPO consumer probes and exact accepts are nonzero;
- `HPWLimprove` or final HPWL improves, not only `HPWLlg`;
- runtime is explained by accepted gain, cache/cap counters, or a bounded
  frontier size.

Stop or pivot:

- if producer is live but consumer accepts are zero, repair consumer liveness;
- if final HPWL regresses while `HPWLlg` improves, preserve the legalizer as a
  stage donor and route handoff/DPO repair.

### Route: Local Residue Exact Closure

Use when:

- the default or current legalizer is already near a good basin;
- residual HPWL is concentrated in dirty rows, row-local conflicts,
  source-edge cells, selected row segments, or boundary-active nets.

Modification idea:

- keep the primary legalizer stable;
- add a bounded exact local consumer after legalization or inside DPO;
- rank small windows or source-edge candidates cheaply, exact-score only the
  top candidates, and accept through local legality plus rollback.

Recommended start and source handles:

- prefer `evolved_diamond` or `diamond` when current evidence is row-local and
  the legalizer is not the bottleneck;
- use `evolved_legalm` only if current stage evidence shows that guidance
  creates a better recoverable basin;
- inspect `src/Place.cpp`, `src/optimization/detailed_reorder.cxx`,
  `src/optimization/detailed_global.cxx`, `src/objective/detailed_hpwl.cxx`,
  and `knowledge/insights/dpo/lightweight_post_dpo_basin.md`.

Typical edit surfaces:

- source-edge or shifted-cell candidate extraction;
- selected row/segment window construction;
- same-row or adjacent-row reorder, pair swap, or endpoint polish;
- affected-net HPWL delta and deterministic accept/reject rules.

Validation:

- selected windows/candidates, exact-scored candidates, accepts, and accepted
  gain are all nonzero;
- final HPWL improves under the runtime gate;
- if mirror is involved, it preserves accepted exact moves instead of becoming
  a standalone optimizer.

Stop or pivot:

- if counters are nonzero but final HPWL barely moves after one meaningful
  repair, mark the family `validated-low-ROI`;
- if runtime grows without accepted gain, rewrite ranking/caps before adding
  more candidates.

### Route: Conflict-Primary Legal Closure With DPO Consumer

Use when:

- legality/conflict repair, scarce rows, fragmented rows, or cut-row-like
  constraints dominate the failure mode;
- negotiation/resource-allocation counters explain why local greedy closure is
  weak or unstable.

Modification idea:

- ensure the conflict/resource legalizer is actually the primary legalizer for
  the route;
- prevent a guidance producer from making the placement fully legal before the
  conflict resolver can act;
- hand off unresolved or recently resolved conflicts to a bounded exact DPO
  consumer.

Recommended start and source handles:

- prefer `default_negotiation` or `evolved_negotiation` when conflict/resource
  counters are the matching bottleneck;
- do not let a guidance producer silently legalize the design before the
  negotiation-primary route can execute;
- inspect `src/NegotiationLegalizer.cpp`, `src/EvolveNegotiationRepair.cpp`,
  `src/StudentAlgorithm.cpp`,
  `knowledge/insights/legalization/algorithm_role_liveness_basics.md`, and
  `knowledge/skills/legalization/differential_guidance_stop_target.md`.

Typical edit surfaces:

- negotiation or resource-allocation candidate generation and cost terms;
- route dispatch order and guidance stop point;
- conflict frontier creation and remapping to DPO dense ids;
- exact DPO moves around conflict-resolved cells and touched nets.

Validation:

- primary legalizer route signal is present;
- conflict queue, resolved conflicts, and legal closure counters are nonzero;
- downstream DPO probes/accepts around the conflict frontier are nonzero;
- final HPWL and legality improve together.

Stop or pivot:

- if the primary legalizer is a no-op, fix dispatch/stop point before tuning
  costs;
- if legality improves but final HPWL worsens, route recoverability or DPO
  consumer repair instead of more conflict-only polish.

### Route: Runtime-Disciplined Quality Donor

Use when:

- lighter routes are live but plateaued;
- runtime headroom exists under the hard gate;
- stage evidence shows a larger recoverable basin that small exact consumers
  cannot reach.

Modification idea:

- spend runtime on one deeper quality mechanism: scoped basin escape,
  node-anchored row-window transactions, endpoint branch scoring, or residual
  diversity search;
- make the heavy mechanism source-local, capped, cache-aware, and deterministic;
- distill any winning branch into a reusable producer/consumer rule rather than
  stacking repeated endpoint-like passes.

Recommended start and source handles:

- start from the best live legalizer route in the current run rather than a
  route label alone;
- assign this only when lighter producer/consumer mechanisms are live but not
  sufficient;
- inspect `src/optimization/detailed_manager.cxx`,
  `src/optimization/detailed_global.cxx`, `src/objective/detailed_hpwl.cxx`,
  and `knowledge/insights/dpo/frontier_guided_basin_consumer.md`.

Typical edit surfaces:

- row-window or node-anchored candidate generation;
- exact transactional dry-run/commit with rollback;
- affected-net journal/caches;
- deterministic parallel scoring for independent candidates.

Validation:

- heavy probes, exact accepts, rollback count, accepted gain, and runtime per
  pass are logged;
- final HPWL improves enough to justify runtime;
- failed or skipped candidates are bounded by explicit caps and gain-rate stop.

Stop or pivot:

- if heavy probes do not produce accepted gain, demote the donor and return to
  producer/handoff repair;
- if quality improves but runtime is too high, keep the mechanism as a quality
  donor and assign a runtime-rewrite route.

### Route: Plateau Escape By Mechanism Redesign

Use when:

- multiple Students return the same stage tuple or near-identical final HPWL;
- changes are mostly thresholds, counters, guard labels, ranking names, or
  passive metadata;
- the case still has material HPWL gap.

Modification idea:

- change the reachable solution space, not the wording around the same path;
- switch at least one of producer policy, handoff payload/consumer mapping,
  DPO move family, exact scoring objective, or transaction acceptance;
- keep one elite guard only if needed, and send the rest of the roster to
  different producer/handoff/consumer hypotheses.

Recommended start and source handles:

- keep one Student on the current best continuation if it is meaningfully
  better than the baseline;
- send other Students to different prepared starts matched to the observed
  failure mode, not to more variants of the same small threshold edit;
- inspect current-run peer packets and Student mechanism cards first; then use
  the source family for the selected route above.

Typical edit surfaces:

- legalizer objective or route sequence;
- DPO candidate generator and move family;
- source-internal objective weights or accept/rollback condition;
- compact handoff producer and consumer pair.

Validation:

- new counters prove a different mechanism executed;
- stage-wise HPWL movement differs from the plateau family;
- final HPWL improves or the mechanism is clearly classified as stage donor,
  implementation bug, consumer failure, or low ROI.

Stop or pivot:

- do not repeat the same redesign if it is live and low-ROI;
- use Student `Next Teacher Handoff` to decide whether to repair implementation
  or switch family.

## Quality Mechanism Families To Prefer

### Producer-Guided Exact DPO Consumer

Best feature match:

- legalization produces a compact frontier, residual-net set, dirty row set, or
  source-edge set;
- after-improve HPWL still has a visible recovery opportunity;
- DPO accepts exact local moves when candidates are ranked by that frontier.

Implementation shape:

- keep producer state in native in-process structures tied to cells, nets, rows,
  or regions;
- rank only a bounded candidate set by frontier/residual evidence;
- exact-score top candidates with affected-net or journal HPWL;
- commit through local legality and rollback guards;
- log producer count, consumer probes, exact accepts, accepted gain, and runtime.
- strong implementations use two exact-consumer tiers: first score source-edge
  or median-box target locations for each cell, then feed accepted move
  segments into a second selected-window reorder or endpoint/pair polish.
- if using manager-level handoff, store compact segment ids or native node/net
  refs, not coordinate dumps; the consumer should be able to sort by accepted
  delta or hot-segment weight.

Promotion rule:

Promote only if final HPWL improves.  If producer counters are nonzero but exact
accepts are zero, mark the result as passive handoff or consumer failure.

### Recoverability-Shaped Legalizer Plus DPO Closure

Best feature match:

- legalization disturbs the global-placement basin too early;
- DPO has enough local structure to recover if the legalizer preserves better
  relative ordering or residual neighborhoods;
- stage metrics show a large gap between `HPWLlg` and `HPWLimprove`.

Implementation shape:

- modify row assignment, conflict repair, target release, or local closure so
  legalized states stay recoverable rather than merely legal;
- expose only accepted or high-confidence frontier records to DPO;
- let DPO choose exact moves instead of forcing producer targets blindly.
- a useful late legalizer repair can add exact HPWL scoring into the
  zero-overflow tail pass, but it must keep legality as the closure condition
  and use lower-bound pruning so HPWL scoring does not become a broad rescan;
- if the legalizer already preserves a recoverable basin, spend the next route
  on the DPO consumer rather than another legalize-only polish.

Promotion rule:

Treat this as a co-optimization mechanism.  Legalizer HPWL can be worse than
global or worse than a stage-only donor if the full flow is better and logs show
that DPO consumed the recoverable basin.

### Source-Edge And Selected-Segment Exact Reorder

Best feature match:

- residual HPWL concentrates near edge-critical cells, shifted cells, selected
  row segments, or boundary-active nets;
- a small number of exact reorders can be tested cheaply;
- broad whole-design exact search would be too expensive or too noisy.

Implementation shape:

- select source-edge/frontier cells from accepted producer or DPO evidence;
- build small row/segment windows;
- exact-score reorder, pair, or endpoint polish candidates;
- stop by accepted-gain rate instead of fixed long tails.
- source-edge global swap should score several target locations per cell:
  median-box center, box edges, current row, nearby rows, and edge-critical
  pin-frontier targets.  Try move and swap, exact-score affected nets, then
  replay and commit only the best positive delta.
- selected-segment reorder should consume hot segments produced by accepted
  exact moves.  It should not scan every segment as a disguised full pass.
- post-reorder polish is strongest when it reuses touched edges: first exact
  local moves around accepted nodes, then pair swaps, then endpoint moves with
  small per-edge and total probe caps.

Promotion rule:

This is a good runtime-controlled quality donor when exact accepts and accepted
gain are nonzero.  Do not credit ranking-only telemetry.

### Runtime-Light Local Closure

Best feature match:

- the default legalizer is close to a good final solution;
- row-local conflicts dominate;
- global or differential guidance creates more disruption than recoverability.

Implementation shape:

- keep Diamond or negotiation closure as the primary legalizer;
- add bounded exact same-row or adjacent-row repair around dirty rows,
  high-residual nets, or displacement outliers;
- rely on exact affected-net scoring and fast rollback.

Promotion rule:

Use as a protected guard or first local route, but do not let all Students chase
the same small local closure once gains flatten.  A guard should still test a
bounded quality mechanism or runtime rewrite unless it is explicitly a
pure-control attribution run.

### Transactional Basin Escape After Stable Descent

Best feature match:

- a stable legalizer/DPO result exists, but several transfer-tested programs
  show the same case type can improve substantially when the local basin is
  changed;
- normal DPO is deterministic and close, while exact source-edge/global/random
  moves have nonzero accepted-delta counters;
- runtime headroom exists, but the route must remain rollback-safe.

Implementation shape:

- capture a legal placement snapshot after the stable legalizer and normal DPO;
- run one bounded kick phase that accepts only multi-row or window-sized kicks;
- recover with a stronger exact DPO script using global, vertical, reorder, and
  random generators;
- validate legality and final HPWL, accept only if recovered HPWL improves, and
  restore the best snapshot on failure.

Promotion rule:

This is a heavy but high-value quality donor.  Promote only with explicit
snapshot restore, legality validation, accepted basin count, kick counters,
and final-HPWL improvement.  If kicks are accepted but recovery does not
improve final HPWL, preserve the source as negative evidence and switch to a
consumer-scoring rewrite.

## Heavy Mechanisms That Need Runtime Discipline

These mechanisms can be valid quality donors, but Teacher should assign them
with a runtime-rewrite plan.

- broad exact DPO basin search;
- endpoint-level full-tail branch scoring;
- residual diversity search with mirror-aware preservation;
- scoped LSMC-style escape after deterministic descent is already live;
- large selected-window or multi-row exact enumeration.

Required discipline:

- cap windows, endpoints, candidates, and restart count;
- use affected-net or journal deltas instead of full HPWL rescans when possible;
- parallelize independent scoring only when acceptance remains deterministic;
- stop by accepted-gain rate, not by a fixed heavy tail;
- report whether extra runtime bought final HPWL rather than only more probes.

## Low-ROI Patterns To Downweight

Downweight these unless Teacher has a specific repair hypothesis:

- legalize-only wins whose final HPWL does not improve;
- mirror-only priority changes without accepted exact moves to preserve;
- guidance producers with zero downstream consumer accepts;
- critical-window or multi-row assignment previews that never commit exact
  improvements;
- passive metadata handoff that is not consumed by DPO;
- threshold or constant edits without a changed candidate generator, scoring
  function, transaction, producer, or consumer;
- broad random tails or repeated endpoint passes without accepted-gain evidence.

## Teacher Use

Before assigning routes, Teacher should classify the current case by evidence
and write a short route decision:

- if `HPWLlg` worsens but `HPWLimprove` can recover strongly, try
  recoverability-shaped legalizer plus exact DPO consumer;
- if final residue is localized, try source-edge or selected-segment exact
  reorder before broad whole-design exact search;
- if all routes are small and runtime-light, allocate one Student to a heavier
  quality donor with caps and one Student to a runtime rewrite of the best
  quality donor;
- if current-case evidence identifies compatible live mechanisms, prefer a
  coherent producer/handoff/consumer stack over another guard-only or
  mirror-only route;
- if a mechanism is live but weak after one real repair, switch mechanism
  family instead of stacking more threshold variants.
- name the selected start kind and explain why that source basin matches the
  observed feature pattern;
- point Student to concrete source handles or current-run peer refs so it can
  inspect implementation details instead of doing broad research;
- keep general knowledge as inspiration and risk calibration.  The matched
  case-type packet is a high-confidence route prior, but clean current-case final
  HPWL, legality, runtime, and mechanism liveness still decide promotion.

Student reports should state whether the implemented change is a producer,
consumer, handoff, transaction, endpoint-selection, or runtime-rewrite
mechanism, and should include enough counters for Teacher to decide whether the
next round should deepen, repair, or abandon that family.
