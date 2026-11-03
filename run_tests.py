#!/usr/bin/env python3
"""Chay tu dong cac chuong trinh test tren mach Logisim (headless) va so sanh voi mo hinh vang (golden ISA simulator).
Dung: python run_tests.py [--circ RiscV_SingleCycle.circ RiscV_Pipeline.circ] [--logisim path/to/logisim.jar] [--java java] [tests/*.s]"""
import sys,os,re,glob,subprocess,argparse,tempfile
import xml.etree.ElementTree as ET
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
import asm
M=0xffffffff
_G=os.path.join(HERE,'Grok_output','tests')
PROGDIR=os.path.join(_G,'programs') if os.path.isdir(_G) else os.path.join(HERE,'tests')
MODDIR=os.path.join(_G if os.path.isdir(_G) else os.path.join(HERE,'tests'),'modules')
def sx(v,b): v&=(1<<b)-1; return v-(1<<b) if v>>(b-1) else v
import struct,math
def f2b(x):
    try: return struct.unpack('<I',struct.pack('<f',x))[0]
    except OverflowError: return 0xff800000 if x<0 else 0x7f800000
def b2f(v): return struct.unpack('<f',struct.pack('<I',v&M))[0]
def fop(fn,*a):
    try: r=fn(*a)
    except (ZeroDivisionError,ValueError,OverflowError): r=None
    return r
def fdiv(a,b):
    if b==0:
        if a==0 or a!=a: return float('nan')
        return math.copysign(float('inf'),a)*math.copysign(1,b)
    return a/b
def fsqrt(a):
    if a<0: return float('nan')
    return math.sqrt(a)
def f2i(x,rm,uns=False):
    if x!=x or math.isinf(x): raise ValueError('FCVT voi NaN/Inf: hanh vi Logisim khong theo chuan, khong dung trong test')
    r={0:lambda v: round(v),1:math.trunc,2:math.floor,3:math.ceil,4:lambda v: math.floor(v+0.5),7:lambda v: round(v)}[rm](x)
    return int(r)&M
