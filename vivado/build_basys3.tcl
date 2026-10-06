# =============================================================================
#  vivado/build_basys3.tcl  -  non-project build, no GUI clicking needed
#  Run from repo root:   vivado -mode batch -source vivado/build_basys3.tcl
#  Output: results/basys3_top.bit + utilization and timing reports
# =============================================================================
set root [file normalize [file join [file dirname [info script]] ..]]
set part xc7a35tcpg236-1
file mkdir $root/results

read_verilog -sv [list \
    $root/rtl/pkg/gpu_pkg.sv \
    $root/rtl/top/blink.sv \
    $root/rtl/top/basys3_top.sv ]
read_xdc $root/constraints/basys3.xdc

synth_design -top basys3_top -part $part
opt_design
place_design
route_design

report_utilization    -file $root/results/basys3_utilization.rpt
report_timing_summary -file $root/results/basys3_timing.rpt
write_bitstream -force $root/results/basys3_top.bit
puts "DONE: results/basys3_top.bit"
