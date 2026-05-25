# Case-Type Quality Mechanism Priority

## Agent Use

- Role: direct Teacher route-map core. This file maps observed case features and stage signatures to blueprint IDs and start-basin priors.
- Use before route assignment; do not read secondary case-evolution cards as route selectors.
- Pair only the selected blueprint with `mechanism_reconstruction_roadmap.md` or the generated focused blueprint packet.


This card is the first routing outline for case-specific DPL evolution.  It maps
observed design/stage features to mechanism blueprints and prepared source
basins.  It intentionally stays short: detailed implementation roadmaps live in
`mechanism_reconstruction_roadmap.md`.

Use this card after reading the current case metrics and stage tuple.  A design
can match more than one feature class; use multiple blueprints as route
hypotheses rather than forcing one selector.

## How Teacher Should Use This Card

1. State the observed stage pattern: `HPWLg`, legalization delta,
   improve-placement delta, final HPWL, legality, runtime, and any live
   counters.
2. Classify the case by observed features, not benchmark name: design size
   (movable cells / runtime scale), density or utilization, legalization HPWL
   movement, DPO/improve-placement HPWL recovery, true macro/SRAM/large-blockage
   or hierarchy/row-fragmentation evidence, and live source-level counters.
   Fixed instance count is not a macro count; taps/endcaps/fillers and other
   fixed cells may be included. A macro is a physically large instance, so use
   geometry/source evidence before routing as a macro or large-blockage case.
3. Pick one or more matching blueprints and prepared start kinds.
4. Open `mechanism_reconstruction_roadmap.md` for the matching blueprint details.
5. Give each Student a concrete mechanism packet: start kind, expected HPWL
   source, first files/functions, required liveness counters, and the first
   repair rule if the mechanism is not live.

This is a route-prior card, not a result predictor.  Do not route by benchmark
name and do not attach expected gains to a route.  Current same-case legality,
final HPWL, runtime, stage attribution, and mechanism liveness decide promotion.

When a retained source ends with preservation, telemetry, or reporting-only
edits, do not treat that final edit as the quality mechanism.  Route from the
complete cumulative mechanism chain that produced final HPWL movement.

## Case-Type Route Signatures

Use these signatures as warm-start method insights.  They are not benchmark-name
selectors: match the current stage tuple, physical structure, counters, and
runtime scale, then assign the matching blueprint plus one diverse alternative.
The route label names the cumulative mechanism chain to reconstruct, not the
last guard or attribution commit.

### Feature-Mechanism Map

These are case-type insights: Teacher maps the current stage, density, size,
runtime, and physical-structure evidence to mechanism families that repeatedly
move final HPWL.  Same-case evidence still controls promotion, but weak local
micro-edits should not hide a feature-matched full mechanism route.
Do not default to the lineage that happened to be evolved on the current
benchmark; the first route should be the strongest mechanism family matched by
the current case features and stage evidence.

| current feature signature | first route to assign | blueprint | current start kind | mechanism Student must reconstruct |
| --- | --- | --- | --- | --- |
| Recoverable negotiation-compatible placement: legal HPWL may inflate, improve placement recovers strongly, high-HPWL endpoint/source cells remain, and runtime can spend a bounded exact tail.  This includes low/mid-util row-rich cases and wrapper-like row-fragmented cases when negotiation closure is legal. | Negotiation recoverability plus exact hot-segment endpoint-source stack | `B` | `default_negotiation` first; `evolved_negotiation` only if calibration clearly prefers it | Add endpoint recoverability bias inside negotiation, exact source-edge/global-swap handoff, hot-segment reorder, hot micro-pack, accepted-window replay cascade, and top-net endpoint-source repair. |
| Stable Diamond-compatible placement with broad DPO recovery or queue-sensitive local residue, especially when exact DPO can afford source-topK/hot-frontier candidates and negotiation is not the clearest producer. | Critical-frontier Diamond-style DPO chain | `A` then `H` | `evolved_diamond` | Keep exact source-topK/global-swap live, record accepted nodes/hot segments, then run critical-row micro-start, critical-net chain assignment, exact local closure, multi-row residual transaction, and residual swap/polish. |
| Small or medium source-edge dominated placement where low-intensity fallback hides exact DPO and the strongest signal is local endpoint/source-edge residue rather than a legalizer payload. | Source-edge ordered-pair and endpoint-escape exact DPO | `A`/`H` | `diamond` | Mark source-edge hot cells, preserve hot tags through legal closure, force exact source-edge scoring, evaluate ordered-pair and endpoint-escape transactions with cached affected-net scoring, and keep zero audit gap. |
| Low-residual dense placement where LEGALM/full legalization exposes target misses, stage3 exact handoff cells, or current-net anchors that selected segments can consume. | LEGALM stage3 current-net anchor plus selected-segment residual consumer | `D`/`E`/`H` | `framework` | Keep LEGALM as a recoverable producer, add low-residual stage3 exact/current-net target repair, publish target-miss/frontier cells, then consume selected residual segments with exact reorder or bounded transactions. |