CSR_ADDR={'mstatus':0x300,'mie':0x304,'mtvec':0x305,'mscratch':0x340,'mepc':0x341,'mcause':0x342,'mip':0x344}
class Golden:
    """Mo hinh ISA: RV32I + M + Zicsr/mret + ngat may (MSI/MTI/MEI) + MMIO + tap con F; dem them su kien de doi chieu bo dem phan cung."""
    def __init__(s,words): s.words=words
    def run(s,maxsteps=200000):
        x=[0]*32; f=[0]*32; mem={}; pc=0; n=0
        cs=dict(MIE=0,MPIE=0,mie=0,mtvec=0,mscratch=0,mepc=0,mcause=0)
        io=dict(led=0,msip=0,mtimecmp=M); uart=[]; s.ev=dict(br=0,dch=0,dcm=0,irq=0)
        cache={}
        words=s.words
        def load_word(ad):
            if ad>>31:
                k=(ad>>2)&7
                return [io['led'],0,0,1,io['msip'],io['mtimecmp'],n&M,0][k]
            k=(ad>>2)&1023; idx=k&15; tag=k>>4
            if cache.get(idx)==tag: s.ev['dch']+=1
            else: s.ev['dcm']+=1; cache[idx]=tag
            return mem.get(k,0)
        def store_word(ad,new,f3,b):
            if ad>>31:
                k=(ad>>2)&7
                if k==0: io['led']=b&0xff
                elif k==2: uart.append(chr(b&0x7f))
                elif k==4: io['msip']=b&1
                elif k==5: io['mtimecmp']=b&M
                return
            k=(ad>>2)&1023; mem[k]=new; cache[k&15]=k>>4
        while n<maxsteps:
            # ---- ngat (kiem tra truoc moi lenh)
            mtip=int((n&M)>=io['mtimecmp']); mip=io['msip']<<3|mtip<<7
            pend=mip&cs['mie']
            if cs['MIE'] and pend:
                cause=0x8000000B if pend&0x800 else (0x80000003 if pend&8 else 0x80000007)
                cs['mepc']=pc; cs['mcause']=cause; cs['MPIE']=cs['MIE']; cs['MIE']=0; pc=cs['mtvec']; s.ev['irq']+=1
            i=words[pc>>2] if (pc>>2)<len(words) else 0; n+=1
            op=i&0x7f; rd=(i>>7)&31; f3=(i>>12)&7; rs1=(i>>15)&31; rs2=(i>>20)&31; f7=i>>25
            a=x[rs1]; b=x[rs2]; npc=pc+4; w=None; wf=None
            immI=sx(i>>20,12); immS=sx((f7<<5)|rd,12)
            immB=sx(((i>>31)&1)<<12|((i>>7)&1)<<11|((i>>25)&63)<<5|((i>>8)&15)<<1,13)
            immJ=sx(((i>>31)&1)<<20|((i>>12)&255)<<12|((i>>20)&1)<<11|((i>>21)&1023)<<1,21)
            def alu(f3,a,b,alt):
                sh=b&31
                return [ (a-b if alt else a+b), a<<sh, int(sx(a,32)<sx(b,32)), int(a<b), a^b,
                         ((sx(a,32)>>sh) if alt else a>>sh), a|b, a&b][f3]&M
            if op==0x33 and f7==1:
                A,B=sx(a,32),sx(b,32)
                if f3==0: w=a*b
                elif f3==1: w=(A*B)>>32
                elif f3==2: w=(A*b)>>32
                elif f3==3: w=(a*b)>>32
                elif f3==4: w=M if B==0 else (A if (A==-2**31 and B==-1) else int(A/B) if abs(A)<2**53 else 0)
                elif f3==5: w=M if b==0 else a//b
                elif f3==6: w=a if B==0 else (0 if (A==-2**31 and B==-1) else A-B*int(A/B))
                elif f3==7: w=a if b==0 else a%b
                if f3==4 and B!=0 and not(A==-2**31 and B==-1):
                    q=abs(A)//abs(B); w=q if (A<0)==(B<0) else -q
                if f3==6 and B!=0 and not(A==-2**31 and B==-1):
                    r=abs(A)%abs(B); w=-r if A<0 else r
                w&=M
            elif op==0x33: w=alu(f3,a,b,f7==0x20)
            elif op==0x13: w=alu(f3,a,immI&M,(f3==5 and f7==0x20))
            elif op in(0x03,0x07):
                ad=(a+immI)&M; o=ad&3; v=load_word(ad)>>(8*o)
                if op==0x07: wf=v&M
                else: w={0:sx(v,8)&M,1:sx(v,16)&M,2:v&M,4:v&0xff,5:v&0xffff}[f3]
            elif op in(0x23,0x27):
                if op==0x27: b=f[rs2]
                ad=(a+immS)&M; o=ad&3; k=ad>>2&1023; mk={0:0xff,1:0xffff,2:M}[f3]<<(8*o)&M
                new=(mem.get(k,0)&~mk | (b<<(8*o))&mk)&M
                store_word(ad,new,f3,b)
            elif op==0x63:
                s.ev['br']+=1
                c={0:a==b,1:a!=b,4:sx(a,32)<sx(b,32),5:sx(a,32)>=sx(b,32),6:a<b,7:a>=b}[f3]
                if c: npc=(pc+immB)&M
            elif op==0x6f: w=npc; npc=(pc+immJ)&M; s.ev['br']+=1
            elif op==0x67: w=npc; npc=(a+immI)&M&~1; s.ev['br']+=1
            elif op==0x37: w=i&0xfffff000
            elif op==0x17: w=(pc+(i&0xfffff000))&M
            elif op==0x73:
                if f3==0:
                    if i==0x30200073: cs['MIE']=cs['MPIE']; cs['MPIE']=1; npc=cs['mepc']
                    else: return dict(x=x,f=f,mem=mem,pc=pc,n=n,uart=''.join(uart),led=io['led'],ev=s.ev)
                else:
                    ca=(i>>20)&0xfff
                    rv={0x300:cs['MIE']<<3|cs['MPIE']<<7|0x1800,0x304:cs['mie'],0x305:cs['mtvec'],0x340:cs['mscratch'],0x341:cs['mepc'],
                        0x342:cs['mcause'],0x344:mip,0xC00:None,0xB00:None}.get(ca,0)
                    if rv is None: raise ValueError('test doc cycle CSR: gia tri phu thuoc thoi gian -> khong so sanh duoc')
                    src=rs1 if f3>=5 else a
                    nv={1:src,2:rv|src,3:rv&~src&M}[f3&3]
                    if ca==0x300: cs['MIE']=nv>>3&1; cs['MPIE']=nv>>7&1
                    elif ca==0x304: cs['mie']=nv&0x888
                    elif ca==0x305: cs['mtvec']=nv
                    elif ca==0x340: cs['mscratch']=nv
                    elif ca==0x341: cs['mepc']=nv
                    elif ca==0x342: cs['mcause']=nv
                    w=rv
            elif op==0x53:
                fa,fb=b2f(f[rs1]),b2f(f[rs2]); f5=f7>>2
                if f5 in(0,1,2,3):
                    r=[lambda: fa+fb,lambda: fa-fb,lambda: fa*fb,lambda: fdiv(fa,fb)][f5]()
                    wf=f2b(r)
                elif f5==0x0B: wf=f2b(fsqrt(fa))
                elif f5==0x04:
                    sa=f[rs1]&0x7fffffff; sb=f[rs2]>>31
                    wf=sa|([sb,sb^1,(f[rs1]>>31)^sb][f3])<<31
                elif f5==0x05:
                    if fa!=fa or fb!=fb: raise ValueError('FMIN/FMAX voi NaN khong dung trong test')
                    if fa==fb==0: wf=(f[rs1]|f[rs2]) if f3==0 else (f[rs1]&f[rs2])
                    else: wf=f[rs1] if ((fa<fb) if f3==0 else (fa>fb)) else f[rs2]
                elif f5==0x14: w=int([fa<=fb,fa<fb,fa==fb][f3])
                elif f5==0x18: w=f2i(fa,f3)
                elif f5==0x1A: wf=f2b(float(sx(a,32) if rs2==0 else a))
                elif f5==0x1C: w=f[rs1]
                elif f5==0x1E: wf=a
            if w is not None and rd: x[rd]=w&M
            if wf is not None: f[rd]=wf&M
            pc=npc
        raise RuntimeError('golden: qua so buoc')
