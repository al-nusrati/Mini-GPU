// ============================================================================
//  File    : rtl/uart_tx.sv
//  Purpose : 8N1 UART transmitter with a valid/ready handshake.
//            A byte is taken when valid && ready are both 1 in the same cycle.
//  Pseudocode
//    IDLE : ready = 1; on valid, load {stop, data, start} into a shift register
//    BUSY : every CLKS_PER_BIT shift one bit out, LSB first, 10 bits total
// ============================================================================
module uart_tx #(
    parameter int CLKS_PER_BIT = 108
) (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       valid,
    input  logic [7:0] data,
    output logic       ready,
    output logic       tx
);
    /* verilator lint_off UNUSEDSIGNAL */
    logic [9:0] shreg;                         // bit 0 (start) is sent directly
    /* verilator lint_on UNUSEDSIGNAL */
    logic [3:0] bits_left;
    logic [$clog2(CLKS_PER_BIT)-1:0] cnt;

    assign ready = (bits_left == 4'd0);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            shreg <= '1;  bits_left <= '0;  cnt <= '0;  tx <= 1'b1;
        end else if (ready) begin
            tx <= 1'b1;
            if (valid) begin
                shreg     <= {1'b1, data, 1'b0};      // stop, data, start
                bits_left <= 4'd10;
                cnt       <= '0;
                tx        <= 1'b0;                    // start bit goes out now
            end
        end else begin
            if (cnt == ($bits(cnt))'(CLKS_PER_BIT - 1)) begin
                cnt       <= '0;
                shreg     <= {1'b1, shreg[9:1]};
                bits_left <= bits_left - 1'b1;
                tx        <= (bits_left == 4'd1) ? 1'b1 : shreg[1];
            end else cnt <= cnt + 1'b1;
        end
    end
endmodule
