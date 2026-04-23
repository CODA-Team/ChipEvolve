# Selective Refinement Budget Observations (2026-04-22)

## Scope

This patch family keeps the HPWL-aware postopt logic but stops applying the
same heavy refinement budget to every movable cell on large designs.

Target surface:
- `NegotiationLegalizer::greedyImprove`

New policy:
- for small designs, preserve full-scan behavior
- for large designs, rank movable cells by refinement priority
- apply wide greedy refinement only to a budgeted subset

Priority inputs:
- displacement
- pin count
- cell area

## Why this family was opened

The earlier wide-postopt family clearly improved HPWL/WNS/TNS, but larger
cases showed unacceptable runtime growth:
- `ibex_nangate45`: `4.433 s -> 54.64 s`
- `aes_asap7`: `5.322 s -> 71.623 s`
- `jpeg_nangate45`: `34.667 s -> 511.864 s`

That made runtime-aware refinement the highest-priority next step.

## First results

### `gcd_nangate45`

Baseline:
- runtime `0.572 s`
- HPWL delta `747.4715`
- setup WNS `0.00893974`

Previous best wide-postopt:
- runtime `1.555 s`
- HPWL delta `292.4015`
- setup WNS `0.0130022`

Selective budget:
- runtime `1.211 s`
- HPWL delta `271.7815`
- setup WNS `0.0130022`

Takeaway:
- better runtime than the previous best
- slightly better HPWL than the previous best

### `ibex_nangate45`

Baseline:
- runtime `4.433 s`
- HPWL delta `16432.4155`
- setup WNS `0.00728351`

Previous best wide-postopt:
- runtime `54.64 s`
- HPWL delta `6556.6705`
- setup WNS `0.015268`

Selective budget:
- runtime `33.342 s`
- HPWL delta `6923.0905`
- setup WNS `0.0154523`

Takeaway:
- runtime reduced by about `39%` versus the previous best
- some HPWL quality is given back
- WNS is preserved or slightly improved

### `aes_asap7`

Baseline:
- runtime `5.322 s`
- HPWL delta `5220.818`
- setup WNS `-27.091`
- setup TNS `-245.143`

Previous best wide-postopt:
- runtime `71.623 s`
- HPWL delta `2236.082`
- setup WNS `-20.4597`
- setup TNS `-151.734`

Selective budget:
- runtime `42.462 s`
- HPWL delta `2435.174`
- setup WNS `-19.6634`
- setup TNS `-160.921`

Takeaway:
- runtime reduced by about `41%` versus the previous best
- HPWL and TNS regress slightly relative to the previous best
- all three quality metrics remain much better than baseline

## Current interpretation

This is the first family that starts to address the main large-case weakness of
the wide-postopt direction.

It does not fully solve the runtime problem yet, but it changes the tradeoff
from:
- maximum quality, extreme runtime

to:
- still-strong quality, noticeably lower runtime

## Current recommendation

Promote this family over the always-on wide-postopt variant as the default
large-case exploration branch.

Next follow-up ideas:
- use stall count or overflow trend to enable larger refinement budgets only
  when the negotiation loop actually needs them
- split refinement into:
  - narrow always-on pass
  - wide budgeted pass for selected cells
- target stuck-cell escape separately from timing/HPWL refinement

## Supporting artifacts

- `evolve_agent/checkpoints/operations/manual_selective_refine_budget_round1_20260422/gcd_n45_selective_budget_r1.json`
- `evolve_agent/checkpoints/operations/manual_selective_refine_budget_round1_20260422/ibex_n45_selective_budget_r2.json`
- `evolve_agent/checkpoints/operations/manual_selective_refine_budget_round1_20260422/aes_asap7_selective_budget_r2.json`
