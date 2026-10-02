# Third-party components and provenance

- `flow/Makefile`, `flow/scripts/`, `flow/util/`, `flow/test/`, and portions of the design configuration
  originate from OpenROAD-flow-scripts. The build/run script license supplied in
  the source installation is preserved as `licenses/ORFS_BUILD_RUN_SCRIPTS.txt`.
  These are the supplied local snapshots and may contain local changes; no exact
  upstream revision is asserted.
- AES, IBEX and JPEG RTL is retained under `flow/designs/src/`. Each component's existing
  license and notice files are preserved there and continue to apply.
- Platform libraries and OpenROAD/Yosys binaries are external dependencies. Obtain
  them from your existing ORFS installation and retain their original notices.
- The supplied QoR-comparator checkpoint and inference source are retained under
  `flow/predict_model/`; the checkpoint is not retrained by this packaging operation.