If the first Teacher plan does not assign at least one route matching the
feature-selected mechanism family, treat the routing as incomplete and fix the
feature map before running a full experiment.  The Student packet must state the
start kind, the full producer-handoff-consumer chain, source files, counters,
and the first repair if a link is not live.

| feature signature | warm-start route | blueprint | first start basin | expected HPWL source | first proof check |
| --- | --- | --- | --- | --- | --- |
| Low/moderate-utilization row-rich stdcell placement, Diamond-compatible or recoverable legal basin, local source-edge/bbox-edge residue, and short-to-medium default runtime | Diamond/source-edge basin route: keep the recoverable legal basin, optionally mark source-edge-hot producer cells before legal closure, force enhanced exact DPO even when intensity heuristics would fall back, generate source-edge move/swap targets, exact-score and replay only positive candidates, then preserve accepted basin with canonical replay checks | `A` | `evolved_diamond`, `diamond`, or a current Diamond-compatible source basin | improve-placement DPO and canonical basin preservation | enhanced DPO dispatch and `DPL-0926`-style source-edge cells/locations/proxy skips/replays/commits, producer hot-cell/vacancy counters if used, low replay rejects, `HPWLimprove` and final HPWL both move |
| Large row-rich design with stable Diamond-like legality, large DPO recovery, and runtime where broad exact candidates are affordable but must stay bounded | Critical-frontier Diamond-DPO route: source-topK exact GS -> hot-segment/critical-frontier handoff -> critical-row micro-start -> critical-net chain assignment -> exact local closure -> multi-row residual transaction -> small residual swap/polish | `A` then `H`/`F` if plateaued | `evolved_diamond` | exact DPO chain plus bounded residual consumers | `DPL-0926` and `DPL-0927` live; micro-start, chain, closure, multi-row, residual counters are nonzero; final HPWL improves with controlled runtime |
| Negotiation-compatible or row-rich placement where legal HPWL may inflate but DPO can recover a large basin, especially when hot/edge-critical segments are visible | Negotiation hot-segment exact consumer stack: top-net endpoint recoverability bias in negotiation -> exact global-swap source/edge candidates with handoff -> edge-critical/hot segment queue -> selected-segment reorder -> post-reorder exact/pair/endpoint polish | `B` | `evolved_negotiation` or `default_negotiation` when conflict/resource closure is useful; otherwise use Diamond-compatible start and the same exact consumer | downstream DPO consumer, not legalization alone | negotiation recoverability cells/bonus counters, exact/global accepts and accepted delta, hot/edge segments consumed by reorder, post-reorder exact/pair/endpoint accepts; final HPWL improves |
| Dense or high-utilization image/control placement with high-impact net residue, legalization inflation, and final mirror composition sensitivity | Top-net target/source repair route: repair high-impact target/source choices, consume with exact DPO or critical-net segment micro-repack, then use mirror dependency only as a downstream batch consumer | `D` | exact-DPO-live source basin, `evolved_diamond`, or `framework` only when target shaping is needed | target/source repair plus DPO/mirror composition | top-net/source counters, critical segment micro-repack accepts, optional mirror dependency batch gain, final HPWL improves |
| Low-residual or target-miss dominated dense placement where legalizer can expose current-net/target-correction anchors before DPO | Recoverable target/source producer route: keep legalizer targets DPO-consumable, add HPWL-aware assignment projection or target release only under exact/full-flow checks, then hand compact target-miss/frontier cells into exact DPO | `D`/`E` | `framework` when target/frontier payload is real; otherwise an exact-DPO-live source basin | target/source producer plus exact consumer | target-miss/frontier/stage3-exact handoff counters, DPO exact accepts, displacement remains controlled, final HPWL improves |
| True macro/SRAM, hierarchy, large blockage, or row-fragmentation evidence splits standard cells into repeated row-window basins | Wrapper/macro row-window route: compact residual/window producer -> DPO handoff -> transactional row-window/component/beam consumer, or exact source-edge route when endpoint geometry dominates | `C` then `J` if plateaued | `framework` for real residual/frontier producer; `evolved_diamond` for stable endpoint/source-edge geometry | richer handoff payload plus larger exact consumer | true macro/large-blockage evidence, produced payload is consumed, exact accepts and accepted-delta-per-runtime are reported, final HPWL improves |
| Low-residual, queue-sensitive image/control or local-residue design where broad queue reranking changes many accepts but hurts final flow | Preserve the exact source-edge or vertical-frontier source, then change only one downstream consumer with exact final-flow proof | `A`/`H`, sometimes `C2` | current exact source-edge/vertical-frontier source basin | candidate quality and final-flow preservation, not broader queue activity | source-edge or vertical/frontier accepts stay live, selected-segment accepts stay aligned, final HPWL does not regress |

