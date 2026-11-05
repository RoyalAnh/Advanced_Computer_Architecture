#!/usr/bin/env python3
"""Assembler RV32I + M + Zicsr + mret + tap con F (toi gian) -> anh ROM Logisim ("v3.0 hex words plain").
Dung: python asm.py prog.s [-o prog.hex] [--list]
Ho tro: R/I/S/B/U/J cua RV32I (lw/sw; lb/lh/... chua co phan cung), ecall/ebreak,
nhan (label), comment # hoac //, so thap phan/hex, gia lenh: nop li mv not neg j jr ret call beqz bnez bgt ble bgtu bleu seqz snez la."""
import sys,re,argparse
REG={f'x{i}':i for i in range(32)}
for i,n in enumerate('zero ra sp gp tp t0 t1 t2 s0 s1 a0 a1 a2 a3 a4 a5 a6 a7 s2 s3 s4 s5 s6 s7 s8 s9 s10 s11 t3 t4 t5 t6'.split()): REG[n]=i
REG['fp']=8
FREG={f'f{i}':i for i in range(32)}
for i,n in enumerate('ft0 ft1 ft2 ft3 ft4 ft5 ft6 ft7 fs0 fs1 fa0 fa1 fa2 fa3 fa4 fa5 fa6 fa7 fs2 fs3 fs4 fs5 fs6 fs7 fs8 fs9 fs10 fs11 ft8 ft9 ft10 ft11'.split()): FREG[n]=i
MEXT={'mul':0,'mulh':1,'mulhsu':2,'mulhu':3,'div':4,'divu':5,'rem':6,'remu':7}
CSRN={'mstatus':0x300,'misa':0x301,'mie':0x304,'mtvec':0x305,'mscratch':0x340,'mepc':0x341,'mcause':0x342,'mip':0x344,'cycle':0xC00,'mcycle':0xB00}
CSRI={'csrrw':1,'csrrs':2,'csrrc':3,'csrrwi':5,'csrrsi':6,'csrrci':7}
RM={'rne':0,'rtz':1,'rdn':2,'rup':3,'rmm':4,'dyn':7}
# (funct7, rs2 co dinh hoac None, f3 co dinh hoac None(=rm), kieu toan hang: dst/src F hay X)
FOP={'fadd.s':(0x00,None,None,'fff'),'fsub.s':(0x04,None,None,'fff'),'fmul.s':(0x08,None,None,'fff'),'fdiv.s':(0x0C,None,None,'fff'),
 'fsqrt.s':(0x2C,0,None,'ff'),'fsgnj.s':(0x10,None,0,'fff'),'fsgnjn.s':(0x10,None,1,'fff'),'fsgnjx.s':(0x10,None,2,'fff'),
 'fmin.s':(0x14,None,0,'fff'),'fmax.s':(0x14,None,1,'fff'),'feq.s':(0x50,None,2,'xff'),'flt.s':(0x50,None,1,'xff'),'fle.s':(0x50,None,0,'xff'),
 'fcvt.w.s':(0x60,0,None,'xf'),'fcvt.wu.s':(0x60,1,None,'xf'),'fcvt.s.w':(0x68,0,None,'fx'),'fcvt.s.wu':(0x68,1,None,'fx'),
 'fmv.x.w':(0x70,0,0,'xf'),'fmv.w.x':(0x78,0,0,'fx')}
R={'add':(0,0),'sub':(0,0x20),'sll':(1,0),'slt':(2,0),'sltu':(3,0),'xor':(4,0),'srl':(5,0),'sra':(5,0x20),'or':(6,0),'and':(7,0)}
I={'addi':0,'slti':2,'sltiu':3,'xori':4,'ori':6,'andi':7}
SH={'slli':(1,0),'srli':(5,0),'srai':(5,0x20)}
L={'lb':0,'lh':1,'lw':2,'lbu':4,'lhu':5}
S={'sb':0,'sh':1,'sw':2}
B={'beq':0,'bne':1,'blt':4,'bge':5,'bltu':6,'bgeu':7}
class AsmError(Exception): pass
def num(t,labels=None,pc=None):
    t=t.strip()
    if labels is not None and t in labels: return labels[t]
    try: return int(t,0)
    except ValueError: raise AsmError(f'gia tri khong hop le: {t}')
def reg(t):
    t=t.strip()
    if t not in REG: raise AsmError(f'thanh ghi khong hop le: {t}')
    return REG[t]
def chk(v,bits,signed=True,what='imm'):
    lo,hi=(-(1<<(bits-1)),(1<<(bits-1))-1) if signed else (0,(1<<bits)-1)
    if not lo<=v<=hi: raise AsmError(f'{what}={v} vuot pham vi {bits} bit')
    return v&((1<<bits)-1)
