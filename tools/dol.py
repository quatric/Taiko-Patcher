import struct,sys,re
class Dol:
    def __init__(s,path):
        s.d=open(path,'rb').read()
        h=struct.unpack('>18I18I18I7I',s.d[:0xE4]) if False else None
        s.off=struct.unpack('>18I',s.d[0:0x48]); s.addr=struct.unpack('>18I',s.d[0x48:0x90]); s.size=struct.unpack('>18I',s.d[0x90:0xD8])
        s.bss,s.bsssz,s.entry=struct.unpack('>3I',s.d[0xD8:0xE4])
        s.secs=[(i,s.off[i],s.addr[i],s.size[i]) for i in range(18) if s.size[i]]
    def v2o(s,a):
        for i,o,ad,sz in s.secs:
            if ad<=a<ad+sz: return o+a-ad
    def o2v(s,o):
        for i,of,ad,sz in s.secs:
            if of<=o<of+sz: return ad+o-of
    def u32(s,a): return struct.unpack('>I',s.d[s.v2o(a):s.v2o(a)+4])[0]
    def find(s,b):
        return [s.o2v(m.start()) for m in re.finditer(re.escape(b),s.d,re.S)]
if __name__=='__main__':
    for n in range(1,6):
        d=Dol(f'taiko{n}.dol'); print(n,hex(d.entry),[(i,hex(a),hex(z)) for i,o,a,z in d.secs],hex(d.bss),hex(d.bsssz))
        for k in [b'KPAD',b'WPAD',b'PAD',b'SIProbe',b'CLASSIC',b'SDK']:
            r=d.find(k); print('  ',k,len(r),[hex(x) for x in r[:4]])