## Route Map

| observed feature pattern | primary blueprint | preferred start basin | first Student assignment | proof target |
| --- | --- | --- | --- | --- |
| Low/mid-util or stable Diamond-compatible basin plus source-edge/bbox-edge residue and strong DPO recovery | `A. Diamond-basin source-edge exact DPO` | `evolved_diamond`, `diamond`, or current Diamond-compatible source basin | preserve or add source-edge-hot producer hints when legal closure can improve local order; force enhanced DPO dispatch, repair low-intensity/legacy fallback if needed, rebuild source-edge exact move/swap scoring, and add canonical basin replay/restore if accepted gain is lost | source-edge producer and exact DPO commits plus final-flow HPWL movement |
| Large row-rich stable basin with broad DPO recovery and hot-frontier evidence | `A. Large row-rich critical-frontier route` | `evolved_diamond` | build source-topK, critical-frontier, micro-start, chain, exact-closure, multi-row, and residual-swap links as one chain | all chain counters live and final HPWL moves, not only a guard label |
| Negotiation/resource closure gives a useful legal state but quality comes from DPO recovery | `B. Negotiation-start hot-segment exact consumer stack` | `evolved_negotiation` or `default_negotiation` | keep negotiation primary only when useful, add recoverability bias for top-net endpoint cells without over-growing displacement, then consume hot/edge-critical evidence with exact GS handoff, selected reorder, and post-reorder exact/pair/endpoint polish | producer recoverability counters plus accepted delta in DPO and selected/post consumers, final HPWL improves |
| Low-residual dense target/source mismatch or stage3 target-miss evidence | `D/E. Recoverable target-source producer plus exact consumer` | `framework` or current exact-DPO-live source basin | repair assignment target/source choices using HPWL-aware projections and pressure/displacement guards, pass compact target-miss/frontier cells to DPO, and exact-score the consumer | target repair counters, stage3/frontier handoff counters, DPO exact accepts, final HPWL improves |
| True macro/SRAM/hierarchy/large-blockage or row-fragmented wrapper features | `C. Wrapper/macro row-window replay and handoff` | `framework` if residual payload is real; `evolved_diamond` if endpoint/source-edge geometry dominates | create a compact residual/window payload and consume it with transactional row-window/component/beam or exact source-edge route | payload produced and consumed, exact accepts nonzero, accepted-delta-per-runtime meaningful |
| Dense/high-util or high-impact-net case where final mirror composition matters | `D. Top-net target-source repair and mirror-dependency hybrid` | exact-DPO-live source, `evolved_diamond`, or target-shaping `framework` | repair top-net target/source choices, use critical-net micro-repack, then mirror dependency batch only after upstream DPO is live | top-net/source and micro-repack counters live; mirror batch is downstream and final HPWL improves |
| Exact/reorder family is live but same stage tuple repeats | `J. Plateau escape by mechanism redesign` | one elite continuation plus one different matched start | change producer policy, handoff payload, move family, exact objective, transaction granularity, or preservation contract; do not retune only caps/guards | a different producer-consumer path executes and final HPWL changes |

## Blueprint Selection Rules

