# Calibration Scripts

This directory contains calibration-adjacent script implementations.

Current scripts:

- `calibrate_start_seeds.sh`: target-local start-kind probe for prepared
  source basins before a Teacher/Student round.
- `summarize_start_seed_calibration.py`: summarizer for that target-local
  probe.

Call these scripts through their canonical namespace:

```text
$DPL_EVOLVE_AGENT_ROOT/scripts/calibration/calibrate_start_seeds.sh
$DPL_EVOLVE_AGENT_ROOT/scripts/calibration/summarize_start_seed_calibration.py
```

Paper-level ReviewDSE Level 1 calibration contracts live under:

```text
$DPL_EVOLVE_AGENT_ROOT/calibration/
```

Generated Level 1 calibration runs should use:

```text
$DPL_EVOLVE_STATE_ROOT/calibrations/<calibration_id>/
```
