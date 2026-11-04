// ============================================================================
//  File    : rtl/sdp_ram.sv
//  Purpose : Simple dual-port RAM: one write port, one read port, 1-cycle read.
//            Vivado turns this exact pattern into Block RAM.
//  Note    : Reading and writing the SAME address in the same cycle returns the
//            OLD value. That is the depth-buffer hazard discussed in
//            rasterizer.sv / depth_unit.sv.
// ============================================================================
module sdp_ram #(
    parameter int WIDTH = 16,
    parameter int DEPTH = 19200
) (
    input  logic                     clk,
    input  logic                     we,
    input  logic [$clog2(DEPTH)-1:0] waddr,
    input  logic [WIDTH-1:0]         wdata,
    input  logic [$clog2(DEPTH)-1:0] raddr,
    output logic [WIDTH-1:0]         rdata
);
    (* ram_style = "block" *) logic [WIDTH-1:0] mem [DEPTH];

    always_ff @(posedge clk) begin
        if (we) mem[waddr] <= wdata;
        rdata <= mem[raddr];
    end
endmodule
