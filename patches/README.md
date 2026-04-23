# Prepare Patches

This directory contains the prepare-time patches used to bootstrap a clean
workspace.

- `openroad_dpl_evolve_base.patch`
  Applies the clean `dpl_evolve` base, the minimal `ord` hooks needed to
  register `detailed_placement_evolve`, and the `DPL_EVOLVE_SRC_DIR` build
  hook to a clean OpenROAD checkout.
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
