## Out-of-context constraint for vivado/core_compare.tcl: only the clock matters
create_clock -name clk -period 10.000 [get_ports clk]
