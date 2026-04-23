# Scripts

This directory contains the top-level executable helpers for `evolve_agent`.

These files are the preferred human/agent entrypoints. If a task can be solved
through a script here, prefer it over rebuilding the workflow from scratch.

## Main entrypoints

- `run_canonical_line.sh`
  Run one canonical baseline line or the clean evolve line.
- `run_place_batch.sh`
  Prepare reusable placement snapshots before code evolve starts.
- `checkpoint.py`
  Create, restore, inspect, and list local edit-state checkpoints.
- `build_openroad_only.sh`
  Fast incremental build of the currently configured OpenROAD tree.
- `configure_openroad_variant.sh`
  Configure an isolated OpenROAD build/install variant, optionally with an
  external `dpl_evolve` source tree.
- `materialize_family_variant.sh`
  Copy the clean initial evolve base and apply a family patch to create a
  dedicated variant source tree.
- `recommend_initial_family.py`
  Read a baseline `metrics.json` and recommend the best initial patch family.
- `compare_runs.py`
  Compare two evaluator JSONs or run results and summarize objective deltas.
- `run_design_evolve_loop.py`
  The main Python evolve loop: checkpoint -> packet -> Codex -> build ->
  evaluate -> accept/reject/restore.
- `run_codex_exec.py`
  Thin wrapper for external `codex exec --json` with token/time logging.

## Compatibility / helper wrappers

- `run_codex_once.sh`
- `run_codex_loop.sh`
- `bootstrap.sh`

These still matter, but they are not the primary place to understand the
workflow. Prefer the Python entrypoints plus the evaluator.

## Typical order

1. `run_place_batch.sh`
2. `recommend_initial_family.py`
3. `checkpoint.py`
4. `materialize_family_variant.sh` if the recommended initial path is a family variant
5. `configure_openroad_variant.sh` if you need an isolated build/binary
6. `build_openroad_only.sh`
7. `run_canonical_line.sh`
8. `run_design_evolve_loop.py`
9. `compare_runs.py`

## Ignore

Do not treat `__pycache__/` as part of the workflow. It is local noise only.
