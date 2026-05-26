# Case-Type Quality Mechanism Priority

## Agent Use

- Role: direct Teacher route-insight core.
- Use this file before route assignment to map current case evidence to a small
  set of validated warm-start mechanism families.
- Do not use benchmark names, old program ids, local run paths, raw result rows,
  or hard-coded scores as route selectors.
- After selecting a route, open only the matching section in
  `mechanism_reconstruction_roadmap.md` and put that concrete packet in the
  Student plan.

This card is intentionally short.  It tells Teacher how to classify a case from
current evidence and which complete mechanism family should be reconstructed.
The implementation details live in `mechanism_reconstruction_roadmap.md`.

## Teacher Classification Checklist

Before assigning Students, state the evidence on these axes:

1. Stage tuple: `HPWLg`, `HPWLlg`, `HPWLimprove`, `HPWLfinal`, legality,
   runtime, avg/max displacement.
2. Size and runtime scale: movable count and default-flow runtime.  A case that
   already takes hundreds of seconds can still spend runtime for quality, but it
   needs controlled passes and accepted-gain evidence.
3. Density/utilization and row pressure: high utilization, row fragmentation,
   scarce sites, or mild/legalization-stable basin.
4. Physical structure: true macro/SRAM/large blockage evidence from geometry,
   not fixed-instance count alone.  Taps/endcaps/fillers can be fixed cells.
5. Stage behavior: whether final HPWL is dominated by legalizer output,
   producer-handoff quality, exact DPO consumption, post-DPO closure, or
   canonical preservation.
6. Live counters: producer cells/frontier, handoff produced/consumed, exact
   probes, exact accepts, accepted delta/gain, replay rejects, and pass runtime.

If more than one feature class matches, assign multiple Students to different
reconstruction hypotheses.  It is also valid to assign multiple Students to the
same strong route when they test different start basins or move-family variants.
Do not allocate the best route only to guard, attribution, or runtime repair;
the best route must keep chasing stronger final HPWL.

## Feature-Mechanism Map

| current evidence pattern | primary warm-start method | blueprint | first start basin | first Student packet |
| --- | --- | --- | --- | --- |
| Broad DPO recovery dominates final quality: legalization may be mildly better or worse, improve placement recovers a large part of the stage loss, and hot/critical segments or source-topK exact accepts can be made live.  This includes large row-rich/control/datapath or wrapper-fragmented cases, and smaller runtime-sensitive cases whose final HPWL responds to exact DPO. | Runtime-balanced critical-frontier exact DPO stack | `A` | `framework` when producer/frontier payload must be shaped; `evolved_diamond` when source-topK exact DPO is already live | Keep exact source-topK/global-swap scoring live, store accepted nodes and hot/critical segments as native manager state, then run critical-row micro-start, critical-net chain assignment, exact local closure, multi-row residual transactions, and segment-local residual swaps. |
| Short or medium runtime case where the negotiation reference already beats the default final HPWL, or is the only preflight/reference flow with useful final HPWL, while framework/LEGALM-frontier or legalize-only routes are worse.  The signature is low or moderate utilization, no true macro blocker evidence, large improve-stage recovery from a worse legal HPWL, and remaining endpoint/source or top-net residue. | Endpoint-source handoff exact consumer stack | `B` | `default_negotiation` first; `evolved_negotiation` only if it preserves the same producer behavior | Rebuild the complete negotiation-produced chain: recoverability-ranked endpoint/source payload, native handoff lifetime, exact source-edge/global-swap, hot reorder/micro-pack, accepted-window replay, then post-reorder endpoint/source pair or small-cluster exact transactions.  Do not treat LEGALM frontier repair as a primary route for this pattern unless Blueprint B first proves handoff/consumer failure. |
| Extreme dense/high-utilization standard-cell case with large legalization HPWL inflation, low-residual target-miss or current-net anchors, and stage3 exact handoff cells that selected segments or vertical moves can consume. | Low-residual current-net / vertical-frontier consumer | `C` | `framework` | Keep LEGALM/full-guidance as a recoverable producer, publish target rows/sites/valid flags and stage3 exact target-miss cells, build balanced row-miss/same-row frontier in improve placement, then consume with exact targeted global/vertical moves and selected-segment reorder. |

## Route Map

