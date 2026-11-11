#!/usr/bin/env python3
"""
==============================================================================
 File    : pc/make_report.py
 Purpose : Collects every results/<scene>_<platform>.json written by
           compare.py into ONE table for the paper:
             results/results_table.csv  and  results/results_table.md
 Usage   : python pc/make_report.py [--mhz 100]
 Columns : FPGA time = cycles / clock. Speedup = CPU raster time / FPGA time.
           "end-to-end" adds the measured upload + readback time (board runs only).
==============================================================================
"""
import argparse
import csv
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mhz", type=float, default=100.0)
    a = ap.parse_args()
    rows = []
    for path in sorted(glob.glob(os.path.join(ROOT, "results", "*_*.json"))):
        if path.endswith(("_golden.json", "_timing.json")):
            continue
        r = json.load(open(path))
        if "fpga" not in r:
            continue
        cyc = r["fpga"]["cycles"]
        fpga_ms = cyc / (a.mhz * 1e3)
        row = {
            "scene": r["scene"], "platform": r["platform"], "pass": r["pass"],
            "triangles": r["triangles"], "culled": r["culled"],
            "pixels_tested": r["fpga"]["tested"], "pixels_written": r["fpga"]["written"],
            "fpga_cycles": cyc, "fpga_ms": round(fpga_ms, 4),
            "cpu_ms": round(r["cpu_ms_per_frame"], 4),
            "speedup_vs_cpu": round(r["cpu_ms_per_frame"] / fpga_ms, 2) if fpga_ms else None,
            "Mpix_per_s": round(r["fpga"]["tested"] / fpga_ms / 1e3, 1) if fpga_ms else None,
            "tris_per_s": round(r["triangles"] / fpga_ms * 1e3) if fpga_ms else None,
            "cycles_per_tri": round(cyc / r["triangles"], 1) if r["triangles"] else None,
            "upload_ms": None, "readback_ms": None, "end_to_end_ms": None,
        }
        ht = r.get("host_timing")
        if ht:
            row["upload_ms"] = round(ht["upload_s"] * 1e3, 2)
            row["readback_ms"] = round(ht["readback_s"] * 1e3, 2)
            row["end_to_end_ms"] = round(row["upload_ms"] + fpga_ms + row["readback_ms"], 2)
        rows.append(row)
    if not rows:
        print("no results yet: run compare.py first")
        return
    keys = list(rows[0].keys())
    with open(os.path.join(ROOT, "results", "results_table.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(ROOT, "results", "results_table.md"), "w") as f:
        f.write("| " + " | ".join(keys) + " |\n|" + "---|" * len(keys) + "\n")
        for r in rows:
            f.write("| " + " | ".join("" if r[k] is None else str(r[k]) for k in keys) + " |\n")
    for r in rows:
        print(f"{r['scene']:8s} {r['platform']:7s} pass={r['pass']}  fpga {r['fpga_ms']} ms  "
              f"cpu {r['cpu_ms']} ms  x{r['speedup_vs_cpu']}  {r['Mpix_per_s']} Mpix/s")
    print("wrote results/results_table.csv and .md")


if __name__ == "__main__":
    main()
