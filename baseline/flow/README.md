# Flow Tcl Drivers

This folder holds the `--track flow` Tcl entry points used by
`baseline/run_baseline.sh`.

These scripts do not run the full ORFS detailed-placement stage. They only run
the commands we want in the `dpl_evolve` sandbox:

- `source_step_tcl PRE DETAIL_PLACE`
- `setRC.tcl`
- optional `balance_row_usage`
- placement padding
- detailed placement
- optional `improve_placement`
- `optimize_mirroring`
- write `legalized.odb/.def/.sdc`

The files are split by command set and engine so each mode stays explicit:

- `detail_place_flow_classic.tcl`
- `detail_place_flow_evolve.tcl`
- `detail_place_flow_evolve_nblg.tcl`
- `detail_place_flow_evolve_nblg_abacus.tcl`
- `detail_place_flow_evolve_legalm.tcl`

Shared implementation lives in `detail_place_flow_core.tcl`.
