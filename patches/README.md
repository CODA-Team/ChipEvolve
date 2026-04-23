# Prepare Patches

This directory contains the prepare-time patches used to bootstrap a clean
workspace.

- `openroad_dpl_evolve_base.patch`
  Applies the clean `dpl_evolve` base and the `DPL_EVOLVE_SRC_DIR` build hook
  to a clean OpenROAD checkout.
- `orfs_overlay.patch`
  Applies the small ORFS-side overlay required by the agent bootstrap. For the
  current supported anchor, that overlay normalizes `.gitmodules` so
  `tools/OpenROAD` points at the real upstream OpenROAD repository.

The exact supported base commits are recorded in:

- `metadata/anchors.json`
