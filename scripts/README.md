# Scripts

This directory contains the top-level executable helpers for `dpl_evolve_agent`.

These files are the preferred human/agent entrypoints. If a task can be solved
through a script here, prefer it over rebuilding the workflow from scratch.

Runtime is resolved through the local control-repo setup:

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
  Wrapper around `materialize_family_variant.py`. Copy the clean initial evolve
  base and materialize a family source tree from a sidecar patch, generated
  matrix variant, or explicit bring-up alias.
- `materialize_family_variant.py`
  Importable materializer API plus CLI. Use `--list-families` before assigning
  a family to an agent.
- `family_mutations.py`
  Shared family mutation registry. Planned R6/netaware14/priority/localized
  names are registered as `bringup_alias_not_algorithm_promotion` until their
  real mutation bodies replace the aliases.
- `run_family_base_gate.py`
  Base bring-up harness. It materializes one family, relinks a private binary,
  runs requested strict gates, and writes `build.json`, per-case JSON, and
  `PROMOTION_DECISION.md`.
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
8. `build_openroad_variant_relink.sh --variant-root <variant-root> --dpl-src <variant-src>`
9. `run_canonical_line.sh`
10. `run_design_evolve_loop.py`
11. `compare_runs.py`

For base-family bring-up, use the gate harness instead of ad-hoc ORFS edits:

```bash
ORFS_ROOT=/abs/path/to/OpenROAD-flow-scripts \
./scripts/run_family_base_gate.py \
  --family negotiation_row_bucket_quality_frontier_r6_twopass \
  --case-set default \
  --legalizer-only-first \
  --eval-timeout-sec 900 \
  --force
```

The first R6/netaware14/priority/localized registrations are intentionally
bring-up aliases. They prove source/build/eval plumbing, not algorithm
promotion.

## Anchor Versus Prepared State

`metadata/anchors.json` records the upstream pre-patch ORFS/OpenROAD commits.
After `prepare_workspace.sh`, `tools/OpenROAD` is expected to be checked out at
a local prepared commit that contains `src/dpl_evolve`.  Do not reset
`tools/OpenROAD` back to the upstream anchor immediately before materializing
families; the clean anchor does not contain the evolvable source tree.

The common-core registry lives under the agent state root, normally:

```text
dpl_evolve_agent/.dpl_evolve_state/openroad_core/<prepared-openroad-sha>/
```

For offline knowledge generation before a new Codex evolve campaign, use:

```bash
ORFS_ROOT=/abs/path/to/OpenROAD-flow-scripts \
./scripts/run_variant_experiment_matrix.py
```

The default matrix reads case ids from `problems/case_sets.json` and then
resolves each case through `problems/<case>/problem.yaml`. Use `--case <id>`
for a single-case debug run and `--case-set <name>` for normal batches. It intentionally
avoids tiny-only evidence, uses 8 parallel evaluator jobs, and gives each
OpenROAD invocation 10 threads. Each evaluation has an explicit timeout so
large-stress cases become runtime evidence instead of blocking the whole
matrix. By default it runs all registered deterministic variants in the script.

## Binary-selection rule

- Clean `openroad_dpl_negotiation`, `dreamplace_default`, and clean `evolve_default`
  may use the root binary.
- Any family or variant run must pass an explicit variant binary:
  - `--openroad-binary /abs/path/to/openroad`
- `variant_env.sh` is an output manifest for humans to inspect, not the normal
  way to select binaries in automated runs. Pass the binary path explicitly.

## Ignore

Do not treat `__pycache__/` as part of the workflow. It is local noise only.
