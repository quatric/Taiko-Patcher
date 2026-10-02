import struct,sys
from dol import Dol
def starts(d,lo,hi):
    out=[]
    for a in range(lo,hi,4):
        o=d.v2o(a); x=struct.unpack('>I',d.d[o:o+4])[0]
        if x>>16==0x9421 and (x&0xFFFF)>0x8000:
            # next few instrs contain mflr
            if any(struct.unpack('>I',d.d[o+4*j:o+4*j+4])[0]==0x7C0802A6 for j in range(1,4)): out.append(a)
    return out
if __name__=='__main__':
    d=Dol(f'taiko{sys.argv[1]}.dol'); print([hex(x) for x in starts(d,int(sys.argv[2],16),int(sys.argv[3],16))])
