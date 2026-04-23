utl::set_metrics_stage "dpl_evolve__snapshot__{}"

source $::env(SCRIPTS_DIR)/load.tcl
source [file join [file dirname [info script]] dpl_evolve_helpers.tcl]

set options [dpl_evolve_baseline::parse_options $argv [dict create \
  input-odb "3_4_place_resized.odb" \
  input-sdc "2_floorplan.sdc" \
  snapshot-tsv [file join $::env(REPORTS_DIR) dpl_evolve_snapshot.tsv] \
  summary-json [file join $::env(REPORTS_DIR) dpl_evolve_snapshot.json]]]

set input_odb [dpl_evolve_baseline::option_value $options input-odb]
set input_sdc [dpl_evolve_baseline::option_value $options input-sdc]
set snapshot_tsv [dpl_evolve_baseline::option_value $options snapshot-tsv]
set summary_json [dpl_evolve_baseline::option_value $options summary-json]

load_design $input_odb $input_sdc

set summary [dict create \
  status "ok" \
  input_odb $input_odb \
  input_sdc $input_sdc \
  snapshot_tsv $snapshot_tsv \
  dbu_per_micron [dpl_evolve_baseline::get_dbu_per_micron] \
  hpwl_proxy_dbu [dpl_evolve_baseline::compute_hpwl_proxy]]

dpl_evolve_baseline::dump_instance_snapshot $snapshot_tsv
foreach {key value} [dpl_evolve_baseline::snapshot_stats] {
  dict set summary $key $value
}
dpl_evolve_baseline::write_summary_json $summary_json $summary
