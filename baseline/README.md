# Baseline Sandbox

This folder is the first executable layer of the `dpl_evolve` research
sandbox. It is meant to answer two questions before we start mutating the
legalizer itself:

1. How do we compare legalization engines without mixing in unrelated flow
   optimizations?
2. How do we keep the comparison close enough to ORFS that the result still
   matters in the real flow?

## Project-facing model

At the project level, keep only these terms:

- canonical baseline lines
- the clean evolve line
- family variants
- strict legalization-only comparison

The canonical line list is:

- `canonical_lines.yaml`

If you are starting a new run, prefer:

- `../scripts/run_canonical_line.sh`
- `run_baseline_suite.sh`

Treat `run_baseline.sh` as the internal dispatcher behind those entrypoints.

## Tracks

### Strict legalizer track

The strict track now runs in two phases so every engine uses the same
post-legalization metrics path.

Phase A is legalization only. [`detail_place_only.tcl`](./detail_place_only.tcl)
or [`detail_place_dreamplace.tcl`](./detail_place_dreamplace.tcl) will:

- `set_placement_padding`
- legalize with either OpenROAD DPL, `dpl_evolve`, or DreamPlace
- write `legalized.odb`, `legalized.def`, and `legalized.sdc`
- dump before/after placement snapshots

Phase B is a uniform post-metrics reload.
[`report_legalized_metrics.tcl`](./report_legalized_metrics.tcl) will:

- reload `legalized.odb` and `legalized.sdc`
- source `setRC.tcl`
- run `check_placement`
- run `estimate_parasitics -placement`
- run ORFS `report_metrics`
- normalize the resulting `3_5_place_dp.json` into a placement-only
  `metadata.json`

It intentionally skips `improve_placement` and `optimize_mirroring`, so the
wirelength, timing, and power deltas are dominated by legalization itself.

### Reduced flow track

`run_baseline.sh --track flow` does not call the full ORFS `detail_place.tcl`.
Instead, it runs a smaller command-only flow that stays close to the ORFS
placement stage without pulling in extra behavior we do not need.

The flow track runs:

- `source_step_tcl PRE DETAIL_PLACE`
- `setRC.tcl`
- optional `balance_row_usage`
- `set_placement_padding` or `set_placement_padding_evolve`
- `detailed_placement` or `detailed_placement_evolve`
- optional `improve_placement` or `improve_placement_evolve`
- `optimize_mirroring` or `optimize_mirroring_evolve`

The classic baseline stays narrow:

- default DPL
- DreamPlace bridge plus Abacus

Everything else belongs to the clean evolve line or to a family variant built
on top of `dpl_evolve`.

`LEGALM` is variant-only. Use it with a LEGALM-capable binary that was built
from a materialized family source tree under
`$DPL_EVOLVE_AGENT_ROOT/family_variants/`.

Those entry points now live under [`flow/`](./flow/README.md).

## Folder map

The directory is organized by role rather than by baseline name:

- shell entry points:
  - `run_baseline.sh`
  - `run_baseline_suite.sh`
  - `run_evolve_line.sh`
  - `run_or_default.sh`
  - `run_dp_abacus.sh`
- Tcl drivers:
  - `detail_place_only.tcl`
  - `detail_place_only_evolve.tcl`
  - `detail_place_strict_core.tcl`
  - `detail_place_dreamplace.tcl`
  - `flow/detail_place_flow_classic.tcl`
  - `flow/detail_place_flow_evolve.tcl`
  - `flow/detail_place_flow_core.tcl`
  - `report_legalized_metrics.tcl`
  - `dump_placement_snapshot.tcl`
  - `export_dreamplace_input.tcl`
  - `import_legalized_coords.tcl`
  - `dpl_evolve_helpers.tcl`
- Python aggregation and adapters:
  - `collect_metrics.py`
  - `gen_orfs_metadata.py`
  - `run_dp_abacus_bridge.py`
  - `flow_paths.py`
- vendored external wrappers:
  - `dreamplace_vendor/`

## Quick start

Run from anywhere:

```bash
export FLOW_HOME=/absolute/path/to/OpenROAD-flow-scripts/flow

"$DPL_EVOLVE_AGENT_ROOT/scripts/run_canonical_line.sh" \
  --line baseline_default \
  --design-config ./designs/nangate45/gcd/config.mk
```

Run the full strict comparison bundle in one shot:

```bash
"$DPL_EVOLVE_AGENT_ROOT/baseline/run_baseline_suite.sh" \
  --design-config ./designs/nangate45/gcd/config.mk \
  --flow-variant smoke_suite \
  --threads 8
```

That bundle runs two fixed baselines plus one standalone evolve line. The
evolve line is intentionally isolated behind `run_evolve_line.sh`, so an agent
can modify the evolve Tcl or a family variant and then rerun just that line.

