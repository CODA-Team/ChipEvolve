utl::set_metrics_stage "dpl_evolve__import_coords__{}"

source $::env(SCRIPTS_DIR)/load.tcl
source [file join [file dirname [info script]] dpl_evolve_helpers.tcl]

set options [dpl_evolve_baseline::parse_options $argv [dict create \
  input-odb "3_4_place_resized.odb" \
  input-sdc "2_floorplan.sdc" \
  coords-tsv "" \
  output-odb [file join $::env(RESULTS_DIR) dpl_evolve_import legalized.odb] \
  output-def [file join $::env(RESULTS_DIR) dpl_evolve_import legalized.def] \
  output-sdc [file join $::env(RESULTS_DIR) dpl_evolve_import legalized.sdc] \
  after-snapshot [file join $::env(REPORTS_DIR) dpl_evolve_import_after.tsv] \
  summary-json [file join $::env(REPORTS_DIR) legalize_summary.json] \
  track "strict" \
  legalizer "external" \
  bridge-manifest "" \
  import-orient "0"]]

set input_odb [dpl_evolve_baseline::option_value $options input-odb]
set input_sdc [dpl_evolve_baseline::option_value $options input-sdc]
set coords_tsv [dpl_evolve_baseline::option_value $options coords-tsv]
set output_odb [dpl_evolve_baseline::option_value $options output-odb]
set output_def [dpl_evolve_baseline::option_value $options output-def]
set output_sdc [dpl_evolve_baseline::option_value $options output-sdc]
set after_snapshot [dpl_evolve_baseline::option_value $options after-snapshot]
set summary_json [dpl_evolve_baseline::option_value $options summary-json]
set track [dpl_evolve_baseline::option_value $options track]
set legalizer [dpl_evolve_baseline::option_value $options legalizer]
set bridge_manifest [dpl_evolve_baseline::option_value $options bridge-manifest]
set import_orient [dpl_evolve_baseline::bool_value [dpl_evolve_baseline::option_value $options import-orient]]

if { $coords_tsv eq "" } {
  error "--coords-tsv is required."
}

load_design $input_odb $input_sdc
source_step_tcl PRE DETAIL_PLACE

dpl_evolve_baseline::apply_snapshot_rows $coords_tsv $import_orient
dpl_evolve_baseline::dump_instance_snapshot $after_snapshot

set summary [dict create \
  status "ok" \
  track $track \
  legalizer_mode $legalizer \
  input_odb $input_odb \
  input_sdc $input_sdc \
  coords_tsv $coords_tsv \
  output_odb $output_odb \
  output_def $output_def \
  output_sdc $output_sdc \
  snapshot_tsv $after_snapshot \
  hpwl_after_dbu [dpl_evolve_baseline::compute_hpwl_proxy] \
  dbu_per_micron [dpl_evolve_baseline::get_dbu_per_micron]]

if { $bridge_manifest ne "" } {
  dict set summary bridge_manifest $bridge_manifest
}

log_cmd write_db [dpl_evolve_baseline::resolve_flow_path $output_odb]
log_cmd write_def [dpl_evolve_baseline::resolve_flow_path $output_def]
log_cmd write_sdc -no_timestamp [dpl_evolve_baseline::resolve_flow_path $output_sdc]

foreach {key value} [dpl_evolve_baseline::snapshot_stats] {
  dict set summary $key $value
}

dpl_evolve_baseline::write_summary_json $summary_json $summary
source_step_tcl POST DETAIL_PLACE
