# Case-Type Quality Mechanism Priority

## Agent Use

- Role: direct Teacher route-insight core.
- Use this file before route assignment to map current case evidence to a small
  set of warm-start mechanism families.
- The routes below are cumulative mechanism stacks.  Do not reduce them to a
  final guard, one cap change, one late polish pass, or a benchmark-name lookup.
- Teacher maps from current metrics and physical features; Student reconstructs
  the selected mechanism in its own workspace from the matching roadmap section.
- After selecting a route, open only the matching section in
  `mechanism_reconstruction_roadmap.md` and put that concrete packet in the
  Student plan.

This card is intentionally a compact route map.  The implementation roadmaps
live in `mechanism_reconstruction_roadmap.md`.

## Teacher Classification Checklist

Before assigning Students, state the current evidence on these axes:

1. Stage tuple: `HPWLg`, `HPWLlg`, `HPWLimprove`, `HPWLfinal`, legality,
   runtime, avg/max displacement.
2. Size/runtime scale: movable count and default-flow runtime.  Long-default
   cases can still spend runtime for quality, but added passes must expose
   accepted gain per runtime.
3. Density/row pressure: utilization, row fragmentation, scarce legal sites,
   and whether the legalizer creates a recoverable or destructive basin.
4. Physical structure: true macro/SRAM/large-blockage evidence from geometry,
   not fixed-instance count alone.  Taps/endcaps/fillers are fixed cells but not
   macro evidence.
5. Stage behavior: whether final HPWL is dominated by legalizer output,
   producer-handoff quality, exact DPO consumption, post-DPO closure, or
   canonical preservation.
6. Live counters: producer cells/frontier, handoff produced/consumed, exact
   probes, exact accepts, accepted delta/gain, replay rejects, pass runtime, and
   accepted gain per runtime.

If several feature classes match, assign different Students to different
reconstruction hypotheses.  It is also valid to assign multiple Students to the
same strong route when they test different start basins, move families,
objectives, or repair hypotheses.  The strongest route must keep chasing final
HPWL; do not freeze it into guard-only, attribution-only, or runtime-only work.

## Feature-Mechanism Map

| current evidence pattern | primary warm-start method | blueprint | first start basin | first Student packet |
| --- | --- | --- | --- | --- |
| Short/medium standard-cell or control/datapath case with little true macro geometry, visible top-net endpoint/source residue after legal closure or early DPO, and enough runtime budget for a quality lane.  Legal HPWL may be neutral or worse; the useful signal is that endpoint/source cells on high-span nets can be turned into exact accepted moves and preserved through downstream passes. | Negotiation recoverability plus endpoint/source exact consumer stack | `B` | `default_negotiation` first; `evolved_negotiation` only if it preserves the same producer behavior | Rebuild the full chain: source-edge exact global swap -> hot-segment reorder -> hot micro-pack -> recoverability-ranked negotiation producer -> accepted-window replay/cascade -> endpoint/source target repair.  If single-cell endpoint repair is live but flat, add bounded pair/small-cluster exact transactions over the same frontier. |
| Large row-rich/control/datapath or runtime-sensitive case where improve placement recovers most legalizer damage, exact source-topK/global-swap accepts are plausible, and the residue is a critical frontier rather than only endpoint/source payload. | Runtime-balanced critical-frontier exact DPO stack | `A` | `evolved_diamond` when source-topK/exact DPO is already live; `framework` when a recoverable producer/frontier must be rebuilt | Rebuild the cumulative exact-consumer chain: source-topK/global-swap exact accept journal -> accepted-node and hot/critical-segment native handoff -> critical-row micro-start -> critical-net chain assignment -> exact local closure -> multi-row residual transactions -> segment-local residual swaps. |
| Dense/high-utilization case where legalization exposes low-residual target-miss or current-net anchors, and downstream improve placement can consume target rows/sites, exact anchors, moved cells, row-miss cells, or selected residual segments.  Density alone is not enough; the low-residual handoff must be visible or intentionally rebuilt. | Low-residual current-net / vertical-frontier consumer | `C` | `framework` | Keep LEGALM/full guidance as a recoverable producer, publish target rows/sites/valid flags and stage3 current-net anchors, build a compact row-miss/same-row residual frontier, then consume with targeted exact global/vertical moves and selected-segment reorder. |
| Compact or low-utilization case where Diamond/source-edge placement already marks high-span boundary/source-edge cells, but the improve-placement path tends to fall back to weak legacy search or leaves endpoint escape opportunities.  Use this when exact source-edge hot tags and ordered-pair/endpoint-escape transactions are the missing consumer. | Diamond source-edge ordered-pair and endpoint-escape exact DPO | `D` | `diamond` or `evolved_diamond` depending on which one keeps source-edge hot tags live | Preserve source-edge hot-cell tags from placement, force exact HPWL-only source-edge global swap instead of low-intensity fallback, add ordered-pair exact transactions, add endpoint-escape partner moves, and cache affected-net delta with an audit gap check. |
| Hierarchical wrapper / macro- or SRAM-heavy / fragmented-row case where legalizer HPWL rises but improve placement recovers a large fraction. | Assign both a quality lane and a value lane | `B` plus `A` | `default_negotiation` for the endpoint/source quality lane; `evolved_diamond` or `framework` for the critical-frontier value lane | Use Blueprint B if endpoint/source residue on top nets is visible; use Blueprint A if the visible residue is accepted-node/hot-critical frontier.  Do not overfit to fixed-instance count; use geometry and row fragmentation. |

