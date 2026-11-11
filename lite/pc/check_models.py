#!/usr/bin/env python3
"""
==============================================================================
 File    : pc/check_models.py      (Member 2's tool: no FPGA needed)
 Purpose : Checks every Blender export in models/ and shows how it will look
           on the 160x120 GPU, using the bit-exact golden model.
 Usage   : python pc/check_models.py                 (all models/*.obj)
           python pc/check_models.py models/teapot.obj --angles 0 45 90
 For each model and angle:
   - loads the .obj (+ .mtl colors), checks the triangle budget (<= 1024)
   - builds the scene, runs golden, writes a preview PNG
 Writes  : results/preview_<model>_a<angle>.png
           results/models_report.csv  (triangles, culled, pixels, cycles, CPU ms)
 Pass    : every model OK, previews look right (front faces, colors, size)
==============================================================================
"""
import argparse
import csv
import glob
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_scene as M   # noqa: E402
import protocol as P     # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(ROOT, "golden", "golden.exe" if os.name == "nt" else "golden")
LIMIT = 1024


def check_one(path, angle, tilt):
    name = os.path.splitext(os.path.basename(path))[0]
    verts, faces = M.load_obj(path)
    row = {"model": name, "angle": angle, "vertices": len(verts), "triangles": len(faces),
           "materials": len({f[3] for f in faces}), "status": "OK", "note": ""}
    if len(faces) > LIMIT:
        row["status"] = "TOO BIG"
        row["note"] = f"{len(faces)} > {LIMIT}: Decimate ratio about {LIMIT / len(faces):.2f}"
        return row
    try:
        data = M.scene_obj(path, angle, tilt)
    except ValueError as e:                      # vertex outside -2048..2047
        row["status"], row["note"] = "BAD", str(e)
        return row
    scene = f"preview_{name}_a{int(angle)}"
    M.save(scene, data)
    subprocess.run([GOLDEN, f"scenes/{scene}.bin", f"results/{scene}"], check=True, cwd=ROOT,
                   stdout=subprocess.DEVNULL)
    g = json.load(open(os.path.join(ROOT, "results", f"{scene}_golden.json")))
    fb = open(os.path.join(ROOT, "results", f"{scene}_golden.bin"), "rb").read()
    P.write_png(os.path.join(ROOT, "results", f"{scene}.png"), P.frame_to_rgb(fb))
    row.update({"culled": g["culled"], "pixels_tested": g["tested"], "pixels_written": g["written"],
                "fpga_cycles": g["predicted_cycles"], "fpga_ms_at_100MHz": round(g["predicted_cycles"] / 1e5, 4),
                "cpu_ms": round(g["cpu_ms_per_frame"], 4)})
    cover = g["written"] / (P.W * P.H)
    if cover < 0.05:
        row["note"] = "model looks very small on screen"
    if len(faces) and g["culled"] == len(faces):
        row["status"], row["note"] = "CHECK", "every face culled: normals/winding flipped? (Blender: Recalculate Outside)"
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="*")
    ap.add_argument("--angles", type=float, nargs="+", default=[0, 45, 90])
    ap.add_argument("--tilt", type=float, default=15)
    a = ap.parse_args()
    paths = a.models or sorted(glob.glob(os.path.join(ROOT, "models", "*.obj")))
    if not paths:
        sys.exit("no .obj files in models/")
    if not os.path.exists(GOLDEN):
        hint = r"golden\build.bat" if os.name == "nt" else "g++ -O2 -std=c++17 golden/golden.cpp -o golden/golden"
        sys.exit("build the golden model first: " + hint)

    rows = []
    for p in paths:
        for ang in a.angles:
            r = check_one(p, ang, a.tilt)
            rows.append(r)
            print(f"{r['model']:14s} a={ang:5.0f}  tris={r['triangles']:5d}  {r['status']:8s} "
                  f"{('cycles=' + str(r['fpga_cycles'])) if 'fpga_cycles' in r else ''}  {r['note']}")
            if r["status"] == "TOO BIG":
                break
    keys = []
    for r in rows:
        keys += [k for k in r if k not in keys]
    out = os.path.join(ROOT, "results", "models_report.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print("previews: results/preview_*.png   report:", out)


if __name__ == "__main__":
    main()
