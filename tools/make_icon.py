#!/usr/bin/env python3
"""Build assets/icon.{png,ico,icns} from assets/logo.png (the Taiko no Tatsujin Wii logo, padded to a square).
icns needs macOS `iconutil`."""
import os, shutil, subprocess, tempfile
from PIL import Image

A = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets')
S = 1024
logo = Image.open(os.path.join(A, 'logo.png')).convert('RGBA')
k = S * 0.96 / max(logo.size)
logo = logo.resize((round(logo.width * k), round(logo.height * k)), Image.LANCZOS)
out = Image.new('RGBA', (S, S), (0, 0, 0, 0))
out.alpha_composite(logo, ((S - logo.width) // 2, (S - logo.height) // 2))
out.save(os.path.join(A, 'icon.png'))
out.save(os.path.join(A, 'icon.ico'), sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
if shutil.which('iconutil'):
    with tempfile.TemporaryDirectory() as t:
        d = os.path.join(t, 'icon.iconset'); os.makedirs(d)
        for s in (16, 32, 128, 256, 512):
            out.resize((s, s), Image.LANCZOS).save(os.path.join(d, f'icon_{s}x{s}.png'))
            out.resize((s * 2, s * 2), Image.LANCZOS).save(os.path.join(d, f'icon_{s}x{s}@2x.png'))
        subprocess.run(['iconutil', '-c', 'icns', d, '-o', os.path.join(A, 'icon.icns')], check=True)
print('icons written')
