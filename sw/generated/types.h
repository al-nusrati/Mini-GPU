// GENERATED from spec/formats.yaml by tools/gen_types.py - DO NOT EDIT BY HAND
#pragma once
#include <stdint.h>
#include <math.h>

static const int SPEC_VERSION = 1;

// ---------------- scalar types ----------------
typedef int32_t pos_t;   // Q16.16 model-space positions and matrix elements
typedef int16_t unit_t;   // Q2.14 unit vectors and light terms (range about -2..+2)
typedef int16_t screen_t;   // Q12.4 screen coordinates, pixel center = n + 0.5
typedef int32_t grad_t;   // Q16.16 gradients for incremental interpolation
typedef uint16_t depth_t;   // 0 = near plane, 65535 = far plane / cleared
typedef uint16_t color_t;   // RGB444 in bits 11..0 on Basys3, RGB565 on Zynq
typedef uint16_t tri_id_t;   // triangle index inside one DRAW_TRIS batch

// ---------------- fixed-point converters ----------------
// Rule (same in Python and golden model): round to nearest, ties away
// from zero, then saturate to the type's range.
static const int POS_FRAC = 16;
static const int64_t POS_MIN = -2147483648LL, POS_MAX = 2147483647LL;
inline pos_t to_pos(double v) {
    double s = v * (double)(1LL << POS_FRAC);
    if (s >= (double)POS_MAX) return (pos_t)POS_MAX;   // saturate first:
    if (s <= (double)POS_MIN) return (pos_t)POS_MIN;   // llround overflow is undefined
    return (pos_t)llround(s);
}
inline double from_pos(pos_t v) { return (double)v / (double)(1LL << POS_FRAC); }

static const int UNIT_FRAC = 14;
static const int64_t UNIT_MIN = -32768LL, UNIT_MAX = 32767LL;
inline unit_t to_unit(double v) {
    double s = v * (double)(1LL << UNIT_FRAC);
    if (s >= (double)UNIT_MAX) return (unit_t)UNIT_MAX;   // saturate first:
    if (s <= (double)UNIT_MIN) return (unit_t)UNIT_MIN;   // llround overflow is undefined
    return (unit_t)llround(s);
}
inline double from_unit(unit_t v) { return (double)v / (double)(1LL << UNIT_FRAC); }

static const int SCREEN_FRAC = 4;
static const int64_t SCREEN_MIN = -32768LL, SCREEN_MAX = 32767LL;
inline screen_t to_screen(double v) {
    double s = v * (double)(1LL << SCREEN_FRAC);
    if (s >= (double)SCREEN_MAX) return (screen_t)SCREEN_MAX;   // saturate first:
    if (s <= (double)SCREEN_MIN) return (screen_t)SCREEN_MIN;   // llround overflow is undefined
    return (screen_t)llround(s);
}
inline double from_screen(screen_t v) { return (double)v / (double)(1LL << SCREEN_FRAC); }

static const int GRAD_FRAC = 16;
static const int64_t GRAD_MIN = -2147483648LL, GRAD_MAX = 2147483647LL;
inline grad_t to_grad(double v) {
    double s = v * (double)(1LL << GRAD_FRAC);
    if (s >= (double)GRAD_MAX) return (grad_t)GRAD_MAX;   // saturate first:
    if (s <= (double)GRAD_MIN) return (grad_t)GRAD_MIN;   // llround overflow is undefined
    return (grad_t)llround(s);
}
inline double from_grad(grad_t v) { return (double)v / (double)(1LL << GRAD_FRAC); }

// ---------------- structs (host-side view; wire format is packed little-endian) ----------------
// Object-space vertex exactly as sent by the host  (160 bits on the wire)
struct vertex_in_t {
    pos_t px;
    pos_t py;
    pos_t pz;
    unit_t nx;
    unit_t ny;
    unit_t nz;
    color_t color;
};
static const int VERTEX_IN_WIRE_BYTES = 20;

// Clip-space position plus lit color  (144 bits on the wire)
struct clip_vert_t {
    pos_t cx;
    pos_t cy;
    pos_t cz;
    pos_t cw;
    color_t color;
};
static const int CLIP_VERT_WIRE_BYTES = 18;

// Screen-space vertex  (64 bits on the wire)
struct screen_vert_t {
    screen_t sx;
    screen_t sy;
    depth_t z;
    color_t color;
};
static const int SCREEN_VERT_WIRE_BYTES = 8;

// One covered pixel  (64 bits on the wire)
struct fragment_t {
    screen_t x;
    screen_t y;
    depth_t z;
    color_t color;
};
static const int FRAGMENT_WIRE_BYTES = 8;

// ---------------- packets ----------------
enum Opcode : uint8_t {
    OP_CLEAR = 0x01,
    OP_SET_MATRIX = 0x02,
    OP_SET_LIGHT = 0x03,
    OP_SET_MODE = 0x04,
    OP_DRAW_TRIS = 0x05,
    OP_FINISH = 0x06,
    OP_READ_FRAME = 0x07,
    OP_READ_STATS = 0x08,
    OP_RAW_SCREEN_TRI = 0x0F,
};
static const uint8_t REPLY_ACK = 0xA0;
static const uint8_t REPLY_ERR = 0xE0;
static const uint8_t REPLY_DONE = 0xD0;
static const uint8_t ERR_BAD_CHECKSUM = 1;
static const uint8_t ERR_BAD_OPCODE = 2;
static const uint8_t ERR_BAD_LENGTH = 3;

// ---------------- targets ----------------
static const int BASYS3_WIDTH = 160, BASYS3_HEIGHT = 120, BASYS3_CLK_MHZ = 100;
static const int ZYNQ_WIDTH = 320, ZYNQ_HEIGHT = 240, ZYNQ_CLK_MHZ = 100;
