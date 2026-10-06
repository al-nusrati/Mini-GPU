#!/usr/bin/env python3
"""
==============================================================================
 File    : tools/gen_types.py
 Purpose : Reads spec/formats.yaml and writes the three generated files:
              sw/generated/types.h      C++ (golden model, mgl, CUDA)
              rtl/pkg/gpu_pkg.sv        SystemVerilog package
              sw/generated/packets.py   Python packet encoder/decoder
 Usage   : python tools/gen_types.py            (run from the repo root)

 Pseudocode
   load yaml
   for each fixed / uint format  -> C++ typedef + converters, SV typedef, Python converters
   for each struct                -> C++ struct, SV packed struct, Python field list
   for each packet                -> C++ opcode enum, SV opcode enum, Python encode/decode
   write files with a "GENERATED - DO NOT EDIT" banner
==============================================================================
"""
import os
import sys
import pprint
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, "spec", "formats.yaml")
OUT_H = os.path.join(ROOT, "sw", "generated", "types.h")
OUT_SV = os.path.join(ROOT, "rtl", "pkg", "gpu_pkg.sv")
OUT_PY = os.path.join(ROOT, "sw", "generated", "packets.py")

BANNER = "GENERATED from spec/formats.yaml by tools/gen_types.py - DO NOT EDIT BY HAND"


