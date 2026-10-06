// ============================================================================
//  File    : rtl/top/zynq_top.sv
//  Purpose : Week 1 ALINX Zynq-7020 top level (PL only, no ARM yet).
//
//  IMPORTANT: set CLK_HZ to your board's PL oscillator frequency, and the
//  pins in constraints/zynq7020.xdc, from the ALINX board manual.
//  If your board has NO oscillator wired to the PL, use the Block Design
//  route instead (ZYNQ7 Processing System -> FCLK_CLK0 drives this module).
// ============================================================================
module zynq_top #(
    parameter int unsigned CLK_HZ = 50_000_000   // TODO: check board manual
) (
    input  logic       clk,
    input  logic       rst_n,    // a PL push button (check if active-low on your board)
    output logic [1:0] led
);
    blink #(.TOGGLE_CYCLES(CLK_HZ / 2)) u_slow (.clk(clk), .rst_n(rst_n), .led(led[0]));
    blink #(.TOGGLE_CYCLES(CLK_HZ / 8)) u_fast (.clk(clk), .rst_n(rst_n), .led(led[1]));
endmodule
