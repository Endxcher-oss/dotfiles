#!/usr/bin/env python3
"""Dump PE header/sections of a Windows exe and flag packer/protector traits.

Usage:
  pe-info.py <file.exe> [--rva 0x1234 | --addr 0x4F280C9]...   # map RVAs/VAs to a section

Stdlib only. Read-only.
"""
import re
import struct
import sys

PACKER_HINTS = [
    b"VMProtect", b"Themida", b"Enigma", b"WinLicense", b"ASProtect", b"Obsidium",
    b"MoleBox", b"UPX", b"PECompact", b"SecuROM", b"SafeDisc", b"StarForce",
    b"skeleton.dll", b".detour", b"protect", b"anti-debug", b"antidebug",
]


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = argv[1]
    probes = []
    i = 2
    while i < len(argv):
        if argv[i] in ("--rva", "--addr") and i + 1 < len(argv):
            probes.append((argv[i][2:], int(argv[i + 1], 0)))
            i += 2
        else:
            print(f"unknown arg: {argv[i]}", file=sys.stderr)
            return 2

    d = open(path, "rb").read()
    if d[:2] != b"MZ":
        print("not a PE (no MZ). size=%d" % len(d))
        return 1
    lfanew = u32(d, 0x3C)
    if d[lfanew:lfanew + 4] != b"PE\0\0":
        print(f"no PE signature at 0x{lfanew:x}")
        return 1
    coff = lfanew + 4
    machine = u16(d, coff)
    nsec = u16(d, coff + 2)
    opt_size = u16(d, coff + 16)
    chars = u16(d, coff + 18)
    opt = coff + 20
    magic = u16(d, opt)
    plus = magic == 0x20B
    ep = u32(d, opt + 16)
    imagebase = struct.unpack_from("<Q" if plus else "<I", d, opt + 28)[0]
    size_image = u32(d, opt + 56)
    subsystem = u16(d, opt + (68 if not plus else 68))

    print(f"file        : {path} ({len(d)} bytes)")
    print(f"machine     : 0x{machine:04x}  ({'x86 32-bit' if machine == 0x14c else 'x86-64' if machine == 0x8664 else '?'})")
    print(f"PE32+       : {plus}   characteristics 0x{chars:04x}")
    print(f"ImageBase   : 0x{imagebase:08X}   SizeOfImage 0x{size_image:X}")
    print(f"EntryPoint  : RVA 0x{ep:X}  (VA 0x{imagebase + ep:08X})   Subsystem {subsystem}")
    print(f"sections    : {nsec}")

    secs = []
    so = opt + opt_size
    for s in range(nsec):
        o = so + 40 * s
        if o + 40 > len(d):
            break
        name = d[o:o + 8].split(b"\0")[0]
        vsize = u32(d, o + 8)
        va = u32(d, o + 12)
        rawsize = u32(d, o + 16)
        rawptr = u32(d, o + 20)
        sc = u32(d, o + 36)
        secs.append(dict(name=name, vsize=vsize, va=va, rawsize=rawsize, rawptr=rawptr, chars=sc))

    print("\n idx  name          VA         VSize      RawPtr     RawSize    Flags")
    for s, sec in enumerate(secs):
        nm = sec["name"].decode("latin1")
        print(f" {s:>3}  {nm!r:<12}  0x{sec['va']:08X} 0x{sec['vsize']:08X} "
              f"0x{sec['rawptr']:08X} 0x{sec['rawsize']:08X} 0x{sec['chars']:08X}")

    print("\n-- heuristics --")
    ep_sec = next((s for s, sec in enumerate(secs)
                   if sec["va"] <= ep < sec["va"] + max(sec["vsize"], sec["rawsize"])), None)
    print(f"EP in section      : {ep_sec} ({secs[ep_sec]['name'].decode('latin1') if ep_sec is not None else '??'})"
          f"{'  <-- EP in LAST section: typical for packers' if ep_sec == len(secs) - 1 else ''}")
    for s, sec in enumerate(secs):
        nm = sec["name"].decode("latin1")
        flags = []
        if not nm.strip():
            flags.append("blank/space name")
        if re.fullmatch(r"[a-z]{6,10}", nm):
            flags.append("random-looking name")
        if sec["vsize"] > 0x100000 and sec["rawsize"] < 0x1000:
            flags.append(f"huge VirtualSize 0x{sec['vsize']:X} with RawSize 0x{sec['rawsize']:X} (runtime-filled)")
        if sec["rawsize"] and sec["rawptr"] + min(sec["rawsize"], 0x1000) <= len(d):
            blob = d[sec["rawptr"]:sec["rawptr"] + sec["rawsize"]]
            mz = blob.find(b"MZ\x90\x00", 0x40)
            if mz > 0:
                flags.append(f"embedded PE stub at section+0x{mz:X}")
        if flags:
            print(f"  section {s} {nm!r}: " + "; ".join(flags))

    # imports
    imp_rva = u32(d, opt + (104 if not plus else 120))
    if imp_rva:
        def rva2off(rva):
            for sec in secs:
                if sec["va"] <= rva < sec["va"] + max(sec["vsize"], sec["rawsize"]):
                    off = sec["rawptr"] + (rva - sec["va"])
                    return off if off < len(d) else None
            return None
        off = rva2off(imp_rva)
        names = []
        while off and off + 20 <= len(d):
            name_rva = u32(d, off + 12)
            if not name_rva:
                break
            noff = rva2off(name_rva)
            if noff is None:
                break
            end = d.find(b"\0", noff)
            names.append(d[noff:end].decode("latin1", "replace"))
            off += 20
        print(f"imports            : {', '.join(names) if names else '(none)'}")

    # packer/name strings anywhere in the file
    hits = sorted({h.decode() for h in PACKER_HINTS if h in d})
    print(f"packer-ish strings : {', '.join(hits) if hits else '(none)'}")

    if probes:
        print("\n-- probe mapping --")
        for kind, val in probes:
            rva = val if kind == "rva" else val - imagebase
            if rva < 0:
                print(f"  0x{val:X}: below ImageBase")
                continue
            hit = None
            for s, sec in enumerate(secs):
                if sec["va"] <= rva < sec["va"] + max(sec["vsize"], sec["rawsize"]):
                    hit = (s, sec)
                    break
            if hit:
                s, sec = hit
                print(f"  0x{val:08X} -> RVA 0x{rva:X} in section {s} {sec['name'].decode('latin1')!r} "
                      f"(+0x{rva - sec['va']:X})")
            else:
                print(f"  0x{val:08X} -> RVA 0x{rva:X} in NO section (unmapped / runtime alloc)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
