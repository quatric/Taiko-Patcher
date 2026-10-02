#!/usr/bin/env python3
"""Write codes/<ID6>.{txt,ini} and riivolution/<ID6>.xml for every supported game (`--check` only verifies)."""
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, ROOT)
from taiko_patcher import codes, games


def outputs():
    for g in games.GAMES.values():
        yield f'codes/{g.id6}.txt', codes.gecko_txt(g)
        yield f'codes/{g.id6}.ini', codes.gecko_ini(g)
        yield f'riivolution/{g.id6}.xml', codes.riivolution_xml(g)


def main():
    stale = []
    for rel, text in outputs():
        path = os.path.join(ROOT, rel)
        if '--check' in sys.argv:
            if not os.path.exists(path) or open(path).read() != text:
                stale.append(rel)
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, 'w').write(text)
    if stale:
        print('stale generated files (run tools/gen_codes.py):', *stale, sep='\n  ')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
