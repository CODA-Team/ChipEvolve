# localized_swap

This directory records the current flow-facing status for `localized_swap`.

Current decision: keep it as opt-in polish only after a legal parent.  It should
not be treated as a base legalizer, a rescue path for illegal parents, or a
large-case success when the parent path times out.

The old hotbucket/R3 skip-polish path is rejected for promotion.  The bounded
local polish evidence is useful, but the saved patch is not a standalone full
implementation in the current clean ORFS checkout, so it is not packaged as
`dpl_evolve.patch` yet.

Before enabling any localized candidate in flow:

- Record the parent baseline and the post-polish delta in the same run.
- Require parent legality before polish.
- Skip explicitly if the parent is illegal or timed out.
- Roll back on legality, runtime, HPWL, displacement, or timing regression.
- Keep the candidate set bounded by hotset, buckets/window, caps, and wall
  clock.

Evidence:

- `../../family_robustness/localized_swap/HARDENING_DECISION_20260425.md`
- `../../family_robustness/localized_swap/WORKER_RESULT_R3_20260425.md`
- `../../family_robustness/localized_swap/ROBUSTNESS_DECISION_20260425.md`
- `../../knowledge/algorithm_cards/priority_localized_card.yaml`
