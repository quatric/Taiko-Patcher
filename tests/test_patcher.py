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


if __name__ == "__main__":
    unittest.main()
