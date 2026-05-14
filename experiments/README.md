# Experiments

This directory contains experiment-specific launchers and workbench generators.
They are intentionally separate from `scripts/`, which is reserved for generic
framework helpers used by Teacher/Student agents and reusable validation flows.

## Launchers

`experiments/launchers/` contains fixed campaign drivers such as 8/9-case BO
sweeps, 9-case evolve sweeps, and historical knowledge-collection pipelines.
These scripts may encode a particular case set, flow variant, concurrency
policy, or paper-experiment setup.

## Workbenches

`experiments/workbenches/` contains one-purpose setup scripts for isolated
repair or validation work. Workbench scripts should generate their own ignored
runtime directory under `DPL_EVOLVE_STATE_ROOT` and should not be treated as
general Teacher/Student helper commands.
