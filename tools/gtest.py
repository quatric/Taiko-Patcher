"""usage: gtest.py N [idle_seconds]   -- build patched image for game N, boot in Dolphin, drive GC pad via pipe, print game state"""
import sys, os, time, struct, subprocess, shutil, json
from harness import *
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, P)
from taiko_patcher.games import GAMES
N = int(sys.argv[1]); idle = float(sys.argv[2]) if len(sys.argv) > 2 else 40
G = GAMES[f'taiko{N}']
SYM = dict(l.split() for l in open(P + '/payload/payload.sym'))
STATE = int(SYM['tp_state'], 16)
NAMES = {1: 'Taiko no Tatsujin Wii (Japan)', 2: 'Taiko no Tatsujin Wii - Chou Goukaban (Japan)',
         3: 'Taiko no Tatsujin Wii - Dodoon to 2-daime! (Japan)', 4: 'Taiko no Tatsujin Wii - Ketteiban (Japan)',
         5: 'Taiko no Tatsujin Wii - Minna de Party 3-daime! (Japan)'}
W = os.environ.get('TAIKO_WORK', os.path.expanduser('~/taiko-work'))  # holds taikoN.patched.dol and scratch images
ORIG = os.path.expanduser(f'~/Downloads/{NAMES[N]}.d')
run = f'{W}/run{N}'
img = f'{W}/taiko{N}.patched.wbfs'
if '--nobuild' not in sys.argv:
    shutil.rmtree(run, ignore_errors=True)
    os.makedirs(run + '/DATA')
    os.symlink(ORIG + '/UPDATE', run + '/UPDATE')
    for f in os.listdir(ORIG + '/DATA'):
        s = ORIG + '/DATA/' + f
        if f == 'files':
            os.symlink(s, run + '/DATA/files')
        elif f == 'sys':
            shutil.copytree(s, run + '/DATA/sys')
        elif os.path.isdir(s):
            shutil.copytree(s, run + '/DATA/' + f)
        else:
            shutil.copy(s, run + '/DATA/' + f)
    shutil.copy(f'{W}/taiko{N}.patched.dol', run + '/DATA/sys/main.dol')
    r = subprocess.run([os.path.expanduser('~/.local/bin/wit'), 'copy', run, '--dest', img, '--wbfs', '--overwrite'], capture_output=True, text=True)
    print('wit rc', r.returncode, flush=True)

# addresses to watch (per game)
WATCH = {
    1: dict(drum=0x80794840, core=0x807b2220, ret=0x806faac0, typ=0x806faab0),
    2: dict(drum=0x804168b8, core=0x8041684c, ret=0x8041e1c0, typ=0x8041e1b0),
    3: dict(drum=0x803e54d8, core=0x803e546c, ret=0x803e81e0, typ=0x803e81d0),
    4: dict(drum=0x803d8df8, core=0x803d8d8c, ret=0x803e0700, typ=0x803e06f0),
    5: dict(drum=0x803813d8, core=0x8038136c, ret=0x80388ce0, typ=0x80388cd0),
}[N]
S = Sess(img)
print('port', S.port, flush=True)
S.go()
time.sleep(1)
pipe = Pipe()
t0 = time.time()

def alive():
    return S.p.poll() is None

def snap(tag):
    if not alive():
        print('DOLPHIN EXITED rc', S.p.returncode, flush=True); sys.exit(3)
    S.stop()
    st = S.peek(STATE, 0x50)
    tk = struct.unpack('>4I', st[0:16]); core = struct.unpack('>4I', st[32:48])
    present = list(st[0x40:0x44])
    h0 = S.u32s(STATE + 0x54, 1)[0]
    d = S.u32s(WATCH['drum'], 4); c = S.u32s(WATCH['core'], 4)
    ret = S.u32s(WATCH['ret'], 2); typ = S.u32s(WATCH['typ'], 2)
    print(f'{time.time()-t0:4.0f}s {tag:12s} tk={tk[0]:#04x} core={core[0]:#06x} present={present[0]} | game: drumHold={d[0]:#04x} coreHold={c[0]:#06x} probe={ret[0]:#x} type={typ[0]:#x} | rawH={h0:#010x}', flush=True)
    S.go()

time.sleep(idle)
snap('idle')
seq = [('A', 'A'), ('B', 'B'), ('X', 'X'), ('Y', 'Y'), ('L', 'L'), ('R', 'R'), ('Z', 'Z'), ('START', 'START'),
       ('D_LEFT', 'D_LEFT'), ('D_RIGHT', 'D_RIGHT'), ('D_UP', 'D_UP'), ('D_DOWN', 'D_DOWN')]
for name, cmd in seq:
    for attempt in range(4):
        pipe.send(f'PRESS {cmd}'); time.sleep(1.2)
        S.stop(); raw = S.u32s(STATE + 0x54, 1)[0]; S.go()
        if raw != 0x808080: break
        pipe.send(f'RELEASE {cmd}'); os.close(pipe.f); time.sleep(1); pipe = Pipe()
    snap(name)
    pipe.send(f'RELEASE {cmd}'); time.sleep(0.4)
for ax, val, tag in (('MAIN', '0 0.5', 'stick left'), ('MAIN', '1 0.5', 'stick right'), ('C', '0 0.5', 'cstick left'), ('C', '1 0.5', 'cstick right')):
    pipe.send(f'SET {ax} {val}'); time.sleep(1.2); snap(tag)
    pipe.send(f'SET {ax} 0.5 0.5'); time.sleep(0.4)
snap('final idle')
S.close()
