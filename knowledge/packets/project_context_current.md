# Project Context for Codex

## Current repository interpretation

- `tools/OpenROAD/src/dpl_evolve/` = target plane
- `flow/results|reports|logs|objects/...` = artifact/eval plane
- `evolve_agent/` = control plane
- optional upstream runtime references may be consulted outside the target plane,
  but no in-repo vendor directory is required

## Codex role

Codex should behave as:
- a bounded patcher
- not a repository-wide explorer
- not the evaluator
- not the scheduler

## Early-phase objective

Demonstrate a self-evolving legalizer in OpenROAD by improving
design-specific legalization-stage wirelength while preserving legality.
