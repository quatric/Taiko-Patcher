#!/usr/bin/env python3
"""Build assets/icon.{png,ico,icns} from assets/icon-source.png.

The source has an opaque white backdrop. Outside the black rim becomes transparent; the band between the
rim and the red face is forced to solid white. icns needs macOS `iconutil`.
"""
import os, shutil, subprocess, tempfile
from collections import deque
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(HERE, '..', 'assets')
S = 1024

im = Image.open(os.path.join(A, 'icon-source.png')).convert('RGBA')
side = max(im.size)
sq = Image.new('RGBA', (side, side), (255, 255, 255, 255))
sq.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
im = sq.resize((S, S), Image.LANCZOS)
px = im.load()

# flood-fill the backdrop from the corners through near-white pixels, stopping at the rim
dark = lambda p: sum(p[:3]) < 3 * 215
outside = bytearray(S * S)
q = deque([(0, 0), (S - 1, 0), (0, S - 1), (S - 1, S - 1)])
while q:
    x, y = q.popleft()
    if x < 0 or y < 0 or x >= S or y >= S or outside[y * S + x] or dark(px[x, y]):
        continue
    outside[y * S + x] = 1
    q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

out = Image.new('RGBA', (S, S), (0, 0, 0, 0))
op = out.load()
for y in range(S):
    for x in range(S):
        if outside[y * S + x]:
            continue
        r, g, b, _ = px[x, y]
        # the bright band between rim and face -> pure white; keep rim / face / antialiasing
        if min(r, g, b) > 215:
            op[x, y] = (255, 255, 255, 255)
        else:
            op[x, y] = (r, g, b, 255)
# soften the outer edge: 1px antialias by blurring only the alpha of the boundary
from PIL import ImageFilter
alpha = out.getchannel('A').filter(ImageFilter.GaussianBlur(1.2))
out.putalpha(alpha)
out.save(os.path.join(A, 'icon.png'))
out.save(os.path.join(A, 'icon.ico'), sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
if shutil.which('iconutil'):
    with tempfile.TemporaryDirectory() as t:
        d = os.path.join(t, 'icon.iconset'); os.makedirs(d)
        for s in (16, 32, 128, 256, 512):
            out.resize((s, s), Image.LANCZOS).save(os.path.join(d, f'icon_{s}x{s}.png'))
            out.resize((s * 2, s * 2), Image.LANCZOS).save(os.path.join(d, f'icon_{s}x{s}@2x.png'))
        subprocess.run(['iconutil', '-c', 'icns', d, '-o', os.path.join(A, 'icon.icns')], check=True)
print('icons written to', os.path.normpath(A))
