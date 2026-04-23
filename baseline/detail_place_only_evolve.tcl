set legalizer_name "evolve"
set padding_cmd "set_placement_padding_evolve"
set place_cmd "detailed_placement_evolve"
set use_negotiation 0
set use_abacus 0

source [file join [file dirname [info script]] detail_place_strict_core.tcl]
