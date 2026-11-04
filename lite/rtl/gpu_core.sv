// ============================================================================
//  File    : rtl/gpu_core.sv
//  Purpose : The whole mini GPU behind a simple byte-stream interface.
//            Basys3 connects the bytes to UART. Zynq connects them to AXI-Lite
//            registers. The core itself is IDENTICAL on both boards.
//
//  Commands (host -> GPU)                         Reply (GPU -> host)
//    0x00 PING                                     'G' 'P' 'U' VERSION
//    0x01 CLEAR      color(2)                      0xA0 when done
//    0x02 LOAD_TRI   26 bytes (see rasterizer.sv)  none
//    0x03 DRAW                                     0xD0 + cycles(4) tested(4)
//                                                  inside(4) written(4) = 17 B
//    0x04 READ                                     W*H pixels, 2 bytes each (LE)
//    0x05 RESET_TRIS                               0xA0
//  Multi-byte values are little-endian. DRAW keeps the loaded triangles, so it
//  can be repeated for timing; RESET_TRIS empties the triangle list.
//
//  Byte interfaces (valid/ready): a byte moves when valid && ready.
// ============================================================================
module gpu_core #(
    parameter int W        = 160,
    parameter int H        = 120,
    parameter int MAX_TRIS = 1024
) (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        in_valid,
    input  logic [7:0]  in_data,
    output logic        in_ready,
    output logic        out_valid,
    output logic [7:0]  out_data,
    input  logic        out_ready,
    // status for LEDs
    output logic        busy,
    output logic        overflow,              // too many triangles loaded
    output logic [$clog2(MAX_TRIS):0] tri_count
);
    localparam int N       = W * H;
    localparam int AW      = $clog2(N);
    localparam int IW      = $clog2(MAX_TRIS);
    localparam logic [7:0] VERSION = 8'd1;

    typedef enum logic [3:0] {S_IDLE, S_GET, S_CLEAR, S_DRAW, S_SEND,
                              S_RD_ADDR, S_RD_LO, S_RD_HI} state_t;
    state_t state;

    logic [7:0]   cmd;
    logic [4:0]   need, got;                  // payload byte counts
    logic [207:0] payload;                    // after 26 bytes: byte k at [8k+7:8k]
                                              // after 2 bytes (CLEAR): at [207:192]
    logic [135:0] reply;                      // up to 17 bytes
    logic [4:0]   reply_len;
    logic [AW-1:0] rb_addr;
    logic [15:0]  rb_data;
    logic [31:0]  cycles;

    // ---------------- triangle memory --------------------------------------
    logic          tri_we;
    logic [IW-1:0] tri_raddr;
    logic [207:0]  tri_rdata;
    sdp_ram #(.WIDTH(208), .DEPTH(MAX_TRIS)) u_tris (
        .clk(clk), .we(tri_we), .waddr(tri_count[IW-1:0]), .wdata(payload),
        .raddr(tri_raddr), .rdata(tri_rdata));

    // ---------------- rasterizer + depth unit ------------------------------
    logic r_start, r_done;
    /* verilator lint_off UNUSEDSIGNAL */
    logic r_busy;                                 // kept for an ILA probe
    /* verilator lint_on UNUSEDSIGNAL */
    logic f_valid;  logic [AW-1:0] f_addr;  logic [15:0] f_depth, f_color;
    logic [31:0] pix_tested, pix_inside, pix_written;
    logic clr_start, clr_busy;

    rasterizer #(.W(W), .H(H), .MAX_TRIS(MAX_TRIS)) u_rast (
        .clk(clk), .rst_n(rst_n), .start(r_start), .tri_count(tri_count),
        .tri_raddr(tri_raddr), .tri_rdata(tri_rdata), .busy(r_busy), .done(r_done),
        .frag_valid(f_valid), .frag_addr(f_addr), .frag_depth(f_depth), .frag_color(f_color),
        .pix_tested(pix_tested), .pix_inside(pix_inside));

    depth_unit #(.W(W), .H(H)) u_depth (
        .clk(clk), .rst_n(rst_n),
        .frag_valid(f_valid), .frag_addr(f_addr), .frag_depth(f_depth), .frag_color(f_color),
        .clear_start(clr_start), .clear_color(payload[207:192]), .clear_busy(clr_busy),
        .rb_addr(rb_addr), .rb_data(rb_data),
        .count_reset(r_start), .pix_written(pix_written));

    // ---------------- byte interfaces --------------------------------------
    assign in_ready  = (state == S_IDLE) || (state == S_GET);
    assign busy      = (state != S_IDLE);
    always_comb begin
        out_valid = 1'b0;
        out_data  = 8'h00;
        case (state)
            S_SEND:  begin out_valid = 1'b1; out_data = reply[7:0];     end
            S_RD_LO: begin out_valid = 1'b1; out_data = rb_data[7:0];   end
            S_RD_HI: begin out_valid = 1'b1; out_data = rb_data[15:8];  end
            default: ;
        endcase
    end

    // ---------------- command FSM ------------------------------------------
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE;  tri_count <= '0;  overflow <= 1'b0;
            got <= '0;  need <= '0;  cmd <= '0;  payload <= '0;
            reply <= '0;  reply_len <= '0;  rb_addr <= '0;  cycles <= '0;
            tri_we <= 1'b0;  r_start <= 1'b0;  clr_start <= 1'b0;
        end else begin
            tri_we    <= 1'b0;
            r_start   <= 1'b0;
            clr_start <= 1'b0;
            if (tri_we) tri_count <= tri_count + 1'b1;   // write happened last cycle

            case (state)
            S_IDLE: if (in_valid) begin
                cmd <= in_data;
                got <= '0;
                case (in_data)
                    8'h00: begin reply <= 136'({VERSION, 8'h55, 8'h50, 8'h47}); reply_len <= 5'd4; state <= S_SEND; end
                    8'h01: begin need <= 5'd2;  state <= S_GET; end
                    8'h02: begin need <= 5'd26; state <= S_GET; end
                    8'h03: begin r_start <= 1'b1; cycles <= '0; state <= S_DRAW; end
                    8'h04: begin rb_addr <= '0; state <= S_RD_ADDR; end
                    8'h05: begin tri_count <= '0; overflow <= 1'b0;
                                 reply <= 136'(8'hA0); reply_len <= 5'd1; state <= S_SEND; end
                    default: ;                                    // ignore unknown bytes
                endcase
            end

            S_GET: if (in_valid) begin
                payload <= {in_data, payload[207:8]};      // bytes shift in from the top
                if (got + 1'b1 == need) begin
                    if (cmd == 8'h01) begin
                        clr_start <= 1'b1;
                        state     <= S_CLEAR;
                    end else begin
                        if (tri_count < (IW+1)'(MAX_TRIS)) tri_we <= 1'b1;
                        else                               overflow <= 1'b1;
                        state <= S_IDLE;
                    end
                end
                got <= got + 1'b1;
            end

            S_CLEAR: if (!clr_start && !clr_busy) begin
                reply <= 136'(8'hA0);  reply_len <= 5'd1;  state <= S_SEND;
            end

            S_DRAW: begin
                cycles <= cycles + 1;
                if (r_done) begin
                    reply <= {pix_written, pix_inside, pix_tested, cycles + 32'd1, 8'hD0};
                    reply_len <= 5'd17;
                    state <= S_SEND;
                end
            end

            S_SEND: if (out_ready) begin
                reply     <= reply >> 8;
                reply_len <= reply_len - 1'b1;
                if (reply_len == 5'd1) state <= S_IDLE;
            end

            S_RD_ADDR: state <= S_RD_LO;                     // RAM read in flight
            S_RD_LO:   if (out_ready) state <= S_RD_HI;
            S_RD_HI:   if (out_ready) begin
                if (rb_addr == AW'(N - 1)) state <= S_IDLE;
                else begin rb_addr <= rb_addr + 1'b1; state <= S_RD_ADDR; end
            end

            default: state <= S_IDLE;
            endcase
        end
    end
endmodule
