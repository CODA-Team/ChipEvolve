# Prepare Patches

This directory contains the prepare-time patches used to bootstrap a clean
workspace.

Patch status is tracked in:

- `PATCH_AUDIT.yaml`

- `openroad_dpl_evolve_base.patch`
  Applies the clean `dpl_evolve` base, the minimal `ord` hooks needed to
  register the evolve command surface (`detailed_placement_evolve`,
  `improve_placement_evolve`, and `optimize_mirroring_evolve`; the legacy
  `optimize_evolve` alias may also exist in older prepared source), and the
  `DPL_EVOLVE_SRC_DIR` build hook to a clean OpenROAD checkout. It
  intentionally does not install a target-side `src/dpl_evolve/README.md`;
  use this control repo's README,
  `AGENTS.md`, and `knowledge/` as the documentation source of truth. During
  `prepare_workspace.sh`, this state is snapshotted as the `diamond`
  start-kind seed before the framework patch is applied.
- `openroad_dpl_evolve_framework.patch`
  Applies the constrained top-level `dpl_evolve` framework on top of the clean
  base. The primary evolved placement command remains `detailed_placement_evolve`; the patch
  introduces framework telemetry, the student-owned algorithm hook, a
  LEGALM-style guidance/legalization starting path, and Abacus-enabled
  negotiation repair as a downstream repair stage. Child agents implement
  case-specific behavior by modifying this private `dpl_evolve` source after
  the orchestrator has collected baseline evidence. During
  `prepare_workspace.sh`, this state is snapshotted as the `framework`
  start-kind seed.
- `orfs_make_overlay.patch`
  Applies the `flow/Makefile` runner hook needed by the control plane so the
  strict baseline wrappers can pass `RUN_OPENROAD_ARGS` and `RUN_SCRIPT_ARGS`
  through the shared ORFS `run` target.
- `orfs_overlay.patch`
  Applies the small ORFS-side overlay required by the agent bootstrap when the
  runner surface differs from the supported ORFS anchor. It is allowed to be
  empty for anchors where no ORFS-side injection is needed.

The exact supported base commits are recorded in:

- `metadata/anchors.json`
