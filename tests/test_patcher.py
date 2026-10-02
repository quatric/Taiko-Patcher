"""Run: python3 -m unittest discover tests   (set TAIKO_DOL_DIR to a folder with taiko1..5.dol for the game tests)"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from taiko_patcher import ppc
from taiko_patcher.dol import Dol
from taiko_patcher.games import GAMES
from taiko_patcher.patcher import PatchError, identify, patch_dol


class PpcTests(unittest.TestCase):
    def test_branches(self):
        self.assertEqual(ppc.b(0x80000000, 0x80000010), 0x48000010)
        self.assertEqual(ppc.bl(0x80000010, 0x80000000), 0x4BFFFFF1)
        self.assertEqual(ppc.branch_target(0x80033EC0, 0x480EF93D), 0x801237FC)


DIR = os.environ.get("TAIKO_DOL_DIR")


@unittest.skipUnless(DIR, "TAIKO_DOL_DIR not set")
class GameTests(unittest.TestCase):
    def test_all_games(self):
        for n in range(1, 6):
            src = open(os.path.join(DIR, f"taiko{n}.dol"), "rb").read()
            g = identify(src)
            self.assertEqual(g.key, f"taiko{n}")
            out = patch_dol(g, src)
            d = Dol(out)
            self.assertIsNotNone(d.v2o(0x80003200))
            self.assertNotEqual(d.u32(g.probe_call.addr), g.probe_call.expect)
            with self.assertRaises(PatchError):  # double patching is refused
                patch_dol(g, out)

    def test_wrong_profile_refused(self):
        src = open(os.path.join(DIR, "taiko4.dol"), "rb").read()
        with self.assertRaises(PatchError):
            patch_dol(GAMES["taiko3"], src)


def apply_gecko(txt):
    """Tiny Gecko interpreter for the two code types we emit: 04 (32-bit write) and 06 (string write)."""
    mem, lines, i = {}, [l.split("*")[0].strip() for l in txt.splitlines() if l and l[0] not in "$*[" ], 0
    while i < len(lines):
        a, b = lines[i].split()
        op, addr = int(a[:2], 16), 0x80000000 + int(a[2:], 16)
        if op == 0x04:
            mem[addr] = bytes.fromhex(b)
            i += 1
        elif op == 0x06:
            n = int(b, 16)
            data = b"".join(bytes.fromhex(x) for ln in lines[i + 1:i + 1 + (n + 7) // 8] for x in ln.split())[:n]
            mem[addr] = data
            i += 1 + (n + 7) // 8
        else:
            raise AssertionError(lines[i])
    return mem


def apply_riivolution(xml, patch_ids):
    import re
    mem = {}
    for pid in patch_ids:
        body = re.search(r'<patch id="%s">(.*?)</patch>' % pid, xml, re.S).group(1)
        for off, val in re.findall(r'offset="(0x[0-9A-F]+)" value="([0-9A-F]+)"', body):
            mem[int(off, 16)] = bytes.fromhex(val)
    return mem


def read_mem(mem, addr, n):
    for a, d in mem.items():
        if a <= addr and addr + n <= a + len(d):
            return d[addr - a:addr - a + n]
    return None


class CodeTests(unittest.TestCase):
    def test_generated_files_are_current(self):
        import subprocess
        tool = os.path.join(os.path.dirname(__file__), "..", "tools", "gen_codes.py")
        self.assertEqual(subprocess.run([sys.executable, tool, "--check"]).returncode, 0)

    @unittest.skipUnless(DIR, "TAIKO_DOL_DIR not set")
    def test_codes_match_dol_patch(self):
        from taiko_patcher import codes
        for n in range(1, 6):
            g = GAMES[f"taiko{n}"]
            patched = Dol(patch_dol(g, open(os.path.join(DIR, f"taiko{n}.dol"), "rb").read()))
            gecko = apply_gecko(codes.gecko_txt(g))
            rii = apply_riivolution(codes.riivolution_xml(g), ["gc"] + (["classic"] if g.tables else []))
            for mem in (gecko, rii):
                for addr, data in mem.items():
                    self.assertEqual(patched.read(addr, len(data)), data, (g.key, hex(addr)))
                # every hook word must be present
                self.assertEqual(read_mem(mem, g.probe_call.addr, 4), patched.read(g.probe_call.addr, 4))
            # the runtime state must never be written by a code
            import taiko_patcher.patcher as P
            _, syms = P._payload()
            for mem in (gecko, rii):
                for addr, data in mem.items():
                    self.assertFalse(addr <= syms["tp_state"] < addr + len(data), "code overwrites tp_state")


if __name__ == "__main__":
    unittest.main()
