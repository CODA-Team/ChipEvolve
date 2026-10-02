export PLATFORM               = asap7

export DESIGN_NAME            = aes_cipher_top
export DESIGN_NICKNAME        = aes

export VERILOG_FILES = $(sort $(wildcard $(DESIGN_HOME)/src/$(DESIGN_NICKNAME)/*.v))
export SDC_FILE = ./designs/asap7/aes/constraint.sdc

export ABC_AREA                 = 1

export CORE_UTILIZATION = 70
export CORE_ASPECT_RATIO        = 1
export CORE_MARGIN              = 2
export PLACE_DENSITY            = 0.65
export TNS_END_PERCENT          = 100
# export EQUIVALENCE_CHECK       ?=   1
export EQUIVALENCE_CHECK       =   0
export REMOVE_CELLS_FOR_EQY     = TAPCELL*

ifeq ($(FLOW_VARIANT),top)
	export DESIGN_NAME = aes_cipher_top
	export SYNTH_BLACKBOXES = aes_key_expand_128
else ifeq ($(FLOW_VARIANT),blackbox)
	export DESIGN_NAME = aes_key_expand_128
else ifeq ($(FLOW_VARIANT),combine)
	export EQUIVALENCE_CHECK = 0
# List blackbox twice to demonstrates that duplicate modules are ignored.
	export SYNTH_NETLIST_FILES = \
	 $(WORK_HOME)/results/$(PLATFORM)/$(DESIGN_NICKNAME)/top/1_synth.v \
	 $(WORK_HOME)/results/$(PLATFORM)/$(DESIGN_NICKNAME)/blackbox/1_synth.v \
	 $(WORK_HOME)/results/$(PLATFORM)/$(DESIGN_NICKNAME)/blackbox/1_synth.v
endif

export PLACE_DENSITY_LB_ADDON   = 0.1
export CTS_CLUSTER_SIZE = 20
export CTS_CLUSTER_DIAMETER = 100
export CELL_PAD_IN_SITES_GLOBAL_PLACEMENT = 0
export CELL_PAD_IN_SITES_DETAIL_PLACEMENT = 0
export SYNTH_FLATTEN = 1
export ENABLE_DPO = 1
export PIN_LAYER_ADJUST =0.5
export ABOVE_LAYER_ADJUST =0.5
export FASTROUTE_TCL = ./designs/$(PLATFORM)/$(DESIGN_NICKNAME)/fastasap_floorplan.tcl
# FASTROUTE_TCL records the floorplan-scoped adjustments in the ODB. The routing
# hook deliberately uses a separate script so post-CTS PIN/ABOVE mutations can be
# applied at global route without rewriting that earlier physical context.
export PRE_GLOBAL_ROUTE_TCL = ./designs/$(PLATFORM)/$(DESIGN_NICKNAME)/fastasap.tcl

# export MIN_ROUTING_LAYER = M2
# export MAX_ROUTING_LAYER = M9
