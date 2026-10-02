"""Gecko code lists (Dolphin .ini / generic .txt) and Riivolution XML, generated from the same plan as the DOL patch.

The payload's runtime state (everything from `tp_state` on) is never written: Gecko handlers re-apply their
writes continuously and would otherwise wipe the state every frame.
"""
from .games import Game
from .patcher import make_plan

GC_TITLE = "GameCube Controller / DK Bongos"
CL_TITLE = "Classic Controller ZL/ZR"


def _chunks(addr, blob, size=0x100):
    for i in range(0, len(blob), size):
        yield addr + i, blob[i:i + size]


def gecko_lines(game: Game):
    """Return [(title, comment_lines, code_lines)]."""
    out = []
    plan = make_plan(game, gc=True, classic=False)
    code = []
    static = plan.payload[:plan.static_len]
    for addr, chunk in _chunks(plan.base, static, 0x100):
        pad = chunk + b"\0" * (-len(chunk) % 8)
        code.append(f"06{addr & 0xFFFFFF:06X} {len(chunk):08X}")
        code += [pad[i:i + 4].hex().upper() + " " + pad[i + 4:i + 8].hex().upper() for i in range(0, len(pad), 8)]
    for addr, word in plan.writes:
        code.append(f"04{addr & 0xFFFFFF:06X} {word:08X}")
    out.append((GC_TITLE, [
        f"*{game.title} ({game.id6})",
        "*Play with GameCube controllers / DK Bongos in any port. They appear to the game as a TaTaCon drum.",
        "*B/Y/down = left don, A/X/up = right don, L/left = left ka, R/right = right ka, Start = pause, Z = cancel.",
    ], code))
    cplan = make_plan(game, gc=False, classic=True)
    if cplan.tables:
        out.append((CL_TITLE, [f"*{game.title} ({game.id6})", "*Classic Controller ZL/ZR also hit ka (the other Taiko Wii games already do)."],
                    [f"04{a & 0xFFFFFF:06X} {w:08X}" for a, w in cplan.tables]))
    return out


def gecko_txt(game: Game):
    lines = []
    for title, comments, code in gecko_lines(game):
        lines += ["$" + title] + comments + code
    return "\n".join(lines) + "\n"


def gecko_ini(game: Game):
    names = [t for t, _, _ in gecko_lines(game)]
    return "[Gecko]\n" + gecko_txt(game) + "[Gecko_Enabled]\n" + "".join(f"${n}\n" for n in names)


def riivolution_xml(game: Game):
    plan = make_plan(game, gc=True, classic=False)
    static = plan.payload[:plan.static_len]
    mem = [f'    <memory offset="0x{a:08X}" value="{c.hex().upper()}" />' for a, c in _chunks(plan.base, static)]
    mem += [f'    <memory offset="0x{a:08X}" value="{w:08X}" />' for a, w in plan.writes]
    cplan = make_plan(game, gc=False, classic=True)
    opts = [f'      <option name="{GC_TITLE}" default="1">\n        <choice name="Enabled"><patch id="gc" /></choice>\n      </option>']
    patches = [f'  <patch id="gc">\n' + "\n".join(mem) + "\n  </patch>"]
    if cplan.tables:
        opts.append(f'      <option name="{CL_TITLE}" default="1">\n        <choice name="Enabled"><patch id="classic" /></choice>\n      </option>')
        patches.append('  <patch id="classic">\n' + "\n".join(
            f'    <memory offset="0x{a:08X}" value="{w:08X}" />' for a, w in cplan.tables) + "\n  </patch>")
    return (f"<!-- {game.title}: patches by quatric -->\n"
            f'<wiidisc version="1" root="/">\n  <id game="{game.id6}" version="0" />\n  <options>\n'
            f'    <section name="{game.title}">\n' + "\n".join(opts) + "\n    </section>\n  </options>\n"
            + "\n".join(patches) + "\n</wiidisc>\n")
