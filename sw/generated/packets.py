# GENERATED from spec/formats.yaml by tools/gen_types.py - DO NOT EDIT BY HAND
"""Packet encoder/decoder for the Mini GPU command protocol."""

SPEC_VERSION = 1
TYPES = {'pos': {'bits': 32,
         'signed': True,
         'frac': 16,
         'kind': 'fixed',
         'doc': 'Q16.16 model-space positions and matrix elements'},
 'unit': {'bits': 16,
          'signed': True,
          'frac': 14,
          'kind': 'fixed',
          'doc': 'Q2.14 unit vectors and light terms (range about -2..+2)'},
 'screen': {'bits': 16,
            'signed': True,
            'frac': 4,
            'kind': 'fixed',
            'doc': 'Q12.4 screen coordinates, pixel center = n + 0.5'},
 'grad': {'bits': 32,
          'signed': True,
          'frac': 16,
          'kind': 'fixed',
          'doc': 'Q16.16 gradients for incremental interpolation'},
 'depth': {'bits': 16,
           'signed': False,
           'frac': 0,
           'kind': 'uint',
           'doc': '0 = near plane, 65535 = far plane / cleared'},
 'color': {'bits': 16,
           'signed': False,
           'frac': 0,
           'kind': 'uint',
           'doc': 'RGB444 in bits 11..0 on Basys3, RGB565 on Zynq'},
 'tri_id': {'bits': 16,
            'signed': False,
            'frac': 0,
            'kind': 'uint',
            'doc': 'triangle index inside one DRAW_TRIS batch'}}
STRUCTS = {'vertex_in': {'name': 'vertex_in',
               'doc': 'Object-space vertex exactly as sent by the host',
               'fields': [{'name': 'px', 'type': 'pos'},
                          {'name': 'py', 'type': 'pos'},
                          {'name': 'pz', 'type': 'pos'},
                          {'name': 'nx', 'type': 'unit'},
                          {'name': 'ny', 'type': 'unit'},
                          {'name': 'nz', 'type': 'unit'},
                          {'name': 'color', 'type': 'color'}]},
 'clip_vert': {'name': 'clip_vert',
               'doc': 'Clip-space position plus lit color',
               'fields': [{'name': 'cx', 'type': 'pos'},
                          {'name': 'cy', 'type': 'pos'},
                          {'name': 'cz', 'type': 'pos'},
                          {'name': 'cw', 'type': 'pos'},
                          {'name': 'color', 'type': 'color'}]},
 'screen_vert': {'name': 'screen_vert',
                 'doc': 'Screen-space vertex',
                 'fields': [{'name': 'sx', 'type': 'screen'},
                            {'name': 'sy', 'type': 'screen'},
                            {'name': 'z', 'type': 'depth'},
                            {'name': 'color', 'type': 'color'}]},
 'fragment': {'name': 'fragment',
              'doc': 'One covered pixel',
              'fields': [{'name': 'x', 'type': 'screen'},
                         {'name': 'y', 'type': 'screen'},
                         {'name': 'z', 'type': 'depth'},
                         {'name': 'color', 'type': 'color'}]}}
PACKETS = {'CLEAR': {'name': 'CLEAR',
           'opcode': 1,
           'payload': [{'name': 'color', 'type': 'color'}, {'name': 'depth', 'type': 'depth'}]},
 'SET_MATRIX': {'name': 'SET_MATRIX',
                'opcode': 2,
                'payload': [{'name': 'id', 'bits': 8}, {'name': 'm', 'type': 'pos', 'count': 16}],
                'doc': 'id 0 = model, 1 = view-projection. 16 values, row-major'},
 'SET_LIGHT': {'name': 'SET_LIGHT',
               'opcode': 3,
               'payload': [{'name': 'lx', 'type': 'unit'},
                           {'name': 'ly', 'type': 'unit'},
                           {'name': 'lz', 'type': 'unit'},
                           {'name': 'ambient', 'type': 'unit'}]},
 'SET_MODE': {'name': 'SET_MODE',
              'opcode': 4,
              'payload': [{'name': 'shade', 'bits': 8},
                          {'name': 'cull', 'bits': 8},
                          {'name': 'depth_test', 'bits': 8}],
              'doc': 'shade 0 = flat, 1 = Gouraud, 2 = depth view'},
 'DRAW_TRIS': {'name': 'DRAW_TRIS',
               'opcode': 5,
               'payload': [{'name': 'count', 'bits': 16},
                           {'name': 'verts', 'struct': 'vertex_in', 'count_field': 'count', 'per_item': 3}],
               'doc': 'count triangles, 3 vertices each. Max 1000 vertices per packet; the driver splits '
                      'bigger meshes'},
 'FINISH': {'name': 'FINISH',
            'opcode': 6,
            'payload': [],
            'doc': 'GPU replies DONE (0xD0) when the pipeline is empty'},
 'READ_FRAME': {'name': 'READ_FRAME', 'opcode': 7, 'payload': []},
 'READ_STATS': {'name': 'READ_STATS', 'opcode': 8, 'payload': []},
 'RAW_SCREEN_TRI': {'name': 'RAW_SCREEN_TRI',
                    'opcode': 15,
                    'payload': [{'name': 'v', 'struct': 'screen_vert', 'count': 3}],
                    'doc': 'debug only: draw one screen-space triangle, skipping transform'}}
OPCODE_TO_NAME = {p['opcode']: n for n, p in PACKETS.items()}
REPLY_ACK = 0xA0
REPLY_ERR = 0xE0
REPLY_DONE = 0xD0
ERR_BAD_CHECKSUM = 1
ERR_BAD_OPCODE = 2
ERR_BAD_LENGTH = 3
TARGETS = {'basys3': {'width': 160, 'height': 120, 'color_format': 'rgb444', 'clk_mhz': 100},
 'zynq': {'width': 320, 'height': 240, 'color_format': 'rgb565', 'clk_mhz': 100}}

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
