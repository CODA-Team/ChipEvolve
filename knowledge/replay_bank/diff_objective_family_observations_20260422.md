# Differential-Style Objective Family Observations (2026-04-22)

## Scope

This patch family moved beyond postopt policy and changed the main-pass
objective itself.

Target surface:
- `NegotiationLegalizer::negotiationCost`
- `NegotiationLegalizer::placementObjective`
- candidate generation in `findBestLocation`

## What was attempted

The experimental family added three ideas:
- adaptive overflow weighting in the negotiation cost
- a smooth connectivity anchor derived from incident net positions
- extra candidate exploration around the smooth anchor

This was meant to mimic ideas from differentiable or continuous-placement
frameworks without rewriting the legalizer around gradients.

## What was learned

- The direction is real and can still improve HPWL on larger designs.
- It is not automatically better than the current best family.
- The first tested version mainly traded a small quality gain for an even
  larger runtime increase.

## Concrete evidence

On `ibex_nangate45`:
- current best evolve HPWL delta: `6556.6705`
- differential-style objective HPWL delta: `6518.9155`
- current best evolve setup WNS: `0.015268`
- differential-style objective setup WNS: `0.0142324`
- current best evolve runtime: `54.64 s`
- differential-style objective runtime: `82.714 s`

## Conclusion

This family is worth keeping in the knowledge base because it opens a new
algorithmic surface:
- objective shaping
- anchor shaping
- candidate generation around continuous surrogates

But the first implementation should be considered a knowledge-gathering run,
not a promoted patch. Any future revisit needs a much tighter runtime budget.
