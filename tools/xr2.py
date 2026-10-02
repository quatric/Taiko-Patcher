import struct,sys
from dol import Dol
def refs(d,target,span=10):
    hi=(target+0x8000)>>16; lo=target&0xFFFF
    res=[]
    for i,o,a,z in d.secs:
        if i>=7: continue
        w=struct.unpack('>%dI'%(z//4),d.d[o:o+z])
        for k,x in enumerate(w):
            if (x>>26)==15 and (x&0xFFFF)==hi and ((x>>16)&31)==0:
                rd=(x>>21)&31
                for j in range(k+1,min(k+span,len(w))):
                    y=w[j]; op=y>>26
                    if ((y>>16)&31)==rd and (op in (14,24) or 32<=op<=55) and (y&0xFFFF)==lo:
                        res.append(a+4*j)
    return res
if __name__=='__main__':
    d=Dol(f'taiko{sys.argv[1]}.dol')
    for t in sys.argv[2:]:
        t=int(t,16); print(hex(t),[hex(x) for x in refs(d,t)])