## Route Map

| blueprint | method name | use first when | use as alternative when | do not use when |
| --- | --- | --- | --- | --- |
| `A` | Runtime-balanced critical-frontier exact DPO stack | DPO recovery, source-topK exact accepts, hot/critical segments, or a recoverable critical frontier dominate final HPWL | endpoint/source residue exists but negotiation producer evidence is weak, or the case needs a faster exact-consumer lane beside a heavier quality lane | endpoint/source residue is the main unconsumed signal and no Blueprint B lane is assigned; exact accepts are not live and no producer can create a frontier |
| `B` | Negotiation recoverability plus endpoint/source exact consumer stack | endpoint/source residue is visible and a negotiation-like legal basin can produce recoverable top-net payload | row-rich/control/wrapper-like cases can spend quality runtime on this full chain beside Blueprint A | the plan only changes negotiation weights without downstream exact consumers, or the handoff is passive metadata never consumed by DPO/reorder |
| `C` | Low-residual current-net / vertical-frontier consumer | target-miss/current-net/stage3 handoff evidence exists or can be rebuilt in the current `framework` producer | a dense case needs one producer-consumer diagnostic lane while another Student tries Blueprint A | density is high but target-miss/current-net/vertical-frontier evidence is absent |
| `D` | Diamond source-edge ordered-pair and endpoint-escape exact DPO | source-edge hot tags exist, exact source-edge search is gated off or weak, and endpoint-escape/ordered-pair moves are plausible | a compact case needs a source-edge exact DPO lane independent of LEGALM or negotiation | the case has no source-edge hot-cell signal, or the desired mechanism is endpoint/source recoverability from negotiation (use Blueprint B instead) |

## Blueprint Selection Rules

- Treat each blueprint as a complete mechanism chain.  A plan that names only a
  guard, local polish pass, cap change, or telemetry is not a reconstruction
  route.
- Do not infer negotiation from large `HPWLimprove` alone.  Use Blueprint B when
  endpoint/source/top-net residue and a recoverable negotiation-like basin are
  visible or worth testing.
- When endpoint/source residue is visible on a short/medium or fragmented-row
  case, allocate at least one Blueprint B lane to the full cumulative chain even
  if Blueprint A is also plausible.
- When DPO recovery is broad and the residue is accepted-node/hot-critical
  frontier rather than endpoint/source payload, allocate at least one Blueprint
  A lane and keep its exact accepted-delta path live.
- When low-residual target-miss/current-net anchors are visible, Blueprint C is
  the producer-consumer route.  Do not use it as a generic dense-case default.
- When Diamond/source-edge hot tags are the main signal, Blueprint D is the
  source-edge exact route.  Do not replace it with LEGALM or negotiation unless
  current counters show those producers are active and consumed.
- If a route has exact accepts but final HPWL is flat, do not only widen caps.
  Repair candidate quality, native handoff lifetime, transaction granularity,
  or canonical replay/restore.
- If runtime grows and final HPWL is flat, keep one Student on quality expansion
  of the strongest route and assign another to a different move family, payload,
  exact objective, or start basin.  Runtime repair matters only when it frees
  budget for stronger quality search.
- If a route plateaus after one or two rounds, Teacher review must reopen this
  feature map and explicitly decide whether the missing link is producer,
  handoff, consumer, objective, move family, or preservation.

## Student Packet Requirements

When Teacher selects a blueprint, the Student plan must include:

- route label and blueprint letter;
- start basin and why current evidence supports it;
- full producer-handoff-consumer chain, not one late polish pass;
- first source files/functions to inspect and edit;
- required counters and log names;
- self-diagnosis rule after build/evaluation;
- one strengthened repair before finalization if the first attempt is weak;
- next-handoff note if the route still fails after the repair.

Student should inspect current source around the assigned handles and may
redesign details, but the final report must prove which route links are live.

## Common Demotion Rules

Downweight these unless current same-case final HPWL and liveness prove value:

- guard-only, attribution-only, telemetry-only, comment-only, or preserve-only
  changes;
- passive handoff metadata that is never consumed by DPO, reorder, vertical, or
  a post-DPO pass;
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
