# Evidence Policy

This repo separates experiment facts from algorithm hypotheses. Agents should
not treat every note as a rule.

## Evidence Levels

- `contract`: hard project boundary. Examples: keep
  `detailed_placement_evolve` as the evolved entrypoint, do not edit
  evaluator/scoring, and keep runtime artifacts out of git.
- `measured_observation`: result seen in a specific run or local matrix. It
  should include the case, binary, command, date, and metrics path when used
  for decisions.
- `working_hypothesis`: plausible explanation or design direction. It may
  guide a patch, but must be tested before promotion.
- `reference_donor`: code or paper mechanism worth studying. It is not a
  direct apply target unless a patch inventory explicitly marks it as such.
- `deprecated_context`: historical evidence kept only for forensics. It should
  not appear in default prompts.

## Current Calibration

- OpenROAD DPL flow is the current strict-track comparison anchor in this repo:
  `detailed_placement`, `improve_placement`, `optimize_mirroring`.
- OpenROAD diamond remains a local-search donor and prepass reference, not a
  standalone canonical baseline runner in the current harness.
- OpenROAD negotiation/NBLG is a repair and mechanism donor. Prior local runs
  showed useful speed work but also exposed that negotiation alone is not the
  root answer for every case.
- LEGALM and DREAMPlace/Abacus are idea and source donors. Their stages,
  objectives, and data structures should be adapted, not copied blindly.
- The constrained `EvolveLegalizer` stage flow is a scaffold. Stage order,
  objective details, and concrete algorithms remain open to evidence-driven
  replacement.

## Prompt Hygiene

When adding knowledge, state one of:

- `observed`: what happened, where, and with which artifacts.
- `hypothesis`: why it may have happened.
- `next_test`: the smallest experiment that would confirm or reject it.

Avoid writing unverified hypotheses as permanent instructions.
