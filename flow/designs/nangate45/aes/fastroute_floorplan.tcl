# These values belong to the placement checkpoint and are not retuned after CTS.
set_global_routing_layer_adjustment metal2-metal3 $::env(FLOORPLAN_PIN_LAYER_ADJUST)
set_global_routing_layer_adjustment metal4-$::env(MAX_ROUTING_LAYER) \
    $::env(FLOORPLAN_ABOVE_LAYER_ADJUST)
set_routing_layers -clock $::env(MIN_CLK_ROUTING_LAYER)-$::env(MAX_ROUTING_LAYER)
set_routing_layers -signal $::env(MIN_ROUTING_LAYER)-$::env(MAX_ROUTING_LAYER)
puts "A2_LAYER_ADJUST scope=floorplan pin=$::env(FLOORPLAN_PIN_LAYER_ADJUST) above=$::env(FLOORPLAN_ABOVE_LAYER_ADJUST)"
