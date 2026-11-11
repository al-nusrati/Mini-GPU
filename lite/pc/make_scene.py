#!/usr/bin/env python3
"""
==============================================================================
 File    : pc/make_scene.py
 Purpose : Builds test scenes as GPU command streams.
           The host (PC / ARM) does the 3D transform + projection + lighting;
           the FPGA does triangle setup, rasterization and the depth test.

 Usage   : python pc/make_scene.py cube   [--angle 30]
           python pc/make_scene.py sphere [--angle 20] [--rings 12 --segs 24]
           python pc/make_scene.py random [--count 500 --size 20 --seed 1]
           python pc/make_scene.py grid      (fill-rule test: covers screen exactly once)
           python pc/make_scene.py overlap   (depth-test check)
           python pc/make_scene.py obj models/teapot.obj [--angle 30 --tilt 15]
                                     (Blender model; see docs/methodology.html, stage S2b)

 Writes  : scenes/<name>.bin   raw bytes, sent as-is to the board
           scenes/<name>.hex   4 length bytes + scene, one byte per line (testbench)
           zynq/scene_<name>.h C array, for the Zynq ARM program

 Every scene = RESET_TRIS, CLEAR, LOAD_TRI ..., DRAW, READ
==============================================================================
"""
import argparse
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import protocol as P   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BG = P.rgb444(0.08, 0.10, 0.14)


# ---------------------------------------------------------------- 3D helpers
def rot(v, ax, ay):
    x, y, z = v
    cy, sy = math.cos(ay), math.sin(ay)
    x, z = cy * x + sy * z, -sy * x + cy * z
    cx, sx = math.cos(ax), math.sin(ax)
    y, z = cx * y - sx * z, sx * y + cx * z
    return (x, y, z)


def sub(a, b):   return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def norm(a):
    l = math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2) or 1.0
    return (a[0] / l, a[1] / l, a[2] / l)


NEAR, FAR, CAM_Z = 0.5, 10.0, 3.0


def project(v):
    """camera at z = -CAM_Z looking +z. Returns integer pixel x, y and depth 0..65535."""
    zc = v[2] + CAM_Z
    f = P.H * 0.9
    sx = int(round(P.W / 2 + f * v[0] / zc))
    sy = int(round(P.H / 2 - f * v[1] / zc))
    d = (1 / zc - 1 / NEAR) / (1 / FAR - 1 / NEAR)          # 0 near .. 1 far, affine in screen
    return (sx, sy), max(0.0, min(65535.0, d * 65535.0))


LIGHT = norm((-0.4, 0.6, -0.7))                     # direction TOWARD the light (up-left, camera side)


def shaded_tri(world, base, center=None):
    """world: 3 vertices after rotation. If center is given, the order is fixed
    so the normal points away from it (outward). Otherwise the order must
    already be counter-clockwise seen from OUTSIDE the object.
    Flat lighting on the host, then projection. The FPGA culls back faces."""
    n = norm(cross(sub(world[1], world[0]), sub(world[2], world[0])))
    if center is not None:
        c = [sum(v[k] for v in world) / 3 - center[k] for k in range(3)]
        if n[0] * c[0] + n[1] * c[1] + n[2] * c[2] < 0:
            world = [world[0], world[2], world[1]]
            n = (-n[0], -n[1], -n[2])
    lam = max(0.0, n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2])
    k = 0.25 + 0.75 * lam
    col = P.rgb444(base[0] * k, base[1] * k, base[2] * k)
    # y flips between world (up) and screen (down), so the screen order is
    # reversed: front faces then have positive area = drawn by the FPGA
    pts, zs = zip(*(project(v) for v in (world[0], world[2], world[1])))
    return P.tri_from_float_depth(list(pts), list(zs), col)


def wrap(cmds):
    return P.cmd_reset() + P.cmd_clear(BG) + b"".join(cmds) + P.cmd_draw() + P.cmd_read()


# ---------------------------------------------------------------- scenes
def scene_cube(a):
    s = 0.8
    v = [(-s, -s, -s), (s, -s, -s), (s, s, -s), (-s, s, -s),
         (-s, -s, s), (s, -s, s), (s, s, s), (-s, s, s)]
    faces = [((0, 3, 2, 1), (1.0, 0.3, 0.3)), ((4, 5, 6, 7), (0.3, 1.0, 0.3)),
             ((0, 1, 5, 4), (0.3, 0.3, 1.0)), ((3, 7, 6, 2), (1.0, 1.0, 0.3)),
             ((0, 4, 7, 3), (1.0, 0.3, 1.0)), ((1, 2, 6, 5), (0.3, 1.0, 1.0))]
    ax, ay = math.radians(a * 0.7), math.radians(a)
    w = [rot(p, ax, ay) for p in v]
    cmds = []
    for (i0, i1, i2, i3), col in faces:
        cmds.append(shaded_tri([w[i0], w[i1], w[i2]], col))
        cmds.append(shaded_tri([w[i0], w[i2], w[i3]], col))
    return wrap(cmds)


