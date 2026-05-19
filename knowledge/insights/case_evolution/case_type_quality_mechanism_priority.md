# Case-Type Quality Mechanism Priority

This card maps observed detailed-placement case types to effective
optimization mechanisms.  Teacher should read the current stage metrics first,
classify the case type, then assign at least one Student to reconstruct or
strengthen the matching mechanism packet.  The remaining Students should
explore complementary producer, handoff, DPO, or alternative-start hypotheses.

Use this card with `runtime_light_final_hpwl_mechanism_priority.md`: this card
says which mechanism route matches the current case type, and the runtime-aware
card says which mechanisms should be tried first under a practical runtime
budget.

This card is not a numerical predictor.  Do not attach expected HPWL gains to a
route and do not route by benchmark name.  Its job is stronger than generic
inspiration: when the current case matches one of the observed case types
below, Teacher should treat the corresponding mechanism chain as a
high-confidence first route, then require same-case build, logs, legality,
runtime, and final-HPWL proof.

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

### Packet: Dense Recoverable Standard-Cell Pressure

Use this packet when dense standard-cell pressure makes legalizer output
important, but the winning evidence comes from downstream recoverability rather
than legalize-only HPWL.

Student route language:

Implement a recoverability-preserving producer rather than a pure displacement
or legalize-only reducer.  Modify row assignment, target release, conflict
repair, or local closure so cells that affect high-fanout/touched nets keep
DPO-friendly relative order and nearby alternatives.  Emit a compact frontier
of touched nets, dirty rows, target misses, and boundary-active cells.  Pair the
producer with a bounded exact DPO consumer that probes top-ranked frontier
cells and commits only exact affected-net HPWL wins.

Required source orientation:

- start from `evolved_legalm` when dense guidance is useful;
- keep one `evolved_diamond`/`diamond` guard only when Diamond is already close;
- inspect `src/LegalmGuidance.cpp`, `src/LegalmFullLegalization.cpp`,
  `src/StudentAlgorithm.cpp`, `src/Optdp.cpp`, and
  `knowledge/insights/dpo/exact_source_edge_recoverability_consumer.md`.

Required proof:

- nonzero producer frontier, nonzero consumer probes and accepts, and a final
  HPWL win after improve placement.  If the producer is live but accepts are
  zero, repair consumer liveness before adding more metadata.

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
- use a current-run verified donor source ref if one exists.

Required proof:

- candidate windows, exact transaction probes, accepts, rollback count,
  accepted gain, cache/cap counters, runtime per pass, and final HPWL.

### Packet: Low-Utilization Or Slack-Rich Local Closure

Use this packet when there is enough whitespace and the default/local basin is
already close.

Student route language:

Keep the stable legalizer.  Add source-edge top-K exact consumer or small
rollback-safe reorder.  Use cheap candidate ranking, exact-score only the top
local moves, and stop by accepted-gain rate.  Do not spend the first route on
heavy LSMC, restart, or broad global guidance unless local exact consumers are
live and plateaued.

Required source orientation:

- start from `diamond` or `evolved_diamond`;
- inspect local closure, detailed reorder, source-edge candidate extraction,
  and affected-net scoring code.

Required proof:

- exact accepts and accepted gain are nonzero, final HPWL improves, and runtime
  remains controlled.

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
and not a claim that one old source state is universal.

| observed feature pattern | high-confidence start kind | first route to assign | source families to inspect |
| --- | --- | --- | --- |
| Dense pressure with a DPO-recoverable basin | `evolved_legalm` when guidance/closure is the anchor; `evolved_negotiation` when legal closure/conflict is the anchor | recoverability-shaped producer -> compact frontier -> exact DPO consumer | `src/LegalmGuidance.cpp`, `src/LegalmFullLegalization.cpp`, `src/StudentAlgorithm.cpp`, `src/Optdp.cpp`, `src/optimization/detailed_global.cxx` |
| Row-local or edge-local residue after a stable legalizer | `evolved_diamond` or `diamond` | local residue exact closure and selected-segment/source-edge reorder | `src/Place.cpp`, `src/optimization/detailed_reorder.cxx`, `src/optimization/detailed_global.cxx`, `src/objective/detailed_hpwl.cxx` |
| Conflict-heavy, fragmented-row, or scarce-row legality pressure | `default_negotiation` or `evolved_negotiation` | negotiation-primary conflict closure -> compact conflict frontier -> exact DPO repair | `src/NegotiationLegalizer.cpp`, `src/EvolveNegotiationRepair.cpp`, `src/StudentAlgorithm.cpp`, `include/dpl_evolve/Opendp.h`, `src/Optdp.cpp` |
| Large row-rich design with post-DPO plateau | best live legalizer route in the current run, plus one verified producer/consumer donor source if available | runtime-disciplined row-window or residual-basin transaction | `src/optimization/detailed_manager.cxx`, `src/optimization/detailed_global.cxx`, `src/objective/detailed_hpwl.cxx`, DPO exact-consumer cards |
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
