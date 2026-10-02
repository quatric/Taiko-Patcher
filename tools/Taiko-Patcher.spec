# -*- mode: python ; coding: utf-8 -*-
import os, sys
from PyInstaller.utils.hooks import collect_all

ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))
try:
    dnd_datas, dnd_binaries, dnd_hidden = collect_all('tkinterdnd2')   # keeps drag-and-drop working when frozen
except Exception:
    dnd_datas, dnd_binaries, dnd_hidden = [], [], []                    # not installed: click-to-browse only
WIT = os.environ.get('WIT') or next((p for p in (os.path.expanduser('~/.local/bin/wit'), '/usr/local/bin/wit', '/opt/homebrew/bin/wit') if os.path.isfile(p)), None)
wit_bins = [(WIT, '.')] if WIT else []                                 # bundled so disc images work out of the box
ICON = os.path.join(ROOT, 'assets', 'icon.icns' if sys.platform == 'darwin' else 'icon.ico')

a = Analysis([os.path.join(ROOT, 'taiko_patcher', 'gui.py')], pathex=[ROOT],
             binaries=dnd_binaries + wit_bins,
             datas=dnd_datas + [(os.path.join(ROOT, 'assets', 'icon.png'), 'assets'),
                                (os.path.join(ROOT, 'assets', 'logo.png'), 'assets'),
                                (os.path.join(ROOT, 'taiko_patcher', 'data'), 'taiko_patcher/data')],
             hiddenimports=dnd_hidden)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Taiko-Patcher', console=False, icon=ICON)
coll = COLLECT(exe, a.binaries, a.datas, name='Taiko-Patcher')
if sys.platform == 'darwin':
    app = BUNDLE(coll, name='Taiko-Patcher.app', icon=ICON, bundle_identifier='xyz.quatric.taiko-patcher')
