# First Patch Recommendation

## Recommended first bounded patch

- chosen file:
  `tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizer.cpp`
- chosen symbol:
  `dpl_evolve::NegotiationLegalizer::legalize()`
- chosen anchor:
  lines `269-277`, the post-optimisation gate block
- chosen patch mode:
  `postopt_enable_or_gate`
- chosen mutation family:
  `postopt_recovery_family`
- engine prerequisite:
  `negotiation`
- rollout policy:
  `default-off`

## Why this is the best first patch

The local repo already gives us a clean, bounded mutation site:

- `NegotiationLegalizer::legalize()` is the strict-track negotiation driver.
- The post-optimisation block is explicitly present.
- The three hook calls are currently commented out:
  - `greedyImprove(5);`
  - `cellSwap();`
  - `greedyImprove(1);`

That means the first experiment can stay small and mechanism-specific without
rewriting the main negotiation loop or widening the patch surface. It also
means the patch should be validated only on a run that actually confirms the
negotiation path.

## Expected metric movement

- likely positive or neutral:
  - `hpwl_proxy.delta_micron`
  - `displacement.average_displacement_micron`
- guardrails to watch closely:
  - `legality.placement_violations`
  - `displacement.max_displacement_micron`
  - `runtime_seconds`

## Main risk

The implementations of `greedyImprove(int passes)` and `cellSwap()` exist in
`NegotiationLegalizerPass.cpp`, but they are not currently active from the
top-level flow. Enabling them without a small gate or budget can regress
runtime or unexpectedly perturb legality-sensitive cases.

## Seam extraction decision

No seam extraction is required before the first mutation.

Reason:

- the activation site is already isolated in a tiny block inside
  `NegotiationLegalizer::legalize()`
- the first experiment can be expressed as a bounded gate change
- this keeps the first patch easy to review and easy to revert

## Recommended next step

Start with the smallest possible patch:

1. add a default-off gate or marker around the post-optimisation block
2. keep the rest of the negotiation pipeline untouched
3. validate first on a strict evolve line with `--engine negotiation`
4. compare only against the closest strict baselines before any suite rerun
