# Skill: run_single_baseline

## Purpose
Run exactly one target line during fast iteration.

## Typical modes
- baseline_default
- baseline_dreamplace_abacus
- evolve_line

## Expected local wrappers
- `$DPL_EVOLVE_AGENT_ROOT/baseline/run_baseline.sh`
- `$DPL_EVOLVE_AGENT_ROOT/baseline/run_evolve_line.sh`
- fixed wrappers:
  - `run_or_default.sh`
  - `run_dp_abacus.sh`

For agent-managed execution, prefer:

- `$DPL_EVOLVE_AGENT_ROOT/adapters/science_codeevolve/evaluator.py --mode single`
- or `$DPL_EVOLVE_AGENT_ROOT/scripts/run_codex_once.sh --mode single`

## Procedure
1. Confirm which line you need:
   - if validating patch quality, prefer `evolve_line`
   - if checking regression against in-tree baseline, run matching baseline wrapper
2. Reuse an existing `FLOW_VARIANT` when you want to reuse upstream ORFS
   snapshots such as `3_4_place_resized.odb`.
3. Launch only the selected line.
4. If the run uses `--family-variant`, source the matching `variant_env.sh`
   first and still pass `--openroad-binary "${OPENROAD_BINARY}"`.
5. Read the resulting:
   - `flow/reports/<platform>/<design>/<flow_variant>/dpl_evolve_baseline/<run_tag>/metrics.json`
6. If this is the first run on a case, classify it before choosing the first
   patch family:
   - `python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/recommend_initial_family.py" --metrics <metrics.json>`
7. Compare only against the closest baseline necessary for the decision.

## Notes for Codex
- Prefer strict legalizer track before reduced-flow track.
- If the same patch fails twice on the same line, inspect replay/debug context before another full rerun.

## Examples

Run one fixed baseline:

```bash
"$DPL_EVOLVE_AGENT_ROOT/baseline/run_or_default.sh" \
  --design-config ./designs/nangate45/gcd/config.mk \
  --flow-variant dpl_evolve_suite_20260422_125226 \
  --run-tag agent_single_default \
  --threads 8
```

Run just the evolve line:

```bash
"$DPL_EVOLVE_AGENT_ROOT/baseline/run_evolve_line.sh" \
  --design-config ./designs/nangate45/gcd/config.mk \
  --flow-variant dpl_evolve_suite_20260422_125226 \
  --run-tag agent_evolve_line \
  --threads 8
```

Run a family variant with an explicit binary:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant_relink.sh" \
  --variant-root "${DPL_EVOLVE_STATE_ROOT}/variants/legalm_engine" \
  --dpl-src /abs/path/to/legalm_engine/dpl_evolve
source "${DPL_EVOLVE_STATE_ROOT}/variants/legalm_engine/variant_env.sh"

"$DPL_EVOLVE_AGENT_ROOT/scripts/run_canonical_line.sh" \
  --line evolve_line \
  --family-variant legalm_engine \
  --openroad-binary "${OPENROAD_BINARY}" \
  --design-config ./designs/nangate45/gcd/config.mk \
  --flow-variant dpl_evolve_suite_20260422_125226 \
  --run-tag agent_legalm_line \
  --threads 8
```

The verified strict-track example in this repo is:

```bash
"$DPL_EVOLVE_AGENT_ROOT/baseline/run_evolve_line.sh" \
  --design-config ./designs/nangate45/gcd/config.mk \
  --flow-variant dpl_evolve_suite_20260422_125226 \
  --run-tag agent_setup_verify \
  --threads 8
```
