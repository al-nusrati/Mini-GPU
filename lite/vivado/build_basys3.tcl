# =============================================================================
#  vivado/build_basys3.tcl  -  full Basys3 bitstream (UART + GPU)
#  Run from the lite/ folder:
#     vivado -mode batch -source vivado/build_basys3.tcl
#  Output: results/basys3_top.bit + utilization / timing / power reports
# =============================================================================
set root [file normalize [file join [file dirname [info script]] ..]]
file mkdir $root/results

read_verilog -sv [glob $root/rtl/*.sv]
read_xdc $root/constraints/basys3.xdc
synth_design -top basys3_top -part xc7a35tcpg236-1
opt_design
place_design
route_design

report_utilization    -file $root/results/basys3_board_utilization.rpt
report_timing_summary -file $root/results/basys3_board_timing.rpt
report_power          -file $root/results/basys3_board_power.rpt
write_bitstream -force $root/results/basys3_top.bit
puts "DONE: results/basys3_top.bit"
