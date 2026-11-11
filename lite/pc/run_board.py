#!/usr/bin/env python3
"""
==============================================================================
 File    : pc/run_board.py
 Purpose : Runs one scene on the Basys3 over USB-UART and saves everything
           compare.py needs, plus host-side timings for the paper.
 Needs   : pip install pyserial
 Usage   : python pc/run_board.py cube --port COM5 [--baud 921600] [--draws 10]
             --draws N   repeat DRAW N times (the GPU keeps the triangles) to
                         get a stable cycle count; the frame is read once at the end
 Writes  : results/<scene>_basys3.bin         every reply byte (for compare.py)
           results/<scene>_basys3_timing.json upload / draw / readback seconds
 Then    : python pc/compare.py <scene> results/<scene>_basys3.bin --tag basys3
                                --timing results/<scene>_basys3_timing.json
==============================================================================
"""
import argparse
import json
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import protocol as P   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_exact(ser, n, what):
    data = ser.read(n)
    if len(data) != n:
        sys.exit(f"timeout waiting for {what}: got {len(data)} of {n} bytes. "
                 "Check the port, the baud rate, and that the bitstream is loaded (LED0 blinking).")
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("--port", required=True, help="e.g. COM5 (Windows) or /dev/ttyUSB1")
    ap.add_argument("--baud", type=int, default=921600)
    ap.add_argument("--draws", type=int, default=1)
    a = ap.parse_args()

    import serial   # pyserial
    scene = open(os.path.join(ROOT, "scenes", a.scene + ".bin"), "rb").read()
    cmds = P.split_commands(scene)
    ser = serial.Serial(a.port, a.baud, timeout=5)
    ser.reset_input_buffer()

    ser.write(P.cmd_ping())
    pong = read_exact(ser, 4, "PING")
    if pong[:3] != b"GPU":
        sys.exit(f"unexpected PING reply {pong.hex()} (expected 475055..)")
    print(f"GPU found on {a.port}, version {pong[3]}")

    replies = bytearray()
    t = {"baud": a.baud, "upload_s": 0.0, "draw_roundtrip_s": [], "readback_s": 0.0,
         "upload_bytes": 0, "clear_s": 0.0}
    upload_start = None
    for op, cmd in cmds:
        if op == P.LOAD_TRI and upload_start is None:
            upload_start = time.perf_counter()
        if op != P.LOAD_TRI and upload_start is not None:
            ser.flush()
            t["upload_s"] = time.perf_counter() - upload_start
            upload_start = None

        if op == P.DRAW:
            for k in range(a.draws):
                t0 = time.perf_counter()
                ser.write(cmd)
                r = read_exact(ser, 17, "DRAW reply")
                t["draw_roundtrip_s"].append(time.perf_counter() - t0)
                if k == a.draws - 1:
                    replies += r                       # keep only the last one for compare.py
                cyc = struct.unpack("<I", r[1:5])[0]
                print(f"  DRAW {k + 1}/{a.draws}: {cyc} cycles = {cyc / 100e3:.3f} ms at 100 MHz")
            continue

        t0 = time.perf_counter()
        ser.write(cmd)
        if op == P.LOAD_TRI:
            t["upload_bytes"] += len(cmd)
        n = P.reply_length(op)
        if n:
            replies += read_exact(ser, n, f"reply to opcode 0x{op:02X}")
        if op == P.READ:
            t["readback_s"] = time.perf_counter() - t0
        if op == P.CLEAR:
            t["clear_s"] = time.perf_counter() - t0
    ser.close()

    out = os.path.join(ROOT, "results", f"{a.scene}_basys3.bin")
    open(out, "wb").write(bytes(replies))
    json.dump(t, open(os.path.join(ROOT, "results", f"{a.scene}_basys3_timing.json"), "w"), indent=2)
    print(f"upload {t['upload_bytes']} B in {t['upload_s']:.3f} s, readback {t['readback_s']:.3f} s")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
