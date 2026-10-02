"""Applies the generic payload + per-game hooks to a main.dol."""
import hashlib
import struct
from importlib import resources

from . import ppc
from .dol import Dol, DolError
from .games import Game


class PatchError(Exception):
    pass


CFG_FIELDS = ["magic", "tk_cl", "tk_rl", "tk_cr", "tk_rr", "core_start", "core_cancel", "flags",
              "stick_thresh", "clap_thresh", "obj_drum", "obj_core"]

FLAG_STICK, FLAG_CLAP, FLAG_CSTICK = 1, 2, 4


def _payload():
    pkg = resources.files(__package__) / "data"
    blob = (pkg / "payload.bin").read_bytes()
    syms = {}
    for line in (pkg / "payload.sym").read_text().splitlines():
        name, addr = line.split()
        syms[name] = int(addr, 16)
    return blob, syms


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def identify(dol_bytes: bytes):
    """Return the Game whose main.dol this is (by SHA-1), or None."""
    from .games import GAMES
    h = sha1(dol_bytes)
    for g in GAMES.values():
        if g.dol_sha1 == h:
            return g
    return None


def _check(dol: Dol, game: Game, name: str, site):
    got = dol.u32(site.addr)
    if got != site.expect:
        raise PatchError(f"{game.key}: {name} @ {site.addr:#010x} is {got:#010x}, expected {site.expect:#010x} "
                         "(wrong game version / already patched?)")


def patch_dol(game: Game, dol_bytes: bytes, *, gc: bool = True, classic: bool = True, flags: int = None) -> bytes:
    if not game.supported:
        raise PatchError(f"{game.title}: not supported yet ({game.note or 'no profile'})")
    try:
        dol = Dol(dol_bytes)
    except DolError as e:
        raise PatchError(str(e)) from e

    blob, syms = _payload()
    base = syms["TP_BASE"]
    if dol.overlaps(base, (len(blob) + 0x1F) & ~0x1F):
        raise PatchError("this DOL looks already patched (payload address is occupied)")

    # --- sanity checks before touching anything -----------------------------------------
    sites = [("probe_call", game.probe_call)]
    if game.family == "A":
        sites += [("hold_tk", game.hold_tk), ("hold_core", game.hold_core)]
    else:
        sites += [("update_hook", game.update_hook)]
    for name, site in sites:
        _check(dol, game, name, site)
    if not ppc.is_bl(game.probe_call.expect):
        raise PatchError("probe_call must be a bl")
    if classic:
        for t in game.tables:
            got = dol.u32(t.addr)
            if got != t.expect:
                raise PatchError(f"{game.key}: table word @ {t.addr:#010x} is {got:#010x}, expected {t.expect:#010x}")

    if gc:
        out = bytearray(blob)

        def poke(sym, word):
            o = syms[sym] - base
            out[o:o + 4] = struct.pack(">I", word)

        cfg = dict(magic=0x544B5054, flags=FLAG_STICK | FLAG_CLAP | FLAG_CSTICK, stick_thresh=48,
                   clap_thresh=0x50, obj_drum=game.obj_drum, obj_core=game.obj_core)
        cfg.update(game.cfg)
        if flags is not None:
            cfg["flags"] = flags
        o = syms["tp_cfg"] - base
        out[o:o + 4 * len(CFG_FIELDS)] = struct.pack(">%dI" % len(CFG_FIELDS), *[cfg[k] for k in CFG_FIELDS])

        # the real WPADProbe call inside our wrapper, then redirect the game's call to the wrapper
        real_probe = ppc.branch_target(game.probe_call.addr, game.probe_call.expect)
        poke("tp_call_probe", ppc.bl(syms["tp_call_probe"], real_probe))
        if game.family == "A":
            poke("tp_exit_hold_tk", ppc.b(syms["tp_exit_hold_tk"], game.hold_tk.addr + 4))
            poke("tp_exit_hold_core", ppc.b(syms["tp_exit_hold_core"], game.hold_core.addr + 4))

        dol.add_text_section(base, bytes(out))
        dol.write_u32(game.probe_call.addr, ppc.bl(game.probe_call.addr, syms["tp_probe_wrap"]))
        if game.family == "A":
            dol.write_u32(game.hold_tk.addr, ppc.b(game.hold_tk.addr, syms["tp_hold_hook_tk"]))
            dol.write_u32(game.hold_core.addr, ppc.b(game.hold_core.addr, syms["tp_hold_hook_core"]))
        else:
            dol.write_u32(game.update_hook.addr, ppc.bl(game.update_hook.addr, syms["tp_update_hook"]))

    if classic:
        for t in game.tables:
            dol.write_u32(t.addr, t.new)
    return dol.to_bytes()
