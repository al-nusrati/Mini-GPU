/*
 * ============================================================================
 *  File    : golden/golden.cpp
 *  Purpose : Bit-exact software model of the FPGA GPU + the CPU baseline.
 *            Reads the SAME command stream the board receives and produces:
 *              results/<name>_golden.bin   framebuffer, W*H x uint16 little-endian
 *              results/<name>_golden.json  counters, CRC32, predicted cycles,
 *                                          CPU time per frame
 *
 *  Build   : g++ -O2 -std=c++17 golden/golden.cpp -o golden/golden
 *  Usage   : golden/golden scenes/cube.bin results/cube [W H]
 *
 *  Pseudocode
 *    parse commands exactly like rtl/gpu_core.sv
 *    DRAW: for each triangle, the SAME integer steps as rtl/rasterizer.sv:
 *          setup -> start values at box corner -> add A per pixel, B per row
 *    count tested / inside / written pixels and predicted cycles
 *    re-run the raster loop many times to measure CPU time per frame
 * ============================================================================
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <chrono>
#include <string>
#include <vector>

namespace {

/* ---------------------------------------------------------------------------
 *  Data
 * ------------------------------------------------------------------------- */
struct Tri {
    int16_t x0, y0, x1, y1, x2, y2;
    int32_t z0, dzdx, dzdy;
    uint16_t color;
};

struct Counters {
    uint64_t tested = 0, inside = 0, written = 0, culled = 0, cycles_raster = 0;
};

const int CYCLES_CULLED = 5;     // FETCH LATCH SETUP1 SETUP2 NEXT
const int CYCLES_DRAWN  = 6;     // + SETUP3, plus one per box pixel
const int CYCLES_FIXED  = 3;     // start + DONE + reply cycle (measured in sim)

int W = 160, H = 120;

/* ---------------------------------------------------------------------------
 *  Helpers
 * ------------------------------------------------------------------------- */
int16_t rd16(const uint8_t* p) { return (int16_t)(p[0] | (p[1] << 8)); }
int32_t rd32(const uint8_t* p) { return (int32_t)((uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24)); }

bool notTopLeft(int ax, int ay, int bx, int by)
{
    int dx = bx - ax, dy = by - ay;
    return !((dy > 0) || (dy == 0 && dx < 0));
}

uint16_t satDepth(int64_t z)
{
    int64_t d = z >> 16;                       // arithmetic shift, same as RTL
    if (d < 0) return 0;
    if (d > 65535) return 0xFFFF;
    return (uint16_t)d;
}

uint32_t crc32(const uint8_t* data, size_t n)
{
    uint32_t c = 0xFFFFFFFFu;
    for (size_t i = 0; i < n; ++i) {
        c ^= data[i];
        for (int k = 0; k < 8; ++k) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u)));
    }
    return ~c;
}

/* ---------------------------------------------------------------------------
 *  rasterTri: the hardware algorithm, step for step
 * ------------------------------------------------------------------------- */
