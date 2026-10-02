"""Input handling: bare DOL, extracted game folder, or a disc image (ISO/WBFS/...), the latter via Wiimms ISO Tool."""
import os
import shutil
import subprocess
import tempfile

from . import games
from .patcher import PatchError, identify, patch_dol

IMAGE_EXTS = {".iso", ".wbfs", ".wdf", ".wia", ".ciso", ".gcz", ".wdf1", ".wdf2"}


def find_wit():
    cand = [os.environ.get("WIT"), shutil.which("wit"), os.path.expanduser("~/.local/bin/wit"), "/usr/local/bin/wit",
            "/opt/homebrew/bin/wit"]
    for c in cand:
        if c and os.path.exists(c):
            return c
    return None


def _find_dol_in_tree(path):
    """Return the path of sys/main.dol for an extracted folder (accepts the .d folder, DATA, or the folder holding sys/)."""
    for sub in ("", "DATA", os.path.join("DATA")):
        p = os.path.join(path, sub, "sys", "main.dol")
        if os.path.isfile(p):
            return p
    return None


def kind_of(path):
    if os.path.isdir(path):
        return "tree" if _find_dol_in_tree(path) else "unknown"
    ext = os.path.splitext(path)[1].lower()
    if ext == ".dol":
        return "dol"
    if ext in IMAGE_EXTS:
        return "image"
    with open(path, "rb") as f:
        head = f.read(0x100)
    # a DOL has its first text section at file offset >= 0x100 and an entry point at 0xE0
    return "dol" if len(head) == 0x100 and head[0:4] == b"\0\0\1\0" else "unknown"


def read_dol_for_info(path):
    k = kind_of(path)
    if k == "dol":
        return open(path, "rb").read()
    if k == "tree":
        return open(_find_dol_in_tree(path), "rb").read()
    return None


def run_wit(*args):
    wit = find_wit()
    if not wit:
        raise PatchError("Wiimms ISO Tool (wit) is needed to read/write disc images. Install it from https://wit.wiimm.de/ "
                         "or patch the extracted main.dol instead.")
    r = subprocess.run([wit, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise PatchError(f"wit {' '.join(args[:2])} failed ({r.returncode}):\n{(r.stderr or r.stdout)[-800:]}")
    return r.stdout


def patch_any(src, dst=None, *, game_key=None, log=print, **opts):
    """Patch SRC (dol / tree / image). Returns the output path."""
    kind = kind_of(src)
    if kind == "unknown":
        raise PatchError(f"{src}: not a DOL, an extracted game folder or a supported disc image")

    def pick(dol_bytes):
        g = games.GAMES[game_key] if game_key else identify(dol_bytes)
        if g is None:
            try:
                from .dol import Dol
                if Dol(dol_bytes).v2o(0x80003200) is not None:
                    raise PatchError("this game already looks patched (restore the .bak / .orig to patch it again)")
            except PatchError:
                raise
            except Exception:
                pass
            raise PatchError("this main.dol is not one of the five known Taiko no Tatsujin Wii versions "
                             "(use --game to force a profile, at your own risk)")
        log(f"game: {g.title} [{g.id6}]")
        return g

    if kind == "dol":
        data = open(src, "rb").read()
        out = patch_dol(pick(data), data, **opts)
        dst = dst or os.path.splitext(src)[0] + ".patched.dol"
        open(dst, "wb").write(out)
        return dst

    if kind == "tree":
        dol_path = _find_dol_in_tree(src)
        data = open(dol_path, "rb").read()
        out = patch_dol(pick(data), data, **opts)
        if dst:  # write only the new DOL
            open(dst, "wb").write(out)
            return dst
        bak = dol_path + ".orig"
        if not os.path.exists(bak):
            shutil.copy2(dol_path, bak)
        open(dol_path, "wb").write(out)
        log(f"patched in place (backup: {bak})")
        return dol_path

    # disc image: extract -> patch main.dol -> recompose
    ext = os.path.splitext(src)[1].lower()
    dst = dst or os.path.splitext(src)[0] + ".patched" + (ext if ext in (".iso", ".wbfs") else ".wbfs")
    if os.path.abspath(dst) == os.path.abspath(src):
        raise PatchError("output must differ from input")
    work = tempfile.mkdtemp(prefix="taiko-patcher-", dir=os.path.dirname(os.path.abspath(dst)))
    try:
        tree = os.path.join(work, "tree")
        log("extracting disc image (this takes a minute)...")
        run_wit("extract", src, tree, "--overwrite")
        dol_path = _find_dol_in_tree(tree)
        if not dol_path:
            raise PatchError("could not find sys/main.dol in the extracted image")
        data = open(dol_path, "rb").read()
        out = patch_dol(pick(data), data, **opts)
        open(dol_path, "wb").write(out)
        log("rebuilding disc image...")
        fmt = "--iso" if dst.lower().endswith(".iso") else "--wbfs"
        run_wit("copy", tree, "--dest", dst, fmt, "--overwrite")
        return dst
    finally:
        shutil.rmtree(work, ignore_errors=True)
