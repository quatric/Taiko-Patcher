import sys,subprocess,tempfile,os
from dol import Dol
OBJ='/opt/devkitpro/devkitPPC/bin/powerpc-eabi-objdump'
def dis(n,lo,hi):
    d=Dol(f'taiko{n}.dol'); o=d.v2o(lo)
    f=tempfile.NamedTemporaryFile(delete=False); f.write(d.d[o:o+(hi-lo)]); f.close()
    r=subprocess.run([OBJ,'-D','-EB','-b','binary','-m','powerpc:750','-M','750cl',f'--adjust-vma={hex(lo)}',f.name],capture_output=True,text=True)
    os.unlink(f.name)
    return '\n'.join(l for l in r.stdout.splitlines()[7:])
if __name__=='__main__':
    print(dis(int(sys.argv[1]),int(sys.argv[2],16),int(sys.argv[3],16)))
