export PLATFORM               = asap7

export DESIGN_NAME            = jpeg_encoder
export DESIGN_NICKNAME        = jpeg

export VERILOG_FILES          = $(sort $(wildcard $(DESIGN_HOME)/src/$(DESIGN_NICKNAME)/*.v))
export VERILOG_INCLUDE_DIRS   = $(DESIGN_HOME)/src/$(DESIGN_NICKNAME)/include
export SDC_FILE               = $(DESIGN_HOME)/$(PLATFORM)/$(DESIGN_NICKNAME)/jpeg_encoder15_7nm.sdc
export ABC_AREA               = 1

export CORE_ASPECT_RATIO      = 1
export CORE_MARGIN            = 2
export PLACE_DENSITY          = 0.75
export DETAILED_ROUTE_END_ITERATION = 5
# export EQUIVALENCE_CHECK     ?=   1

export EQUIVALENCE_CHECK=0
export REMOVE_CELLS_FOR_EQY     = TAPCELL*

export CORE_UTILIZATION         = 70
export CELL_PAD_IN_SITES_GLOBAL_PLACEMENT = 0
export CELL_PAD_IN_SITES_DETAIL_PLACEMENT = 0
export ENABLE_DPO = 1
export PIN_LAYER_ADJUST = 0.5
export ABOVE_LAYER_ADJUST = 0.5
export PLACE_DENSITY_LB_ADDON = 0.1
export CTS_CLUSTER_SIZE = 20
export CTS_CLUSTER_DIAMETER = 100
export SYNTH_FLATTEN = 1
export TNS_END_PERCENT = 100
export FASTROUTE_TCL = ./designs/$(PLATFORM)/$(DESIGN_NICKNAME)/fastasap.tcl
export PRE_GLOBAL_ROUTE_TCL = ./designs/$(PLATFORM)/$(DESIGN_NICKNAME)/fastasap.tcl