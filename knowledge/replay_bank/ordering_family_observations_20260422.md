# Ordering Family Observations (2026-04-22)

## Scope

This patch family modified negotiation ordering behavior in the main pass
instead of only changing post-optimization.

Target surface:
- `NegotiationLegalizer::sortByNegotiationOrder`
- negotiation-loop prioritization logic

## What was attempted

The attempted direction biased ordering more strongly with local
wirelength-related pressure so that cells with worse local HPWL pressure were
processed earlier.

## What was learned

- On small cases, this can produce some extra HPWL movement.
- It is much less stable than the postopt/objective family.
- The ordering-only family did not preserve clean timing improvements across
  cases.

## Why it was rejected

The ordering family was not promoted because:
- `gcd_nangate45` showed some HPWL benefit
- `aes_nangate45` lost timing quality, especially the clean TNS signal
- runtime did not improve enough to justify the extra risk

## Role going forward

Ordering remains a useful secondary mutation family, but it should be treated
as:
- a case-specific tuner
- not the default cross-case direction
- lower priority than runtime-aware selective refinement
