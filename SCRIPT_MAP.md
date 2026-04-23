# Script Map

This file is the canonical map of the scripts that matter in the current
`OpenROAD-flow-scripts` workspace.

It exists to keep agents and humans away from generated noise such as
checkpoint snapshots and emitted driver Tcl files.

## Read This First

Treat only the following directories as live script sources for the
`dpl_evolve` workflow:

- `evolve_agent/scripts/`
- `evolve_agent/baseline/`
- `evolve_agent/adapters/science_codeevolve/`
- `flow/scripts/`
- `flow/util/`
- `tools/OpenROAD/src/dpl_evolve/test/`

Do **not** treat the following as source-of-truth scripts:

- `evolve_agent/checkpoints/operations/**/snapshot/**`
- `flow/objects/**`
- `flow/results/**`
- `flow/reports/**`
- `flow/logs/**`

Those locations contain generated Tcl drivers, copied snapshots, or run
artifacts. They are evidence, not authoring surfaces.

## Canonical Entry Scripts

These are the main entry points an agent should prefer.

### Repo / build

- `build_openroad.sh`
  Full ORFS/OpenROAD local build.
- `dev_env.sh`
  Shared dependency environment setup for local builds.

### evolve_agent control plane

- `evolve_agent/scripts/run_place_batch.sh`
  Prepare reusable placement snapshots before code evolve.
- `evolve_agent/scripts/run_canonical_line.sh`
  Agent-facing runner for one canonical baseline line or the clean evolve line.
- `evolve_agent/scripts/checkpoint.py`
  Create / restore local edit-state checkpoints.
- `evolve_agent/scripts/build_openroad_only.sh`
  Fast incremental OpenROAD-only build for agent loops.
- `evolve_agent/scripts/configure_openroad_variant.sh`
  Configure an isolated OpenROAD build/install variant, optionally with an
  external `dpl_evolve` source directory.
- `evolve_agent/scripts/materialize_family_variant.sh`
  Materialize a family-specific `dpl_evolve` source tree from the clean initial
  evolve base.
- `evolve_agent/scripts/recommend_initial_family.py`
  Read baseline `metrics.json` and recommend the best initial patch family.
- `evolve_agent/scripts/compare_runs.py`
  Compare two run results using the current multi-objective interpretation.
- `evolve_agent/scripts/run_codex_exec.py`
  Run external `codex exec --json` and log token usage plus event traces.
- `evolve_agent/scripts/run_design_evolve_loop.py`
  Full Python loop: checkpoint -> Codex -> build -> evaluate -> keep/reject.
- `evolve_agent/scripts/run_codex_once.sh`
  Thin wrapper around packet generation + evaluator for one iteration.
- `evolve_agent/scripts/run_codex_loop.sh`
  Loop helper that prepares checkpoint context before the Python flow.
- `evolve_agent/scripts/bootstrap.sh`
  Bootstrap helper for early repo/control-plane setup.

## Current prompt surfaces

- `evolve_agent/tasks/design_evolve/`
  Active per-design prompts for the Python/Codex loop.
- `evolve_agent/tasks/archive/`
  Historical bootstrap and first-patch task sheets. Keep for provenance, not as
  the first place to start current design work.

### Baseline harness

- `evolve_agent/baseline/canonical_lines.yaml`
  Canonical baseline/evolve line list.
- `evolve_agent/baseline/run_baseline.sh`
  Internal baseline dispatcher.
- `evolve_agent/baseline/run_baseline_suite.sh`
  Run the fixed suite of canonical baseline lines plus the clean evolve line.
- `evolve_agent/baseline/run_evolve_line.sh`
  Run the standalone clean evolve line only.
- `evolve_agent/baseline/run_or_default.sh`
  Wrapper for the `baseline_default` canonical line.
- `evolve_agent/baseline/run_or_nblg.sh`
  Wrapper for the `baseline_nblg` canonical line.