void rasterTri(const Tri& t, uint16_t* depth, uint16_t* color, Counters& k)
{
    // SETUP1
    int32_t a0 = t.y2 - t.y1, b0 = t.x1 - t.x2;
    int32_t a1 = t.y0 - t.y2, b1 = t.x2 - t.x0;
    int32_t a2 = t.y1 - t.y0, b2 = t.x0 - t.x1;
    int32_t bias0 = notTopLeft(t.x1, t.y1, t.x2, t.y2);
    int32_t bias1 = notTopLeft(t.x2, t.y2, t.x0, t.y0);
    int32_t bias2 = notTopLeft(t.x0, t.y0, t.x1, t.y1);
    int32_t area  = (t.x2 - t.x0) * (t.y1 - t.y0) - (t.y2 - t.y0) * (t.x1 - t.x0);

    int minx = t.x0 < t.x1 ? t.x0 : t.x1;  if (t.x2 < minx) minx = t.x2;
    int maxx = t.x0 > t.x1 ? t.x0 : t.x1;  if (t.x2 > maxx) maxx = t.x2;
    int miny = t.y0 < t.y1 ? t.y0 : t.y1;  if (t.y2 < miny) miny = t.y2;
    int maxy = t.y0 > t.y1 ? t.y0 : t.y1;  if (t.y2 > maxy) maxy = t.y2;
    if (minx < 0)     minx = 0;
    if (maxx > W - 1) maxx = W - 1;
    if (miny < 0)     miny = 0;
    if (maxy > H - 1) maxy = H - 1;

    // SETUP2: cull
    if (area <= 0 || minx > maxx || miny > maxy) {
        k.culled++;
        k.cycles_raster += CYCLES_CULLED;
        return;
    }

    // SETUP3: start values at the top-left corner of the box
    int32_t r0 = (minx - t.x1) * a0 + (miny - t.y1) * b0 - bias0;
    int32_t r1 = (minx - t.x2) * a1 + (miny - t.y2) * b1 - bias1;
    int32_t r2 = (minx - t.x0) * a2 + (miny - t.y0) * b2 - bias2;
    int64_t zr = (int64_t)t.z0 + (int64_t)t.dzdx * (minx - t.x0) + (int64_t)t.dzdy * (miny - t.y0);
    int addr_r = miny * W + minx;

    // WALK
    for (int y = miny; y <= maxy; ++y) {
        int32_t e0 = r0, e1 = r1, e2 = r2;
        int64_t z = zr;
        int addr = addr_r;
        for (int x = minx; x <= maxx; ++x) {
            k.tested++;
            if (e0 >= 0 && e1 >= 0 && e2 >= 0) {
                k.inside++;
                uint16_t d = satDepth(z);
                if (d < depth[addr]) {
                    depth[addr] = d;
                    color[addr] = t.color;
                    k.written++;
                }
            }
            e0 += a0;  e1 += a1;  e2 += a2;  z += t.dzdx;  addr++;
        }
        r0 += b0;  r1 += b1;  r2 += b2;  zr += t.dzdy;  addr_r += W;
    }
    k.cycles_raster += CYCLES_DRAWN + (uint64_t)(maxx - minx + 1) * (maxy - miny + 1);
}

void drawAll(const std::vector<Tri>& tris, uint16_t* depth, uint16_t* color, Counters& k)
{
    for (const Tri& t : tris) rasterTri(t, depth, color, k);
}

bool checkRange(const Tri& t)
{
    const int v[6] = { t.x0, t.y0, t.x1, t.y1, t.x2, t.y2 };
    for (int c : v) if (c < -2048 || c > 2047) return false;
    return true;
}

} // namespace

/* ===========================================================================
 *  main
 * ======================================================================== */
