# Script Map

This file is the canonical map of the scripts that matter for the
`dpl_evolve_agent` control plane.

All runtime commands below assume:

- the real workspace root is an ORFS checkout
- this repo is located via `DPL_EVOLVE_AGENT_ROOT`
- packet/checkpoint/operation state is located via `DPL_EVOLVE_STATE_ROOT`
- `ORFS_ROOT` is explicit, or attached via `DPL_EVOLVE_AGENT_ROOT/.mounted_orfs`

It exists to keep agents and humans away from generated noise such as
checkpoint snapshots and emitted driver Tcl files.

## Read This First

Treat only the following directories as live script sources for the
`dpl_evolve` workflow:

- `$DPL_EVOLVE_AGENT_ROOT/scripts/`
- `$DPL_EVOLVE_AGENT_ROOT/baseline/`
- `$DPL_EVOLVE_AGENT_ROOT/adapters/science_codeevolve/`
- `$DPL_EVOLVE_AGENT_ROOT/skills/`
- `flow/scripts/`
- `flow/util/`
- `tools/OpenROAD/src/dpl_evolve/test/`

Do **not** treat the following as source-of-truth scripts:

- `${DPL_EVOLVE_STATE_ROOT}/checkpoints/operations/**/snapshot/**`
- `flow/objects/**`
- `flow/results/**`
- `flow/reports/**`
- `flow/logs/**`

Those locations contain generated Tcl drivers, copied snapshots, or run
artifacts. They are evidence, not authoring surfaces.

## Canonical Entry Scripts

These are the main entry points an agent should prefer.

### Repo / build

- `dev_env.sh`
  Shared dependency environment setup for local builds.

### control plane

- `$DPL_EVOLVE_AGENT_ROOT/scripts/run_place_batch.sh`
  Prepare reusable placement snapshots before code evolve.
- `$DPL_EVOLVE_AGENT_ROOT/scripts/attach_orfs_workspace.sh`
  Optional convenience helper that attaches an ignored local ORFS mount at
  `.mounted_orfs`.
- `$DPL_EVOLVE_AGENT_ROOT/scripts/run_canonical_line.sh`
  Agent-facing runner for one canonical baseline line or the clean evolve line.
- `$DPL_EVOLVE_AGENT_ROOT/scripts/checkpoint.py`
  Create / restore local edit-state checkpoints.
- `$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_only.sh`
  Fast incremental OpenROAD-only build for the root binary or fallback
  full-variant builds.
- `$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_core.sh`
  Choose the common-core seed location and emit `core_env.sh`.
- `$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_core.sh`
  Build the reusable common-core OpenROAD tree once for the current anchor.
- `$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant_relink.sh`
  Configure the preferred lightweight variant relink path against a shared
  common-core build.
- `$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_variant_relink.sh`
  Rebuild agent-owned `dpl_evolve` objects and relink a private `openroad`
  binary. When common-core `sta` exists, the variant install tree receives a
  symlink to that `sta`; it is not separately installed per variant.
- `$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant.sh`
  Heavier fallback path for a full variant-specific OpenROAD build/install.
- `$DPL_EVOLVE_AGENT_ROOT/scripts/materialize_family_variant.sh`
  Materialize a family-specific `dpl_evolve` source tree from the clean initial
  evolve base.
- `$DPL_EVOLVE_AGENT_ROOT/scripts/recommend_initial_family.py`
  Read baseline `metrics.json` and recommend the best initial patch family.
- `$DPL_EVOLVE_AGENT_ROOT/scripts/compare_runs.py`
  Compare two run results using the current multi-objective interpretation.
- `$DPL_EVOLVE_AGENT_ROOT/scripts/run_codex_exec.py`
  Run external `codex exec --json` and log token usage plus event traces.
- `$DPL_EVOLVE_AGENT_ROOT/scripts/run_design_evolve_loop.py`
  Full Python loop: checkpoint -> Codex -> build -> evaluate -> keep/reject.
- `$DPL_EVOLVE_AGENT_ROOT/scripts/run_codex_once.sh`
  Thin wrapper around packet generation + evaluator for one iteration.
