// ============================================================================
//  File    : rtl/top/basys3_top.sv
//  Purpose : Week 1 Basys3 top level.
//              LED0      : toggles every 0.5 s       (clock + reset work)
//              LED1      : 4x faster                 (second instance)
//              LED15..12 : show SPEC_VERSION         (generated package is in the build)
//              btnC      : reset while held
//  Later weeks replace the body with gpu_top + uart + vga.
// ============================================================================
module basys3_top
    import gpu_pkg::*;
(
    input  logic        clk,     // 100 MHz, pin W5
    input  logic        btnC,    // center button = reset
    output logic [15:0] led
);
    logic rst_n;
    assign rst_n = ~btnC;

    blink #(.TOGGLE_CYCLES(BASYS3_CLK_MHZ * 500_000)) u_slow (.clk(clk), .rst_n(rst_n), .led(led[0]));
    blink #(.TOGGLE_CYCLES(BASYS3_CLK_MHZ * 125_000)) u_fast (.clk(clk), .rst_n(rst_n), .led(led[1]));

    assign led[11:2]  = '0;
    assign led[15:12] = 4'(SPEC_VERSION);
endmodule