def scene_sphere(a, rings, segs):
    ax, ay = math.radians(25), math.radians(a)
    pt = lambda r, s: rot((math.sin(math.pi * r / rings) * math.cos(2 * math.pi * s / segs),
                           math.cos(math.pi * r / rings),
                           math.sin(math.pi * r / rings) * math.sin(2 * math.pi * s / segs)), ax, ay)
    cmds = []
    for r in range(rings):
        for s in range(segs):
            p00, p01, p10, p11 = pt(r, s), pt(r, s + 1), pt(r + 1, s), pt(r + 1, s + 1)
            col = (0.95, 0.6, 0.2) if (r + s) % 2 else (0.9, 0.85, 0.8)
            if r != 0:
                cmds.append(shaded_tri([p00, p01, p10], col, (0, 0, 0)))
            if r != rings - 1:
                cmds.append(shaded_tri([p01, p11, p10], col, (0, 0, 0)))
    return wrap(cmds)


def _fix_winding(v):
    (x0, y0), (x1, y1), (x2, y2) = v
    area = (x2 - x0) * (y1 - y0) - (y2 - y0) * (x1 - x0)
    return [v[0], v[2], v[1]] if area < 0 else v


def scene_random(count, size, seed):
    rng = random.Random(seed)
    cmds = []
    for _ in range(count):
        cx, cy = rng.uniform(0, P.W), rng.uniform(0, P.H)
        v = [(int(round(cx + rng.uniform(-size, size) / 2)), int(round(cy + rng.uniform(-size, size) / 2)))
             for _ in range(3)]
        v = _fix_winding(v)
        zs = [rng.uniform(1000, 64000) for _ in range(3)]
        cmds.append(P.tri_from_float_depth(v, zs, rng.randrange(1, 4096)))
    return wrap(cmds)


