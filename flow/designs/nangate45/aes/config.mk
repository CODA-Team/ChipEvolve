export DESIGN_NICKNAME = aes
export DESIGN_NAME = aes_cipher_top
export PLATFORM    = nangate45

export VERILOG_FILES = $(sort $(wildcard $(DESIGN_HOME)/src/$(DESIGN_NICKNAME)/*.v))
export SDC_FILE = ./designs/nangate45/aes/constraint.sdc

# export FLOORPLAN_DEF = $(DESIGN_HOME)/$(PLATFORM)/$(DESIGN_NICKNAME)/aes_ng45_fp.def

export PLACE_DENSITY_LB_ADDON = 0.20
export TNS_END_PERCENT        = 100
export REMOVE_CELLS_FOR_EQY   = TAPCELL*

# workaround for high congestion in post-grt repair
export SKIP_INCREMENTAL_REPAIR = 1

export CORE_UTILIZATION = 50
# export EQUIVALENCE_CHECK       ?=   1
export EQUIVALENCE_CHECK       =   0
export REMOVE_CELLS_FOR_EQY     = TAPCELL*
export CELL_PAD_IN_SITES_GLOBAL_PLACEMENT = 0
export CELL_PAD_IN_SITES_DETAIL_PLACEMENT = 0
export ENABLE_DPO = 1