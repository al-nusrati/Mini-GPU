"""
==============================================================================
 File    : pc/protocol.py
 Purpose : Everything both PC scripts need to speak to the GPU:
             - build commands (exactly the bytes rtl/gpu_core.sv expects)
             - split a scene file back into commands
             - parse the GPU's reply bytes
             - tiny PNG writer (no Pillow needed)
 Protocol: see the header of rtl/gpu_core.sv
==============================================================================
"""
import struct
import zlib

W, H = 160, 120

PING, CLEAR, LOAD_TRI, DRAW, READ, RESET_TRIS = 0x00, 0x01, 0x02, 0x03, 0x04, 0x05
PAYLOAD = {PING: 0, CLEAR: 2, LOAD_TRI: 26, DRAW: 0, READ: 0, RESET_TRIS: 0}


# ---------------------------------------------------------------- commands
def cmd_ping():        return bytes([PING])
def cmd_clear(color):  return bytes([CLEAR]) + struct.pack("<H", color)
def cmd_draw():        return bytes([DRAW])
def cmd_read():        return bytes([READ])
def cmd_reset():       return bytes([RESET_TRIS])


def cmd_tri(v, z0, dzdx, dzdy, color):
    """v = [(x0,y0),(x1,y1),(x2,y2)] integer pixels; z values raw Q16.16 ints."""
    for x, y in v:
        if not (-2048 <= x <= 2047 and -2048 <= y <= 2047):
            raise ValueError(f"vertex ({x},{y}) outside -2048..2047")
    return bytes([LOAD_TRI]) + struct.pack("<6h3iH", v[0][0], v[0][1], v[1][0], v[1][1],
                                           v[2][0], v[2][1], z0, dzdx, dzdy, color)


def tri_from_float_depth(v, zf, color):
    """v: 3 integer (x,y), zf: 3 depths in 0..65535 (float).
    Fits the depth plane through the 3 corners and returns a LOAD_TRI command."""
    (x0, y0), (x1, y1), (x2, y2) = v
    det = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    if det == 0:
        a = b = 0.0
    else:
        a = ((zf[1] - zf[0]) * (y2 - y0) - (zf[2] - zf[0]) * (y1 - y0)) / det
        b = ((zf[2] - zf[0]) * (x1 - x0) - (zf[1] - zf[0]) * (x2 - x0)) / det
    q = lambda f: max(-2**31, min(2**31 - 1, int(round(f * 65536))))
    return cmd_tri(v, q(zf[0]), q(a), q(b), color)


def rgb444(r, g, b):
    """r, g, b in 0..1 -> 12-bit color."""
    c = lambda t: max(0, min(15, int(round(t * 15))))
    return (c(r) << 8) | (c(g) << 4) | c(b)


# ---------------------------------------------------------------- scene files
def split_commands(data):
    """bytes of a scene -> list of (opcode, command bytes)."""
    out, i = [], 0
    while i < len(data):
        op = data[i]
        if op not in PAYLOAD:
            raise ValueError(f"unknown opcode 0x{op:02X} at byte {i}")
        n = 1 + PAYLOAD[op]
        out.append((op, data[i:i + n]))
        i += n
    return out


def reply_length(op, w=W, h=H):
    return {PING: 4, CLEAR: 1, LOAD_TRI: 0, DRAW: 17, READ: w * h * 2, RESET_TRIS: 1}[op]


def parse_replies(scene, replies, w=W, h=H):
    """Walk the scene's commands and cut the reply bytes into results.
    Returns dict with 'draws' (list of counter dicts) and 'frame' (last READ)."""
    res, pos = {"draws": [], "frame": None, "ping": None}, 0
    for op, _ in split_commands(scene):
        n = reply_length(op, w, h)
        chunk = replies[pos:pos + n]
        if len(chunk) != n:
            raise ValueError(f"replies ended early: needed {n} bytes for opcode 0x{op:02X} at byte {pos}")
        pos += n
        if op == PING:
            res["ping"] = chunk
        elif op in (CLEAR, RESET_TRIS) and chunk != b"\xA0":
            raise ValueError(f"expected ACK 0xA0, got {chunk.hex()}")
        elif op == DRAW:
            if chunk[0] != 0xD0:
                raise ValueError(f"expected 0xD0, got 0x{chunk[0]:02X}")
            cyc, tested, inside, written = struct.unpack("<4I", chunk[1:])
            res["draws"].append({"cycles": cyc, "tested": tested, "inside": inside, "written": written})
        elif op == READ:
            res["frame"] = chunk
    if pos != len(replies):
        res["extra_bytes"] = len(replies) - pos
    return res


# ---------------------------------------------------------------- images
def frame_to_rgb(frame, w=W, h=H):
    """W*H little-endian uint16 RGB444 -> bytes RGB888."""
    out = bytearray()
    for i in range(w * h):
        c = frame[2 * i] | (frame[2 * i + 1] << 8)
        out += bytes((((c >> 8) & 15) * 17, ((c >> 4) & 15) * 17, (c & 15) * 17))
    return bytes(out)


def write_png(path, rgb, w=W, h=H, scale=4):
    """Pure-Python PNG writer, nearest-neighbour upscale for easy viewing."""
    raw = bytearray()
    for y in range(h * scale):
        raw.append(0)
        row = rgb[(y // scale) * w * 3:((y // scale) + 1) * w * 3]
        for x in range(w * scale):
            raw += row[(x // scale) * 3:(x // scale) * 3 + 3]
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w * scale, h * scale, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
