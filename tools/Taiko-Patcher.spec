# -*- mode: python ; coding: utf-8 -*-
import os, sys
from PyInstaller.utils.hooks import collect_all

ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))
dnd_datas, dnd_binaries, dnd_hidden = collect_all('tkinterdnd2')   # keeps drag-and-drop working when frozen
ICON = os.path.join(ROOT, 'assets', 'icon.icns' if sys.platform == 'darwin' else 'icon.ico')

a = Analysis([os.path.join(ROOT, 'taiko_patcher', 'gui.py')], pathex=[ROOT],
             binaries=dnd_binaries,
             datas=dnd_datas + [(os.path.join(ROOT, 'assets', 'icon.png'), 'assets'),
                                (os.path.join(ROOT, 'taiko_patcher', 'data'), 'taiko_patcher/data')],
             hiddenimports=dnd_hidden)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Taiko-Patcher', console=False, icon=ICON)
coll = COLLECT(exe, a.binaries, a.datas, name='Taiko-Patcher')
if sys.platform == 'darwin':
    app = BUNDLE(coll, name='Taiko-Patcher.app', icon=ICON, bundle_identifier='xyz.quatric.taiko-patcher')
