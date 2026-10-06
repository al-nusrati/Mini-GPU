# =============================================================================
#  vivado/program_basys3.tcl  -  load the bitstream onto a connected Basys3
#  Run: vivado -mode batch -source vivado/program_basys3.tcl
# =============================================================================
set root [file normalize [file join [file dirname [info script]] ..]]
open_hw_manager
connect_hw_server
open_hw_target
set dev [lindex [get_hw_devices xc7a35t*] 0]
current_hw_device $dev
set_property PROGRAM.FILE $root/results/basys3_top.bit $dev
program_hw_devices $dev
puts "PROGRAMMED"
close_hw_manager
