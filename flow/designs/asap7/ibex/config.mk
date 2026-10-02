export PLATFORM               = asap7

export DESIGN_NICKNAME        = ibex
export DESIGN_NAME            = ibex_core

export VERILOG_FILES = $(sort $(wildcard $(DESIGN_HOME)/src/ibex_sv/*.sv)) \
    $(DESIGN_HOME)/src/ibex_sv/syn/rtl/prim_clock_gating.v

export VERILOG_INCLUDE_DIRS = \
    $(DESIGN_HOME)/src/ibex_sv/vendor/lowrisc_ip/prim/rtl/

export SYNTH_HDL_FRONTEND = slang

# if FLOW_VARIANT == pos_slack, use an SDC file that has a larger clock
# resulting in positive slack
ifeq ($(FLOW_VARIANT),pos_slack)
export SDC_FILE = ./designs/asap7/ibex/constraint.sdc
else
export SDC_FILE = ./designs/asap7/ibex/constraint.sdc
endif

export EQUIVALENCE_CHECK=0
export REMOVE_CELLS_FOR_EQY     = TAPCELL*

export CORE_UTILIZATION = 70
export CELL_PAD_IN_SITES_GLOBAL_PLACEMENT = 0
export CELL_PAD_IN_SITES_DETAIL_PLACEMENT = 0
export ENABLE_DPO = 1
export PIN_LAYER_ADJUST =0.5
export ABOVE_LAYER_ADJUST =0.5
export PLACE_DENSITY_LB_ADDON = 0.1
export CTS_CLUSTER_SIZE = 20
export CTS_CLUSTER_DIAMETER = 100
export SYNTH_FLATTEN = 1
export TNS_END_PERCENT = 100

export FASTROUTE_TCL = ./designs/$(PLATFORM)/$(DESIGN_NICKNAME)/fastasap.tcl
# Re-apply layer adjustments at grt too (FASTROUTE_TCL runs at floorplan; DRP
# victims clone a checkpoint and never re-run floorplan -> their new routing
# params were dead). No-op for fresh runs; see aes/config.mk for details.
export PRE_GLOBAL_ROUTE_TCL = ./designs/$(PLATFORM)/$(DESIGN_NICKNAME)/fastasap.tcl