- `evolve_agent/baseline/run_or_nblg_abacus.sh`
  Wrapper for the `baseline_nblg_abacus` canonical line.
- `evolve_agent/baseline/run_dp_abacus.sh`
  Wrapper for the `baseline_dreamplace_abacus` canonical line.

## Baseline Support Scripts

These are not top-level entry points, but they are active authored scripts.

### Tcl drivers

- `evolve_agent/baseline/detail_place_only.tcl`
- `evolve_agent/baseline/detail_place_only_nblg.tcl`
- `evolve_agent/baseline/detail_place_only_nblg_abacus.tcl`
- `evolve_agent/baseline/detail_place_only_evolve.tcl`
- `evolve_agent/baseline/detail_place_only_evolve_nblg.tcl`
- `evolve_agent/baseline/detail_place_only_evolve_nblg_abacus.tcl`
- `evolve_agent/baseline/detail_place_only_evolve_legalm.tcl`
  Variant-only strict legalizer driver for a LEGALM-capable binary.
- `evolve_agent/baseline/detail_place_dreamplace.tcl`
- `evolve_agent/baseline/detail_place_strict_core.tcl`
- `evolve_agent/baseline/dpl_evolve_helpers.tcl`
- `evolve_agent/baseline/report_legalized_metrics.tcl`
- `evolve_agent/baseline/dump_placement_snapshot.tcl`
- `evolve_agent/baseline/export_dreamplace_input.tcl`
- `evolve_agent/baseline/import_legalized_coords.tcl`

### Reduced-flow Tcl drivers

- `evolve_agent/baseline/flow/detail_place_flow_core.tcl`
- `evolve_agent/baseline/flow/detail_place_flow_classic.tcl`
- `evolve_agent/baseline/flow/detail_place_flow_classic_nblg.tcl`
- `evolve_agent/baseline/flow/detail_place_flow_classic_nblg_abacus.tcl`
- `evolve_agent/baseline/flow/detail_place_flow_evolve.tcl`
- `evolve_agent/baseline/flow/detail_place_flow_evolve_nblg.tcl`
- `evolve_agent/baseline/flow/detail_place_flow_evolve_nblg_abacus.tcl`
- `evolve_agent/baseline/flow/detail_place_flow_evolve_legalm.tcl`
  Variant-only reduced-flow driver for a LEGALM-capable binary.

### Baseline Python helpers

- `evolve_agent/baseline/collect_metrics.py`
- `evolve_agent/baseline/gen_orfs_metadata.py`
- `evolve_agent/baseline/run_dp_abacus_bridge.py`
- `evolve_agent/baseline/flow_paths.py`

## Runtime / Adapter Scripts

These are active authored control-plane modules.

- `evolve_agent/adapters/science_codeevolve/evaluator.py`
- `evolve_agent/adapters/science_codeevolve/kb_query.py`
- `evolve_agent/adapters/science_codeevolve/guarded_exec.py`
- `evolve_agent/adapters/science_codeevolve/lock.py`
- `evolve_agent/adapters/science_codeevolve/archive.py`

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

1. `evolve_agent/scripts/run_place_batch.sh`
2. `evolve_agent/scripts/recommend_initial_family.py`
3. `evolve_agent/scripts/checkpoint.py`
4. if the chosen initial path is a family variant, materialize it with
   `evolve_agent/scripts/materialize_family_variant.sh`
5. build via `evolve_agent/scripts/build_openroad_only.sh`
6. evaluate via `evolve_agent/scripts/run_canonical_line.sh` or
   `evolve_agent/adapters/science_codeevolve/evaluator.py`
7. compare via `evolve_agent/scripts/compare_runs.py`
8. only then expand to suites or other cases

## Context Hygiene Rules

When reading this repo, prefer:

- entry scripts over helpers
- helpers over generated drivers
- current authored sources over checkpoint snapshots

If a path lives under `checkpoints/operations/*/snapshot/` or `flow/objects/`,
assume it is a copy or an emitted artifact unless there is strong evidence
otherwise.
