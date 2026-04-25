# JPEG Efficiency Proposal Matrix, 2026-04-25

This note consolidates the read-only sub-agent investigations for the current
JPEG bottleneck.  The goal is not to crown a final best family yet.  The goal
is to turn "the family is slow" into a concrete implementation queue with
measurable gates.

## Current JPEG Baseline

The canonical baseline harness was tightened after the first draft of this
note.  The current strict baseline lines are `dreamplace_default`,
`openroad_dpl_negotiation`, and `evolve_default`.

| Line | Status | OpenROAD runtime | Outer elapsed | HPWL delta | Avg disp | Max disp | Engine |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| dreamplace_default | ok | 10.024s | ~21.6s | 373078.6255 | see metrics | see metrics | dreamplace_default |
| openroad_dpl_negotiation | ok | 33.503s | ~45.9s | 164045.8655 | see metrics | see metrics | negotiation |
| evolve_default | ok | 6.500s | ~18.8s | 74618.5505 | see metrics | see metrics | evolve_default |
| old r5 alias | ok | 30.478s | 44.793s | 161992.2955 | 1.7474 | 24.9626 | negotiation |
| threaded r6 alias | ok | 25.102s | 38.723s | 161992.2955 | 1.7474 | 24.9626 | negotiation |
| netaware14 alias | ok | 65.899s | 79.270s | 126963.4655 | 1.4507 | 20.7881 | negotiation |
| LEGALM r6 alias | ok | 34.683s | 48.652s | 164045.8655 | 1.7485 | 21.3263 | negotiation |
| priority alias | ok | 24.840s | 39.631s | 153235.1555 | 1.6874 | 23.9530 | negotiation |
| localized swap alias | ok | 36.926s | 50.504s | 158402.5155 | 1.7036 | 26.0348 | negotiation |

Important interpretation:

- The fixed metrics/report stage is about 12 seconds on JPEG.  The current
  optimization target is therefore the legalizer runtime, not the full outer
  elapsed time.
- `openroad_dpl_negotiation` is the OpenROAD DPL baseline for algorithm-family
  comparisons.  `evolve_default` is the clean sidecar command contract that
  agent variants should preserve while changing the private `dpl_evolve`
  implementation.
- `-threads 10` is reaching the command line, and threaded logs confirm a
  worker budget of 10, but legalizer CPU utilization is still near one core.
  The main bottleneck is still serial work in rip-up, candidate search, DRC,
  grid sync, or bystander/active-set maintenance.
- The current `netaware14_rowedge_shortlist_hpwl` gate is not yet the intended
  algorithm.  It aliases to an older row-guard frontier variant, so the 65.899s
  result should be treated as source-of-truth debt, not as a final judgement
  on net-aware shortlist HPWL.

## P0 Implementation Queue

These are the highest-ROI changes that should be implemented before broad
family tuning.

| Priority | Change | Owner family | Why now | Gate |
| --- | --- | --- | --- | --- |
| P0-1 | Split evaluator timing into legalizer, metrics/report, and outer elapsed | harness | Prevent optimizing the fixed 12s report stage instead of the family | JPEG canonical baselines all parse |
| P0-2 | Make JPEG trigger the dirty-region bystander path, not only designs with >=100k cells | negotiation | JPEG has 59k instances and still pays repeated broad scans | aes+jpeg strict |
| P0-3 | Add JPEG-triggered candidate budget/top-K in `findBestLocation` | negotiation | JPEG does not trigger current large-design candidate caps | aes+jpeg strict |
| P0-4 | Add always-on aggregate telemetry for candidates, DRC calls, no-valid, returned-current, active-set size | all negotiation-derived | Next round should not infer hotspots from total runtime only | jpeg strict telemetry present |
| P0-5 | Implement true two-pass cheap frontier before quality/net-anchor scoring | negotiation | Current online frontier is traversal-order biased and can waste scoring budget | aes+jpeg strict |
| P0-6 | Replace netaware14 alias with a real clean materializable generator | netaware | Current netaware14 result is not the intended algorithm | aes+jpeg strict |
| P0-7 | Add cached local HPWL/net bbox proxy for net-aware shortlist | netaware | Removes repeated `getITerms`/net bbox traversal inside shortlist scoring | jpeg strict |
| P0-8 | Fix LEGALM Stage1 to use static-only relaxed placement and allow movable overflow | LEGALM | Current greedy non-overlap Stage1 is inconsistent with relaxed LEGALM and creates displacement tail | aes+jpeg strict |

