"""Minimal GameCube/Wii DOL reader/writer (text/data sections, address translation, patching)."""
import struct

HEADER_SIZE = 0x100
N_TEXT = 7
N_SECT = 18


class DolError(Exception):
    pass


class Dol:
    def __init__(self, data: bytes):
        if len(data) < HEADER_SIZE:
            raise DolError("file too small to be a DOL")
        self.data = bytearray(data)
        self.offsets = list(struct.unpack(">18I", data[0x00:0x48]))
        self.addrs = list(struct.unpack(">18I", data[0x48:0x90]))
        self.sizes = list(struct.unpack(">18I", data[0x90:0xD8]))
        self.bss_addr, self.bss_size, self.entry = struct.unpack(">3I", data[0xD8:0xE4])
        for i in range(N_SECT):
            if self.sizes[i] and self.offsets[i] + self.sizes[i] > len(data):
                raise DolError(f"section {i} exceeds file size (not a DOL?)")

    # -- address translation -------------------------------------------------------------
    def sections(self):
        return [(i, self.offsets[i], self.addrs[i], self.sizes[i]) for i in range(N_SECT) if self.sizes[i]]

    def v2o(self, addr: int):
        for _, off, a, sz in self.sections():
            if a <= addr < a + sz:
                return off + addr - a
        return None

    def read(self, addr: int, n: int) -> bytes:
        o = self.v2o(addr)
        if o is None or self.v2o(addr + n - 1) is None:
            raise DolError(f"address {addr:#010x}+{n} is not inside a DOL section")
        return bytes(self.data[o:o + n])

    def u32(self, addr: int) -> int:
        return struct.unpack(">I", self.read(addr, 4))[0]

    def write(self, addr: int, blob: bytes):
        o = self.v2o(addr)
        if o is None or self.v2o(addr + len(blob) - 1) is None:
            raise DolError(f"address {addr:#010x}+{len(blob)} is not inside a DOL section")
        self.data[o:o + len(blob)] = blob

    def write_u32(self, addr: int, v: int):
        self.write(addr, struct.pack(">I", v & 0xFFFFFFFF))

    # -- sections --------------------------------------------------------------------------
    def overlaps(self, addr: int, size: int) -> bool:
        for _, _, a, sz in self.sections():
            if addr < a + sz and a < addr + size:
                return True
        if self.bss_size and addr < self.bss_addr + self.bss_size and self.bss_addr < addr + size:
            return True
        return False

    def add_text_section(self, addr: int, blob: bytes) -> int:
        if addr % 0x20:
            raise DolError("section address must be 32-byte aligned")
        size = (len(blob) + 0x1F) & ~0x1F
        if self.overlaps(addr, size):
            raise DolError(f"new section {addr:#010x}+{size:#x} overlaps an existing section/bss")
        slot = next((i for i in range(N_TEXT) if self.sizes[i] == 0), None)
        if slot is None:
            raise DolError("no free text section slot")
        off = (len(self.data) + 0x1F) & ~0x1F
        self.data.extend(b"\0" * (off - len(self.data)))
        self.data.extend(blob + b"\0" * (size - len(blob)))
        self.offsets[slot], self.addrs[slot], self.sizes[slot] = off, addr, size
        self._write_header()
        return slot

    def _write_header(self):
        self.data[0x00:0x48] = struct.pack(">18I", *self.offsets)
        self.data[0x48:0x90] = struct.pack(">18I", *self.addrs)
        self.data[0x90:0xD8] = struct.pack(">18I", *self.sizes)

    def to_bytes(self) -> bytes:
        return bytes(self.data)
