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
  Internal OpenROAD-only build helper used by `build_openroad_core.sh`. Do not
  use it as the normal per-variant path.
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
- `run_variant_experiment_matrix.py`
  Offline evidence-generation runner. It copies the clean `dpl_evolve` source
  into private variant directories, applies deterministic dpl_evolve-only
  algorithm mutations, relinks private OpenROAD binaries, evaluates many
  medium/large cases in parallel, and writes RunDB/KnowledgeDB evidence.
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

For offline knowledge generation before a new Codex evolve campaign, use:

```bash
ORFS_ROOT=/abs/path/to/OpenROAD-flow-scripts \
./scripts/run_variant_experiment_matrix.py
```

The default matrix intentionally avoids tiny-only evidence. It covers
`aes_nangate45`, `ibex_nangate45`, `jpeg_nangate45`, `ariane133_nangate45`,
and `bp_quad_nangate45`, with 8 parallel evaluator jobs and 10 OpenROAD threads
per job. Each evaluation has an explicit timeout so large-stress cases such as
`bp_quad_nangate45` become runtime evidence instead of blocking the whole
matrix. By default it runs all registered deterministic variants in the script.
Add `gcd_nangate45` manually only as a quick sanity case.

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
