# Baseline Harness

This directory runs strict legalization-only comparisons and reduced-flow
comparisons for `dpl_evolve`.

Most agents should call:

- `$DPL_EVOLVE_AGENT_ROOT/adapters/science_codeevolve/evaluator.py`
- `$DPL_EVOLVE_AGENT_ROOT/scripts/run_canonical_line.sh`
- `$DPL_EVOLVE_AGENT_ROOT/baseline/run_baseline_suite.sh`

Treat `run_baseline.sh` as the internal dispatcher.

## Project Terms

- `baseline_default`: upstream OpenROAD detailed placement.
- `baseline_dreamplace_abacus`: DreamPlace bridge plus Abacus.
- `evolve_line`: clean `dpl_evolve`.
- family variant: materialized `dpl_evolve` source plus private binary.

## Strict Track

Strict runs reuse:

```text
flow/results/<platform>/<design>/<FLOW_VARIANT>/3_4_place_resized.odb
```

Then they run legalization and post-metrics in isolated
`dpl_evolve_baseline/<run_tag>/` directories.

This track should not rerun upstream Yosys/place when the snapshot exists.

## Variant Binary Rule

Family/variant runs must use an explicit binary:

```bash
source "${DPL_EVOLVE_STATE_ROOT}/variants/<agent_id>/variant_env.sh"
"$DPL_EVOLVE_AGENT_ROOT/scripts/run_canonical_line.sh" \
  --line evolve_line \
  --openroad-binary "${OPENROAD_BINARY}" \
  --design-config ./designs/nangate45/gcd/config.mk \
  --flow-variant <FLOW_VARIANT> \
  --run-tag <RUN_TAG>
```

## Outputs

Primary result:

```text
flow/reports/<platform>/<design>/<FLOW_VARIANT>/dpl_evolve_baseline/<run_tag>/metrics.json
```

Support files live beside it and under matching `results/`, `logs/`, and
`objects/` subdirectories.

## Authored Files

- `run_baseline.sh`: dispatcher.
- `run_evolve_line.sh`: clean evolve line wrapper.
- `run_or_default.sh`: upstream baseline wrapper.
- `run_dp_abacus.sh`: DreamPlace/Abacus wrapper.
- `run_baseline_suite.sh`: fixed comparison suite.
- `detail_place_*.tcl`: strict Tcl drivers.
- `flow/detail_place_flow_*.tcl`: reduced-flow Tcl drivers.
- `collect_metrics.py`: metrics normalization.
