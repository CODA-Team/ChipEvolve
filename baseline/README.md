# Baseline Harness

This directory runs the strict legalization-only baselines used by
`dpl_evolve_agent`.

The harness intentionally has exactly three canonical lines:

- `dreamplace_default`: DreamPlace bridge default placement.
- `openroad_dpl_negotiation`: OpenROAD `detailed_placement -use_negotiation`.
- `evolve_default`: clean `detailed_placement_evolve`.

There is no reduced-flow track and no engine environment variable that changes
what a baseline line means.  The selected canonical line is the command
contract.

## Strict Track

Each run reuses:

```text
flow/results/<platform>/<design>/<FLOW_VARIANT>/3_4_place_resized.odb
```

Then it writes isolated outputs under:

```text
dpl_evolve_baseline/<run_tag>/
```

## Common Commands

Run the full three-line suite:

```bash
./dpl_evolve_agent/baseline/run_baseline_suite.sh \
  --case jpeg_nangate45 \
  --flow-variant place_batch_20260421_220319 \
  --threads 10 \
  --dreamplace-root /opt/EDAs/DREAMPlace \
  --dreamplace-python /opt/conda/miniforge3/envs/dreamplace/bin/python
```

Run one canonical line:

```bash
./dpl_evolve_agent/scripts/run_canonical_line.sh \
  --line openroad_dpl_negotiation \
  --case jpeg_nangate45 \
  --flow-variant place_batch_20260421_220319 \
  --threads 10
```

## Authored Files

- `run_baseline.sh`: strict-only internal dispatcher.
- `run_dreamplace_default.sh`: DreamPlace canonical wrapper.
- `run_openroad_negotiation.sh`: OpenROAD negotiation canonical wrapper.
- `run_evolve_default.sh`: evolve default canonical wrapper.
- `run_baseline_suite.sh`: three-line strict comparison suite.
- `detail_place_strict_core.tcl`: shared strict OpenROAD/evolve Tcl core.
- `detail_place_dreamplace.tcl`: DreamPlace bridge Tcl driver.
- `collect_metrics.py`: metrics normalization.
