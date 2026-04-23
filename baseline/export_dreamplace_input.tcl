utl::set_metrics_stage "dpl_evolve__dreamplace_export__{}"

source $::env(SCRIPTS_DIR)/load.tcl
source [file join [file dirname [info script]] dpl_evolve_helpers.tcl]

set options [dpl_evolve_baseline::parse_options $argv [dict create \
  input-odb "3_4_place_resized.odb" \
  input-sdc "2_floorplan.sdc" \
  output-json [file join $::env(REPORTS_DIR) dpl_evolve_dreamplace_input.json]]]

set input_odb [dpl_evolve_baseline::option_value $options input-odb]
set input_sdc [dpl_evolve_baseline::option_value $options input-sdc]
set output_json [dpl_evolve_baseline::option_value $options output-json]

load_design $input_odb $input_sdc
dpl_evolve_baseline::write_dreamplace_input $output_json $input_odb $input_sdc