def golden(words,maxsteps=200000):
    r=Golden(words).run(maxsteps); return r['x'],r['mem'],r['pc'],r['n']
# ---- Doc thanh ghi khong can 31 chan debug: moi lenh ecall duoc thay bang "jal x0, DUMP";
# doan DUMP (them vao cuoi chuong trinh) ghi x0..x31 vao DMEM word 480..511 (byte 0x780..0x7FC, base x0)
# (+ f0..f31 vao word 448..479 bang fsw neu mach ho tro F) roi ecall.
# Dia chi cac lenh goc khong doi (an toan voi jalr dia chi tuyet doi). So chu ky bao cao = do duoc - chi phi DUMP
# (chi phi do bang chuong trinh chi gom 'ecall', chay ca 2 dang).
DUMP_BASE=480; FDUMP_BASE=448
def enc_jal(rd,off):
    v=off&0x1fffff
    return ((v>>20)&1)<<31|((v>>1)&1023)<<21|((v>>11)&1)<<20|((v>>12)&255)<<12|rd<<7|0x6f
def with_dump(words,fp=False):
    w=list(words); d=len(w)
    for k,x in enumerate(words):
        if x==0x73: w[k]=enc_jal(0,(d-k)*4)
    for r in range(32):
        off=(DUMP_BASE+r)*4
        w.append(((off>>5)&127)<<25|r<<20|0<<15|2<<12|(off&31)<<7|0x23)
    if fp:
        for r in range(32):
            off=(FDUMP_BASE+r)*4
            w.append(((off>>5)&127)<<25|r<<20|0<<15|2<<12|(off&31)<<7|0x27)
    w.append(0x73); return w
def out_pins(circ):
    root=ET.parse(circ).getroot()
    main=[c for c in root.iter('circuit') if c.get('name')=='main'][0]
    pins=[]
    for comp in main.iter('comp'):
        if comp.get('name')=='Pin':
            a={x.get('name'):x.get('val') for x in comp.iter('a')}
            if a.get('type')=='output' and a['label']!='halt': pins.append(a['label'])  # tty khong in cot halt
    return pins