# ---------------------------------------------------------------------------
#  Private helpers
# ---------------------------------------------------------------------------
def _load_spec():
    with open(SPEC, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _types_table(spec):
    """name -> {bits, signed, frac, kind} for every scalar type."""
    t = {}
    for fx in spec["fixed"]:
        t[fx["name"]] = {"bits": fx["int_bits"] + fx["frac_bits"], "signed": fx["signed"],
                         "frac": fx["frac_bits"], "kind": "fixed", "doc": fx.get("doc", "")}
    for u in spec["uints"]:
        t[u["name"]] = {"bits": u["bits"], "signed": False, "frac": 0, "kind": "uint",
                        "doc": u.get("doc", "")}
    for name, v in t.items():
        if v["bits"] not in (8, 16, 32):
            sys.exit(f"type '{name}': width {v['bits']} must be 8, 16 or 32 (byte-aligned wire format)")
    return t


def _field_bits(field, types):
    if "type" in field:
        return types[field["type"]]["bits"]
    return field["bits"]


def _struct_bits(struct, types):
    return sum(_field_bits(f, types) for f in struct["fields"])


def _cpp_int(bits, signed):
    return f"{'int' if signed else 'uint'}{bits}_t"


# ---------------------------------------------------------------------------
#  C++ header
# ---------------------------------------------------------------------------
def _gen_cpp(spec, types):
    L = []
    w = L.append
    w(f"// {BANNER}")
    w("#pragma once")
    w("#include <stdint.h>")
    w("#include <math.h>")
    w("")
    w(f"static const int SPEC_VERSION = {spec['version']};")
    w("")
    w("// ---------------- scalar types ----------------")
    for name, t in types.items():
        w(f"typedef {_cpp_int(t['bits'], t['signed'])} {name}_t;   // {t['doc']}")
    w("")
    w("// ---------------- fixed-point converters ----------------")
    w("// Rule (same in Python and golden model): round to nearest, ties away")
    w("// from zero, then saturate to the type's range.")
    for name, t in types.items():
        if t["kind"] != "fixed":
            continue
        lo = -(1 << (t["bits"] - 1))
        hi = (1 << (t["bits"] - 1)) - 1
        up = name.upper()
        w(f"static const int {up}_FRAC = {t['frac']};")
        w(f"static const int64_t {up}_MIN = {lo}LL, {up}_MAX = {hi}LL;")
        w(f"inline {name}_t to_{name}(double v) {{")
        w(f"    double s = v * (double)(1LL << {up}_FRAC);")
        w(f"    if (s >= (double){up}_MAX) return ({name}_t){up}_MAX;   // saturate first:")
        w(f"    if (s <= (double){up}_MIN) return ({name}_t){up}_MIN;   // llround overflow is undefined")
        w(f"    return ({name}_t)llround(s);")
        w("}")
        w(f"inline double from_{name}({name}_t v) {{ return (double)v / (double)(1LL << {up}_FRAC); }}")
        w("")
    w("// ---------------- structs (host-side view; wire format is packed little-endian) ----------------")
    for s in spec["structs"]:
        w(f"// {s.get('doc', '')}  ({_struct_bits(s, types)} bits on the wire)")
        w(f"struct {s['name']}_t {{")
        for f in s["fields"]:
            w(f"    {f['type']}_t {f['name']};")
        w("};")
        w(f"static const int {s['name'].upper()}_WIRE_BYTES = {_struct_bits(s, types) // 8};")
        w("")
    w("// ---------------- packets ----------------")
    w("enum Opcode : uint8_t {")
    for p in spec["packets"]:
        w(f"    OP_{p['name']} = 0x{p['opcode']:02X},")
    w("};")
    for k, v in spec["replies"].items():
        w(f"static const uint8_t REPLY_{k} = 0x{v:02X};")
    for k, v in spec["errors"].items():
        w(f"static const uint8_t ERR_{k} = {v};")
    w("")
    w("// ---------------- targets ----------------")
    for tname, t in spec["targets"].items():
        up = tname.upper()
        w(f"static const int {up}_WIDTH = {t['width']}, {up}_HEIGHT = {t['height']}, {up}_CLK_MHZ = {t['clk_mhz']};")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
#  SystemVerilog package
# ---------------------------------------------------------------------------
def _gen_sv(spec, types):
    L = []
    w = L.append
    w(f"// {BANNER}")
    w("package gpu_pkg;")
    w("    // Not every constant is used by every module; that is expected.")
    w("    /* verilator lint_off UNUSEDPARAM */")
    w("")
    w(f"    localparam int SPEC_VERSION = {spec['version']};")
    w("")
    w("    // ---------------- scalar types ----------------")
    for name, t in types.items():
        up = name.upper()
        sgn = " signed" if t["signed"] else ""
        w(f"    localparam int {up}_W    = {t['bits']};")
        if t["kind"] == "fixed":
            w(f"    localparam int {up}_FRAC = {t['frac']};")
        w(f"    typedef logic{sgn} [{up}_W-1:0] {name}_t;   // {t['doc']}")
    w("")
    w("    // ---------------- structs (first field = most significant bits) ----------------")
    for s in spec["structs"]:
        w(f"    // {s.get('doc', '')}")
        w("    typedef struct packed {")
        for f in s["fields"]:
            w(f"        {f['type']}_t {f['name']};")
        w(f"    }} {s['name']}_t;")
        w(f"    localparam int {s['name'].upper()}_BITS = {_struct_bits(s, types)};")
        w("")
    w("    // ---------------- packets ----------------")
    w("    typedef enum logic [7:0] {")
    items = [f"        OP_{p['name']} = 8'h{p['opcode']:02X}" for p in spec["packets"]]
    w(",\n".join(items))
    w("    } opcode_e;")
    w("")
    for k, v in spec["replies"].items():
        w(f"    localparam logic [7:0] REPLY_{k} = 8'h{v:02X};")
    for k, v in spec["errors"].items():
        w(f"    localparam logic [7:0] ERR_{k} = 8'd{v};")
    w("")
    w("    // ---------------- targets ----------------")
    for tname, t in spec["targets"].items():
        up = tname.upper()
        w(f"    localparam int {up}_WIDTH = {t['width']};")
        w(f"    localparam int {up}_HEIGHT = {t['height']};")
        w(f"    localparam int {up}_CLK_MHZ = {t['clk_mhz']};")
    w("")
    w("    /* verilator lint_on UNUSEDPARAM */")
    w("endpackage")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
#  Python packet module
# ---------------------------------------------------------------------------
_PY_RUNTIME = r'''
import math
import struct as _st

# ---------------------------------------------------------------- converters
def to_fixed(value, type_name):
    """float -> raw int. Round to nearest, ties away from zero, then saturate."""
    t = TYPES[type_name]
    scaled = value * (1 << t["frac"])
    mag = abs(scaled)
    whole = math.floor(mag)
    r = int(whole) + (1 if mag - whole >= 0.5 else 0)   # same as C llround
    r = r if scaled >= 0 else -r
    if t["signed"]:
        lo, hi = -(1 << (t["bits"] - 1)), (1 << (t["bits"] - 1)) - 1
    else:
        lo, hi = 0, (1 << t["bits"]) - 1
    return max(lo, min(hi, r))

def from_fixed(raw, type_name):
    return raw / (1 << TYPES[type_name]["frac"])

def _fmt(bits, signed):
    return {8: "b", 16: "h", 32: "i"}[bits] if signed else {8: "B", 16: "H", 32: "I"}[bits]

def _scalar_fmt(field):
    if "type" in field:
        t = TYPES[field["type"]]
        return _fmt(t["bits"], t["signed"]), field["type"]
    return _fmt(field["bits"], False), None

def _pack_scalar(field, value):
    fmt, tname = _scalar_fmt(field)
    if tname and TYPES[tname]["kind"] == "fixed" and not isinstance(value, int):
        value = to_fixed(value, tname)
    return _st.pack("<" + fmt, value)

def _pack_struct(sname, item):
    out = b""
    for f in STRUCTS[sname]["fields"]:
        out += _pack_scalar(f, item[f["name"]])
    return out

def _checksum(data):
    return sum(data) & 0xFF

# ---------------------------------------------------------------- encode
def encode(name, **args):
    """Build one packet. Fixed-point fields accept floats (converted) or raw ints."""
    p = PACKETS[name]
    payload = b""
    for f in p["payload"]:
        n = f["name"]
        if "struct" in f:
            items = args[n]
            if "count_field" in f:
                need = args[f["count_field"]] * f.get("per_item", 1)
            else:
                need = f["count"]
            if len(items) != need:
                raise ValueError(f"{name}.{n}: expected {need} items, got {len(items)}")
            for it in items:
                payload += _pack_struct(f["struct"], it)
        elif "count" in f:
            vals = args[n]
            if len(vals) != f["count"]:
                raise ValueError(f"{name}.{n}: expected {f['count']} values")
            for v in vals:
                payload += _pack_scalar(f, v)
        else:
            payload += _pack_scalar(f, args[n])
    if len(payload) > 0xFFFF:
        raise ValueError(f"{name}: payload too long ({len(payload)} bytes)")
    head = _st.pack("<BH", p["opcode"], len(payload))
    body = head + payload
    return body + bytes([_checksum(body)])

# ---------------------------------------------------------------- decode
def _unpack_scalar(field, data, pos):
    fmt, _ = _scalar_fmt(field)
    size = _st.calcsize(fmt)
    return _st.unpack_from("<" + fmt, data, pos)[0], pos + size

def decode(packet):
    """bytes of ONE packet -> (name, dict of raw ints). Raises on bad checksum/length."""
    if _checksum(packet[:-1]) != packet[-1]:
        raise ValueError("bad checksum")
    opcode, length = _st.unpack_from("<BH", packet, 0)
    if length != len(packet) - 4:
        raise ValueError("bad length")
    name = OPCODE_TO_NAME.get(opcode)
    if name is None:
        raise ValueError(f"bad opcode 0x{opcode:02X}")
    pos, out = 3, {}
    for f in PACKETS[name]["payload"]:
        n = f["name"]
        if "struct" in f:
            cnt = out[f["count_field"]] * f.get("per_item", 1) if "count_field" in f else f["count"]
            items = []
            for _ in range(cnt):
                it = {}
                for sf in STRUCTS[f["struct"]]["fields"]:
                    it[sf["name"]], pos = _unpack_scalar(sf, packet, pos)
                items.append(it)
            out[n] = items
        elif "count" in f:
            vals = []
            for _ in range(f["count"]):
                v, pos = _unpack_scalar(f, packet, pos)
                vals.append(v)
            out[n] = vals
        else:
            out[n], pos = _unpack_scalar(f, packet, pos)
    return name, out

def split_stream(data):
    """bytes of many packets (a trace file) -> list of single-packet bytes."""
    pkts, pos = [], 0
    while pos < len(data):
        length = _st.unpack_from("<H", data, pos + 1)[0]
        end = pos + 3 + length + 1
        pkts.append(data[pos:end])
        pos = end
    return pkts

# ---------------------------------------------------------------- helpers
def clear(color, depth=0xFFFF):              return encode("CLEAR", color=color, depth=depth)
def set_matrix(mid, m16):                    return encode("SET_MATRIX", id=mid, m=list(m16))
def set_light(lx, ly, lz, ambient):          return encode("SET_LIGHT", lx=lx, ly=ly, lz=lz, ambient=ambient)
def set_mode(shade=0, cull=1, depth_test=1): return encode("SET_MODE", shade=shade, cull=cull, depth_test=depth_test)
def draw_tris(verts):                        return encode("DRAW_TRIS", count=len(verts) // 3, verts=verts)
def finish():                                return encode("FINISH")
def read_frame():                            return encode("READ_FRAME")
def read_stats():                            return encode("READ_STATS")
def raw_screen_tri(v3):                      return encode("RAW_SCREEN_TRI", v=v3)
'''


def _gen_py(spec, types):
    structs = {s["name"]: s for s in spec["structs"]}
    packets = {p["name"]: p for p in spec["packets"]}
    L = [f"# {BANNER}", '"""Packet encoder/decoder for the Mini GPU command protocol."""', ""]
    L.append(f"SPEC_VERSION = {spec['version']}")
    L.append("TYPES = " + pprint.pformat(types, width=110, sort_dicts=False))
    L.append("STRUCTS = " + pprint.pformat(structs, width=110, sort_dicts=False))
    L.append("PACKETS = " + pprint.pformat(packets, width=110, sort_dicts=False))
    L.append("OPCODE_TO_NAME = {p['opcode']: n for n, p in PACKETS.items()}")
    for k, v in spec["replies"].items():
        L.append(f"REPLY_{k} = 0x{v:02X}")
    for k, v in spec["errors"].items():
        L.append(f"ERR_{k} = {v}")
    L.append("TARGETS = " + pprint.pformat(spec["targets"], width=110, sort_dicts=False))
    return "\n".join(L) + "\n" + _PY_RUNTIME


# ---------------------------------------------------------------------------
#  Public entry point
# ---------------------------------------------------------------------------
def main():
    spec = _load_spec()
    types = _types_table(spec)
    outputs = {OUT_H: _gen_cpp(spec, types), OUT_SV: _gen_sv(spec, types), OUT_PY: _gen_py(spec, types)}
    for path, text in outputs.items():
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"wrote {os.path.relpath(path, ROOT)}")


if __name__ == "__main__":
    main()