def scene_grid():
    """Cells of 20x20 covering the whole 160x120 screen exactly once.
    Pass condition: inside == W*H (every pixel covered by exactly one triangle)."""
    cmds, c = [], 20
    for j in range(P.H // c):
        for i in range(P.W // c):
            x0, y0, x1, y1 = i * c, j * c, (i + 1) * c, (j + 1) * c
            # include the far edge of the last row/col by extending past the screen
            tl, tr, bl, br = (x0, y0), (x1, y0), (x0, y1), (x1, y1)
            col = P.rgb444(0.3 + 0.7 * ((i + j) % 2), 0.5, 0.3 + 0.07 * i)
            tris = [[tl, tr, br], [tl, br, bl]] if (i + j) % 2 == 0 else [[tl, tr, bl], [tr, br, bl]]
            for t in tris:
                cmds.append(P.tri_from_float_depth(_fix_winding(t), [30000] * 3, col))
    return wrap(cmds)


def scene_overlap():
    """A far big triangle drawn FIRST, a near one SECOND, then a far one LAST.
    The near one must stay on top everywhere they overlap."""
    cmds = [
        P.tri_from_float_depth(_fix_winding([(10, 10), (150, 20), (60, 110)]), [50000] * 3, P.rgb444(0.9, 0.2, 0.2)),
        P.tri_from_float_depth(_fix_winding([(40, 30), (140, 60), (30, 100)]), [10000, 20000, 15000], P.rgb444(0.2, 0.9, 0.2)),
        P.tri_from_float_depth(_fix_winding([(20, 50), (150, 50), (90, 115)]), [60000] * 3, P.rgb444(0.2, 0.3, 0.9)),
    ]
    return wrap(cmds)


# ---------------------------------------------------------------- Blender / OBJ models
def load_mtl(path):
    """name -> (r, g, b) from 'Kd' lines of a .mtl file (Blender writes these)."""
    colors, cur = {}, None
    if not os.path.exists(path):
        return colors
    for line in open(path, encoding="utf-8", errors="ignore"):
        t = line.split()
        if not t:
            continue
        if t[0] == "newmtl":
            cur = " ".join(t[1:])
        elif t[0] == "Kd" and cur is not None and len(t) >= 4:
            colors[cur] = tuple(max(0.0, min(1.0, float(x))) for x in t[1:4])
    return colors


def load_obj(path):
    """Reads a Wavefront .obj (Blender: File > Export > Wavefront).
    Returns (vertices, faces) where faces = [(i0, i1, i2, (r, g, b)), ...].
    Polygons with more than 3 corners are split as a fan. Negative indices work."""
    verts, faces = [], []
    colors, color = {}, (0.8, 0.8, 0.8)
    base = os.path.dirname(os.path.abspath(path))
    for line in open(path, encoding="utf-8", errors="ignore"):
        t = line.split()
        if not t or t[0].startswith("#"):
            continue
        if t[0] == "v":
            verts.append(tuple(float(x) for x in t[1:4]))
        elif t[0] == "mtllib":
            colors.update(load_mtl(os.path.join(base, " ".join(t[1:]))))
        elif t[0] == "usemtl":
            color = colors.get(" ".join(t[1:]), (0.8, 0.8, 0.8))
        elif t[0] == "f":
            idx = []
            for c in t[1:]:
                i = int(c.split("/")[0])
                idx.append(i - 1 if i > 0 else len(verts) + i)
            for k in range(1, len(idx) - 1):
                faces.append((idx[0], idx[k], idx[k + 1], color))
    if not verts or not faces:
        sys.exit(f"{path}: no vertices or faces found")
    return verts, faces


def scene_obj(path, a, tilt):
    """Centers the model, scales it to fit radius 1, then the SAME rotate /
    light / project path as the built-in scenes. OBJ faces are counter-clockwise
    seen from outside, so the FPGA culls the back faces."""
    verts, faces = load_obj(path)
    lo = [min(v[k] for v in verts) for k in range(3)]
    hi = [max(v[k] for v in verts) for k in range(3)]
    c = [(lo[k] + hi[k]) / 2 for k in range(3)]
    r = max(math.sqrt(sum((v[k] - c[k]) ** 2 for k in range(3))) for v in verts) or 1.0
    # Blender's default OBJ export is "-Z forward, Y up", so the model's front
    # faces +Z. Our camera looks along +Z, so turn 180 deg: angle 0 = Blender front view.
    ax, ay = math.radians(tilt), math.radians(a + 180)
    w = [rot(((v[0] - c[0]) / r, (v[1] - c[1]) / r, (v[2] - c[2]) / r), ax, ay) for v in verts]
    cmds = [shaded_tri([w[i0], w[i1], w[i2]], col) for i0, i1, i2, col in faces]
    return wrap(cmds)


# ---------------------------------------------------------------- output
def save(name, data):
    os.makedirs(os.path.join(ROOT, "scenes"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "zynq"), exist_ok=True)
    with open(os.path.join(ROOT, "scenes", name + ".bin"), "wb") as f:
        f.write(data)
    with open(os.path.join(ROOT, "scenes", name + ".hex"), "w", newline="\n") as f:
        head = len(data).to_bytes(4, "little")            # testbench reads the length first
        f.write("\n".join(f"{b:02x}" for b in head + data) + "\n")
    with open(os.path.join(ROOT, "zynq", f"scene_{name}.h"), "w", newline="\n") as f:
        f.write(f"// generated by pc/make_scene.py\n#pragma once\n#include <stdint.h>\n")
        f.write(f"static const uint32_t SCENE_LEN = {len(data)};\nstatic const uint8_t SCENE[] = {{\n")
        for i in range(0, len(data), 16):
            f.write("  " + ",".join(f"0x{b:02x}" for b in data[i:i + 16]) + ",\n")
        f.write("};\n")
    ntri = sum(1 for op, _ in P.split_commands(data) if op == P.LOAD_TRI)
    print(f"scenes/{name}.bin : {len(data)} bytes, {ntri} triangles")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene", choices=["cube", "sphere", "random", "grid", "overlap", "obj"])
    ap.add_argument("file", nargs="?", help="for scene obj: path to the .obj file")
    ap.add_argument("--tilt", type=float, default=15, help="obj: rotation about x in degrees")
    ap.add_argument("--name", help="output name (default: scene name)")
    ap.add_argument("--angle", type=float, default=30)
    ap.add_argument("--rings", type=int, default=12)
    ap.add_argument("--segs", type=int, default=24)
    ap.add_argument("--count", type=int, default=500)
    ap.add_argument("--size", type=float, default=20)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    if a.scene == "cube":      data = scene_cube(a.angle)
    elif a.scene == "sphere":  data = scene_sphere(a.angle, a.rings, a.segs)
    elif a.scene == "random":  data = scene_random(a.count, a.size, a.seed)
    elif a.scene == "grid":    data = scene_grid()
    elif a.scene == "overlap": data = scene_overlap()
    else:
        if not a.file:
            sys.exit("usage: make_scene.py obj models/name.obj [--angle 30 --tilt 15] [--name out]")
        data = scene_obj(a.file, a.angle, a.tilt)
        a.name = a.name or os.path.splitext(os.path.basename(a.file))[0]

    ntri = sum(1 for op, _ in P.split_commands(data) if op == P.LOAD_TRI)
    if ntri > 1024:
        sys.exit(f"{ntri} triangles > 1024 (the GPU's triangle memory). "
                 "In Blender: add a Decimate modifier and lower the ratio, then export again.")
    save(a.name or a.scene, data)


if __name__ == "__main__":
    main()
