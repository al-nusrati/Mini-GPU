// ============================================================================
//  File    : rtl/depth_unit.sv
//  Purpose : Depth (Z) buffer + color framebuffer + clear engine + readback port.
//
//  Fragment pipeline (2 stages)
//    cycle t   : fragment arrives -> read stored depth at its address
//    cycle t+1 : stored depth ready -> if new depth < stored: write depth + color
//
//  Clear engine: on clear_start, writes depth = 0xFFFF and color = clear_color
//  to every pixel, one per clock (W*H cycles).
//  Readback: rb_addr -> rb_data one cycle later (color only).
// ============================================================================
module depth_unit #(
    parameter int W = 160,
    parameter int H = 120
) (
    input  logic                    clk,
    input  logic                    rst_n,
    // fragments from rasterizer
    input  logic                    frag_valid,
    input  logic [$clog2(W*H)-1:0]  frag_addr,
    input  logic [15:0]             frag_depth,
    input  logic [15:0]             frag_color,
    // clear
    input  logic                    clear_start,
    input  logic [15:0]             clear_color,
    output logic                    clear_busy,
    // readback
    input  logic [$clog2(W*H)-1:0]  rb_addr,
    output logic [15:0]             rb_data,
    // counter
    input  logic                    count_reset,
    output logic [31:0]             pix_written
);
    localparam int N  = W * H;
    localparam int AW = $clog2(N);

    // ---------------- stage 1 registers ------------------------------------
    logic          s1_valid;
    logic [AW-1:0] s1_addr;
    logic [15:0]   s1_depth, s1_color;
    logic [15:0]   stored_depth;
    logic          pass;
    assign pass = s1_valid && (s1_depth < stored_depth);

    // ---------------- clear engine -----------------------------------------
    logic [AW-1:0] clr_addr;
    logic [15:0]   clr_color;

    // ---------------- write-port mux ---------------------------------------
    logic          we;
    logic [AW-1:0] waddr;
    logic [15:0]   wdepth, wcolor;
    always_comb begin
        if (clear_busy) begin
            we = 1'b1;  waddr = clr_addr;  wdepth = 16'hFFFF;  wcolor = clr_color;
        end else begin
            we = pass;  waddr = s1_addr;   wdepth = s1_depth;  wcolor = s1_color;
        end
    end

    sdp_ram #(.WIDTH(16), .DEPTH(N)) u_depth (
        .clk(clk), .we(we), .waddr(waddr), .wdata(wdepth),
        .raddr(frag_addr), .rdata(stored_depth));

    sdp_ram #(.WIDTH(16), .DEPTH(N)) u_color (
        .clk(clk), .we(we), .waddr(waddr), .wdata(wcolor),
        .raddr(rb_addr), .rdata(rb_data));

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            s1_valid <= 1'b0;  clear_busy <= 1'b0;  clr_addr <= '0;  clr_color <= '0;
            pix_written <= '0;
        end else begin
            s1_valid <= frag_valid;
            s1_addr  <= frag_addr;
            s1_depth <= frag_depth;
            s1_color <= frag_color;

            if (count_reset)   pix_written <= '0;
            else if (pass)     pix_written <= pix_written + 1;

            if (clear_start && !clear_busy) begin
                clear_busy <= 1'b1;
                clr_addr   <= '0;
                clr_color  <= clear_color;
            end else if (clear_busy) begin
                if (clr_addr == AW'(N - 1)) clear_busy <= 1'b0;
                clr_addr <= clr_addr + 1'b1;
            end
        end
    end
endmodule
