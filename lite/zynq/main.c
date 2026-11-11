/*
 * ============================================================================
 *  File    : zynq/main.c   (Vitis bare-metal application, ARM Cortex-A9)
 *  Purpose : Runs a scene on the Zynq's GPU (gpu_axil.v in the PL) using the
 *            SAME byte protocol as the Basys3, and prints the results.
 *
 *  Setup   : 1. python pc/make_scene.py cube       -> zynq/scene_cube.h
 *            2. add main.c + scene_cube.h to your Vitis app (change the
 *               #include below for another scene)
 *            3. open a serial terminal on the board's USB-UART (115200)
 *
 *  Output  : cycles, counters, CRC32 of the frame, host-side times, and the
 *            SAME scene rendered in software on the ARM (time + CRC).
 *            Compare the CRC with results/<scene>_golden.json ("crc32").
 *            Set DUMP_FRAME 1 to print the frame as hex; save the terminal
 *            log and run:  python pc/zynq_log.py log.txt <scene>
 * ============================================================================
 */
#include <stdio.h>
#include <stdint.h>
#include "xil_io.h"
#include "xtime_l.h"
#include "xparameters.h"
#include "scene_cube.h"                 /* <- change scene here */

/* The base address comes from Vivado's Address Editor. Vitis usually defines
 * it in xparameters.h; the exact name depends on your block-design instance
 * name. If it does not compile, put the address from the Address Editor here. */
#if defined(XPAR_GPU_AXIL_0_BASEADDR)
#define GPU_BASE XPAR_GPU_AXIL_0_BASEADDR
#else
#define GPU_BASE 0x43C00000u
#endif

#define REG_TX     0x00
#define REG_STATUS 0x04
#define REG_RX     0x08
#define REG_ID     0x0C

#define W 160
#define H 120
#define DUMP_FRAME 0

static uint16_t frame[W * H];

/* ---------------------------------------------------------------------------
 *  Private helpers: one byte in, one byte out (same as the UART on Basys3)
 * ------------------------------------------------------------------------- */
static void gpu_put(uint8_t b)
{
    while ((Xil_In32(GPU_BASE + REG_STATUS) & 1u) == 0) { }   /* wait in_ready */
    Xil_Out32(GPU_BASE + REG_TX, b);
}

static uint8_t gpu_get(void)
{
    uint32_t r;
    do { r = Xil_In32(GPU_BASE + REG_RX); } while ((r & 0x100u) == 0);
    return (uint8_t)r;
}

static uint32_t get32(void)
{
    uint32_t v = 0;
    for (int i = 0; i < 4; ++i) v |= (uint32_t)gpu_get() << (8 * i);
    return v;
}

static uint32_t crc32(const uint8_t* d, uint32_t n)
{
    uint32_t c = 0xFFFFFFFFu;
    for (uint32_t i = 0; i < n; ++i) {
        c ^= d[i];
        for (int k = 0; k < 8; ++k) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u)));
    }
    return ~c;
}

/* ---------------------------------------------------------------------------
 *  Software rasterizer on the ARM: the SAME algorithm as golden/golden.cpp.
 *  This is the fair CPU baseline: same chip, ARM Cortex-A9 vs FPGA fabric.
 * ------------------------------------------------------------------------- */
typedef struct { int16_t x0, y0, x1, y1, x2, y2; int32_t z0, dzdx, dzdy; uint16_t color; } Tri;

static Tri      tris[1024];
static uint16_t sw_depth[W * H], sw_color[W * H];

static int16_t rd16(const uint8_t* p) { return (int16_t)(p[0] | (p[1] << 8)); }
static int32_t rd32(const uint8_t* p) { return (int32_t)((uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24)); }
static int not_top_left(int ax, int ay, int bx, int by) { int dx = bx - ax, dy = by - ay; return !((dy > 0) || (dy == 0 && dx < 0)); }

static void sw_raster(const Tri* t)
{
    int32_t a0 = t->y2 - t->y1, b0 = t->x1 - t->x2, a1 = t->y0 - t->y2, b1 = t->x2 - t->x0;
    int32_t a2 = t->y1 - t->y0, b2 = t->x0 - t->x1;
    int32_t area = (t->x2 - t->x0) * (t->y1 - t->y0) - (t->y2 - t->y0) * (t->x1 - t->x0);
    int minx = t->x0, maxx = t->x0, miny = t->y0, maxy = t->y0;
    if (t->x1 < minx) minx = t->x1;  if (t->x2 < minx) minx = t->x2;
    if (t->x1 > maxx) maxx = t->x1;  if (t->x2 > maxx) maxx = t->x2;
    if (t->y1 < miny) miny = t->y1;  if (t->y2 < miny) miny = t->y2;
    if (t->y1 > maxy) maxy = t->y1;  if (t->y2 > maxy) maxy = t->y2;
    if (minx < 0) minx = 0;  if (maxx > W - 1) maxx = W - 1;
    if (miny < 0) miny = 0;  if (maxy > H - 1) maxy = H - 1;
    if (area <= 0 || minx > maxx || miny > maxy) return;

    int32_t r0 = (minx - t->x1) * a0 + (miny - t->y1) * b0 - not_top_left(t->x1, t->y1, t->x2, t->y2);
    int32_t r1 = (minx - t->x2) * a1 + (miny - t->y2) * b1 - not_top_left(t->x2, t->y2, t->x0, t->y0);
    int32_t r2 = (minx - t->x0) * a2 + (miny - t->y0) * b2 - not_top_left(t->x0, t->y0, t->x1, t->y1);
    int64_t zr = (int64_t)t->z0 + (int64_t)t->dzdx * (minx - t->x0) + (int64_t)t->dzdy * (miny - t->y0);
    int addr_r = miny * W + minx;
    for (int y = miny; y <= maxy; ++y) {
        int32_t e0 = r0, e1 = r1, e2 = r2;  int64_t z = zr;  int addr = addr_r;
        for (int x = minx; x <= maxx; ++x) {
            if (e0 >= 0 && e1 >= 0 && e2 >= 0) {
                int64_t d = z >> 16;
                uint16_t dd = d < 0 ? 0 : d > 65535 ? 0xFFFF : (uint16_t)d;
                if (dd < sw_depth[addr]) { sw_depth[addr] = dd; sw_color[addr] = t->color; }
            }
            e0 += a0;  e1 += a1;  e2 += a2;  z += t->dzdx;  addr++;
        }
        r0 += b0;  r1 += b1;  r2 += b2;  zr += t->dzdy;  addr_r += W;
    }
}

