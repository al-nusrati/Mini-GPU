// ============================================================================
//  File    : rtl/uart_rx.sv
//  Purpose : 8N1 UART receiver. One byte out per frame, as a 1-cycle pulse.
//  Pseudocode
//    sync the rx pin (2 flip-flops, avoids metastability)
//    IDLE : wait for falling edge (start bit)
//    START: wait half a bit, check line is still low
//    DATA : sample 8 bits, one every CLKS_PER_BIT, LSB first
//    STOP : wait one bit, then pulse valid
// ============================================================================
module uart_rx #(
    parameter int CLKS_PER_BIT = 108          // 100 MHz / 921600 baud
) (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       rx,
    output logic       valid,                 // 1-cycle pulse
    output logic [7:0] data
);
    typedef enum logic [1:0] {IDLE, START, DATA, STOP} state_t;
    state_t state;

    logic rx_s1, rx_s2;
    logic [$clog2(CLKS_PER_BIT)-1:0] cnt;
    logic [2:0] bit_idx;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rx_s1 <= 1'b1;  rx_s2 <= 1'b1;
        end else begin
            rx_s1 <= rx;    rx_s2 <= rx_s1;
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;  cnt <= '0;  bit_idx <= '0;  valid <= 1'b0;  data <= '0;
        end else begin
            valid <= 1'b0;
            case (state)
                IDLE: begin
                    cnt <= '0;  bit_idx <= '0;
                    if (!rx_s2) state <= START;
                end
                START: begin
                    if (cnt == ($bits(cnt))'(CLKS_PER_BIT / 2 - 1)) begin
                        cnt   <= '0;
                        state <= rx_s2 ? IDLE : DATA;      // glitch -> back to idle
                    end else cnt <= cnt + 1'b1;
                end
                DATA: begin
                    if (cnt == ($bits(cnt))'(CLKS_PER_BIT - 1)) begin
                        cnt           <= '0;
                        data[bit_idx] <= rx_s2;
                        if (bit_idx == 3'd7) state <= STOP;
                        bit_idx <= bit_idx + 1'b1;
                    end else cnt <= cnt + 1'b1;
                end
                STOP: begin
                    if (cnt == ($bits(cnt))'(CLKS_PER_BIT - 1)) begin
                        cnt   <= '0;
                        state <= IDLE;
                        valid <= rx_s2;                    // drop frame if stop bit bad
                    end else cnt <= cnt + 1'b1;
                end
                default: state <= IDLE;
            endcase
        end
    end
endmodule
