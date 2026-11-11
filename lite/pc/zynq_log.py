#!/usr/bin/env python3
"""
==============================================================================
 File    : pc/zynq_log.py
 Purpose : Turns the Zynq serial-terminal log (main.c with DUMP_FRAME 1) into
           the same reply file compare.py uses, then you compare as usual.
 Usage   : python pc/zynq_log.py zynq_log.txt cube
           python pc/compare.py cube results/cube_zynq.bin --tag zynq --timing results/cube_zynq_timing.json
==============================================================================
"""
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import protocol as P   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    log, scene_name = sys.argv[1], sys.argv[2]
    text = open(log, errors="ignore").read()
    val = lambda k: int(re.search(rf"{k}\s*=\s*(\d+)", text).group(1))
    fl = lambda k: float(re.search(rf"{k}\s*=\s*([\d.]+)", text).group(1))
    m = re.search(r"FRAME_BEGIN(.*?)FRAME_END", text, re.S)
    if not m:
        sys.exit("no FRAME_BEGIN/FRAME_END in the log (set DUMP_FRAME 1 in main.c)")
    hexs = re.sub(r"[^0-9a-fA-F]", "", m.group(1))
    frame = b"".join(struct.pack("<H", int(hexs[i:i + 4], 16)) for i in range(0, len(hexs), 4))

    scene = open(os.path.join(ROOT, "scenes", scene_name + ".bin"), "rb").read()
    out = bytearray()
    for op, _ in P.split_commands(scene):
        if op in (P.CLEAR, P.RESET_TRIS):
            out += b"\xA0"
        elif op == P.DRAW:
            out += b"\xD0" + struct.pack("<4I", val("cycles"), val("tested"), val("inside"), val("written"))
        elif op == P.READ:
            out += frame
        elif op == P.PING:
            out += b"GPU\x01"
    path = os.path.join(ROOT, "results", f"{scene_name}_zynq.bin")
    open(path, "wb").write(bytes(out))
    timing = {"upload_s": fl("upload_us") / 1e6, "draw_roundtrip_s": [fl("draw_roundtrip_us") / 1e6],
              "readback_s": fl("readback_us") / 1e6, "link": "AXI-Lite (ARM polling)"}
    json.dump(timing, open(os.path.join(ROOT, "results", f"{scene_name}_zynq_timing.json"), "w"), indent=2)
    print("wrote", path)


if __name__ == "__main__":
    main()