static double us(XTime a, XTime b) { return (double)(b - a) * 1e6 / COUNTS_PER_SECOND; }

static int cmd_size(uint8_t op) { return op == 0x01 ? 3 : op == 0x02 ? 27 : 1; }

/* ===========================================================================
 *  main
 * ======================================================================== */
int main(void)
{
    printf("\r\n=== Mini GPU on Zynq ===\r\n");
    printf("ID = %08lx (expect 47505501)\r\n", (unsigned long)Xil_In32(GPU_BASE + REG_ID));

    XTime t0, t1, tUp0 = 0, tUp1 = 0;
    double upload_us = 0, draw_us = 0, read_us = 0;
    uint32_t cycles = 0, tested = 0, inside = 0, written = 0;

    uint32_t i = 0;
    while (i < SCENE_LEN) {
        uint8_t op = SCENE[i];
        int n = cmd_size(op);

        if (op == 0x02 && tUp0 == 0) XTime_GetTime(&tUp0);
        if (op != 0x02 && tUp0 != 0 && tUp1 == 0) { XTime_GetTime(&tUp1); upload_us = us(tUp0, tUp1); }

        XTime_GetTime(&t0);
        for (int k = 0; k < n; ++k) gpu_put(SCENE[i + k]);

        if (op == 0x01 || op == 0x05) {                    /* CLEAR, RESET: ACK */
            if (gpu_get() != 0xA0) printf("bad ACK\r\n");
        } else if (op == 0x03) {                           /* DRAW */
            if (gpu_get() != 0xD0) printf("bad DRAW reply\r\n");
            cycles = get32();  tested = get32();  inside = get32();  written = get32();
            XTime_GetTime(&t1);  draw_us = us(t0, t1);
        } else if (op == 0x04) {                           /* READ */
            for (int p = 0; p < W * H; ++p) {
                uint16_t lo = gpu_get();
                frame[p] = (uint16_t)(lo | ((uint16_t)gpu_get() << 8));
            }
            XTime_GetTime(&t1);  read_us = us(t0, t1);
        }
        i += n;
    }

    printf("cycles  = %lu  (%.3f ms at 100 MHz)\r\n", (unsigned long)cycles, cycles / 100000.0);
    printf("tested  = %lu\r\ninside  = %lu\r\nwritten = %lu\r\n",
           (unsigned long)tested, (unsigned long)inside, (unsigned long)written);
    printf("crc32   = %08lx\r\n", (unsigned long)crc32((const uint8_t*)frame, sizeof(frame)));
    printf("upload_us = %.1f\r\ndraw_roundtrip_us = %.1f\r\nreadback_us = %.1f\r\n",
           upload_us, draw_us, read_us);

    /* ---- same scene in software on the ARM ---- */
    int ntri = 0;
    uint16_t clear_color = 0;
    for (uint32_t j = 0; j < SCENE_LEN; j += cmd_size(SCENE[j])) {
        const uint8_t* p = &SCENE[j + 1];
        if (SCENE[j] == 0x01) clear_color = (uint16_t)rd16(p);
        if (SCENE[j] == 0x02 && ntri < 1024) {
            Tri* t = &tris[ntri++];
            t->x0 = rd16(p); t->y0 = rd16(p + 2); t->x1 = rd16(p + 4); t->y1 = rd16(p + 6);
            t->x2 = rd16(p + 8); t->y2 = rd16(p + 10);
            t->z0 = rd32(p + 12); t->dzdx = rd32(p + 16); t->dzdy = rd32(p + 20);
            t->color = (uint16_t)rd16(p + 24);
        }
    }
    const int RUNS = 20;
    double arm_total = 0;
    for (int r = 0; r < RUNS; ++r) {
        for (int q = 0; q < W * H; ++q) { sw_depth[q] = 0xFFFF; sw_color[q] = clear_color; }
        XTime_GetTime(&t0);
        for (int k = 0; k < ntri; ++k) sw_raster(&tris[k]);
        XTime_GetTime(&t1);
        arm_total += us(t0, t1);
    }
    printf("arm_sw_us = %.1f  (avg of %d, Cortex-A9 software, same algorithm)\r\n", arm_total / RUNS, RUNS);
    printf("arm_crc32 = %08lx  (must equal crc32 above)\r\n",
           (unsigned long)crc32((const uint8_t*)sw_color, sizeof(sw_color)));
    printf("fpga_vs_arm_speedup = %.2f\r\n", (arm_total / RUNS) / (cycles / 100.0));

#if DUMP_FRAME
    printf("FRAME_BEGIN\r\n");
    for (int p = 0; p < W * H; ++p) {
        printf("%04x", frame[p]);
        if ((p % 32) == 31) printf("\r\n");
    }
    printf("FRAME_END\r\n");
#endif
    printf("=== done ===\r\n");
    return 0;
}