Switch to the reduced flow track:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/run_canonical_line.sh" \
  --line evolve_line \
  --design-config ./designs/asap7/aes/config.mk \
  --track flow
```

Run a LEGALM family variant:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant_relink.sh" \
  --variant-root "${DPL_EVOLVE_STATE_ROOT}/variants/legalm_engine" \
  --dpl-src /abs/path/to/legalm_engine/dpl_evolve
source "${DPL_EVOLVE_STATE_ROOT}/variants/legalm_engine/variant_env.sh"

"$DPL_EVOLVE_AGENT_ROOT/scripts/run_canonical_line.sh" \
  --line evolve_line \
  --family-variant legalm_engine \
  --openroad-binary "${OPENROAD_BINARY}" \
  --design-config ./designs/nangate45/gcd/config.mk \
  --track strict
```

Family-variant runs intentionally refuse to fall back to the root
`tools/install/OpenROAD/bin/openroad`. Use a dedicated variant binary every
time.

## Outputs

All baseline scripts now treat generated artifact paths as relative to
`FLOW_HOME`. The runner records those relative paths in manifests and summary
JSON, while the Tcl/Python helpers resolve them back to real filesystem paths
at execution time.

Each run writes into the normal ORFS result tree for the chosen
`FLOW_VARIANT`, plus a dedicated experiment subdirectory:

- `results/<platform>/<design>/<variant>/dpl_evolve_baseline/<run_tag>/`
- `reports/<platform>/<design>/<variant>/dpl_evolve_baseline/<run_tag>/`

The strict track emits:

- `before.tsv`
- `after.tsv`
- `legalized.odb`
- `legalized.def`
- `legalized.sdc`
- `legalize_summary.json`
- `post_metrics_summary.json`
- `3_5_place_dp.json`
- `metadata.json`
- `metrics.json`

The reduced flow track emits:

- snapshot TSVs before and after the reduced placement flow
- `legalized.odb`
- `legalized.def`
- `legalized.sdc`
- `legalize_summary.json`
- `post_metrics_summary.json`
- `metadata.json`
- `metrics.json`
- `3_5_place_dp.json`

## Which JSON to compare

Use `metrics.json` as the primary comparison file for every baseline run:

`flow/reports/<platform>/<design>/<flow_variant>/dpl_evolve_baseline/<run_tag>/metrics.json`

That file is the stable summary view. It already merges:

- run provenance from `run_manifest.json`
- HPWL proxy before/after
- displacement statistics from the TSV snapshots
- compact legalization summary
- compact detailed-place stage runtime summary
- ORFS `report_metrics` JSON
- placement-only normalized metadata derived from `3_5_place_dp.json`
- DreamPlace bridge status when applicable
- relative links to supporting raw files

After a baseline line finishes, the next control-plane step should be:

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/recommend_initial_family.py" \
  --metrics flow/reports/<platform>/<design>/<flow_variant>/dpl_evolve_baseline/<run_tag>/metrics.json
