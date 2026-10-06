## =============================================================================
##  constraints/zynq7020.xdc  -  FILL THESE IN FROM YOUR ALINX BOARD MANUAL
##  Look for: "PL clock" (oscillator pin + frequency), "PL LED", "PL KEY".
##  Replace every XX with the real pin, check the I/O standard, uncomment.
## =============================================================================
# set_property -dict { PACKAGE_PIN XX IOSTANDARD LVCMOS33 } [get_ports clk]
# create_clock -name pl_clk -period 20.000 [get_ports clk]    ;# 20 ns = 50 MHz, must match CLK_HZ
# set_property -dict { PACKAGE_PIN XX IOSTANDARD LVCMOS33 } [get_ports rst_n]
# set_property -dict { PACKAGE_PIN XX IOSTANDARD LVCMOS33 } [get_ports {led[0]}]
# set_property -dict { PACKAGE_PIN XX IOSTANDARD LVCMOS33 } [get_ports {led[1]}]