- If `HPWLlg` worsens but `HPWLimprove` recovers strongly, treat the legalizer
  as a producer.  Route to a producer/handoff/consumer chain (`A`, `B`, `C`, or
  `D`) instead of rejecting it as a legalize-only loss.
- If the case has low/mid utilization, stable or recoverable Diamond-like
  legality, strong improve-stage recovery, and source-edge or bbox-edge
  residue, assign at least one Student to the exact source-edge basin route.
  The first implementation must prove enhanced DPO dispatch, repair any
  low-intensity legacy fallback, exact replay-only-positive commits, and
  final-flow HPWL movement before adding mirror or guard work.
- If the design is large and row-rich with broad DPO recovery, the fast stable
  route is the critical-frontier Diamond-DPO chain: source-topK exact GS,
  hot/critical frontier handoff, micro-start, chain assignment, exact closure,
  multi-row residual, and small residual swap.  A final guard commit is not the
  mechanism; Teacher must route from the cumulative chain.
- If a negotiation source basin or post-reorder endpoint route gives only weak final
  movement, do not keep widening endpoint/source caps or replay halos.  Repair
  the missing link: start basin, exact source-edge objective, native handoff,
  selected-segment consumer, canonical replay/restore, or a larger transaction
  family.
- If a wrapper-like or hierarchy-like case is suspected, first prove it with
  physical evidence: true macro/SRAM or large blockage geometry, row
  fragmentation, repeated row-window basins, or residual/window payloads.
  Fixed instance count alone is not macro evidence.
- If top-net/source repair and mirror dependency are selected, mirror is only a
  downstream consumer of accepted DPO or critical-net repair.  Do not assign
  mirror-only work or mirror-aware objective logs as the main quality route.
- If runtime grows but final HPWL is flat, keep one elite-expansion Student and
  route at least one other Student to a different mechanism family.  Runtime
  repair should free budget for stronger exact search, not become the quality
  objective.
- It is valid to assign multiple Students to the same promising blueprint when
  they test different reconstruction hypotheses, such as Diamond source-edge
  exact DPO versus negotiation-compatible hot-segment consumer versus top-net
  target/source repair.  Do not spend all slots on guards, telemetry, constants,
  or same-family micro-polish.

## Student Packet Requirements

When Teacher selects a blueprint, the Student packet should include:

- `route label`: the blueprint name and the adapted case-specific mechanism;
- `start/parent`: the source basin to prepare first;
- `expected HPWL source`: producer, handoff, DPO consumer, post-consumer, or
  composition;
- `first patch handles`: 1-3 source files/functions from the roadmap;
- `support handles`: adjacent files/functions needed for the same mechanism;
- `pipeline coverage`: producer/legalizer action, handoff/frontier action, and
  consumer/DPO action;
- `required counters`: producer count, consumed/probed count, exact accepts,
  accepted HPWL gain or accepted delta, rollback/reject count, pass runtime, and
  `accepted_delta_per_runtime` or enough fields to compute it;
- `first repair rule`: what to repair if the producer is live but consumer
  accepts are zero, or if accepts are live but final HPWL is flat.

The detailed per-blueprint steps, source anchors, counters, and partial-route
demotion rules are in `mechanism_reconstruction_roadmap.md`.

## Common Demotion Rules

Downweight these unless same-case final HPWL and liveness prove otherwise:

- legalize-only wins that are erased after improve placement;
- mirror-only priority changes without accepted upstream exact moves;
- guidance/frontier producers with zero downstream consumer accepts;
- passive handoff metadata that DPO does not consume;
- threshold, constant, or telemetry edits that do not change candidate
  generation, scoring, transaction, producer, or consumer behavior;
- broad random tails or repeated endpoint passes without accepted-gain evidence;
- final guard or preservation commits treated as if they were the mechanism.

## Relationship To Other Cards

- Read this card first for case-type route selection.
- Read `mechanism_reconstruction_roadmap.md` immediately after a blueprint
  matches and before writing Student implementation guidance.
- Use `runtime_light_final_hpwl_mechanism_priority.md` only after route
  selection to refine cost control or runtime-repair plans.
- Use `evidence_weighted_mechanism_priority.md` only after route selection to
  check whether a partial mechanism should be continued, repaired, or demoted.
- Use `dpo/exact_source_edge_recoverability_consumer.md`,
  `dpo/frontier_guided_basin_consumer.md`, and
  `dpo/openroad_native_handoff.md` only to refine a concrete selected route.
