set legalizer_name "flow_evolve_legalm"
set padding_cmd "set_placement_padding_evolve"
set place_cmd "detailed_placement_evolve"
set improve_cmd "improve_placement_evolve"
set mirror_cmd "optimize_mirroring_evolve"
set check_cmd "check_placement_evolve"
set use_negotiation 0
set use_legalm 1
set use_abacus 0

source [file join [file dirname [info script]] detail_place_flow_core.tcl]
