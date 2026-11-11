#!/usr/bin/env python3
"""
==============================================================================
 File    : pc/compare.py
 Purpose : Checks the FPGA (or simulation) result against the golden model.
 Usage   : python pc/compare.py <scene> <replies.bin> [--tag sim|basys3|zynq]
             <scene>       name, e.g. cube   (uses scenes/cube.bin, results/cube_golden.*)
             <replies>     every byte the GPU sent back, in order
                           (.hex from the testbench, .bin from run_board.py)
 Writes  : results/<scene>_<tag>.png, results/<scene>_golden.png,
           results/<scene>_<tag>_diff.png (red = different pixel),
           results/<scene>_<tag>.json (all numbers, for the paper tables)
 Exit    : 0 = PASS (frame identical AND counters identical), 1 = FAIL
==============================================================================
"""
import argparse
import json
import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import protocol as P   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("replies")
    ap.add_argument("--tag", default="sim")
    ap.add_argument("--timing", help="optional json with host timings (from run_board.py)")
    ap.add_argument("--skip", type=int, default=0, help="ignore this many leading reply bytes (e.g. 4 for a PING)")
    a = ap.parse_args()

    res_dir = os.path.join(ROOT, "results")
    scene = open(os.path.join(ROOT, "scenes", a.scene + ".bin"), "rb").read()
    golden_fb = open(os.path.join(res_dir, a.scene + "_golden.bin"), "rb").read()
    golden = json.load(open(os.path.join(res_dir, a.scene + "_golden.json")))
    if a.replies.endswith(".hex"):                        # testbench output: one hex byte per line
        replies = bytes(int(t, 16) for t in open(a.replies).read().split())
    else:                                                 # board output: raw bytes
        replies = open(a.replies, "rb").read()
    if a.skip:
        print(f"skipped leading bytes: {replies[:a.skip].hex()}  (PING reply should be 47505501 = 'GPU' v1)")
        replies = replies[a.skip:]

    r = P.parse_replies(scene, replies, golden["width"], golden["height"])
    fb = r["frame"]
    if fb is None:
        sys.exit("no READ reply found")
    w, h = golden["width"], golden["height"]

    diff = sum(1 for i in range(w * h) if fb[2 * i:2 * i + 2] != golden_fb[2 * i:2 * i + 2])
    last = r["draws"][-1]
    checks = {
        "frame_identical": diff == 0,
        "tested_match":  last["tested"]  == golden["tested"],
        "inside_match":  last["inside"]  == golden["inside"],
        "written_match": last["written"] == golden["written"],
    }
    cyc_err = last["cycles"] - golden["predicted_cycles"]

    # images
    P.write_png(os.path.join(res_dir, f"{a.scene}_golden.png"), P.frame_to_rgb(golden_fb, w, h), w, h)
    P.write_png(os.path.join(res_dir, f"{a.scene}_{a.tag}.png"), P.frame_to_rgb(fb, w, h), w, h)
    drgb = bytearray()
    for i in range(w * h):
        same = fb[2 * i:2 * i + 2] == golden_fb[2 * i:2 * i + 2]
        drgb += b"\x20\x20\x20" if same else b"\xff\x20\x20"
    P.write_png(os.path.join(res_dir, f"{a.scene}_{a.tag}_diff.png"), bytes(drgb), w, h)

    out = {
        "scene": a.scene, "platform": a.tag, "width": w, "height": h,
        "triangles": golden["triangles"], "culled": golden["culled"],
        "fpga": last, "golden": {k: golden[k] for k in ("tested", "inside", "written", "predicted_cycles")},
        "cycle_model_error": cyc_err,
        "pixels_different": diff, "crc32_fpga": f"{zlib.crc32(fb) & 0xFFFFFFFF:08x}",
        "crc32_golden": golden["crc32"], "cpu_ms_per_frame": golden["cpu_ms_per_frame"],
        "checks": checks, "pass": all(checks.values()),
    }
    if a.timing:
        out["host_timing"] = json.load(open(a.timing))
    json.dump(out, open(os.path.join(res_dir, f"{a.scene}_{a.tag}.json"), "w"), indent=2)

    print(f"[{a.tag}] {a.scene}: pixels different = {diff}, "
          f"tested {last['tested']}/{golden['tested']}, inside {last['inside']}/{golden['inside']}, "
          f"written {last['written']}/{golden['written']}")
    print(f"         cycles = {last['cycles']} (model predicted {golden['predicted_cycles']}, error {cyc_err})")
    for k, v in checks.items():
        print(f"         [{'PASS' if v else 'FAIL'}] {k}")
    print("RESULT:", "PASS" if out["pass"] else "FAIL")
    sys.exit(0 if out["pass"] else 1)


if __name__ == "__main__":
    main()
