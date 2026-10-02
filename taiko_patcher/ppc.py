"""Tiny PowerPC encoders used for hook patching (branches only)."""
import struct


def _rel24(src: int, dst: int) -> int:
    off = dst - src
    if off % 4 or not -0x2000000 <= off < 0x2000000:
        raise ValueError(f"branch {src:#010x} -> {dst:#010x} out of range")
    return off & 0x03FFFFFC


def b(src: int, dst: int) -> int:
    return 0x48000000 | _rel24(src, dst)


def bl(src: int, dst: int) -> int:
    return 0x48000001 | _rel24(src, dst)


def is_bl(word: int) -> bool:
    return (word >> 26) == 18 and (word & 3) == 1


def branch_target(src: int, word: int) -> int:
    off = word & 0x03FFFFFC
    if off & 0x02000000:
        off -= 0x04000000
    return (src + off) & 0xFFFFFFFF


def w32(v: int) -> bytes:
    return struct.pack(">I", v & 0xFFFFFFFF)

NOP = 0x60000000