```

That turns the baseline result into a case classification and recommends the
current best initial evolve path.

### Fields to compare first

For all baselines, compare:

- `manifest.track`
- `hpwl_proxy.delta_micron`
- `displacement.average_displacement_micron`
- `displacement.max_displacement_micron`
- `timing_metrics.setup_ws`
- `timing_metrics.setup_tns`
- `timing_metrics.hold_ws`
- `timing_metrics.hold_tns`
- `timing_metrics.fmax`
- `power_metrics.total`
- `design_metrics.estimated_wirelength` when present
- `runtime_seconds`

For legality, also check:

- `legalization.status`
- `legality.placement_violations`

For DreamPlace runs, also check:

- `dreamplace_bridge.status`
- `dreamplace_bridge.greedy_legality_check_passed`
- `dreamplace_bridge.legality_check_passed`

### Supporting JSONs

Open these only when you need more detail:

- `supporting_files`: relative paths to the raw JSON/TSV files for this run
- `run_manifest.json`: exact run configuration and resolved output paths
- `legalize_summary.json`: legalization-stage summary before ODB reload
- `post_metrics_summary.json`: uniform post-metrics reload summary
- `metadata.json`: normalized placement-only metadata derived from
  `3_5_place_dp.json`
- `3_5_place_dp.json`: raw ORFS `report_metrics` JSON
- `dreamplace_manifest.json`: DreamPlace bridge health and legality checks
- `before_summary.json`: DreamPlace export summary
- `before_snapshot.json` / `after_snapshot.json`: flow-track snapshot summaries

### Example `jq`

```bash
jq '{
  track: .manifest.track,
  hpwl_delta_um: .hpwl_proxy.delta_micron,
  avg_disp_um: .displacement.average_displacement_micron,
  max_disp_um: .displacement.max_displacement_micron,
  setup_ws_ns: .timing_metrics.setup_ws,
  setup_tns_ns: .timing_metrics.setup_tns,
  hold_ws_ns: .timing_metrics.hold_ws,
  hold_tns_ns: .timing_metrics.hold_tns,
  fmax_hz: .timing_metrics.fmax,
  total_power: .power_metrics.total,
  est_wl: .design_metrics.estimated_wirelength,
  runtime_s: .runtime_seconds,
  status: .legalization.status,
  placement_violations: .legality.placement_violations,
  dp_legal: .dreamplace_bridge.legality_check_passed
}' metrics.json
```

## Files

- `run_baseline.sh`: shared runner for canonical baseline lines and the clean evolve line.
- `run_or_default.sh`: wrapper for the classic default baseline.
- `run_dp_abacus.sh`: wrapper for the DreamPlace Greedy+Abacus baseline.
- `detail_place_only.tcl`: strict classic default legalizer.
- `detail_place_only_evolve.tcl`: strict evolve default legalizer.
- `detail_place_only_evolve_nblg.tcl`: strict evolve negotiation legalizer.
- `detail_place_only_evolve_nblg_abacus.tcl`: strict evolve negotiation+Abacus legalizer.
- `detail_place_strict_core.tcl`: shared strict-track OpenROAD core.
- `detail_place_dreamplace.tcl`: strict DreamPlace export/import driver.
- `flow/detail_place_flow_classic.tcl`: reduced-flow classic default legalizer.
- `flow/detail_place_flow_evolve.tcl`: reduced-flow evolve default legalizer.
- `flow/detail_place_flow_evolve_nblg.tcl`: reduced-flow evolve negotiation legalizer.
- `flow/detail_place_flow_evolve_nblg_abacus.tcl`: reduced-flow evolve negotiation+Abacus legalizer.
- `flow/detail_place_flow_core.tcl`: shared reduced-flow legalizer core.
- `report_legalized_metrics.tcl`: uniform ODB reload + RC + parasitics +
  report-metrics stage.
- `dump_placement_snapshot.tcl`: standalone snapshot exporter.
- `import_legalized_coords.tcl`: coordinate re-import path for external
  comparators.
- `collect_metrics.py`: joins summaries, detailed-place metrics, metadata, and
  displacement stats.
- `gen_orfs_metadata.py`: normalizes `3_5_place_dp.json` into a stable
  placement-only `metadata.json`.
- `export_dreamplace_input.tcl`: exports the minimum node/core/region data that
  the DreamPlace Abacus bridge needs.
- `run_dp_abacus_bridge.py`: Python bridge that calls
  DREAMPlace `GreedyLegalize` followed by `AbacusLegalize`.
- `dreamplace_vendor/`: vendored lightweight DREAMPlace Python wrappers.
  The wrappers live in-tree; the compiled `*_cpp.so` operators are still reused
  from the external DREAMPlace build under `/opt/EDAs/DREAMPlace/build/dreamplace/ops/`.

## Script style

The baseline Tcl files now avoid custom `DPL_EVOLVE_*` environment variables.
`run_baseline.sh` generates a tiny per-run driver Tcl that stores a plain Tcl
`dict` of options, then sources the real baseline script.

The legalizer modes are split into explicit files instead of routing through
one large mode switch. Keep classic `dpl` on the default path. If you want an
evolve-side negotiation family, use `detail_place_only_evolve_nblg.tcl` or the
matching reduced-flow evolve Tcl.

## DreamPlace line

The DreamPlace baseline is now wired as a separate driver:

```bash
$DPL_EVOLVE_AGENT_ROOT/baseline/run_dp_abacus.sh \
  --design-config ./designs/nangate45/gcd/config.mk \
  --flow-variant smoke_dpl
```

This path exports an Abacus input JSON from the live ODB, runs the
DreamPlace legalizer in Python, and then imports the legalized coordinates
back into OpenDB.

The vendored wrappers now live under
`$DPL_EVOLVE_AGENT_ROOT/baseline/dreamplace_vendor/`, so the baseline
no longer depends on the external DREAMPlace Python package layout. The only
external pieces it still expects are the built DREAMPlace op shared objects
under `/opt/EDAs/DREAMPlace/build/dreamplace/ops/`.

The driver will automatically prefer a Python with `torch`, checking these
in order:

- `--dreamplace-python`
- `/opt/conda/miniforge3/envs/dreamplace/bin/python`
- `/home/zhiyuzheng/.conda/envs/xplace/bin/python`
- `python3`

If you already ran `conda activate dreamplace`, that also works.
