import socket,sys,time
class G:
    def __init__(s,port,host='127.0.0.1'):
        s.s=socket.create_connection((host,port),timeout=5)
    def _csum(s,b): return sum(b)&0xff
    def cmd(s,c):
        b=c.encode(); s.s.sendall(b'$'+b+b'#%02x'%s._csum(b))
        buf=b''
        t=time.time()
        while time.time()-t<5:
            try: d=s.s.recv(65536)
            except socket.timeout: break
            if not d: break
            buf+=d
            if b'#' in buf[buf.find(b'$'):] and len(buf)-buf.rfind(b'#')>=3: break
        s.s.sendall(b'+')
        i=buf.find(b'$'); j=buf.rfind(b'#')
        return buf[i+1:j].decode() if i>=0 else buf.decode(errors='replace')
    def mem(s,addr,n):
        r=s.cmd('m%x,%x'%(addr,n)); return bytes.fromhex(r)
    def cont(s): s.s.sendall(b'$c#63')
    def halt(s): s.s.sendall(b'\x03')
if __name__=='__main__':
    g=G(int(sys.argv[1]))
    print(g.cmd('?'))
    print(g.mem(int(sys.argv[2],16),int(sys.argv[3])).hex())
