# Case-Type Quality Mechanism Priority

## Agent Use

- Role: direct Teacher route-insight core.
- Use this file before route assignment to map current case evidence to a small
  set of warm-start mechanism families.
- The routes below are cumulative mechanism stacks.  Do not reduce them to the
  last small patch, a guard, a single cap change, or a benchmark-name lookup.
- Do not use local run paths, raw result rows, or hard-coded
  scores as route selectors.  Teacher maps from current metrics and physical
  features; Student reconstructs the selected mechanism in its own workspace.
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
2. Size and runtime scale: movable count and default-flow runtime.  Cases that
   already take hundreds of seconds can still spend runtime for quality, but the
   extra passes must show accepted gain per runtime.
3. Density/utilization and row pressure: high utilization, row fragmentation,
   scarce sites, or a mild/legalization-stable basin.
4. Physical structure: true macro/SRAM/large blockage evidence from geometry,
   not fixed-instance count alone.  Taps/endcaps/fillers can be fixed cells.
5. Stage behavior: whether final HPWL is dominated by legalizer output,
   producer-handoff quality, exact DPO consumption, post-DPO closure, or
   canonical preservation.
6. Live counters: producer cells/frontier, handoff produced/consumed, exact
   probes, exact accepts, accepted delta/gain, replay rejects, pass runtime, and
   accepted gain per runtime.

If more than one feature class matches, assign multiple Students to different
reconstruction hypotheses.  It is also valid to assign multiple Students to the
same strong route when they test different start basins, move families,
objectives, or repair hypotheses.  Do not allocate the best route only to guard,
attribution, or runtime repair; the best route must keep chasing stronger final
HPWL.

## Feature-Mechanism Map

| current evidence pattern | primary warm-start method | blueprint | first start basin | first Student packet |
| --- | --- | --- | --- | --- |
| Broad DPO recovery dominates final quality: legal HPWL may be mildly better or worse, but improve placement recovers a large fraction of the loss; source-topK/global-swap exact accepts, accepted nodes, hot/critical segments, or source-edge Diamond traces can be made live.  This fits large row-rich/control/datapath cases, wrapper-fragmented cases, and runtime-sensitive cases where a controlled exact DPO stack is more valuable than a heavy producer rewrite. | Runtime-balanced critical-frontier exact DPO stack | `A` | `evolved_diamond` when source-topK exact DPO is already live; `framework` when producer/frontier shaping is also needed | Rebuild the cumulative exact-consumer chain: source-topK/global-swap exact accept journal -> accepted-node and hot/critical-segment native handoff -> critical-row micro-start -> critical-net chain assignment -> exact local closure -> multi-row residual transactions -> segment-local residual swaps. |
| Short or medium runtime, low/moderate utilization, no true macro blocker evidence, and remaining top-net endpoint/source residue after legal closure.  Negotiation/resource closure or a negotiation-like legal basin is useful only when it creates recoverable endpoint/source payload that DPO can consume; the quality jump comes from the full handoff-consumer stack, not from negotiation alone. | Negotiation recoverability plus endpoint/source exact consumer stack | `B` | `default_negotiation` for a clean negotiation basin; `evolved_negotiation` only when it preserves the same producer behavior | Rebuild the cumulative chain: exact source-edge/global-swap -> hot-segment reorder -> hot micro-pack -> recoverability-ranked negotiation producer -> accepted-window residual replay/cascade -> post-reorder endpoint/source target repair and, when single-cell repair is flat, pair/small-cluster exact transactions. |
| Dense or high-utilization standard-cell case where legalization creates large HPWL inflation but also exposes low-residual target-miss, current-net anchor, or stage3 exact handoff cells that downstream selected segments/vertical moves can consume. | Low-residual current-net / vertical-frontier consumer | `C` | `framework` | Keep LEGALM/full guidance as a recoverable producer, publish target rows/sites/valid flags and stage3 current-net anchors, build a compact row-miss/same-row residual frontier, then consume with targeted exact global/vertical moves and selected-segment reorder. |

## Route Map

| blueprint | method name | use first when | use as alternative when | do not use when |
| --- | --- | --- | --- | --- |
| `A` | Runtime-balanced critical-frontier exact DPO stack | DPO recovery, source-topK exact accepts, hot/critical segments, or row-rich/wrapper-like recoverable frontier dominate final HPWL | a short/medium case has endpoint residue but negotiation is not proven; a dense case has no low-residual target-miss handoff | the only evidence is legalizer HPWL improvement with no exact DPO accepted gain |
| `B` | Negotiation recoverability plus endpoint/source exact consumer stack | endpoint/source residue is visible and a negotiation-like producer provides the recoverable legal basin | a short case can spend runtime on aggressive endpoint/source exact transactions after Blueprint A plateaus | negotiation is not the producer, handoff is passive, or the implementation only changes negotiation without the downstream consumer chain |
| `C` | Low-residual current-net / vertical-frontier consumer | target-miss/current-net/stage3 handoff evidence exists and improve placement can consume it | a dense case needs one producer-consumer diagnostic lane while another Student tries Blueprint A | density is high but target-miss/current-net/vertical frontier evidence is absent |

## Blueprint Selection Rules

- Treat each blueprint as a complete mechanism chain.  If a plan names only a
  late guard, one local polish pass, one cap change, or telemetry, it is not a
  valid reconstruction route.
- Do not infer negotiation from large `HPWLimprove` alone.  Use Blueprint B only
  when current evidence says the negotiation-like legal basin produces
  endpoint/source payload or top-net residue that the exact consumer can use.
- When a short/medium case has endpoint/source residue and previous attempts
  with Blueprint A stay flat, allocate at least one Blueprint B lane to the
  complete cumulative chain.  Do not spend most lanes repairing framework or
  LEGALM-frontier workbenches that do not create consumable payload.
- If Blueprint B has source-edge or endpoint accepts but final HPWL is flat, the
  next repair is not another single-cell cap change.  Add accepted-window replay
  and pair/small-cluster exact transactions over the same top-net frontier, then
  preserve the accepted footprint.
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
- the full producer-handoff-consumer chain, not just one late polish pass;
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
