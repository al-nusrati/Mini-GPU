# =============================================================================
#  sim/cocotb/Makefile  -  run: make            (default test: blink)
#                          make TEST=blink      (pick a test)
#  Needs Verilator 5 + cocotb (see README, WSL2 on Windows).
# =============================================================================
SIM            ?= verilator
TOPLEVEL_LANG   = verilog
TEST           ?= blink
RTL            := $(abspath ../../rtl)

ifeq ($(TEST),blink)
VERILOG_SOURCES     = $(RTL)/top/blink.sv
COCOTB_TOPLEVEL     = blink
COCOTB_TEST_MODULES = test_blink
EXTRA_ARGS         += -GTOGGLE_CYCLES=8
endif

# old (cocotb 1.x) names, kept so both versions work
TOPLEVEL = $(COCOTB_TOPLEVEL)
MODULE   = $(COCOTB_TEST_MODULES)

include $(shell cocotb-config --makefiles)/Makefile.sim
