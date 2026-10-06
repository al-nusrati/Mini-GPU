// ============================================================================
//  File    : rtl/top/blink.sv
//  Purpose : Week 1 "hello hardware". A counter that toggles a signal every
//            TOGGLE_CYCLES clocks. Proves: toolchain works, clock + reset +
//            pins are right, and simulation matches the board.
//
//  Pseudocode
//    on every clock:
//      if reset            : count = 0, led = 0
//      else if count == N-1: count = 0, led = ~led
//      else                : count = count + 1
// ============================================================================
module blink #(
    parameter int unsigned TOGGLE_CYCLES = 50_000_000   // 0.5 s at 100 MHz
) (
    input  logic clk,
    input  logic rst_n,      // active-low reset
    output logic led
);
    localparam int CW = (TOGGLE_CYCLES > 1) ? $clog2(TOGGLE_CYCLES) : 1;
    logic [CW-1:0] count;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count <= '0;
            led   <= 1'b0;
        end else if (count == CW'(TOGGLE_CYCLES - 1)) begin
            count <= '0;
            led   <= ~led;
        end else begin
            count <= count + 1'b1;
        end
    end
endmodule