## Negotiation / R5-Threaded Proposals

Recommended immediate top three:

1. Adaptive dirty-region bystander scan for JPEG-sized designs.
2. Candidate budget and true top-K cheap frontier for JPEG-sized designs.
3. Always-on aggregate telemetry for candidate/DRC/active-set breakdown.

| ID | Change | Expected effect | Complexity | Risk | Minimal gate |
| --- | --- | --- | --- | --- | --- |
| N1 | Lower dirty-region scan threshold from large-only to adaptive by cell count, utilization, and active-set size | Runtime reduction by avoiding full bystander scans across 58 JPEG iterations | M | Missed bystanders can hurt legality | aes+jpeg strict |
| N2 | Add JPEG-triggered candidate cap/top-K in `findBestLocation` | Runtime reduction in candidate enumeration and DRC calls | M | Top-K too small can hurt convergence | jpeg strict vs r5 baseline |
| N3 | Always-on aggregate telemetry counters | Makes future slowdowns diagnosable | S | Slight log overhead | jpeg strict emits summary |
| N4 | True two-pass frontier: collect cheap candidates, then score top-K with net-anchor terms | Runtime stability and better HPWL ranking | M | Need tie-break care | aes+jpeg strict |
| N5 | Split DRC history update into moved/DRC-positive hotsets | Runtime reduction in history update | M | Weaker congestion history may increase iterations | jpeg strict, iterations not worse |
| N6 | Dirty sync for `syncAllCellsToDplGrid` | Avoid full grid/cell sync barriers | L | Stale grid bugs are subtle | aes+jpeg plus simple overlap checks |
| N7 | Incremental active-cell ordering | Reduce repeated full sorts | M | Stale priority can slow convergence | jpeg strict |
| N8 | Persistent row bucket/index | Avoid rebuilding row buckets for dirty scans and active-set expansion | M | Move updates must be exact | jpeg strict |
| N9 | Conservative DRC prefilter before expensive DRC count | Reduce per-candidate DRC cost | M | False negatives can select invalid candidates | jpeg legality |
| N10 | Row-disjoint batch planner for parallel candidate evaluation and commit | Actually use threads in the serial hot path | L | Convergence behavior changes | aes smoke, then jpeg |
| N11 | Prefix/summed row history cache for repeated adjacent candidate costs | Reduce repeated pixel/window scans | M/L | Multi-height details | jpeg strict |
| N12 | Adaptive current-window search shrinking for low-overuse cells | Runtime reduction with limited search loss | S/M | Escape ability may weaken | aes+jpeg strict |

## Net-Aware Proposals

Recommended immediate top three:

1. Replace the current alias with a real clean `netaware14_rowedge_shortlist_hpwl`
   generator or clean patch.
2. Add per-cell low-fanout net bbox cache for local HPWL delta.
3. Gate row-edge probes so they are fallback/late/cheap-frontier only.

