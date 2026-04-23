# Multi-case Negotiation Observations (2026-04-22)

## Scope

These observations come from manual bounded-patch runs on:
- `gcd_nangate45`
- `aes_nangate45`
- `gcd_asap7`
- and later larger-case validation on:
  - `ibex_nangate45`
  - `aes_asap7`
  - `jpeg_nangate45`

The target legalizer path was:
- `detailed_placement_evolve -use_negotiation`

## Effective code regions

The useful mutation surface in this round was:
- `src/dpl_evolve/src/NegotiationLegalizer.cpp`
- `src/dpl_evolve/src/NegotiationLegalizerPass.cpp`
- `src/dpl_evolve/src/NegotiationLegalizer.h`

The highest-value symbols were:
- `NegotiationLegalizer::legalize`
- `NegotiationLegalizer::placementObjective`
- `NegotiationLegalizer::wirelengthDeltaCost`
- `NegotiationLegalizer::greedyImprove`
- `NegotiationLegalizer::cellSwap`

## What worked

### 1. HPWL-aware local objective was necessary

Replacing pure displacement-only postopt scoring with:

- `targetCost(...) + hpwl_weight * wirelengthDeltaCost(...)`

was the turning point that enabled real HPWL improvement instead of only runtime
or displacement improvements.

The local HPWL proxy worked best when:
- very large nets were skipped
- only nets incident to the moved cell were evaluated
- the proxy was blended into both `greedyImprove` and `cellSwap`

### 2. Postopt legality guards were necessary

Enabling stronger postopt without legality guards immediately produced illegal
placements.

The following protections were required:
- DRC filtering inside `greedyImprove`
- legality recheck after each accepted `greedyImprove` move
- legality recheck after each `cellSwap`
- full revert when a move or swap became illegal

Without these guards, HPWL improvements were not usable.

### 3. Objective-based `cellSwap` was useful

Changing `cellSwap` acceptance from pure displacement improvement to objective
improvement was beneficial.

This was especially useful once the objective already included the HPWL proxy.
It helped preserve or recover HPWL improvements that displacement-only swap
logic would miss.

### 4. Wide postopt search helped timing-sensitive cases

Allowing `greedyImprove` to search a wider neighborhood around both:
- the global-placement anchor
- the current legalized location

produced the strongest HPWL/WNS/TNS gains on negative-slack cases.

This was the first direction in this round that improved all of:
- HPWL
- setup WNS
- setup TNS

on real cases with negative setup slack.

## Case-by-case observations

### `gcd_nangate45`

Effective pattern:
- HPWL-aware objective
- legality-preserving postopt
- widened greedy postopt

Observed behavior:
- strong HPWL improvement
- positive setup WNS movement
- lower displacement

Important caveat:
- baseline `setup_tns = 0`, so there is no available TNS headroom to improve
- this case is useful for HPWL/WNS validation, not for proving TNS gain
- runtime tradeoff stayed moderate here:
  - baseline `0.572 s`
  - best evolve `1.555 s`

### `aes_nangate45`

Effective pattern:
- HPWL-aware objective
- objective-based `cellSwap`
- wide search around both init and current positions

Observed behavior on the best version:
- HPWL improved
- setup WNS improved
- setup TNS improved

Important tradeoff:
- runtime increased sharply
- baseline `9.398 s`
- best evolve `34.996 s`

Rejected variants:
- reducing greedy passes from `5+1` to `2+1`
- keeping init search narrow while only widening current-position search

Both rejected variants preserved some HPWL improvement but lost the clean TNS
gain on `aes_nangate45`.

### `gcd_asap7`

Effective pattern:
- same family as `aes_nangate45`

Observed behavior:
- HPWL improved
- setup WNS improved
- setup TNS improved
- runtime overhead was much smaller than on `aes_nangate45`

Interpretation:
- the wide HPWL-aware postopt is more scalable on this case than on
  `aes_nangate45`
- runtime tradeoff stayed small:
  - baseline `2.373 s`
  - best evolve `2.414 s`

### `ibex_nangate45`

Observed behavior:
- HPWL improved strongly
- setup WNS improved
- runtime exploded

Important tradeoff:
- baseline `4.433 s`
- best evolve `54.64 s`

Interpretation:
- quality scales
- runtime does not
- this case is a hard warning that always-on wide postopt is not viable as a
  default policy for larger designs

### `aes_asap7`

Observed behavior:
- HPWL improved strongly
- setup WNS improved strongly
- setup TNS improved strongly
- runtime exploded

Important tradeoff:
- baseline `5.322 s`
- best evolve `71.623 s`

Interpretation:
- this family remains high-value for quality exploration
- but it must be converted into a budgeted or selective refinement policy

### `jpeg_nangate45`

Observed behavior:
- HPWL improved strongly
- setup WNS improved
- setup TNS improved
- runtime exploded further

Important tradeoff:
- baseline `34.667 s`
- best evolve `511.864 s`

Interpretation:
- this is the clearest evidence so far that wide refinement should be treated
  as a targeted secondary stage, not a default full-design behavior

## Rejected directions

### `cellSwap()` only

Outcome:
- slight runtime improvement
- no meaningful HPWL / WNS / TNS gain

Use:
- low-risk sanity step only

### Fewer greedy passes

Attempt:
- `greedyImprove(5)` -> `greedyImprove(2)` before `cellSwap`

Outcome:
- not a reliable runtime recovery
- `aes_nangate45` lost the clean TNS gain

Decision:
- reject as general policy

### Narrow init search + wide current search

Attempt:
- keep GP-anchor search narrow
- widen only current-location search

Outcome:
- `gcd_nangate45` remained good
- `gcd_asap7` stayed positive
- `aes_nangate45` lost the positive TNS signal

Decision:
- reject as current best state

## Current best known direction

The strongest quality-only direction from this round is:
- keep the HPWL-aware blended objective
- keep legality-preserving postopt
- keep objective-based `cellSwap`
- keep widened greedy search around both init and current locations

This is the strongest current evidence for real HPWL/WNS/TNS improvement, but
it is no longer acceptable as an unconditional default because runtime on
larger designs diverges too far from the baseline.

The next family should target:
- selective refinement budget
- stall-triggered stuck-cell escape
- localized refinement only on overflow-heavy or timing-sensitive regions

That next step has now been opened and recorded in:
- `evolve_agent/knowledge/replay_bank/selective_refinement_budget_observations_20260422.md`

## Supporting artifacts

Representative baseline artifacts:
- `evolve_agent/checkpoints/operations/manual_gcd_round_20260422/baseline_eval.json`
- `evolve_agent/checkpoints/operations/manual_cross_case_hpwl_start/aes_baseline_eval.json`
- `evolve_agent/checkpoints/operations/manual_cross_case_hpwl_start/gcd_asap7_baseline_eval.json`

Representative improving artifacts:
- `evolve_agent/checkpoints/operations/manual_gcd_round_20260422/candidate6_eval.json`
- `evolve_agent/checkpoints/operations/manual_hpwl_timing_search_before_wide_greedy/aes_candidate3_eval.json`
- `evolve_agent/checkpoints/operations/manual_hpwl_timing_search_before_wide_greedy/gcd_asap7_candidate3_eval.json`
- `evolve_agent/checkpoints/operations/manual_broader_case_sweep_20260422/ibex_n45_evolve.json`
- `evolve_agent/checkpoints/operations/manual_broader_case_sweep_20260422/aes_asap7_evolve.json`
- `evolve_agent/checkpoints/operations/manual_broader_case_sweep_20260422/jpeg_n45_evolve_retry.json`
