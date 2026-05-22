# Case-Type Quality Mechanism Priority

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
2. Classify the case by design/stage features using the table below.
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

## Route Map

| observed feature pattern | primary blueprint | preferred start basin | first Student assignment | proof target |
| --- | --- | --- | --- | --- |
| Low/moderate-utilization placement with stable Diamond legal state and remaining source-edge or bbox-edge residue | `A. Diamond-basin source-edge exact DPO` | `evolved_diamond` or `diamond` | preserve the Diamond-compatible legal basin, force enhanced DPO dispatch, rebuild exact source-edge/global-swap scoring | `HPWLlg` remains stable, `HPWLimprove` improves, source-edge exact scores/replays/commits are nonzero, final HPWL improves |
| Negotiation-compatible or row-rich placement where legal HPWL is not best but DPO can recover a large basin | `B. Negotiation-start hot-segment exact consumer stack` | `evolved_diamond` or `diamond` for stable source-edge residue; `evolved_negotiation` or `default_negotiation` for conflict/resource closure | keep a DPO-recoverable legal basin live, force enhanced exact source-edge/global-swap dispatch, then consume accepted evidence with hot-segment reorder and bounded post-reorder polish | exact source-edge/global/frontier accepts, hot segments, selected reorder accepts, post-reorder accepted delta, final HPWL improves |
| Macro, memory, hierarchy, or blockage structure fragments cells into repeated row-window basins | `C. Wrapper/macro row-window replay and handoff` | `evolved_legalm` when residual target state is useful; `evolved_diamond` when Diamond endpoint geometry is useful | build residual/window replay and pass accepted-window evidence into later consumers; avoid net-heavy or telemetry-only handoff | replay/window candidates, accepted windows, changed cells/nets, accepted gain, final HPWL improves |
| Dense or high-utilization case with high-impact or boundary-active net residue and incomplete DPO recovery | `D. Top-net target-source repair and mirror-dependency hybrid` | exact-DPO-live source, `evolved_diamond`, or `evolved_legalm` when target shaping is needed | rank high-impact nets/source cells, repair target/source choices, run exact DPO/critical segment consumer, use mirror only as downstream dependency protection | top-net sources, exact accepts, critical segment accepts, optional mirror batch gain, final HPWL improves |
| Dense row pressure where legalization may worsen HPWL but creates a DPO-recoverable basin | `E. Recoverable producer plus hot-segment exact consumer` | `evolved_legalm`; use negotiation-compatible closure when conflict repair is the anchor | create a recoverability-shaped producer, keep compact frontier/handoff, consume it with exact DPO and selected-segment reorder | producer frontier, handoff consumed count, exact accepts, reorder accepts, final HPWL follows DPO recovery |
| Stable legal endpoint repeatedly returns to same local minimum and runtime headroom exists | `F. Adaptive transactional basin gain-rate` | current best legal source in the same run | snapshot legal placement, run bounded kick/recover trials, exact-accept only legal positive basins, stop by gain rate | snapshots/restores, basin trials, accepted basin gain, legality validation, final HPWL improves |
| Negotiation/resource-aware closure creates a useful recoverable basin, but generic exact search erases or misses it | `G. Negotiation-compatible residual transaction handoff` | `default_negotiation` or `evolved_negotiation` | record compact residual/conflict evidence from negotiation, import it into DPO, exact-score local transactions | negotiation-primary signal, residual windows produced/consumed, exact transaction accepts, final HPWL improves |
| Legalizer is already stable and residual HPWL is row-local or edge-local | `H. Row-local or edge-local exact closure` | `evolved_diamond`, `diamond`, or the current best stable source | build small same-row/adjacent-row exact windows around dirty rows, source-edge cells, selected segments, or boundary-active nets | selected windows, exact-scored candidates, accepts, accepted gain, final HPWL improves |
| Conflict-heavy, scarce-row, fragmented-row, or cut-row-like constraints dominate legality | `I. Conflict-primary legal closure with DPO consumer` | `default_negotiation` or `evolved_negotiation` | prove the conflict/resource legalizer is primary, stop guidance before it erases the conflict route, hand off resolved conflicts to exact DPO | primary legalizer liveness, conflict closure, DPO probes/accepts around conflict frontier, final legal HPWL improves |
| Multiple Students return same stage tuple or tiny same-family gains | `J. Plateau escape by mechanism redesign` | one elite continuation plus different matched starts | change producer policy, handoff mapping, DPO move family, scoring objective, or transaction acceptance; do not retune only thresholds | new counters prove a different mechanism executed and stage tuple changes |

## Blueprint Selection Rules

- If `HPWLlg` worsens but `HPWLimprove` recovers strongly, do not judge the
  route by legalization HPWL alone.  Prefer a producer/handoff/consumer
  blueprint such as `E`, `B`, or `G`.
- If the legalizer is stable and final residue is local, prefer `A` or `H`
  before heavy whole-design search.
- If exact/reorder routes are live but plateau, keep one elite-expansion route
  and assign another Student to `F` or `J`.
- If a low/moderate-utilization row-rich case gets only a weak final move from
  negotiation, residual reorder, guard, or late polish after one repair, treat
  that donor as an incomplete chain.  The next plan must include at least one
  `B` full-chain reconstruction or alternate start-basin route that changes the
  legal basin plus exact DPO consumer stack, not only the donor's thresholds.
- If negotiation/resource closure is the best observed basin, assign at least
  one Student to `G` or `I` and require negotiation-primary liveness.
- If final mirror interaction matters, use it only as a downstream consumer or
  protection step in `C` or `D`; do not assign mirror-only optimization.
- If a route has frontier counters but zero DPO accepts, the missing link is
  consumer liveness, id mapping, candidate quality, or exact acceptance.  Do
  not widen passive metadata.
- It is valid to assign multiple Students to the same promising case-type
  blueprint when they test different reconstruction hypotheses, for example
  Diamond-compatible start plus exact source-edge descent, negotiation-compatible
  closure plus the same exact consumer, and runtime-compressed exact consumer
  with stronger post-reorder repair.  Do not spend all slots on guard,
  mirror-only work, or same-family micro-polish.

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
  accepted HPWL gain or accepted delta, rollback/reject count, and pass runtime;
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
- Use `runtime_light_final_hpwl_mechanism_priority.md` to choose between
  matching blueprints under the runtime budget.
- Use `evidence_weighted_mechanism_priority.md` to judge whether a mechanism
  family deserves more active search budget.
- Use `dpo/exact_source_edge_recoverability_consumer.md`,
  `dpo/frontier_guided_basin_consumer.md`, and
  `dpo/openroad_native_handoff.md` only to refine a concrete selected route.