| ID | Change | Expected effect | Complexity | Risk | Minimal gate |
| --- | --- | --- | --- | --- | --- |
| W1 | Implement true clean netaware14 materializer/generator | Removes alias confusion and makes results reproducible | L | Generator patch size | aes+jpeg strict |
| W2 | Integrate cheap-first frontier plus bounded HPWL shortlist | Keep HPWL gains without scoring all candidates | L | Quality/runtimes need tuning | aes+jpeg+ariane strict |
| W3 | Cache local HPWL bbox excluding self for selected nets | Reduce repeated net traversal | M | Cache invalidation | jpeg strict |
| W4 | Precompute fanout and low/medium-fanout net lists per cell | Avoid repeated fanout/getITerms work | M/L | More state to maintain | aes+jpeg strict |
| W5 | Replace vector full sort with fixed-size top-K heap | Reduce shortlist sorting cost | M | Tie-break changes | jpeg strict |
| W6 | Dynamic shortlist margin: early narrow, late wider | Reduce early HPWL work while preserving late quality | S | HPWL gains may shrink | jpeg strict |
| W7 | Gated row-edge probes only for bad cheap frontier or late unsettled cells | Avoid row-edge probe explosion | S/M | May lose some HPWL improvement | jpeg+ariane strict |
| W8 | Deduplicate row-edge and anchor candidates before DRC | Reduce duplicate DRC/cost calls | S | Low risk | jpeg strict |
| W9 | Rewrite netaware12 overlay as clean generator recipe | Reproducible parent for future work | L | Reproduction mismatch | aes+jpeg strict |
| W10 | Add net-aware telemetry: shortlist size, HPWL evals, fanout skips, row-edge accepts | Diagnose whether HPWL or DRC is the real cost | M | Log noise | jpeg debug run |
| W11 | Cheap geometry filter before DRC for row-edge candidates | Reduce DRC calls in current alias-like paths | M | DRC false-negative risk | jpeg legality |
| W12 | Use current-blend/history-runtime-trim as default objective seed instead of row-guard/capacity-slack | Prior evidence suggests better JPEG runtime/HPWL tradeoff | S/M | May be JPEG-specialized | jpeg+aes strict |
| W13 | Materialize JPEG specialist `soft_threshold + overflow_only + gated rowedge + cached HPWL` as donor | Strong prior from algobank JPEG result | M | Not default-safe | jpeg strict, then aes smoke |
| W14 | Combine threaded row-bucket base with net-aware shortlist | Let active-set runtime savings pay for HPWL secondary scoring | L | Family attribution complexity | aes+jpeg strict |

## LEGALM Proposals

Recommended immediate top three:

1. Split static placement validity from full non-overlap validity.
2. Implement relaxed Stage1 scanline/plate projection.
3. Make Stage2/3 use overflow/hotset-driven BGD with capped candidate stencil.

| ID | Change | Expected effect | Complexity | Risk | Minimal gate |
| --- | --- | --- | --- | --- | --- |
| L1 | Split `siteRectIsStaticPlaceable` from full placeability | Align Stage1 with relaxed LEGALM semantics | M | Stage2 must clear overflow | jpeg strict |
| L2 | Relax Stage1 to allow movable overflow while satisfying static constraints | Reduce displacement tail caused by greedy non-overlap slot grabbing | M | More overflow after Stage1 | aes+jpeg strict |
| L3 | Build plate/row free-interval index | Reduce Stage1 search cost and improve locality | M/L | Region/fence correctness | aes+jpeg strict |
| L4 | Plate-local nearest row interval projection | Better relaxed initialization than full window scan | M | Multi-height complications | jpeg max-disp check |
| L5 | Deduplicate and cap Stage1 candidates with telemetry | Runtime reduction and diagnosability | S | Too-small cap can fail | jpeg strict |
| L6 | Stage2 active set = overflow cells plus neighbors | Avoid full-cell BGD after relaxed Stage1 | M | Hotset too narrow can stall | jpeg strict |
| L7 | BGD visit cap and overflow-priority ranking | Focus compute on cells that reduce overflow | M | Local optimum risk | jpeg stage telemetry |
| L8 | Separate Stage2 legalization stencil from Stage3 refinement stencil | Legalize first, polish second | M | More implementation paths | aes+jpeg strict |
| L9 | Cheap-first candidate cost before HPWL/anchor cost | Avoid R5-style scalar quality overhead | M | HPWL gains weaker | jpeg runtime no worse than R5 |
| L10 | Queue-based zero-overflow repair from overflow sites | Avoid broad cell scans | L | Needs occupancy bookkeeping | jpeg strict |
| L11 | Stage3 only targets high-displacement tail and low-fanout nets | Directly reduce JPEG displacement tail | M | HPWL may change | jpeg max disp improves |
| L12 | Component pressure and plate escape guidance | Better local-optimum escape | M/L | Constraint semantics risk | jpeg plus region testcase |
| L13 | Stable row-band partitions | Reduce partition rebuild overhead | M | Fixed partitions may reduce convergence | jpeg telemetry |
| L14 | Stage timers and candidate counters | Identify Stage1 vs Stage2/3 bottleneck | S | Log overhead | jpeg strict |
| L15 | Replace per-cell verbose candidate logs with histograms | Avoid message-limit and log overhead | S | Less cell-level debug | jpeg log summary |

