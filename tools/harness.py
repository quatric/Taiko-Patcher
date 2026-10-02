import subprocess, sys, time, os, re, struct
from gdbc import G

U = os.environ.get('DOLPHIN_USER', os.path.expanduser('~/taiko-dolphin-user'))  # isolated Dolphin user dir with GCPadNew.ini (Pipe/0/pad1) and SIDevice0=6


def launch(image):
    p = subprocess.Popen(['/Applications/Dolphin.app/Contents/MacOS/Dolphin', '-u', U, '-b', '-e', image],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    port = None
    for _ in range(60):
        time.sleep(1)
        out = subprocess.run(['lsof', '-nP', '-a', '-p', str(p.pid), '-iTCP', '-sTCP:LISTEN'],
                             capture_output=True, text=True).stdout
        m = re.search(r':(\d+) \(LISTEN\)', out)
        if m:
            port = int(m.group(1))
            break
    if not port:
        p.kill()
        raise SystemExit('no gdb port')
    return p, port


class Pipe:
    def __init__(s, name='pad1'):
        s.f = os.open(f'{U}/Pipes/{name}', os.O_WRONLY | os.O_NONBLOCK)

    def send(s, line):
        os.write(s.f, (line + '\n').encode())


class Sess:
    def __init__(s, image):
        s.p, s.port = launch(image)
        s.g = G(s.port)
        s.g.cmd('?')
        s.pipe = None

    def go(s):
        s.g.cont()

    def stop(s):
        s.g.halt()
        time.sleep(0.4)
        s.g.s.settimeout(3)
        try:
            s.g.s.recv(512)
        except Exception:
            pass

    def peek(s, addr, n):
        return s.g.mem(addr, n)

    def u32s(s, addr, n):
        return struct.unpack('>%dI' % n, s.peek(addr, 4 * n))

    def close(s):
        try:
            s.p.kill()
        except Exception:
            pass
