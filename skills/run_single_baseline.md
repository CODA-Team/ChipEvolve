# Skill: run_single_baseline

## Purpose
Run exactly one target line during fast iteration.

## Typical modes
- baseline_default
- baseline_dreamplace_abacus
- evolve_line

## Expected local wrappers
- `evolve_agent/baseline/run_baseline.sh`
- `evolve_agent/baseline/run_evolve_line.sh`
- fixed wrappers:
  - `run_or_default.sh`
  - `run_dp_abacus.sh`

For agent-managed execution, prefer:

- `evolve_agent/adapters/science_codeevolve/evaluator.py --mode single`
- or `evolve_agent/scripts/run_codex_once.sh --mode single`

## Procedure
1. Confirm which line you need:
   - if validating patch quality, prefer `evolve_line`
   - if checking regression against in-tree baseline, run matching baseline wrapper
2. Reuse an existing `FLOW_VARIANT` when you want to reuse upstream ORFS
   snapshots such as `3_4_place_resized.odb`.
3. Launch only the selected line.
4. Read the resulting:
   - `flow/reports/<platform>/<design>/<flow_variant>/dpl_evolve_baseline/<run_tag>/metrics.json`
5. If this is the first run on a case, classify it before choosing the first
   patch family:
   - `python3 evolve_agent/scripts/recommend_initial_family.py --metrics <metrics.json>`
6. Compare only against the closest baseline necessary for the decision.

## Notes for Codex
- Prefer strict legalizer track before reduced-flow track.
- If the same patch fails twice on the same line, inspect replay/debug context before another full rerun.

## Examples

Run one fixed baseline:

```bash
./evolve_agent/baseline/run_or_default.sh \
  --design-config ./designs/nangate45/gcd/config.mk \
  --flow-variant dpl_evolve_suite_20260422_125226 \
  --run-tag agent_single_default \
  --threads 8
```

Run just the evolve line:

```bash
./evolve_agent/baseline/run_evolve_line.sh \
  --design-config ./designs/nangate45/gcd/config.mk \
  --flow-variant dpl_evolve_suite_20260422_125226 \
  --run-tag agent_evolve_line \
  --threads 8
```

The verified strict-track example in this repo is:

```bash
./evolve_agent/baseline/run_evolve_line.sh \
  --design-config ./designs/nangate45/gcd/config.mk \
  --flow-variant dpl_evolve_suite_20260422_125226 \
  --run-tag agent_setup_verify \
  --threads 8
```