## Priority Escape Proposals

Priority is currently a repair/operator line, not a primary base.  It should
not be promoted as default until telemetry proves it triggers only on real
stuck/no-valid cases.  However, its current JPEG alias is fast and has better
HPWL than the threaded alias, so it is worth inspecting.

| ID | Change | Expected effect | Complexity | Risk | Minimal gate |
| --- | --- | --- | --- | --- | --- |
| P1 | Remove any diamond-first path from priority variants | Avoid false success through fallback | S | None if entrypoint is negotiation | engine-path assertion |
| P2 | Add structured find-best result: seen, valid, cap-hit, no-valid, returned-current | Diagnose real stuck/no-valid | M | Signature changes | aes+jpeg strict |
| P3 | Per-cell stuck state with no-valid and returned-current streaks | Trigger escape only when needed | M | State memory | aes+jpeg zero/near-zero trigger |
| P4 | Escape candidates only for illegal/stuck cells | Avoid always-on search widening | M | May miss soft improvements | synthetic stuck gate |
| P5 | Track attempted, accepted, rollback, fixed-stuck counts | Prove repair effectiveness | S | Telemetry overhead | stuck gate |
| P6 | Bounded row-edge/free-interval endpoint escape | Scale-safe stuck repair | M | Displacement risk | jpeg+stuck gate |
| P7 | Rollback-safe escape acceptance | Protect legality/HPWL | M | Runtime overhead | jpeg strict |
| P8 | Compare priority alias with threaded r6 for actual code differences | Determine why priority alias is currently faster on JPEG | S | May reveal alias confusion | diff + log audit |

## Localized Swap Proposals

Localized swap should stay polish-only and legal-parent-only.  Its current JPEG
runtime is not competitive as a base, but bounded transactional polish remains
useful after a runtime-safe parent.

| ID | Change | Expected effect | Complexity | Risk | Minimal gate |
| --- | --- | --- | --- | --- | --- |
| S1 | Parent legality guard before any swap | Prevent using swap as legalization fallback | S | None | legal parent check |
| S2 | Parent runtime/displacement guard | Skip polish when parent is already expensive | S | Less polish coverage | jpeg parent gate |
| S3 | Bounded hotset selection | Avoid full pair enumeration | M | Missed opportunities | aes+jpeg polish gate |
| S4 | Same-height/same-PG/near-row pair cap | Scale-safe candidate pairs | M | Smaller search | jpeg strict |
| S5 | Transactional apply/check/rollback | Maintain legality and displacement guard | M | Local legality complexity | aes+jpeg strict |
| S6 | Cached local HPWL delta for swaps | Faster scoring | M | Cache invalidation | jpeg polish gate |
| S7 | Wall-time and pair-eval hard budget | Prevent JPEG slowdown | S | Less HPWL improvement | pair/time telemetry |
| S8 | Report accepted swaps and post-polish deltas | Decide if polish is worth keeping | S | None | telemetry present |

## Next Worker Dispatch Recommendation

1. Harness worker: implement timing split, legalizer-only gate, thread/CPU
   fields, and telemetry extraction.
2. Negotiation worker: implement P0-1/P0-2/P0-3 from the negotiation list,
   then rerun JPEG/AES.
3. Netaware worker: fix source-of-truth and implement a real clean netaware14
   generator before interpreting any more netaware14 timing.
4. LEGALM worker: implement relaxed Stage1 validity split plus telemetry.
5. Priority worker: audit why priority alias is faster than threaded r6 and
   prove whether it is real priority logic or shared row-bucket behavior.

The first acceptance target is not native DPL parity.  The immediate target is:

- JPEG legalizer runtime below 25s with no fallback.
- HPWL no worse than current threaded r6 alias.
- Telemetry sufficient to explain candidate count, DRC count, active-set size,
  and per-stage elapsed time.