- `$DPL_EVOLVE_AGENT_ROOT/scripts/run_codex_loop.sh`
  Loop helper that prepares checkpoint context before the Python flow.
- `$DPL_EVOLVE_AGENT_ROOT/scripts/bootstrap.sh`
  Bootstrap helper for early repo/control-plane setup.

## Current prompt surfaces

- `$DPL_EVOLVE_AGENT_ROOT/tasks/design_evolve/`
  Active per-design prompts for the Python/Codex loop.
- `$DPL_EVOLVE_AGENT_ROOT/tasks/archive/`
  Historical bootstrap and first-patch task sheets. Keep for provenance, not as
  the first place to start current design work.

### Baseline harness

- `$DPL_EVOLVE_AGENT_ROOT/baseline/canonical_lines.yaml`
  Canonical baseline/evolve line list.
- `$DPL_EVOLVE_AGENT_ROOT/baseline/run_baseline.sh`
  Internal baseline dispatcher.
- `$DPL_EVOLVE_AGENT_ROOT/baseline/run_baseline_suite.sh`
  Run the fixed suite of canonical baseline lines plus the clean evolve line.
- `$DPL_EVOLVE_AGENT_ROOT/baseline/run_evolve_line.sh`
  Run the standalone clean evolve line only.
- `$DPL_EVOLVE_AGENT_ROOT/baseline/run_or_default.sh`
  Wrapper for the `baseline_default` canonical line.
- `$DPL_EVOLVE_AGENT_ROOT/baseline/run_dp_abacus.sh`
  Wrapper for the `baseline_dreamplace_abacus` canonical line.

## Baseline Support Scripts

These are not top-level entry points, but they are active authored scripts.

### Tcl drivers

- `$DPL_EVOLVE_AGENT_ROOT/baseline/detail_place_only.tcl`
- `$DPL_EVOLVE_AGENT_ROOT/baseline/detail_place_only_evolve.tcl`
- `$DPL_EVOLVE_AGENT_ROOT/baseline/detail_place_only_evolve_nblg.tcl`
- `$DPL_EVOLVE_AGENT_ROOT/baseline/detail_place_only_evolve_nblg_abacus.tcl`
- `$DPL_EVOLVE_AGENT_ROOT/baseline/detail_place_only_evolve_legalm.tcl`
  Variant-only strict legalizer driver for a LEGALM-capable binary.
- `$DPL_EVOLVE_AGENT_ROOT/baseline/detail_place_dreamplace.tcl`
- `$DPL_EVOLVE_AGENT_ROOT/baseline/detail_place_strict_core.tcl`
- `$DPL_EVOLVE_AGENT_ROOT/baseline/dpl_evolve_helpers.tcl`
- `$DPL_EVOLVE_AGENT_ROOT/baseline/report_legalized_metrics.tcl`
- `$DPL_EVOLVE_AGENT_ROOT/baseline/dump_placement_snapshot.tcl`
- `$DPL_EVOLVE_AGENT_ROOT/baseline/export_dreamplace_input.tcl`
- `$DPL_EVOLVE_AGENT_ROOT/baseline/import_legalized_coords.tcl`

### Reduced-flow Tcl drivers

- `$DPL_EVOLVE_AGENT_ROOT/baseline/flow/detail_place_flow_core.tcl`
- `$DPL_EVOLVE_AGENT_ROOT/baseline/flow/detail_place_flow_classic.tcl`
- `$DPL_EVOLVE_AGENT_ROOT/baseline/flow/detail_place_flow_evolve.tcl`
- `$DPL_EVOLVE_AGENT_ROOT/baseline/flow/detail_place_flow_evolve_nblg.tcl`
- `$DPL_EVOLVE_AGENT_ROOT/baseline/flow/detail_place_flow_evolve_nblg_abacus.tcl`
- `$DPL_EVOLVE_AGENT_ROOT/baseline/flow/detail_place_flow_evolve_legalm.tcl`
  Variant-only reduced-flow driver for a LEGALM-capable binary.

### Baseline Python helpers