def find_runner(java=None,jar=None):
    """Tim cach chay Logisim headless. Tra ve list tien to lenh, vd [java,'-jar',jar] hoac [logisim-evolution.exe].
    Thu tu: --java/--logisim chi dinh -> tools/jdk/bin/java(.exe) trong du an -> bien JAVA / JAVA_HOME -> java trong PATH
    -> logisim-evolution.exe (dung JRE dong goi san, khong can cai Java)."""
    import shutil
    jars=[j for j in (jar,os.environ.get('LOGISIM_JAR'),os.path.join(HERE,'tools','logisim-evolution.jar'),
          r'C:\Program Files\logisim-evolution\app\logisim-evolution-5.0.0-all.jar') if j and os.path.exists(j)]
    jav=[]
    if java: jav.append(java)
    for b in ('java.exe','java'): jav.append(os.path.join(HERE,'tools','jdk','bin',b))
    if os.environ.get('JAVA'): jav.append(os.environ['JAVA'])
    if os.environ.get('JAVA_HOME'): jav.append(os.path.join(os.environ['JAVA_HOME'],'bin','java'))
    jav.append(shutil.which('java'))
    for j in jav:
        if j and (os.path.exists(j) or shutil.which(j)) and jars: return [j,'-jar',jars[0]]
    for e in (os.environ.get('LOGISIM_EXE'),r'C:\Program Files\logisim-evolution\logisim-evolution.exe',shutil.which('logisim-evolution')):
        if e and os.path.exists(e): return [e]
    raise SystemExit('Khong tim thay Java + logisim jar, cung khong thay logisim-evolution.exe. Xem README muc "Chay test".')
_STAGE=None
def ascii_path(p):
    """logisim-evolution.exe (launcher jpackage) lam hong ky tu Unicode trong duong dan (vd 'Kien truc' co dau).
    Neu duong dan khong phai ASCII thi chep file sang mot thu muc ASCII tam roi dung ban chep."""
    global _STAGE
    if p.isascii(): return p
    if _STAGE is None:
        import shutil
        for base in (tempfile.gettempdir(),os.environ.get('PUBLIC',''),os.path.splitdrive(HERE)[0]+os.sep,'C:\\Users\\Public'):
            if base and base.isascii() and os.path.isdir(base):
                try: _STAGE=os.path.join(base,'rv32i_logisim_tmp'); os.makedirs(_STAGE,exist_ok=True); break
                except OSError: _STAGE=None
        if _STAGE is None: raise SystemExit('Khong tim duoc thu muc ASCII de chay Logisim')
    import shutil,hashlib
    q=os.path.join(_STAGE,hashlib.md5(p.encode()).hexdigest()[:8]+'_'+(os.path.basename(p) if os.path.basename(p).isascii() else 'f'+os.path.splitext(p)[1]))
    shutil.copyfile(p,q); return q
def run(circ,hexfile,java,jar,timeout=int(os.environ.get("RT_TIMEOUT","300"))):
    ram=tempfile.mktemp(suffix='.txt')
    if not ram.isascii(): ascii_path(circ); ram=os.path.join(_STAGE,os.path.basename(ram))
    cmd=RUNNER+[ascii_path(circ),'-l',ascii_path(hexfile),'IMEM','-t','table,halt'+(',tty' if 'name="TTY"' in open(circ,encoding='utf-8').read() else ''),'--save',ram]
    p=subprocess.run(cmd,capture_output=True,text=True,errors='replace',timeout=timeout)
    # ky tu TTY (UART) duoc in xen vao dau dong bang -> tach ra
    rows=[]; uart=''
    for l in p.stdout.splitlines(True):
        m=re.match(r'(.*?)((?:[01xXuU]{1,4}(?: [01xXuU]{4})*\t)+[01xXuU]{1,4}(?: [01xXuU]{4})*)\s*$',l,re.S)
        if m: uart+=m.group(1); rows.append(m.group(2))
        elif not l.startswith('[main]'): uart+=l
    if not rows: raise RuntimeError('khong co output:\n'+p.stdout[-2000:]+p.stderr[-2000:])
    last=[c.replace(' ','') for c in rows[-1].split('\t') if c.strip()]
    vals=dict(zip(out_pins(circ),last))
    mem={}
    if os.path.exists(ram):
        ws=open(ram).read().split()[4:] if open(ram).read().startswith('v3.0') else []
        # dinh dang: v3.0 hex words plain, co the co n*val
        k=0
        for t in ws:
            if '*' in t: n,v=t.split('*'); n=int(n); v=int(v,16)
            else: n,v=1,int(t,16)
            for _ in range(n):
                if v: mem[k]=v
                k+=1
        os.remove(ram)
    halted='halted due to halt pin' in (p.stdout+p.stderr)
    return vals,mem,halted,uart
FEATS={'M':'name="MulDiv"','F':'name="FPU"','CSR':'name="CSRFile"','IO':'name="MMIO"'}
def feats(circ):
    t=open(circ,encoding='utf-8').read(); return {k for k,v in FEATS.items() if re.search('<comp [^>]*'+v,t)}
