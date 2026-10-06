#!/usr/bin/env python3
"""
==============================================================================
 File    : tools/test_spec.py
 Purpose : Checks the generated files agree with each other.
             1. fixed-point rounding + saturation edge cases (Python)
             2. every packet encodes -> decodes back to the same values
             3. bad checksum / bad length are rejected
             4. (optional) C++ to_xxx() gives the SAME raw ints as Python
 Usage   : python tools/test_spec.py
           python tools/test_spec.py --cpp path/to/check_types(.exe)
==============================================================================
"""
import os
import random
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sw", "generated"))
import packets as P   # noqa: E402

FAILS = 0


def check(ok, what):
    global FAILS
    print(f"  [{'PASS' if ok else 'FAIL'}] {what}")
    if not ok:
        FAILS += 1


# ---------------------------------------------------------------------------
def test_fixed():
    print("Fixed-point conversions")
    check(P.to_fixed(1.0, "pos") == 65536, "1.0 -> Q16.16 = 65536")
    check(P.to_fixed(-1.0, "unit") == -16384, "-1.0 -> Q2.14 = -16384")
    check(P.to_fixed(2.5 / 16, "screen") == 3, "tie 2.5 rounds away from zero -> 3")
    check(P.to_fixed(-2.5 / 16, "screen") == -3, "tie -2.5 rounds away from zero -> -3")
    check(P.to_fixed(1e9, "pos") == 2**31 - 1, "large value saturates to max")
    check(P.to_fixed(-1e9, "pos") == -(2**31), "large negative saturates to min")
    check(P.to_fixed(3.0, "unit") == 2**15 - 1, "Q2.14 saturates above ~2.0")
    check(abs(P.from_fixed(P.to_fixed(0.7071, "unit"), "unit") - 0.7071) < 1 / 16384, "unit round-trip error < 1 LSB")


def _rand_vertex(rng):
    return {"px": rng.uniform(-50, 50), "py": rng.uniform(-50, 50), "pz": rng.uniform(-50, 50),
            "nx": rng.uniform(-1, 1), "ny": rng.uniform(-1, 1), "nz": rng.uniform(-1, 1),
            "color": rng.randrange(0, 4096)}


def test_packets():
    print("Packet encode/decode")
    rng = random.Random(1)

    name, d = P.decode(P.clear(0x0ABC, 0xFFFF))
    check(name == "CLEAR" and d == {"color": 0x0ABC, "depth": 0xFFFF}, "CLEAR round-trip")

    m = [rng.uniform(-4, 4) for _ in range(16)]
    name, d = P.decode(P.set_matrix(1, m))
    check(name == "SET_MATRIX" and d["id"] == 1 and d["m"] == [P.to_fixed(x, "pos") for x in m], "SET_MATRIX round-trip")

    name, d = P.decode(P.set_light(0.0, -0.7071, -0.7071, 0.2))
    check(d["ly"] == P.to_fixed(-0.7071, "unit") and d["ambient"] == P.to_fixed(0.2, "unit"), "SET_LIGHT round-trip")

    verts = [_rand_vertex(rng) for _ in range(30)]
    pkt = P.draw_tris(verts)
    name, d = P.decode(pkt)
    ok = name == "DRAW_TRIS" and d["count"] == 10 and len(d["verts"]) == 30
    ok = ok and all(d["verts"][i]["px"] == P.to_fixed(verts[i]["px"], "pos") and
                    d["verts"][i]["nz"] == P.to_fixed(verts[i]["nz"], "unit") for i in range(30))
    check(ok, "DRAW_TRIS (10 triangles) round-trip")
    check(len(pkt) == 3 + 2 + 30 * 20 + 1, "DRAW_TRIS size = header 3 + count 2 + 20 B/vertex + checksum 1")

    sv = [{"sx": 10.5, "sy": 2.5, "z": 100, "color": 0xF00},
          {"sx": 80.5, "sy": 20.5, "z": 200, "color": 0x0F0},
          {"sx": 30.5, "sy": 90.5, "z": 300, "color": 0x00F}]
    name, d = P.decode(P.raw_screen_tri(sv))
    check(d["v"][0]["sx"] == 168 and d["v"][2]["z"] == 300, "RAW_SCREEN_TRI round-trip (10.5 px -> 168 in Q12.4)")

    for f in (P.finish, P.read_frame, P.read_stats):
        name, d = P.decode(f())
        check(d == {}, f"{name} has empty payload")

    stream = P.clear(0, 0xFFFF) + P.set_mode(1, 1, 1) + P.draw_tris(verts[:3]) + P.finish()
    names = [P.decode(p)[0] for p in P.split_stream(stream)]
    check(names == ["CLEAR", "SET_MODE", "DRAW_TRIS", "FINISH"], "split_stream on a 4-packet trace")

    bad = bytearray(P.clear(1, 2)); bad[3] ^= 0xFF
    try:
        P.decode(bytes(bad)); check(False, "bad checksum rejected")
    except ValueError:
        check(True, "bad checksum rejected")
    try:
        P.decode(P.clear(1, 2)[:-2] + bytes([0]))
        check(False, "short packet rejected")
    except ValueError:
        check(True, "short packet rejected")


def test_cpp(exe):
    print("C++ vs Python rounding")
    rng = random.Random(7)
    cases = []
    for t in ("pos", "unit", "screen", "grad"):
        lsb = 1 / (1 << P.TYPES[t]["frac"])
        cases += [(t, k * lsb / 2) for k in range(-41, 42)]          # exact ties
        cases += [(t, rng.uniform(-3, 3)) for _ in range(300)]
        cases += [(t, 1e12), (t, -1e12)]                               # saturation
    inp = "\n".join(f"{t} {v!r}" for t, v in cases) + "\n"
    out = subprocess.run([exe], input=inp, capture_output=True, text=True, check=True).stdout.split("\n")
    bad = 0
    for (t, v), line in zip(cases, out):
        raw = int(line.split()[2])
        if raw != P.to_fixed(v, t):
            bad += 1
    check(bad == 0 and len(out) - 1 == len(cases), f"{len(cases)} values identical in C++ and Python ({bad} differ)")


if __name__ == "__main__":
    test_fixed()
    test_packets()
    if "--cpp" in sys.argv:
        test_cpp(sys.argv[sys.argv.index("--cpp") + 1])
    print("ALL PASSED" if FAILS == 0 else f"{FAILS} FAILED")
    sys.exit(1 if FAILS else 0)
