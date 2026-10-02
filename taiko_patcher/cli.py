import argparse
import sys

from . import __version__, games
from .disc import kind_of, patch_any, read_dol_for_info
from .patcher import PatchError, identify


def main(argv=None):
    ap = argparse.ArgumentParser(prog="taiko-patcher",
                                 description="Add GameCube pad / DK Bongo / better Classic Controller support to "
                                             "the five Taiko no Tatsujin Wii games.")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list supported games")

    p = sub.add_parser("info", help="identify a main.dol / extracted folder")
    p.add_argument("input")

    p = sub.add_parser("patch", help="patch a main.dol, an extracted game folder or a disc image")
    p.add_argument("input")
    p.add_argument("-o", "--output")
    p.add_argument("--game", choices=sorted(games.GAMES), help="force a game profile (normally auto-detected)")
    p.add_argument("--no-gc", action="store_true", help="do not add GameCube pad / DK Bongo support")
    p.add_argument("--no-classic", action="store_true", help="do not touch the Classic Controller layout")
    p.add_argument("--no-stick", action="store_true", help="GC left stick does not act as D-pad")
    p.add_argument("--no-clap", action="store_true", help="DK Bongo clap does not act as ka")
    args = ap.parse_args(argv)

    if args.cmd == "list":
        for g in games.GAMES.values():
            print(f"{g.key}  {g.id6}  {g.title}  [{'supported' if g.supported else 'research in progress'}]")
        return 0

    if args.cmd == "info":
        data = read_dol_for_info(args.input)
        if data is None:
            print(f"{args.input}: kind={kind_of(args.input)} (info needs a DOL or an extracted folder)")
            return 1
        g = identify(data)
        print(f"{args.input}: {g.title} [{g.id6}] (profile {g.key}, family {g.family or '-'})" if g
              else f"{args.input}: unknown DOL")
        return 0 if g else 1

    flags = None
    if args.no_stick or args.no_clap:
        flags = 4  # C-stick stays on
        if not args.no_stick:
            flags |= 1
        if not args.no_clap:
            flags |= 2
    try:
        out = patch_any(args.input, args.output, game_key=args.game, gc=not args.no_gc,
                        classic=not args.no_classic, flags=flags)
    except PatchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"done: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
