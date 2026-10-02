export DESIGN_NICKNAME = jpeg
export DESIGN_NAME = jpeg_encoder
export PLATFORM    = nangate45

export VERILOG_FILES = $(sort $(wildcard $(DESIGN_HOME)/src/$(DESIGN_NICKNAME)/*.v))
export VERILOG_INCLUDE_DIRS = $(DESIGN_HOME)/src/$(DESIGN_NICKNAME)/include
export SDC_FILE = ./designs/nangate45/jpeg/constraint.sdc
export ABC_AREA = 1

export PLACE_DENSITY_LB_ADDON = 0.20
export TNS_END_PERCENT        = 100

export CORE_UTILIZATION = 50
# export EQUIVALENCE_CHECK       ?=   1
export EQUIVALENCE_CHECK       =   0
export REMOVE_CELLS_FOR_EQY     = TAPCELL*
export CELL_PAD_IN_SITES_GLOBAL_PLACEMENT = 0
export CELL_PAD_IN_SITES_DETAIL_PLACEMENT = 0
export ENABLE_DPO = 1