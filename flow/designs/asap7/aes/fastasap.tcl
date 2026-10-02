if {![info exists ::env(PIN_LAYER_ADJUST)] || $::env(PIN_LAYER_ADJUST) == ""} {
    set ::env(PIN_LAYER_ADJUST) 0.5
}

if {![info exists ::env(ABOVE_LAYER_ADJUST)] || $::env(ABOVE_LAYER_ADJUST) == ""} {
    set ::env(ABOVE_LAYER_ADJUST) 0.5
}

set_global_routing_layer_adjustment M2-M3 $::env(PIN_LAYER_ADJUST)
set_global_routing_layer_adjustment M4-$::env(MAX_ROUTING_LAYER) $::env(ABOVE_LAYER_ADJUST)

set_routing_layers -signal $::env(MIN_ROUTING_LAYER)-$::env(MAX_ROUTING_LAYER)
set ::env(PL_ROUTING_ADJUSTMENT) 1.0