def enc_r(f7,rs2,rs1,f3,rd,op): return f7<<25|rs2<<20|rs1<<15|f3<<12|rd<<7|op
def enc_i(imm,rs1,f3,rd,op): return chk(imm,12)<<20|rs1<<15|f3<<12|rd<<7|op
def enc_s(imm,rs2,rs1,f3,op):
    v=chk(imm,12); return (v>>5)<<25|rs2<<20|rs1<<15|f3<<12|(v&31)<<7|op
def enc_b(off,rs2,rs1,f3):
    if off&1: raise AsmError('offset nhanh le')
    v=chk(off,13,what='branch offset')
    return ((v>>12)&1)<<31|((v>>5)&63)<<25|rs2<<20|rs1<<15|f3<<12|((v>>1)&15)<<8|((v>>11)&1)<<7|0x63
def enc_j(off,rd):
    v=chk(off,21,what='jal offset')
    return ((v>>20)&1)<<31|((v>>1)&1023)<<21|((v>>11)&1)<<20|((v>>12)&255)<<12|rd<<7|0x6f
def freg(t):
    t=t.strip()
    if t not in FREG: raise AsmError(f'thanh ghi FP khong hop le: {t}')
    return FREG[t]
def csrn(t,labels=None):
    t=t.strip().lower()
    return CSRN[t] if t in CSRN else num(t)
def memop(t):
    m=re.fullmatch(r'\s*(.*?)\s*\(\s*(\w+)\s*\)\s*',t)
    if not m: raise AsmError(f'toan hang bo nho sai: {t}')
    return (m.group(1) or '0'),reg(m.group(2))
def expand(mn,a):
    """gia lenh -> list lenh that (so lenh co dinh de tinh nhan)"""
    if mn=='nop': return [('addi',['x0','x0','0'])]
    if mn=='mv': return [('addi',[a[0],a[1],'0'])]
    if mn=='not': return [('xori',[a[0],a[1],'-1'])]
    if mn=='neg': return [('sub',[a[0],'x0',a[1]])]
    if mn=='seqz': return [('sltiu',[a[0],a[1],'1'])]
    if mn=='snez': return [('sltu',[a[0],'x0',a[1]])]
    if mn=='j': return [('jal',['x0',a[0]])]
    if mn=='jr': return [('jalr',['x0',f'0({a[0]})'])]
    if mn=='ret': return [('jalr',['x0','0(ra)'])]
    if mn=='call': return [('jal',['ra',a[0]])]
    if mn=='beqz': return [('beq',[a[0],'x0',a[1]])]
    if mn=='bnez': return [('bne',[a[0],'x0',a[1]])]
    if mn in('bgt','ble','bgtu','bleu'): return [({'bgt':'blt','ble':'bge','bgtu':'bltu','bleu':'bgeu'}[mn],[a[1],a[0],a[2]])]
    if mn in('li','la'): return [('__li_hi',a),('__li_lo',a)]
    if mn=='csrr': return [('csrrs',[a[0],a[1],'x0'])]
    if mn=='csrw': return [('csrrw',['x0',a[0],a[1]])]
    if mn=='csrs': return [('csrrs',['x0',a[0],a[1]])]
    if mn=='csrc': return [('csrrc',['x0',a[0],a[1]])]
    if mn=='csrwi': return [('csrrwi',['x0',a[0],a[1]])]
    if mn=='csrsi': return [('csrrsi',['x0',a[0],a[1]])]
    if mn=='csrci': return [('csrrci',['x0',a[0],a[1]])]
    if mn in('rdcycle',): return [('csrrs',[a[0],'cycle','x0'])]
    if mn=='fmv.s': return [('fsgnj.s',[a[0],a[1],a[1]])]
    if mn=='fneg.s': return [('fsgnjn.s',[a[0],a[1],a[1]])]
    if mn=='fabs.s': return [('fsgnjx.s',[a[0],a[1],a[1]])]
    if mn=='fmv.x.s': return [('fmv.x.w',a)]
    if mn=='fmv.s.x': return [('fmv.w.x',a)]
    if mn=='jal' and len(a)==1: return [('jal',['ra',a[0]])]
    if mn=='jalr' and len(a)==1: return [('jalr',['ra',f'0({a[0]})'])]
    return [(mn,a)]
