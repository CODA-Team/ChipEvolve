# Prepare Patches

This directory contains the prepare-time patches used to bootstrap a clean
workspace.

Patch status is tracked in:

- `PATCH_AUDIT.yaml`

- `openroad_dpl_evolve_base.patch`
  Applies the clean `dpl_evolve` base, the minimal `ord` hooks needed to
  register `detailed_placement_evolve`, and the `DPL_EVOLVE_SRC_DIR` build
  hook to a clean OpenROAD checkout.
- `openroad_dpl_evolve_framework.patch`
  Applies the constrained top-level `dpl_evolve` framework on top of the clean
  base. The command entrypoint remains `detailed_placement_evolve`; the patch
  introduces framework stage skeletons, telemetry, and the V1 plugin loader
  (`DPL_EVOLVE_PLUGIN_SO` / `EvolvePluginApi.h`) while default behavior stays
  diamond-compatible unless negotiation is explicitly requested.
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