- `$DPL_EVOLVE_AGENT_ROOT/baseline/collect_metrics.py`
- `$DPL_EVOLVE_AGENT_ROOT/baseline/gen_orfs_metadata.py`
- `$DPL_EVOLVE_AGENT_ROOT/baseline/run_dp_abacus_bridge.py`
- `$DPL_EVOLVE_AGENT_ROOT/baseline/flow_paths.py`

## Runtime / Adapter Scripts

These are active authored control-plane modules.

- `$DPL_EVOLVE_AGENT_ROOT/adapters/science_codeevolve/evaluator.py`
- `$DPL_EVOLVE_AGENT_ROOT/adapters/science_codeevolve/kb_query.py`
- `$DPL_EVOLVE_AGENT_ROOT/adapters/science_codeevolve/guarded_exec.py`
- `$DPL_EVOLVE_AGENT_ROOT/adapters/science_codeevolve/lock.py`
- `$DPL_EVOLVE_AGENT_ROOT/adapters/science_codeevolve/archive.py`

## ORFS Flow Scripts

These belong to the upstream flow plane. They are real sources, but agents
should avoid editing them unless the task explicitly expands scope.

### Main stage drivers

- `flow/scripts/floorplan.tcl`
- `flow/scripts/io_placement.tcl`
- `flow/scripts/global_place.tcl`
- `flow/scripts/detail_place.tcl`
- `flow/scripts/cts.tcl`
- `flow/scripts/global_route.tcl`
- `flow/scripts/detail_route.tcl`
- `flow/scripts/final_report.tcl`

### Common utilities

- `flow/scripts/util.tcl`
- `flow/scripts/report_metrics.tcl`
- `flow/scripts/defaults.py`
- `flow/scripts/run_command.py`
- `flow/scripts/flow.sh`

### Utility helpers

- `flow/util/genMetrics.py`
- `flow/util/genRuleFile.py`
- `flow/util/checkMetadata.py`
- `flow/util/createGallery.py`
- `flow/util/makeIssue.sh`

## dpl_evolve Test Scripts

These are source tests, not generated artifacts. They are useful when the task
is specifically about validating the target plane.

Examples:

- `tools/OpenROAD/src/dpl_evolve/test/check1.tcl`
- `tools/OpenROAD/src/dpl_evolve/test/gcd.tcl`
- `tools/OpenROAD/src/dpl_evolve/test/aes.tcl`
- `tools/OpenROAD/src/dpl_evolve/test/ibex.tcl`

The full test directory contains many more Tcl/Python test scripts. Prefer the
smallest relevant smoke first.

## Current Workflow Order

If the goal is to evolve `dpl_evolve`, the intended order is:

1. `$DPL_EVOLVE_AGENT_ROOT/scripts/run_place_batch.sh`
2. `$DPL_EVOLVE_AGENT_ROOT/scripts/recommend_initial_family.py`
3. `$DPL_EVOLVE_AGENT_ROOT/scripts/checkpoint.py`
4. `$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_core.sh`
5. `$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_core.sh`
6. if the chosen initial path is a family variant, materialize it with
   `$DPL_EVOLVE_AGENT_ROOT/scripts/materialize_family_variant.sh`
7. if you need a private binary, configure relink with
   `$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant_relink.sh`
8. source the matching `<variant-root>/variant_env.sh`
9. build via `$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_variant_relink.sh`
10. evaluate via `$DPL_EVOLVE_AGENT_ROOT/scripts/run_canonical_line.sh` or
   `$DPL_EVOLVE_AGENT_ROOT/adapters/science_codeevolve/evaluator.py`
11. compare via `$DPL_EVOLVE_AGENT_ROOT/scripts/compare_runs.py`
12. only then expand to suites or other cases

## Context Hygiene Rules

When reading this repo, prefer:

- entry scripts over helpers
- helpers over generated drivers
- current authored sources over checkpoint snapshots

If a path lives under `checkpoints/operations/*/snapshot/` or `flow/objects/`,
assume it is a copy or an emitted artifact unless there is strong evidence
otherwise.
