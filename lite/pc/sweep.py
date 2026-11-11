#!/usr/bin/env python3
"""
==============================================================================
 File    : pc/sweep.py
 Purpose : The main paper experiment in one command: how does speed change
           with triangle SIZE? (big triangles = pixel-bound, tiny = setup-bound)
           For each size: make scene -> golden (CPU time + cycle model)
           -> optionally run on the Basys3 and compare.
 Usage   : python pc/sweep.py                       (golden only, no board)
           python pc/sweep.py --port COM5           (also runs on the Basys3)
           python pc/sweep.py --sizes 4 8 16 32 64 --count 500
 Writes  : results/sweep.csv
==============================================================================
"""
import argparse
import csv
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
GOLDEN = os.path.join(ROOT, "golden", "golden.exe" if os.name == "nt" else "golden")


def run(args):
    print("  $", " ".join(args))
    subprocess.run(args, check=True, cwd=ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="+", default=[4, 8, 16, 32, 64])
    ap.add_argument("--count", type=int, default=500)
    ap.add_argument("--port")
    ap.add_argument("--baud", type=int, default=921600)
    ap.add_argument("--mhz", type=float, default=100.0)
    a = ap.parse_args()

    rows = []
    for size in a.sizes:
        name = f"rand_s{size}"
        print(f"== size {size} px ==")
        run([PY, "pc/make_scene.py", "random", "--count", str(a.count), "--size", str(size), "--name", name])
        run([GOLDEN, f"scenes/{name}.bin", f"results/{name}"])
        g = json.load(open(os.path.join(ROOT, "results", f"{name}_golden.json")))
        row = {"size_px": size, "triangles": g["triangles"], "culled": g["culled"],
               "pixels_tested": g["tested"], "predicted_cycles": g["predicted_cycles"],
               "fpga_ms_model": round(g["predicted_cycles"] / (a.mhz * 1e3), 4),
               "cpu_ms": round(g["cpu_ms_per_frame"], 4),
               "board_cycles": None, "board_pass": None, "upload_ms": None, "readback_ms": None}
        if a.port:
            run([PY, "pc/run_board.py", name, "--port", a.port, "--baud", str(a.baud), "--draws", "5"])
            res = subprocess.run([PY, "pc/compare.py", name, f"results/{name}_basys3.bin", "--tag", "basys3",
                                  "--timing", f"results/{name}_basys3_timing.json"], cwd=ROOT)
            r = json.load(open(os.path.join(ROOT, "results", f"{name}_basys3.json")))
            row["board_cycles"] = r["fpga"]["cycles"]
            row["board_pass"] = res.returncode == 0
            row["upload_ms"] = round(r["host_timing"]["upload_s"] * 1e3, 2)
            row["readback_ms"] = round(r["host_timing"]["readback_s"] * 1e3, 2)
        rows.append(row)

    path = os.path.join(ROOT, "results", "sweep.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("\nsize  tested   fpga_ms  cpu_ms   board")
    for r in rows:
        print(f"{r['size_px']:4d}  {r['pixels_tested']:7d}  {r['fpga_ms_model']:7.3f}  {r['cpu_ms']:7.3f}  "
              f"{'' if r['board_pass'] is None else ('PASS' if r['board_pass'] else 'FAIL')}")
    print("wrote", path)


if __name__ == "__main__":
    main()
