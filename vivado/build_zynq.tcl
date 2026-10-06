# =============================================================================
#  vivado/build_zynq.tcl  -  PL-only blink for the ALINX Zynq-7020
#  BEFORE RUNNING: check the exact part number in your board manual,
#  fill constraints/zynq7020.xdc, and set CLK_HZ below.
# =============================================================================
set root   [file normalize [file join [file dirname [info script]] ..]]
set part   xc7z020clg400-2      ;# TODO: confirm in the ALINX manual
set clk_hz 50000000             ;# TODO: your PL oscillator frequency
file mkdir $root/results

read_verilog -sv [list $root/rtl/top/blink.sv $root/rtl/top/zynq_top.sv]
read_xdc $root/constraints/zynq7020.xdc

synth_design -top zynq_top -part $part -generic CLK_HZ=$clk_hz
opt_design
place_design
route_design
report_utilization    -file $root/results/zynq_utilization.rpt
report_timing_summary -file $root/results/zynq_timing.rpt
write_bitstream -force $root/results/zynq_top.bit
puts "DONE: results/zynq_top.bit"
