# Floorplan-time routing context is distinct from the final routing knobs. DRP may
# retune PIN/ABOVE after CTS, but those new values must not be applied retroactively
# while reproducing the physical state created at floorplan.
if {![info exists ::env(FLOORPLAN_PIN_LAYER_ADJUST)] ||
    $::env(FLOORPLAN_PIN_LAYER_ADJUST) == ""} {
    if {![info exists ::env(PIN_LAYER_ADJUST)] || $::env(PIN_LAYER_ADJUST) == ""} {
        set ::env(PIN_LAYER_ADJUST) 0.5
    }
    set ::env(FLOORPLAN_PIN_LAYER_ADJUST) $::env(PIN_LAYER_ADJUST)
}

if {![info exists ::env(FLOORPLAN_ABOVE_LAYER_ADJUST)] ||
    $::env(FLOORPLAN_ABOVE_LAYER_ADJUST) == ""} {
    if {![info exists ::env(ABOVE_LAYER_ADJUST)] || $::env(ABOVE_LAYER_ADJUST) == ""} {
        set ::env(ABOVE_LAYER_ADJUST) 0.5
    }
    set ::env(FLOORPLAN_ABOVE_LAYER_ADJUST) $::env(ABOVE_LAYER_ADJUST)
}

set_global_routing_layer_adjustment M2-M3 $::env(FLOORPLAN_PIN_LAYER_ADJUST)
set_global_routing_layer_adjustment M4-$::env(MAX_ROUTING_LAYER) \
    $::env(FLOORPLAN_ABOVE_LAYER_ADJUST)

set_routing_layers -signal $::env(MIN_ROUTING_LAYER)-$::env(MAX_ROUTING_LAYER)
set ::env(PL_ROUTING_ADJUSTMENT) 1.0
