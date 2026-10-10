# Apply the post-CTS proposal to the inherited checkpoint at global routing.
set_global_routing_layer_adjustment metal2-metal3 $::env(PIN_LAYER_ADJUST)
set_global_routing_layer_adjustment metal4-$::env(MAX_ROUTING_LAYER) \
    $::env(ABOVE_LAYER_ADJUST)
set_routing_layers -clock $::env(MIN_CLK_ROUTING_LAYER)-$::env(MAX_ROUTING_LAYER)
set_routing_layers -signal $::env(MIN_ROUTING_LAYER)-$::env(MAX_ROUTING_LAYER)
puts "A2_LAYER_ADJUST scope=routing pin=$::env(PIN_LAYER_ADJUST) above=$::env(ABOVE_LAYER_ADJUST)"