def assemble(src):
    items=[];labels={};pc=0;errs=[]
    for ln,line in enumerate(src.splitlines(),1):
        line=re.split(r'#|//|;',line)[0].strip()
        while True:
            m=re.match(r'([A-Za-z_.]\w*)\s*:\s*(.*)',line)
            if not m: break
            labels[m.group(1)]=pc; line=m.group(2).strip()
        if not line: continue
        p=line.split(None,1); mn=p[0].lower(); args=[x.strip() for x in p[1].split(',')] if len(p)>1 else []
        if mn=='.word':
            for x in args: items.append((ln,pc,'.word',[x],line)); pc+=4
            continue
        if mn in('.text','.globl','.global','.data','.section'): continue
        for e in expand(mn,args): items.append((ln,pc,e[0],e[1],line)); pc+=4
    words=[];lst=[]
    for ln,pc,mn,a,txt in items:
        try:
            if mn=='.word': w=num(a[0],labels)&0xffffffff
            elif mn=='__li_hi':
                v=num(a[1],labels)&0xffffffff; hi=((v+0x800)>>12)&0xfffff; w=hi<<12|reg(a[0])<<7|0x37
            elif mn=='__li_lo':
                v=num(a[1],labels)&0xffffffff; lo=v&0xfff; lo=lo-4096 if lo>=2048 else lo
                w=enc_i(lo,reg(a[0]),0,reg(a[0]),0x13)
            elif mn in R: f3,f7=R[mn]; w=enc_r(f7,reg(a[2]),reg(a[1]),f3,reg(a[0]),0x33)
            elif mn in I: w=enc_i(num(a[2],labels),reg(a[1]),I[mn],reg(a[0]),0x13)
            elif mn in SH: f3,f7=SH[mn]; w=f7<<25|chk(num(a[2]),5,False,'shamt')<<20|reg(a[1])<<15|f3<<12|reg(a[0])<<7|0x13
            elif mn in L: o,r=memop(a[1]); w=enc_i(num(o,labels),r,L[mn],reg(a[0]),0x03)
            elif mn in S: o,r=memop(a[1]); w=enc_s(num(o,labels),reg(a[0]),r,S[mn],0x23)
            elif mn in B: w=enc_b(num(a[2],labels)-pc if a[2] in labels else num(a[2]),reg(a[1]),reg(a[0]),B[mn])
            elif mn=='jal': w=enc_j(num(a[1],labels)-pc if a[1] in labels else num(a[1]),reg(a[0]))
            elif mn=='jalr':
                if len(a)==3: o,r=a[2],reg(a[1])
                else: o,r=memop(a[1])
                w=enc_i(num(o,labels),r,0,reg(a[0]),0x67)
            elif mn=='lui': w=chk(num(a[1],labels),20,False,'imm20')<<12|reg(a[0])<<7|0x37
            elif mn=='auipc': w=chk(num(a[1],labels),20,False,'imm20')<<12|reg(a[0])<<7|0x17
            elif mn in MEXT: w=enc_r(1,reg(a[2]),reg(a[1]),MEXT[mn],reg(a[0]),0x33)
            elif mn in CSRI:
                src=chk(num(a[2]),5,False,'zimm') if CSRI[mn]>=5 else reg(a[2])
                w=chk(csrn(a[1]),12,False,'csr')<<20|src<<15|CSRI[mn]<<12|reg(a[0])<<7|0x73
            elif mn=='mret': w=0x30200073
            elif mn=='flw': o,r=memop(a[1]); w=enc_i(num(o,labels),r,2,freg(a[0]),0x07)
            elif mn=='fsw': o,r=memop(a[1]); w=enc_s(num(o,labels),freg(a[0]),r,2,0x27)
            elif mn in FOP:
                f7,r2,f3,k=FOP[mn]
                rr=[freg(t) if c=='f' else reg(t) for c,t in zip(k,a)]
                if f3 is None:
                    rmv=RM[a[len(k)].strip().lower()] if len(a)>len(k) else 7
                    f3=rmv
                w=enc_r(f7,rr[2] if r2 is None else r2,rr[1],f3,rr[0],0x53)
            elif mn=='ecall': w=0x73
            elif mn=='ebreak': w=0x100073
            else: raise AsmError(f'lenh khong ho tro: {mn}')
        except (AsmError,IndexError) as e:
            errs.append(f'dong {ln}: {e} [{txt}]'); w=0
        words.append(w); lst.append(f'{pc:08x}: {w:08x}   {txt}')
    if errs: raise AsmError('\n'.join(errs))
    return words,lst,labels
def to_image(words): return 'v3.0 hex words plain\n'+'\n'.join(f'{w:08x}' for w in words)+'\n'
def to_rom_contents(words): return 'addr/data: 10 32\n'+' '.join(f'{w:x}' for w in words)+'\n'
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('-o'); ap.add_argument('--list',action='store_true')
    g=ap.parse_args()
    try: words,lst,_=assemble(open(g.src,encoding='utf-8').read())
    except AsmError as e: print('LOI:\n'+str(e),file=sys.stderr); sys.exit(1)
    out=g.o or re.sub(r'\.s$','',g.src)+'.hex'
    open(out,'w').write(to_image(words))
    if g.list: print('\n'.join(lst))
    print(f'{len(words)} lenh -> {out}',file=sys.stderr)
