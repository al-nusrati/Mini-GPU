// ============================================================================
//  File    : rtl/rasterizer.sv
//  Purpose : The GPU's core. Reads triangles from tri memory one by one and
//            walks each one's bounding box at ONE PIXEL PER CLOCK, sending every
//            covered pixel ("fragment") to depth_unit.sv.
//
//  Triangle word (208 bits, little-endian byte order as sent by the host)
//    [15:0] x0  [31:16] y0  [47:32] x1  [63:48] y1  [79:64] x2  [95:80] y2
//    [127:96] z0 (Q16.16 depth at v0)  [159:128] dz/dx  [191:160] dz/dy
//    [207:192] color
//    Coordinates are integer pixels, must stay in -2048 .. 2047.
//
//  Math (all integer, same as golden/golden.cpp)
//    edge e(a->b, p) = (px-ax)*(by-ay) - (py-ay)*(bx-ax)
//    e0 = e(v1->v2), e1 = e(v2->v0), e2 = e(v0->v1)
//    area = e2 at p = v2.  area <= 0 -> back-facing or flat -> skipped
//    is_in = all of (e_i - bias_i) >= 0   (bias = 0 on top-left edges, else 1)
//    stepping right adds A_i = by-ay, stepping down adds B_i = ax-bx
//    depth z steps the same way with dz/dx, dz/dy (48-bit accumulator)
//
//  Cycles per triangle:  culled = 5,  drawn = 6 + (box width * box height)
//    FETCH -> LATCH -> SETUP1 -> SETUP2 -> [SETUP3 -> WALK ... ] -> NEXT
//
//  Depth hazard: depth_unit needs 2 cycles (read, then write). A new
//  triangle's first fragment arrives at least 6 cycles after the old one's
//  last, so the setup latency already hides the hazard. A faster, pipelined
//  setup would need forwarding (good "future work" for the paper).
// ============================================================================
module rasterizer #(
    parameter int W        = 160,
    parameter int H        = 120,
    parameter int MAX_TRIS = 1024
) (
    input  logic                         clk,
    input  logic                         rst_n,
    input  logic                         start,       // 1-cycle pulse
    input  logic [$clog2(MAX_TRIS):0]    tri_count,
    output logic [$clog2(MAX_TRIS)-1:0]  tri_raddr,
    input  logic [207:0]                 tri_rdata,
    output logic                         busy,
    output logic                         done,        // 1-cycle pulse
    // fragment out (registered)
    output logic                         frag_valid,
    output logic [$clog2(W*H)-1:0]       frag_addr,
    output logic [15:0]                  frag_depth,
    output logic [15:0]                  frag_color,
    // performance counters (cleared on start)
    output logic [31:0]                  pix_tested,
    output logic [31:0]                  pix_inside
);
    localparam int AW = $clog2(W*H);
    localparam int IW = $clog2(MAX_TRIS);

    typedef enum logic [3:0] {IDLE, FETCH, LATCH, SETUP1, SETUP2, SETUP3, WALK, NEXT, DONE} state_t;
    state_t state;

    logic [IW:0] idx;
    assign tri_raddr = idx[IW-1:0];
    assign busy      = (state != IDLE);

    // ---------------- latched triangle -------------------------------------
    logic signed [15:0] x0, y0, x1, y1, x2, y2;
    logic signed [31:0] z0, dzdx, dzdy;
    logic        [15:0] color;

    // ---------------- setup results ----------------------------------------
    logic signed [31:0] a0, a1, a2, b0, b1, b2;          // step right / down
    logic        [2:0]  bias;                            // 1 = not top-left
    logic signed [31:0] area;
    logic signed [15:0] minx, maxx, miny, maxy;

    // products (SETUP2), kept in registers to help timing
    logic signed [31:0] p0a, p0b, p1a, p1b, p2a, p2b;
    logic signed [47:0] pzx, pzy;
    logic        [AW-1:0] addr_start;

    // ---------------- walk state -------------------------------------------
    logic signed [15:0] x, y;
    logic signed [31:0] e0, e1, e2, r0, r1, r2;           // current + row start
    logic signed [47:0] z, zr;
    logic        [AW-1:0] addr, addr_r;

    // ---------------- helpers (pure functions) -----------------------------
    function automatic logic signed [15:0] min3(input logic signed [15:0] a, b, c);
        logic signed [15:0] m;
        m = (a < b) ? a : b;
        return (m < c) ? m : c;
    endfunction
    function automatic logic signed [15:0] max3(input logic signed [15:0] a, b, c);
        logic signed [15:0] m;
        m = (a > b) ? a : b;
        return (m > c) ? m : c;
    endfunction
    // top-left rule for edge a->b: dy > 0, or dy == 0 and dx < 0
    function automatic logic not_top_left(input logic signed [15:0] ax, ay, bx, by);
        logic signed [16:0] dx, dy;
        dx = 17'(bx) - 17'(ax);
        dy = 17'(by) - 17'(ay);
        return !((dy > 0) || (dy == 0 && dx < 0));
    endfunction
    /* verilator lint_off UNUSEDSIGNAL */          // low 16 bits are the fraction
    function automatic logic [15:0] sat_depth(input logic signed [47:0] zz);
        logic signed [31:0] d;
        d = zz[47:16];                                    // arithmetic >> 16
        if (d < 0)          return 16'd0;
        else if (d > 65535) return 16'hFFFF;
        else                return d[15:0];
    endfunction
    /* verilator lint_on UNUSEDSIGNAL */

    // combinational: is the current pixel inside the triangle?
    logic is_in;
    assign is_in = !e0[31] && !e1[31] && !e2[31];

    logic signed [15:0] bx0, bx1, by0, by1;               // unclamped box
    assign bx0 = min3(x0, x1, x2);
    assign bx1 = max3(x0, x1, x2);
    assign by0 = min3(y0, y1, y2);
    assign by1 = max3(y0, y1, y2);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;  idx <= '0;  done <= 1'b0;  frag_valid <= 1'b0;
            pix_tested <= '0;  pix_inside <= '0;
        end else begin
            done       <= 1'b0;
            frag_valid <= 1'b0;

            case (state)
            IDLE: if (start) begin
                idx        <= '0;
                pix_tested <= '0;
                pix_inside <= '0;
                state      <= (tri_count == 0) ? DONE : FETCH;
            end

            FETCH: state <= LATCH;                        // RAM read in flight

            LATCH: begin
                x0 <= tri_rdata[15:0];    y0 <= tri_rdata[31:16];
                x1 <= tri_rdata[47:32];   y1 <= tri_rdata[63:48];
                x2 <= tri_rdata[79:64];   y2 <= tri_rdata[95:80];
                z0 <= tri_rdata[127:96];  dzdx <= tri_rdata[159:128];
                dzdy <= tri_rdata[191:160];
                color <= tri_rdata[207:192];
                state <= SETUP1;
            end

            SETUP1: begin
                a0 <= 32'(y2) - 32'(y1);   b0 <= 32'(x1) - 32'(x2);
                a1 <= 32'(y0) - 32'(y2);   b1 <= 32'(x2) - 32'(x0);
                a2 <= 32'(y1) - 32'(y0);   b2 <= 32'(x0) - 32'(x1);
                bias[0] <= not_top_left(x1, y1, x2, y2);
                bias[1] <= not_top_left(x2, y2, x0, y0);
                bias[2] <= not_top_left(x0, y0, x1, y1);
                area <= (32'(x2) - 32'(x0)) * (32'(y1) - 32'(y0))
                      - (32'(y2) - 32'(y0)) * (32'(x1) - 32'(x0));
                minx <= (bx0 < 0)          ? 16'sd0 : bx0;
                maxx <= (bx1 > 16'(W - 1)) ? 16'(W - 1) : bx1;
                miny <= (by0 < 0)          ? 16'sd0 : by0;
                maxy <= (by1 > 16'(H - 1)) ? 16'(H - 1) : by1;
                state <= SETUP2;
            end

            SETUP2: begin
                if (area <= 0 || minx > maxx || miny > maxy) begin
                    state <= NEXT;                        // culled
                end else begin
                    p0a <= (32'(minx) - 32'(x1)) * a0;   p0b <= (32'(miny) - 32'(y1)) * b0;
                    p1a <= (32'(minx) - 32'(x2)) * a1;   p1b <= (32'(miny) - 32'(y2)) * b1;
                    p2a <= (32'(minx) - 32'(x0)) * a2;   p2b <= (32'(miny) - 32'(y0)) * b2;
                    pzx <= 48'(dzdx) * (48'(minx) - 48'(x0));
                    pzy <= 48'(dzdy) * (48'(miny) - 48'(y0));
                    addr_start <= AW'(miny) * AW'(W) + AW'(minx);
                    state <= SETUP3;
                end
            end

            SETUP3: begin
                e0 <= p0a + p0b - 32'(bias[0]);   r0 <= p0a + p0b - 32'(bias[0]);
                e1 <= p1a + p1b - 32'(bias[1]);   r1 <= p1a + p1b - 32'(bias[1]);
                e2 <= p2a + p2b - 32'(bias[2]);   r2 <= p2a + p2b - 32'(bias[2]);
                z  <= 48'(z0) + pzx + pzy;        zr <= 48'(z0) + pzx + pzy;
                addr <= addr_start;               addr_r <= addr_start;
                x <= minx;  y <= miny;
                state <= WALK;
            end

            WALK: begin
                // emit this pixel
                pix_tested <= pix_tested + 1;
                if (is_in) begin
                    pix_inside <= pix_inside + 1;
                    frag_valid <= 1'b1;
                end
                frag_addr  <= addr;
                frag_depth <= sat_depth(z);
                frag_color <= color;

                // move to the next pixel
                if (x == maxx) begin
                    if (y == maxy) begin
                        state <= NEXT;
                    end else begin
                        y  <= y + 1'b1;   x <= minx;
                        r0 <= r0 + b0;    e0 <= r0 + b0;
                        r1 <= r1 + b1;    e1 <= r1 + b1;
                        r2 <= r2 + b2;    e2 <= r2 + b2;
                        zr <= zr + 48'(dzdy);  z <= zr + 48'(dzdy);
                        addr_r <= addr_r + AW'(W);  addr <= addr_r + AW'(W);
                    end
                end else begin
                    x  <= x + 1'b1;
                    e0 <= e0 + a0;  e1 <= e1 + a1;  e2 <= e2 + a2;
                    z  <= z + 48'(dzdx);
                    addr <= addr + 1'b1;
                end
            end

            NEXT: begin
                idx   <= idx + 1'b1;
                state <= (idx + 1'b1 == tri_count) ? DONE : FETCH;
            end

            DONE: begin
                done  <= 1'b1;
                state <= IDLE;
            end

            default: state <= IDLE;
            endcase
        end
    end
endmodule
