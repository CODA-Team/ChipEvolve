export DESIGN_NICKNAME = ibex
export DESIGN_NAME = ibex_core
export PLATFORM    = nangate45

export VERILOG_FILES = $(sort $(wildcard $(DESIGN_HOME)/src/ibex_sv/*.sv)) \
    $(DESIGN_HOME)/src/ibex_sv/syn/rtl/prim_clock_gating.v

export VERILOG_INCLUDE_DIRS = \
    $(DESIGN_HOME)/src/ibex_sv/vendor/lowrisc_ip/prim/rtl/

export SYNTH_HDL_FRONTEND = slang

export SDC_FILE = ./designs/nangate45/ibex/constraint.sdc

export PLACE_DENSITY_LB_ADDON = 0.20
export TNS_END_PERCENT        = 100


# export EQUIVALENCE_CHECK       ?=   1
export EQUIVALENCE_CHECK       =   0
export REMOVE_CELLS_FOR_EQY     = TAPCELL*

export CORE_UTILIZATION = 50
export CELL_PAD_IN_SITES_GLOBAL_PLACEMENT = 0
export CELL_PAD_IN_SITES_DETAIL_PLACEMENT = 0
export ENABLE_DPO = 1