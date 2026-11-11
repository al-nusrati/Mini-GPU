#!/usr/bin/env python3
"""
==============================================================================
 File    : pc/collect_vivado.py
 Purpose : Reads the Vivado reports written by vivado/core_compare.tcl and
           makes ONE table: results/fpga_compare.csv (+ prints it).
           Fmax estimate = 1000 / (10 ns - WNS).
 Usage   : python pc/collect_vivado.py
==============================================================================
"""
import csv
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")


def util(path):
    """-> dict name -> (used, available) for the rows we care about."""
    want = {"Slice LUTs": "LUT", "Slice Registers": "FF", "Block RAM Tile": "BRAM36", "DSPs": "DSP"}
    out = {}
    for line in open(path, encoding="utf-8", errors="ignore"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5:
            continue
        name = cells[0].rstrip("*").strip()
        if name in want and want[name] not in out:
            try:
                used = float(cells[1])
                avail = float(cells[-2])
                out[want[name]] = (used, avail)
            except ValueError:
                pass
    return out


def wns(path):
    lines = open(path, encoding="utf-8", errors="ignore").read().splitlines()
    for i, line in enumerate(lines):
        if "WNS(ns)" in line and "TNS(ns)" in line:
            for row in lines[i + 1:i + 4]:
                nums = re.findall(r"-?\d+\.\d+", row)
                if nums:
                    return float(nums[0])
    return None


def power(path):
    out = {}
    for line in open(path, encoding="utf-8", errors="ignore"):
        m = re.match(r"\|\s*(Total On-Chip Power \(W\)|Dynamic \(W\)|Device Static \(W\))\s*\|\s*([\d.]+)", line)
        if m:
            out[m.group(1).split(" (")[0]] = float(m.group(2))
    return out


def main():
    rows = []
    for name in ("basys3", "zynq"):
        u = os.path.join(RES, f"{name}_core_utilization.rpt")
        if not os.path.exists(u):
            print(f"(no reports for {name}, run vivado/core_compare.tcl first)")
            continue
        ut = util(u)
        w = wns(os.path.join(RES, f"{name}_core_timing.rpt"))
        pw = power(os.path.join(RES, f"{name}_core_power.rpt"))
        row = {"board": name}
        for k in ("LUT", "FF", "BRAM36", "DSP"):
            used, avail = ut.get(k, (None, None))
            row[k] = used
            row[k + "_pct"] = round(100 * used / avail, 2) if used is not None and avail else None
        row["WNS_ns"] = w
        row["Fmax_MHz"] = round(1000 / (10 - w), 1) if w is not None else None
        row["power_total_W"] = pw.get("Total On-Chip Power")
        row["power_dynamic_W"] = pw.get("Dynamic")
        rows.append(row)
    if not rows:
        return
    path = os.path.join(RES, "fpga_compare.csv")
    with open(path, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    for r in rows:
        print(r)
    print("wrote", path)


if __name__ == "__main__":
    main()