def num(vals,k):
    v=vals.get(k,'x'); return int(v,2) if re.fullmatch('[01]+',v) else None
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('tests',nargs='*'); ap.add_argument('--circ',nargs='+',default=[os.path.join(HERE,'RiscV_SingleCycle.circ'),os.path.join(HERE,'RiscV_Pipeline.circ')])
    ap.add_argument('--logisim',default=None,help='duong dan logisim-evolution jar (tu dong tim neu bo trong)')
    ap.add_argument('--java',default=None,help='duong dan java (tu dong tim neu bo trong)')
    ap.add_argument('--modules',action='store_true',help='chay them test vector cho cac module')
    ap.add_argument('--csv',default=None,help='ghi bang ket qua (chu ky, bo dem) ra file CSV')
    g=ap.parse_args()
    global RUNNER; RUNNER=find_runner(g.java,g.logisim); print('Logisim runner:',' '.join(RUNNER))
    if g.modules:
        for circ in g.circ:
            fs=feats(circ)
            for sub,f,need in (('ALU','alu',None),('ImmGen','immgen',None),('BranchUnit','branch',None),('MulDiv','muldiv','M'),('FPU','fpu','F')):
                if need and need not in fs: continue
                if not os.path.exists(os.path.join(MODDIR,f+'_vectors.txt')): continue
                p=subprocess.run(RUNNER+[ascii_path(circ),'-w',sub,ascii_path(os.path.join(MODDIR,f+'_vectors.txt'))],capture_output=True,text=True,errors='replace')
                mm=re.search(r'Passed: (\d+), Failed: (\d+)',p.stdout+p.stderr)
                print(f'[MODULE] {os.path.basename(circ):24s} {sub:10s} '+(f'Passed {mm.group(1)}, Failed {mm.group(2)}' if mm else 'LOI: '+(p.stdout+p.stderr)[-300:]))
    tests=g.tests or sorted(glob.glob(os.path.join(PROGDIR,'*.s')))
    tmpd=tempfile.mkdtemp()
    def hexof(words,name):
        p=os.path.join(tmpd,name+'.hex'); open(p,'w').write(asm.to_image(words)); return p
    over={}; base={}; fs={c:feats(c) for c in g.circ}
    for circ in g.circ:
        v0=run(circ,hexof([0x73],'plain'),g.java,g.logisim)[0]
        v1=run(circ,hexof(with_dump([0x73],'F' in fs[circ]),'dump%d'%('F' in fs[circ])),g.java,g.logisim)[0]
        over[circ]=num(v1,'cycles')-num(v0,'cycles'); base[circ]=v0
        print(f'[INFO] {os.path.basename(circ)}: tinh nang={sorted(fs[circ]) or "RV32I"}; chi phi DUMP={over[circ]} chu ky (tru ra khi bao cao)')
    total=0;fail=0;skip=0;rows=[]
    for t in tests:
        src=open(t,encoding='utf-8').read()
        req=set((re.search(r'#\s*requires:(.*)',src) or [None,''])[1].split())
        exp_uart=re.search(r'#\s*expect_uart:\s*"(.*)"',src); exp_led=re.search(r'#\s*expect_led:\s*(\S+)',src)
        words,_,_=asm.assemble(src)
        hx=t[:-2]+'.hex'; open(hx,'w').write(asm.to_image(words))
        G=Golden(words).run(); gx,gmem,ginstr=G['x'],G['mem'],G['n']
        assert not any(k>=FDUMP_BASE for k in gmem), 'chuong trinh test ghi vao vung DUMP (word 448..511)'
        for circ in g.circ:
            name=os.path.basename(circ); tn=os.path.basename(t)
            if not req<=fs[circ]:
                print(f'[SKIP] {tn:16s} {name:24s} (mach khong co: {" ".join(sorted(req-fs[circ]))})'); skip+=1; continue
            total+=1; fp='F' in fs[circ]
            hd=hexof(with_dump(words,fp),tn[:-2]+'_dump%d'%fp)
            try: vals,mem,halted,uart=run(circ,hd,g.java,g.logisim)
            except Exception as e: print(f'[LOI ] {tn} @ {name}: {e}'); fail+=1; continue
            errs=[]
            if not halted: errs.append('khong halt')
            regs={r:mem.pop(DUMP_BASE+r,0) for r in range(32)}
            fregs={r:mem.pop(FDUMP_BASE+r,0) for r in range(32)} if fp else None
            for k in [k for k in mem if k>=FDUMP_BASE]: mem.pop(k)
            if regs[0]!=0: errs.append(f'x0: mach={hex(regs[0])} (phai = 0)')
            for r in range(1,32):
                if regs[r]!=gx[r]: errs.append(f'x{r}: mach={hex(regs[r])} mong_doi={hex(gx[r])}')
            if fp and 'F' in req:
                for r in range(32):
                    if fregs[r]!=G['f'][r]: errs.append(f'f{r}: mach={hex(fregs[r])} mong_doi={hex(G["f"][r])}')
            for k in set(gmem)|set(mem):
                if gmem.get(k,0)!=mem.get(k,0): errs.append(f'mem[{k*4}]: mach={hex(mem.get(k,0))} mong_doi={hex(gmem.get(k,0))}')
            if exp_uart:
                want=exp_uart.group(1).encode().decode('unicode_escape')
                if G['uart']!=want: errs.append(f'golden UART={G["uart"]!r} khac expect {want!r}')
                if uart.strip('\n')!=want.strip('\n'): errs.append(f'UART: mach={uart!r} mong_doi={want!r}')
            if exp_led:
                if num(vals,'LED')!=int(exp_led.group(1),0): errs.append(f'LED: mach={num(vals,"LED")} mong_doi={exp_led.group(1)}')
            cyc=num(vals,'cycles'); cyc=cyc-over[circ] if cyc is not None else -1
            info=f'lenh={ginstr:5d} chu_ky={cyc:5d}'
            ex=dict(test=tn,circ=name,instr=ginstr,cycles=cyc)
            tdep='# timing_dependent' in src
            if 'INSTRET' in vals and not tdep:
                # INSTRET dem ca doan DUMP -> tru di (ret(ecall)+33(+32))-1
                ir=num(vals,'INSTRET'); dumpn=len(with_dump([0x73],fp))-1
                want=ginstr+dumpn-1   # lenh ecall cuoi gay halt, khong duoc dem retire
                if ir!=want: errs.append(f'INSTRET: mach={ir} mong_doi={want}')
                pass
            ex.update(cpi=round(cyc/ginstr,3))
            for k,gk in (('BR_CNT','br'),('DC_HIT','dch'),('DC_MISS','dcm')):
                if k in vals:
                    v=num(vals,k); ex[k]=v
                    if 'DC' in k and fp: pass
                    if k=='BR_CNT' and not tdep and v!=G['ev']['br']+1: errs.append(f'BR_CNT: mach={v} mong_doi={G["ev"]["br"]+1} (+1 lenh jal sang DUMP)')
            for k in ('BR_MISS','STALL','FLUSH','MSTALL'):
                if k in vals: ex[k]=num(vals,k)
            if not tdep and 'DC_HIT' in vals and re.search(r'<comp [^>]*name="DCache"',open(circ,encoding='utf-8').read()):
                h,mi=ex['DC_HIT'],ex['DC_MISS']
                if (h,mi)!=(G['ev']['dch'],G['ev']['dcm']): errs.append(f'DCACHE hit/miss: mach={h}/{mi} mong_doi={G["ev"]["dch"]}/{G["ev"]["dcm"]}')
            for k in ('BR_CNT','BR_MISS','DC_HIT','DC_MISS','STALL','FLUSH','MSTALL'):
                if k in ex: info+=f' {k}={ex[k]}'
            if 'INSTRET' in vals: info+=f' CPI={ex["cpi"]}'
            rows.append(ex)
            st='PASS' if not errs else 'FAIL'; fail+=bool(errs)
            print(f'[{st}] {tn:16s} {name:24s} {info}'+('' if not errs else '\n    '+'\n    '.join(errs)))
    print(f'\nTong: {total-fail}/{total} PASS'+(f', {skip} SKIP (mach khong co tinh nang)' if skip else ''))
    if g.csv:
        import csv
        ks=sorted({k for r in rows for k in r},key=lambda k:['test','circ','instr','cycles','cpi'].index(k) if k in ['test','circ','instr','cycles','cpi'] else 9)
        with open(g.csv,'w',newline='') as fh:
            w=csv.DictWriter(fh,fieldnames=ks); w.writeheader(); w.writerows(rows)
    sys.exit(1 if fail else 0)
if __name__=='__main__': main()
