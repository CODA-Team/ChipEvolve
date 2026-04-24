# Scripts

This directory contains the top-level executable helpers for `dpl_evolve_agent`.

These files are the preferred human/agent entrypoints. If a task can be solved
through a script here, prefer it over rebuilding the workflow from scratch.

Runtime is resolved through:

- `DPL_EVOLVE_AGENT_ROOT`
- `ORFS_ROOT`
- `DPL_EVOLVE_STATE_ROOT`

If you do not want to export `ORFS_ROOT` manually, attach a local ignored mount
first:

- `attach_orfs_workspace.sh`

## Main entrypoints

- `run_canonical_line.sh`
  Run one canonical baseline line or the clean evolve line.
- `run_place_batch.sh`
  Prepare reusable placement snapshots before code evolve starts.
- `checkpoint.py`
  Create, restore, inspect, and list local edit-state checkpoints.
- `build_openroad_only.sh`
  Fast incremental build of the currently configured OpenROAD tree. The first
  OpenROAD-only configure disables OpenROAD tests by default. By default it
  publishes only the needed binaries (`openroad` and, when built, `sta`) instead
  of running a full `cmake --install`.
- `configure_openroad_core.sh`
  Choose the common-core seed location and write `<core-root>/core_env.sh`.
- `build_openroad_core.sh`
  Build the reusable common-core OpenROAD tree once for the current anchor.
- `configure_openroad_variant_relink.sh`
  Point one agent-owned variant at the shared common core and emit
  `<variant-root>/variant_env.sh` for the lightweight relink path.
- `build_openroad_variant_relink.sh`
  Recompile only the variant-owned `dpl_evolve` pieces and relink a private
  `openroad` binary.
- `configure_openroad_variant.sh`
  Configure an isolated OpenROAD build/install variant, optionally with an
  external `dpl_evolve` source tree and a reusable common-core seed. It also
  writes `<variant-root>/variant_env.sh`.
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
5. `configure_openroad_core.sh`
6. `build_openroad_core.sh`
7. `configure_openroad_variant_relink.sh` if you need a private variant binary
8. `source <variant-root>/variant_env.sh`
9. `build_openroad_variant_relink.sh`
10. `run_canonical_line.sh`
11. `run_design_evolve_loop.py`
12. `compare_runs.py`

## Fallback build path

When relink is not enough, the older fallback path is still:

1. `configure_openroad_variant.sh`
2. `source <variant-root>/variant_env.sh`
3. `build_openroad_only.sh`

That path is heavier because it keeps a full variant-specific OpenROAD build
tree.

## Binary-selection rule

- Clean `baseline_default`, `baseline_dreamplace_abacus`, and clean `evolve_line`
  may use the root binary.
- Any run with `--family-variant` must pass an explicit variant binary:
  - either `--openroad-binary /abs/path/to/openroad`
  - or `source <variant-root>/variant_env.sh` before running the wrapper
- Prefer both for agent loops:
  - source `variant_env.sh`
  - still pass `--openroad-binary "${OPENROAD_BINARY}"`

## Ignore

Do not treat `__pycache__/` as part of the workflow. It is local noise only.