int main(int argc, char** argv)
{
    if (argc < 3) { fprintf(stderr, "usage: golden scene.bin out_prefix [W H]\n"); return 1; }
    if (argc >= 5) { W = atoi(argv[3]); H = atoi(argv[4]); }

    FILE* f = fopen(argv[1], "rb");
    if (!f) { fprintf(stderr, "cannot open %s\n", argv[1]); return 1; }
    std::vector<uint8_t> s;
    for (int c; (c = fgetc(f)) != EOF;) s.push_back((uint8_t)c);
    fclose(f);

    std::vector<uint16_t> depth(W * H, 0), color(W * H, 0);
    std::vector<Tri> tris;
    Counters k;
    uint16_t clearColor = 0;
    int draws = 0;

    // ---- parse the command stream (same as gpu_core.sv) -------------------
    for (size_t i = 0; i < s.size();) {
        uint8_t op = s[i++];
        if (op == 0x01) {                                       // CLEAR
            clearColor = (uint16_t)rd16(&s[i]);  i += 2;
            for (int p = 0; p < W * H; ++p) { depth[p] = 0xFFFF; color[p] = clearColor; }
        } else if (op == 0x02) {                                // LOAD_TRI
            const uint8_t* p = &s[i];  i += 26;
            Tri t;
            t.x0 = rd16(p);  t.y0 = rd16(p + 2);  t.x1 = rd16(p + 4);  t.y1 = rd16(p + 6);
            t.x2 = rd16(p + 8);  t.y2 = rd16(p + 10);
            t.z0 = rd32(p + 12);  t.dzdx = rd32(p + 16);  t.dzdy = rd32(p + 20);
            t.color = (uint16_t)rd16(p + 24);
            if (!checkRange(t)) { fprintf(stderr, "triangle %zu out of -2048..2047\n", tris.size()); return 1; }
            if (tris.size() < 1024) tris.push_back(t);
        } else if (op == 0x03) {                                // DRAW
            k = Counters();
            drawAll(tris, depth.data(), color.data(), k);
            draws++;
        } else if (op == 0x05) {                                // RESET_TRIS
            tris.clear();
        }
        // 0x00 PING and 0x04 READ change nothing
    }

    // ---- CPU timing: same raster work, repeated ---------------------------
    std::vector<uint16_t> d2(W * H), c2(W * H);
    double rasterMs = 0, wallMs = 0;  int runs = 0;       // time only the raster loop
    auto t0 = std::chrono::steady_clock::now();
    while (wallMs < 300.0 || runs < 5) {
        for (int p = 0; p < W * H; ++p) { d2[p] = 0xFFFF; c2[p] = clearColor; }
        auto a = std::chrono::steady_clock::now();
        Counters tmp;
        drawAll(tris, d2.data(), c2.data(), tmp);
        auto b = std::chrono::steady_clock::now();
        rasterMs += std::chrono::duration<double, std::milli>(b - a).count();
        wallMs    = std::chrono::duration<double, std::milli>(b - t0).count();
        runs++;
    }
    double cpuMs = rasterMs / runs;

    // ---- outputs ------------------------------------------------------------
    std::vector<uint8_t> fb(W * H * 2);
    for (int p = 0; p < W * H; ++p) { fb[2 * p] = color[p] & 0xFF;  fb[2 * p + 1] = color[p] >> 8; }
    uint32_t crc = crc32(fb.data(), fb.size());

    std::string pre = argv[2];
    FILE* fo = fopen((pre + "_golden.bin").c_str(), "wb");
    if (!fo) { fprintf(stderr, "cannot write %s_golden.bin (does the folder exist?)\n", pre.c_str()); return 1; }
    fwrite(fb.data(), 1, fb.size(), fo);  fclose(fo);

    uint64_t cycles = draws ? k.cycles_raster + CYCLES_FIXED : 0;
    FILE* fj = fopen((pre + "_golden.json").c_str(), "w");
    fprintf(fj, "{\n  \"width\": %d, \"height\": %d,\n  \"triangles\": %zu, \"culled\": %llu,\n"
                "  \"tested\": %llu, \"inside\": %llu, \"written\": %llu,\n"
                "  \"predicted_cycles\": %llu,\n  \"crc32\": \"%08x\",\n  \"cpu_ms_per_frame\": %.6f, \"cpu_runs\": %d\n}\n",
            W, H, tris.size(), (unsigned long long)k.culled,
            (unsigned long long)k.tested, (unsigned long long)k.inside, (unsigned long long)k.written,
            (unsigned long long)cycles, crc, cpuMs, runs);
    fclose(fj);

    printf("golden: %zu tris (%llu culled), tested %llu, inside %llu, written %llu\n",
           tris.size(), (unsigned long long)k.culled, (unsigned long long)k.tested,
           (unsigned long long)k.inside, (unsigned long long)k.written);
    printf("        predicted FPGA cycles %llu, CRC32 %08x, CPU %.4f ms/frame (%d runs)\n",
           (unsigned long long)cycles, crc, cpuMs, runs);
    return 0;
}
