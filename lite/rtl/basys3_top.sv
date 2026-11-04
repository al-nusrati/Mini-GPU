// ============================================================================
//  File    : rtl/basys3_top.sv
//  Purpose : Basys3 board wrapper:  USB-UART  <->  gpu_core
//  LEDs    : 0 heartbeat, 1 GPU busy, 2 triangle overflow,
//            3 byte dropped (host sent while GPU busy), 15..8 triangle count
//  Reset   : hold the center button
// ============================================================================
module basys3_top #(
    parameter int CLKS_PER_BIT = 108        // 100 MHz / 921600 baud
) (
    input  logic        clk,                // 100 MHz
    input  logic        btnC,
    input  logic        RsRx,
    output logic        RsTx,
    output logic [15:0] led
);
    logic rst_n;
    logic [1:0] rst_sync;
    always_ff @(posedge clk) rst_sync <= {rst_sync[0], ~btnC};
    assign rst_n = rst_sync[1];

    logic       rx_valid, in_ready, out_valid, out_ready, busy, overflow;
    logic [7:0] rx_data, out_data;
    logic [10:0] tri_count;
    logic       dropped;

    uart_rx #(.CLKS_PER_BIT(CLKS_PER_BIT)) u_rx (
        .clk(clk), .rst_n(rst_n), .rx(RsRx), .valid(rx_valid), .data(rx_data));

    gpu_core #(.W(160), .H(120), .MAX_TRIS(1024)) u_gpu (
        .clk(clk), .rst_n(rst_n),
        .in_valid(rx_valid), .in_data(rx_data), .in_ready(in_ready),
        .out_valid(out_valid), .out_data(out_data), .out_ready(out_ready),
        .busy(busy), .overflow(overflow), .tri_count(tri_count));

    uart_tx #(.CLKS_PER_BIT(CLKS_PER_BIT)) u_tx (
        .clk(clk), .rst_n(rst_n), .valid(out_valid), .data(out_data),
        .ready(out_ready), .tx(RsTx));

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)                     dropped <= 1'b0;
        else if (rx_valid && !in_ready) dropped <= 1'b1;
    end

    logic [26:0] hb;
    always_ff @(posedge clk) hb <= hb + 1'b1;

    assign led[0]    = hb[26];
    assign led[1]    = busy;
    assign led[2]    = overflow;
    assign led[3]    = dropped;
    assign led[7:4]  = '0;
    assign led[15:8] = (tri_count > 11'd255) ? 8'hFF : tri_count[7:0];   // saturates at 255
endmodule
