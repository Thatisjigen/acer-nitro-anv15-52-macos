#!/usr/bin/env python3
"""Remove flat-namespace weak-import binds from a Mach-O dylib.

Mesa declares every driver entrypoint weak. On macOS the ones NVK does not
implement stay undefined and are bound with a flat-namespace lookup: at every
dlopen dyld searches each of them in every image already loaded, and always
finds nothing, so the pointer stays 0. This script drops exactly those binds
and keeps every other bind unchanged. The slots already hold 0 in the file,
so the result at run time is the same, without the search.

Usage: python3 -I drop_flat_weak_binds.py IN OUT
The output must be signed again (ad hoc) before use.
"""
import struct, sys

LC_SEGMENT_64, LC_DYLD_INFO, LC_DYLD_INFO_ONLY = 0x19, 0x22, 0x80000022
BIND_SPECIAL_FLAT = -2
BIND_WEAK_IMPORT = 0x1


def uleb(b, i):
    v = s = 0
    while True:
        x = b[i]; i += 1
        v |= (x & 0x7F) << s; s += 7
        if x < 0x80:
            return v, i


def sleb(b, i):
    v = s = 0
    while True:
        x = b[i]; i += 1
        v |= (x & 0x7F) << s; s += 7
        if x < 0x80:
            if x & 0x40:
                v -= 1 << s
            return v, i


def enc_uleb(v):
    out = bytearray()
    while True:
        x = v & 0x7F; v >>= 7
        out.append(x | (0x80 if v else 0))
        if not v:
            return bytes(out)


def enc_sleb(v):
    out = bytearray()
    while True:
        x = v & 0x7F; v >>= 7
        done = (v == 0 and not x & 0x40) or (v == -1 and x & 0x40)
        out.append(x | (0 if done else 0x80))
        if done:
            return bytes(out)


def decode(b, start, size):
    """Return the bind records of a regular (non-lazy) bind stream."""
    recs, i, end = [], start, start + size
    ordinal, sym, flags, typ, addend, seg, off = 0, None, 0, 1, 0, 0, 0
    while i < end:
        op = b[i] & 0xF0; imm = b[i] & 0x0F; i += 1
        if op == 0x00:
            break
        elif op == 0x10: ordinal = imm
        elif op == 0x20: ordinal, i = uleb(b, i)
        elif op == 0x30: ordinal = (imm | 0xF0) - 256 if imm else 0
        elif op == 0x40:
            j = b.index(0, i); sym = b[i:j].decode(); flags = imm; i = j + 1
        elif op == 0x50: typ = imm
        elif op == 0x60: addend, i = sleb(b, i)
        elif op == 0x70: seg = imm; off, i = uleb(b, i)
        elif op == 0x80: d, i = uleb(b, i); off = (off + d) & (2**64 - 1)
        elif op in (0x90, 0xA0, 0xB0):
            recs.append((ordinal, sym, flags, typ, addend, seg, off)); off += 8
            if op == 0xA0: d, i = uleb(b, i); off = (off + d) & (2**64 - 1)
            if op == 0xB0: off += imm * 8
        elif op == 0xC0:
            n, i = uleb(b, i); skip, i = uleb(b, i)
            for _ in range(n):
                recs.append((ordinal, sym, flags, typ, addend, seg, off)); off += 8 + skip
        else:
            sys.exit(f"unsupported bind opcode 0x{op:02x} at 0x{i - 1:x}")
    return recs


def encode(recs):
    out = bytearray(); st = {}
    for ordinal, sym, flags, typ, addend, seg, off in recs:
        if st.get("ord") != ordinal:
            if ordinal <= 0: out.append(0x30 | (ordinal & 0x0F))
            elif ordinal < 16: out.append(0x10 | ordinal)
            else: out += bytes([0x20]) + enc_uleb(ordinal)
            st["ord"] = ordinal
        if st.get("sym") != (sym, flags):
            out += bytes([0x40 | flags]) + sym.encode() + b"\0"; st["sym"] = (sym, flags)
        if st.get("typ") != typ:
            out.append(0x50 | typ); st["typ"] = typ
        if st.get("add", 0) != addend:
            out += bytes([0x60]) + enc_sleb(addend); st["add"] = addend
        out += bytes([0x70 | seg]) + enc_uleb(off)
        out.append(0x90)
    out.append(0x00)
    return bytes(out)


def main(src, dst):
    b = bytearray(open(src, "rb").read())
    magic, _, _, _, ncmds, _, _ = struct.unpack_from("<IiiIIII", b, 0)
    if magic != 0xFEEDFACF:
        sys.exit("not a thin 64-bit Mach-O")
    p, segs, info = 32, [], None
    for _ in range(ncmds):
        cmd, size = struct.unpack_from("<II", b, p)
        if cmd == LC_SEGMENT_64:
            name = b[p + 8:p + 24].rstrip(b"\0").decode()
            vmaddr, vmsize, fileoff, filesize = struct.unpack_from("<QQQQ", b, p + 24)
            segs.append((name, vmaddr, fileoff, filesize))
        elif cmd in (LC_DYLD_INFO, LC_DYLD_INFO_ONLY):
            info = p
        p += size
    if info is None:
        sys.exit("no LC_DYLD_INFO: chained fixups are not handled")
    bind_off, bind_size = struct.unpack_from("<II", b, info + 16)
    recs = decode(b, bind_off, bind_size)
    drop = [r for r in recs if r[0] == BIND_SPECIAL_FLAT and r[2] & BIND_WEAK_IMPORT]
    keep = [r for r in recs if r not in drop]
    for ordinal, sym, flags, typ, addend, seg, off in drop:
        name, vmaddr, fileoff, filesize = segs[seg]
        if addend or typ != 1 or off + 8 > filesize:
            sys.exit(f"{sym}: unexpected bind (addend {addend}, type {typ})")
        if struct.unpack_from("<Q", b, fileoff + off)[0] != 0:
            sys.exit(f"{sym}: slot is not 0 in the file; dropping the bind would change it")
    new = encode(keep)
    if len(new) > bind_size:
        sys.exit("re-encoded bind stream is larger than the original")
    b[bind_off:bind_off + bind_size] = new + bytes(bind_size - len(new))
    if decode(b, bind_off, bind_size) != keep:
        sys.exit("round trip failed")
    open(dst, "wb").write(b)
    print(f"binds: {len(recs)} -> {len(keep)} (dropped {len(drop)} flat weak-import); "
          f"stream {bind_size} bytes, {len(new)} used")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
