#!/usr/bin/env python3
"""Consistency checks run by CI (no game files needed)."""
import filecmp
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, ROOT)
errors = []


def need(cond, msg):
    if not cond:
        errors.append(msg)


from taiko_patcher import games, ppc
from taiko_patcher.patcher import CFG_FIELDS, _payload

# payload shipped inside the package must be the one built from payload/
for f in ('payload.bin', 'payload.sym'):
    need(filecmp.cmp(os.path.join(ROOT, 'payload', f), os.path.join(ROOT, 'taiko_patcher', 'data', f), shallow=False),
         f'taiko_patcher/data/{f} differs from payload/{f} (rebuild with payload/build.sh and copy)')

blob, syms = _payload()
base = syms['TP_BASE']
need(base % 0x20 == 0, 'payload base not 32-byte aligned')
need(base + len(blob) <= 0x80003800, 'payload runs into 0x80003800+, which the game overwrites at runtime')
for s in ('tp_cfg', 'tp_state', 'tp_probe_wrap', 'tp_call_probe', 'tp_update_hook', 'tp_hold_hook_tk',
          'tp_hold_hook_core', 'tp_exit_hold_tk', 'tp_exit_hold_core', 'tp_poll_ch'):
    need(s in syms, f'payload symbol {s} missing')
need(int.from_bytes(blob[syms['tp_cfg'] - base:][:4], 'big') == 0x544B5054, 'tp_cfg magic wrong')
need(syms['tp_state'] - syms['tp_cfg'] >= 4 * len(CFG_FIELDS), 'tp_cfg too small for CFG_FIELDS')

ids, shas = set(), set()
for g in games.GAMES.values():
    need(re.fullmatch(r'[A-Z0-9]{6}', g.id6), f'{g.key}: bad id6')
    need(g.id6 not in ids, f'{g.key}: duplicate id6')
    ids.add(g.id6)
    need(g.supported, f'{g.key}: no hook family')
    need(g.dol_sha1 and re.fullmatch(r'[0-9a-f]{40}', g.dol_sha1), f'{g.key}: missing/bad dol_sha1')
    need(g.dol_sha1 not in shas, f'{g.key}: duplicate sha1')
    shas.add(g.dol_sha1)
    need(ppc.is_bl(g.probe_call.expect), f'{g.key}: probe_call is not a bl')
    for site in [g.probe_call] + [s for s in (g.hold_tk, g.hold_core, g.update_hook) if s]:
        need(0x80004000 <= site.addr < 0x80800000 and site.addr % 4 == 0, f'{g.key}: bad site {site.addr:#x}')
    if g.family == 'A':
        need(g.hold_tk and g.hold_core, f'{g.key}: family A needs hold_tk/hold_core')
    else:
        need(g.update_hook and g.obj_drum and g.obj_core, f'{g.key}: family B needs update_hook and object addresses')

for a in ('icon.png', 'icon.ico', 'icon.icns', 'logo.png'):
    need(os.path.getsize(os.path.join(ROOT, 'assets', a)) > 1000, f'assets/{a} missing')

if errors:
    print('\n'.join('FAIL: ' + e for e in errors))
    sys.exit(1)
print('ok: payload', len(blob), 'bytes @', hex(base), '|', len(games.GAMES), 'games')
