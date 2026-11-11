// ============================================================================
//  File    : zynq/gpu_axil.v   (plain Verilog on purpose: Vivado's block design
//            "Add Module" needs a Verilog/VHDL top; the SV files sit under it)
//  Purpose : AXI4-Lite slave that lets the ARM talk to the SAME gpu_core.sv
//            using the SAME byte protocol as the Basys3 UART.
//
//  Registers (32-bit, offsets from the base address Vivado assigns)
//    0x00 W  TX      bits[7:0] = byte to send. Only write when STATUS.in_ready=1
//    0x04 R  STATUS  [0] in_ready [1] out_valid [2] busy [3] overflow
//                    [4] dropped (a TX write was lost) [26:16] triangle count
//    0x08 R  RX      [8] valid, [7:0] byte. Reading it with valid=1 consumes the byte
//    0x0C R  ID      0x47505501 ("GPU" v1)
// ============================================================================
module gpu_axil #(
    parameter W        = 160,
    parameter H        = 120,
    parameter MAX_TRIS = 1024
) (
    input  wire        s_axi_aclk,
    input  wire        s_axi_aresetn,
    input  wire [4:0]  s_axi_awaddr,
    input  wire        s_axi_awvalid,
    output reg         s_axi_awready,
    input  wire [31:0] s_axi_wdata,
    input  wire [3:0]  s_axi_wstrb,
    input  wire        s_axi_wvalid,
    output reg         s_axi_wready,
    output reg  [1:0]  s_axi_bresp,
    output reg         s_axi_bvalid,
    input  wire        s_axi_bready,
    input  wire [4:0]  s_axi_araddr,
    input  wire        s_axi_arvalid,
    output reg         s_axi_arready,
    output reg  [31:0] s_axi_rdata,
    output reg  [1:0]  s_axi_rresp,
    output reg         s_axi_rvalid,
    input  wire        s_axi_rready
);
    wire clk   = s_axi_aclk;
    wire rst_n = s_axi_aresetn;

    // ---------------- gpu core ----------------------------------------------
    reg         in_valid;
    reg  [7:0]  in_data;
    wire        in_ready;
    wire        out_valid;
    wire [7:0]  out_data;
    reg         out_ready;
    wire        busy, overflow;
    wire [10:0] tri_count;
    reg         dropped;

    gpu_core #(.W(W), .H(H), .MAX_TRIS(MAX_TRIS)) u_gpu (
        .clk(clk), .rst_n(rst_n),
        .in_valid(in_valid), .in_data(in_data), .in_ready(in_ready),
        .out_valid(out_valid), .out_data(out_data), .out_ready(out_ready),
        .busy(busy), .overflow(overflow), .tri_count(tri_count));

    // ---------------- write channel ------------------------------------------
    // accept address and data together, one write at a time
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            s_axi_awready <= 1'b0;  s_axi_wready <= 1'b0;
            s_axi_bvalid  <= 1'b0;  s_axi_bresp  <= 2'b00;
            in_valid <= 1'b0;  in_data <= 8'h00;  dropped <= 1'b0;
        end else begin
            in_valid      <= 1'b0;
            s_axi_awready <= 1'b0;
            s_axi_wready  <= 1'b0;

            if (s_axi_awvalid && s_axi_wvalid && !s_axi_awready && !s_axi_bvalid) begin
                s_axi_awready <= 1'b1;
                s_axi_wready  <= 1'b1;
                if (s_axi_awaddr[4:2] == 3'd0 && s_axi_wstrb[0]) begin
                    if (in_ready) begin
                        in_valid <= 1'b1;
                        in_data  <= s_axi_wdata[7:0];
                    end else begin
                        dropped  <= 1'b1;
                    end
                end
                s_axi_bvalid <= 1'b1;
                s_axi_bresp  <= 2'b00;
            end else if (s_axi_bvalid && s_axi_bready) begin
                s_axi_bvalid <= 1'b0;
            end
        end
    end

    // ---------------- read channel -------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            s_axi_arready <= 1'b0;  s_axi_rvalid <= 1'b0;  s_axi_rdata <= 32'd0;
            s_axi_rresp   <= 2'b00; out_ready    <= 1'b0;
        end else begin
            s_axi_arready <= 1'b0;
            out_ready     <= 1'b0;

            if (s_axi_arvalid && !s_axi_arready && !s_axi_rvalid) begin
                s_axi_arready <= 1'b1;
                s_axi_rvalid  <= 1'b1;
                s_axi_rresp   <= 2'b00;
                case (s_axi_araddr[4:2])
                    3'd1: s_axi_rdata <= {5'd0, tri_count, 11'd0, dropped, overflow, busy, out_valid, in_ready};
                    3'd2: begin
                        s_axi_rdata <= {23'd0, out_valid, out_data};
                        out_ready   <= out_valid;          // pop the byte we just returned
                    end
                    3'd3: s_axi_rdata <= 32'h47505501;
                    default: s_axi_rdata <= 32'd0;
                endcase
            end else if (s_axi_rvalid && s_axi_rready) begin
                s_axi_rvalid <= 1'b0;
            end
        end
    end
endmodule
