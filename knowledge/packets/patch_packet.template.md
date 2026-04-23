# Patch Packet Template

## Problem
- problem_id: <fill>
- design/platform: <fill>
- mode: <strict|reduced-flow|flow-faithful>

## Primary Objective
- <e.g., reduce legalization HPWL perturbation>

## Patch Surface
- file: <fill>
- symbol: <fill>
- patch_mode: <param_tuning|local_formula_change|ordering_logic_change|search_window_policy_change|postopt_enable_or_gate>

## Relevant Knowledge
- stage_context: <fill>
- delta_ledger entries: <fill>
- symbol_cards: <fill>
- mutation_playbook family: <fill>

## Hard Gates
- legality must remain true
- metrics contract must pass
- runtime regression within contract
- displacement guard within contract

## Notes
- Do not widen patch scope without updating mutation contract.
- Prefer one mechanism change per patch.
