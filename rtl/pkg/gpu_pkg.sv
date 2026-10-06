// GENERATED from spec/formats.yaml by tools/gen_types.py - DO NOT EDIT BY HAND
package gpu_pkg;
    // Not every constant is used by every module; that is expected.
    /* verilator lint_off UNUSEDPARAM */

    localparam int SPEC_VERSION = 1;

    // ---------------- scalar types ----------------
    localparam int POS_W    = 32;
    localparam int POS_FRAC = 16;
    typedef logic signed [POS_W-1:0] pos_t;   // Q16.16 model-space positions and matrix elements
    localparam int UNIT_W    = 16;
    localparam int UNIT_FRAC = 14;
    typedef logic signed [UNIT_W-1:0] unit_t;   // Q2.14 unit vectors and light terms (range about -2..+2)
    localparam int SCREEN_W    = 16;
    localparam int SCREEN_FRAC = 4;
    typedef logic signed [SCREEN_W-1:0] screen_t;   // Q12.4 screen coordinates, pixel center = n + 0.5
    localparam int GRAD_W    = 32;
    localparam int GRAD_FRAC = 16;
    typedef logic signed [GRAD_W-1:0] grad_t;   // Q16.16 gradients for incremental interpolation
    localparam int DEPTH_W    = 16;
    typedef logic [DEPTH_W-1:0] depth_t;   // 0 = near plane, 65535 = far plane / cleared
    localparam int COLOR_W    = 16;
    typedef logic [COLOR_W-1:0] color_t;   // RGB444 in bits 11..0 on Basys3, RGB565 on Zynq
    localparam int TRI_ID_W    = 16;
    typedef logic [TRI_ID_W-1:0] tri_id_t;   // triangle index inside one DRAW_TRIS batch

    // ---------------- structs (first field = most significant bits) ----------------
    // Object-space vertex exactly as sent by the host
    typedef struct packed {
        pos_t px;
        pos_t py;
        pos_t pz;
        unit_t nx;
        unit_t ny;
        unit_t nz;
        color_t color;
    } vertex_in_t;
    localparam int VERTEX_IN_BITS = 160;

    // Clip-space position plus lit color
    typedef struct packed {
        pos_t cx;
        pos_t cy;
        pos_t cz;
        pos_t cw;
        color_t color;
    } clip_vert_t;
    localparam int CLIP_VERT_BITS = 144;

    // Screen-space vertex
    typedef struct packed {
        screen_t sx;
        screen_t sy;
        depth_t z;
        color_t color;
    } screen_vert_t;
    localparam int SCREEN_VERT_BITS = 64;

    // One covered pixel
    typedef struct packed {
        screen_t x;
        screen_t y;
        depth_t z;
        color_t color;
    } fragment_t;
    localparam int FRAGMENT_BITS = 64;

    // ---------------- packets ----------------
    typedef enum logic [7:0] {
        OP_CLEAR = 8'h01,
        OP_SET_MATRIX = 8'h02,
        OP_SET_LIGHT = 8'h03,
        OP_SET_MODE = 8'h04,
        OP_DRAW_TRIS = 8'h05,
        OP_FINISH = 8'h06,
        OP_READ_FRAME = 8'h07,
        OP_READ_STATS = 8'h08,
        OP_RAW_SCREEN_TRI = 8'h0F
    } opcode_e;

    localparam logic [7:0] REPLY_ACK = 8'hA0;
    localparam logic [7:0] REPLY_ERR = 8'hE0;
    localparam logic [7:0] REPLY_DONE = 8'hD0;
    localparam logic [7:0] ERR_BAD_CHECKSUM = 8'd1;
    localparam logic [7:0] ERR_BAD_OPCODE = 8'd2;
    localparam logic [7:0] ERR_BAD_LENGTH = 8'd3;

    // ---------------- targets ----------------
    localparam int BASYS3_WIDTH = 160;
    localparam int BASYS3_HEIGHT = 120;
    localparam int BASYS3_CLK_MHZ = 100;
    localparam int ZYNQ_WIDTH = 320;
    localparam int ZYNQ_HEIGHT = 240;
    localparam int ZYNQ_CLK_MHZ = 100;

    /* verilator lint_on UNUSEDPARAM */
endpackage
