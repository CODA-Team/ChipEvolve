# Baseline Harness

This directory runs the strict legalization-only baselines used by
`dpl_evolve_agent`.

The harness intentionally has exactly two canonical lines:

- `openroad_dpl_flow`: OpenROAD `detailed_placement`, `improve_placement`,
  and `optimize_mirroring`.
- `evolve_default`: clean `detailed_placement_evolve`,
  `improve_placement_evolve`, and `optimize_mirroring_evolve`.

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

Run the full canonical suite:

```bash
./dpl_evolve_agent/baseline/run_baseline_suite.sh \
  --case jpeg_nangate45 \
  --flow-variant <FLOW_VARIANT_WITH_3_4_PLACE_RESIZED_ODB> \
  --threads 10
```

Run one canonical line:

```bash
./dpl_evolve_agent/scripts/run_canonical_line.sh \
  --line openroad_dpl_flow \
  --case jpeg_nangate45 \
  --flow-variant <FLOW_VARIANT_WITH_3_4_PLACE_RESIZED_ODB> \
  --threads 10
```

Run `detailed_placement_evolve` with a private relinked OpenROAD binary:

```bash
./dpl_evolve_agent/baseline/run_baseline.sh \
  --line evolve_default \
  --case jpeg_nangate45 \
  --flow-variant <FLOW_VARIANT_WITH_3_4_PLACE_RESIZED_ODB> \
  --threads 10 \
  --openroad-binary <private-variant-openroad-bin>
```

## Authored Files

- `run_baseline.sh`: strict-only internal dispatcher.
- `run_openroad_dpl_flow.sh`: OpenROAD DPL flow canonical wrapper.
- `run_evolve_default.sh`: evolve default canonical wrapper.
- `run_baseline_suite.sh`: two-line strict comparison suite.
- `detail_place_openroad.tcl`: fixed OpenROAD DPL flow Tcl driver.
- `detail_place_evolve.tcl`: fixed `detailed_placement_evolve` Tcl driver.
- `collect_metrics.py`: metrics normalization.

DreamPlace/Abacus is still a donor/reference mechanism under
`family_variants/`, but it is not part of the default baseline suite.