| blueprint | method name | use first when | use as alternative when | do not use when |
| --- | --- | --- | --- | --- |
| `A` | Runtime-balanced critical-frontier exact DPO stack | DPO recovery, source-topK exact accepts, hot/critical segments, or row-rich/wrapper-like recoverable frontier dominate final HPWL | a short/medium case has endpoint residue but negotiation is not proven; a dense case has no low-residual target-miss handoff | the only evidence is legalizer HPWL improvement with no exact DPO accepted gain |
| `B` | Endpoint-source handoff exact consumer stack | negotiation/resource closure is the useful producer, especially when negotiation is already the best final-HPWL reference and LEGALM/frontier lines are worse | a short case can spend runtime on aggressive endpoint/source exact transactions after Blueprint A plateaus | negotiation is not the producer, handoff is passive, or endpoint accepts are saturated with flat final HPWL after pair/small-cluster repair |
| `C` | Low-residual current-net / vertical-frontier consumer | extreme dense target-miss/current-net/stage3 handoff evidence exists and improve placement can consume it | a dense case needs one producer-consumer diagnostic lane while another Student tries Blueprint A | density is high but target-miss/current-net/vertical frontier evidence is absent |

## Blueprint Selection Rules

- Do not infer negotiation from large `HPWLimprove` alone.  Use Blueprint B only
  when current evidence says negotiation/resource closure produces a uniquely
  useful legal state or endpoint/source residue that DPO can consume.
- When the negotiation reference is the only reference that beats the default
  final HPWL on a short or medium case, make Blueprint B the primary route for
  at least two Students.  One may preserve the clean negotiation basin while
  another changes the move family; do not spend most lanes repairing
  LEGALM/frontier workbenches that are still worse than both default and
  negotiation.
- If a Blueprint B lane has exact accepts but final HPWL stays worse than the
  negotiation reference, the next repair is not another single-cell cap change.
  Use post-reorder endpoint/source pair or small-cluster exact transactions,
  accepted-window replay, and canonical preservation over the accepted
  footprint.
- Do not infer macro behavior from fixed-instance count.  Route as macro or
  large-blockage only after geometry or row-fragmentation evidence is present;
  otherwise use the row-rich/frontier evidence in Blueprint A.
- Do not promote a legalize-only win.  `HPWLlg`, avg displacement, and max
  displacement are diagnostics; final full-flow HPWL and downstream exact
  accepted gain decide promotion.
- If runtime grows and final HPWL is flat, keep one Student on quality expansion
  of the strongest route and assign another to a different move family, payload,
  exact objective, or start basin.  Runtime repair is useful only when it frees
  budget for stronger quality search.
- If exact accepts are live but final HPWL is flat, do not only widen caps.  Fix
  candidate quality, native handoff lifetime, transaction granularity, or
  canonical replay/restore.
- If a route reaches a plateau after one or two rounds, the next Teacher review
  must re-open this feature map and explicitly decide whether the missing link
  is producer, handoff, consumer, objective, move family, or preservation.

## Student Packet Requirements

When Teacher selects a blueprint, the Student plan must include:

- route label and blueprint letter;
- start basin and why current evidence supports it;
- full producer-handoff-consumer chain, not just one late polish pass;
- first source files/functions to inspect and edit;
- required counters and log names;
- self-diagnosis rule after build/evaluation;
- one strengthened repair before finalization if the first attempt is weak;
- next-handoff note if the route still fails after the repair.

The Student should inspect the current source around the assigned handles and
may redesign details, but the report must prove which route links are live.

## Common Demotion Rules

Downweight these unless current same-case final HPWL and liveness prove value:

- guard-only, attribution-only, telemetry-only, or comment-only changes;
- passive handoff metadata that is never consumed by DPO or a post-DPO pass;
- legalize-only or `HPWLlg`-only wins that worsen displacement or are erased by
  downstream flow;
- mirror-only priority changes without upstream exact accepted moves;
- repeated endpoint/source-edge cap widening when final HPWL is flat;
- exact candidates scored but never replayed and committed with positive exact
  delta;
- proxy-positive moves accepted without journal/touched-net exact scoring;
- final preservation commits treated as the quality mechanism.

## Relationship To Other Cards

- Read this card first for route selection.
- Read `mechanism_reconstruction_roadmap.md` only for the selected blueprint.
- Use other `case_evolution/`, `dpo/`, `legalization/`, and `legalm/` cards as
  support after the route is selected, not as competing route selectors.
