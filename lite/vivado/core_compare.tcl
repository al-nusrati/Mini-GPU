# =============================================================================
#  vivado/core_compare.tcl  -  THE comparison experiment
#  Implements the SAME gpu_core on both chips, out of context (no board pins),
#  at 100 MHz, and writes resource / timing / power reports for each.
#  Works even without the Zynq board connected.
#     vivado -mode batch -source vivado/core_compare.tcl
#  Then: python pc/collect_vivado.py   (makes results/fpga_compare.csv)
# =============================================================================
set root [file normalize [file join [file dirname [info script]] ..]]
file mkdir $root/results

# name  part                 (check the Zynq part in your ALINX manual)
set targets {
    basys3  xc7a35tcpg236-1
    zynq    xc7z020clg400-2
}

foreach {name part} $targets {
    puts "===== $name ($part) ====="
    close_project -quiet
    create_project -in_memory -part $part
    read_verilog -sv [list $root/rtl/sdp_ram.sv $root/rtl/rasterizer.sv \
                           $root/rtl/depth_unit.sv $root/rtl/gpu_core.sv]
    read_xdc -mode out_of_context $root/constraints/core_ooc.xdc
    synth_design -top gpu_core -part $part -mode out_of_context
    opt_design
    place_design
    route_design
    report_utilization    -file $root/results/${name}_core_utilization.rpt
    report_timing_summary -file $root/results/${name}_core_timing.rpt
    report_power          -file $root/results/${name}_core_power.rpt
}
puts "DONE: results/*_core_*.rpt"
