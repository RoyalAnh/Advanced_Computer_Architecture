import os
import lg, subprocess, sys, wire, layout
from lg import Circ
# ===== cau hinh tinh nang (bien moi truong, dung cho so sanh baseline / mutation) =====
ENV=lambda k,d='1': os.environ.get(k,d)
BP=ENV('BP')=='1'          # du doan nhanh BTB + BHT 2 bit (0 = luon du doan khong nhay, nhu ban co ban)
CACHE=ENV('CACHE','1')     # '1' = D-cache direct-mapped; 'none' = khong cache, moi load cham P chu ky; '0' = bo nho 1 chu ky (ly tuong)
ADVFWD=ENV('ADVFWD')=='1'  # forwarding MEM->MEM cho du lieu store (bo stall load->store)
MISS_P=3                   # so chu ky phat khi miss
MUT=os.environ.get('MUT','')
# ---------- control table ----------
ADD,SUB,SLL,SLT,SLTU,XOR,SRL,SRA,OR,AND=range(10)
IMM_I,IMM_S,IMM_B,IMM_U,IMM_J=range(5)
RS_Y,RS_PC4,RS_MD,RS_CSR,RS_FPU=range(5)
FADD,FSUB,FMUL,FDIV,FSQRT,FSGNJ,FMINMAX,FCMP,FCVTWS,FCVTWUS,FCVTSW,FCVTSWU,FMV=range(13)
CTRL_FIELDS=[('RegWrite',1),('ASel',2),('BSel',1),('ALUOp',4),('MemRead',1),('MemWrite',1),('ResSel',3),('ImmSel',3),
 ('Branch',1),('Jal',1),('Jalr',1),('Halt',1),('UseRs1',1),('UseRs2',1),('Valid',1),('Csr',1),('Mret',1),('FpOp',4),('RdF',1),('Rs1F',1),('Rs2F',1)]
CW=sum(w for _,w in CTRL_FIELDS)
assert CW==32
def cword(**kv):
    v=0;b=0
    for n,w in CTRL_FIELDS: v|=(kv.get(n,0)&((1<<w)-1))<<b; b+=w
    return v
def decode(op,f3,f7,b20):
    V=dict(Valid=1)
    if op==0x33:
        if f7==1: return cword(RegWrite=1,ResSel=RS_MD,UseRs1=1,UseRs2=1,**V)
        alu={(0,0):ADD,(0,0x20):SUB,(1,0):SLL,(2,0):SLT,(3,0):SLTU,(4,0):XOR,(5,0):SRL,(5,0x20):SRA,(6,0):OR,(7,0):AND}.get((f3,f7))
        return cword(RegWrite=1,ALUOp=alu,UseRs1=1,UseRs2=1,**V) if alu is not None else 0
    if op==0x13:
        if f3==1 and f7!=0: return 0
        if f3==5 and f7 not in(0,0x20): return 0
        alu={0:ADD,2:SLT,3:SLTU,4:XOR,6:OR,7:AND,1:SLL,5:SRA if f7 else SRL}[f3]
        return cword(RegWrite=1,BSel=1,ALUOp=alu,ImmSel=IMM_I,UseRs1=1,**V)
    if op==0x03 and f3 in(0,1,2,4,5): return cword(RegWrite=1,BSel=1,ALUOp=ADD,MemRead=1,ImmSel=IMM_I,UseRs1=1,**V)
    if op==0x07 and f3==2: return cword(RegWrite=1,BSel=1,ALUOp=ADD,MemRead=1,ImmSel=IMM_I,UseRs1=1,RdF=1,**V)
    if op==0x23 and f3 in(0,1,2): return cword(BSel=1,ALUOp=ADD,MemWrite=1,ImmSel=IMM_S,UseRs1=1,UseRs2=1,**V)
    if op==0x27 and f3==2: return cword(BSel=1,ALUOp=ADD,MemWrite=1,ImmSel=IMM_S,UseRs1=1,UseRs2=1,Rs2F=1,**V)
    if op==0x63 and f3 not in(2,3): return cword(Branch=1,ImmSel=IMM_B,UseRs1=1,UseRs2=1,**V)
    if op==0x6f: return cword(RegWrite=1,ResSel=RS_PC4,Jal=1,ImmSel=IMM_J,**V)
    if op==0x67 and f3==0: return cword(RegWrite=1,BSel=1,ALUOp=ADD,ResSel=RS_PC4,Jalr=1,ImmSel=IMM_I,UseRs1=1,**V)
    if op==0x37: return cword(RegWrite=1,ASel=2,BSel=1,ALUOp=ADD,ImmSel=IMM_U,**V)
    if op==0x17: return cword(RegWrite=1,ASel=1,BSel=1,ALUOp=ADD,ImmSel=IMM_U,**V)
    if op==0x73:
        if f3==0:
            if f7==0x18 and b20==0: return cword(Mret=1,**V)
            return cword(Halt=1,**V)
        if f3 in(1,2,3): return cword(RegWrite=1,ResSel=RS_CSR,ImmSel=IMM_I,UseRs1=1,Csr=1,**V)
        if f3 in(5,6,7): return cword(RegWrite=1,ResSel=RS_CSR,ImmSel=IMM_I,Csr=1,**V)
        return 0
    if op==0x53:
        F=lambda fop,rd,r1,r2: cword(RegWrite=1,ResSel=RS_FPU,FpOp=fop,RdF=rd,Rs1F=r1,Rs2F=r2,UseRs1=1,UseRs2=int(r2>=0),**V) if True else 0
        def Fx(fop,rd,r1,two): return cword(RegWrite=1,ResSel=RS_FPU,FpOp=fop,RdF=rd,Rs1F=r1,Rs2F=1 if two else 0,UseRs1=1,UseRs2=1 if two else 0,**V)
        f5=f7>>2
        if f7&3: return 0
        if f5 in(0,1,2,3): return Fx([FADD,FSUB,FMUL,FDIV][f5],1,1,True)
        if f5==0x0B: return Fx(FSQRT,1,1,False)
        if f5==0x04 and f3 in(0,1,2): return Fx(FSGNJ,1,1,True)
        if f5==0x05 and f3 in(0,1): return Fx(FMINMAX,1,1,True)
        if f5==0x14 and f3 in(0,1,2): return Fx(FCMP,0,1,True)
        if f5==0x18: return Fx(FCVTWUS if b20 else FCVTWS,0,1,False)
        if f5==0x1A: return Fx(FCVTSWU if b20 else FCVTSW,1,0,False)
        if f5==0x1C and f3==0: return Fx(FMV,0,1,False)
        if f5==0x1E and f3==0: return Fx(FMV,1,0,False)
        return 0
    return 0
def rle(vals):
    out=[];i=0
    while i<len(vals):
        j=i
        while j<len(vals) and vals[j]==vals[i]: j+=1
        n=j-i; out.append(('%d*%x'%(n,vals[i])) if n>1 else '%x'%vals[i]); i=j
    return ' '.join(out)
def ctrl_rom():
    # dia chi 16 bit (LSB truoc): op[6:2] | f3 | funct7 | instr[20]
    t=[]
    for a in range(1<<16):
        op=(a&31)<<2|3; f3=(a>>5)&7; f7=(a>>8)&127; b20=a>>15
        t.append(decode(op,f3,f7,b20))
    return 'addr/data: 16 %d\n'%CW+rle(t)+'\n'
def slice_ctrl(c,word,prefix,only=None):
    b=0
    for n,w in CTRL_FIELDS:
        if only is None or n in only: c.slice(word,CW,b,b+w-1,prefix+n)
        b+=w
# ---------- modules ----------
def m_alu():
    c=Circ('ALU'); c.pin_in('a',32); c.pin_in('b',32); c.pin_in('op',4); c.pin_out('y',32)
    c.add('Adder',{'width':32},['a','b','add']); c.add('Subtractor',{'width':32},['a','b','sub'])
    c.slice('b',32,0,4,'sh')
    for nm,t in (('sll','ll'),('srl','lr'),('sra','ar')): c.add('Shifter',{'width':32,'shift':t},['a','sh',nm])
    c.add('Comparator',{'width':32,'mode':'twosComplement'},['a','b',None,None,'lts'])
    c.add('Comparator',{'width':32,'mode':'unsigned'},['a','b',None,None,'ltu'])
    c.ext('slt','lts',1,32); c.ext('sltu','ltu',1,32)
    c.gate('XOR Gate','xor',['a','b'],32); c.gate('OR Gate','or',['a','b'],32); c.gate('AND Gate','and',['a','b'],32)
    c.const('z32',0,32)
    c.mux('y','op',['add','sub','sll','slt','sltu','xor','srl','sra','or','and']+['z32']*6,32)
    return c
def m_regfile(n=32):
    k=n.bit_length()-1; name='RegFile' if n==32 else 'RegFile%d'%n
    c=Circ(name)
    for p,w in (('clk',1),('we',1),('rs1',k),('rs2',k),('rd',k),('wd',32)): c.pin_in(p,w)
    c.pin_out('r1',32); c.pin_out('r2',32)
    c.const('x0',0,32)
    if n==32:
        c.add('Decoder',{'select':5,'enable':'false'},['dec%d'%i for i in range(32)]+['rd'])
    else:  # 64: x0..x31 = thanh ghi nguyen, x32..x63 = f0..f31
        c.slice('rd',6,0,4,'rdl'); c.slice('rd',6,5,5,'rdh'); c.gate('NOT Gate','nrdh',['rdh'])
        c.add('Decoder',{'select':5,'enable':'false'},['dl%d'%i for i in range(32)]+['rdl'])
        for i in range(32):
            c.gate('AND Gate','dec%d'%i,['dl%d'%i,'nrdh']); c.gate('AND Gate','dec%d'%(i+32),['dl%d'%i,'rdh'])
    for i in range(1,n):
        c.gate('AND Gate','en%d'%i,['we','dec%d'%i]); c.reg('x%d'%i,'wd','clk',32,en='en%d'%i)
    regs=['x%d'%i for i in range(n)]
    for r in ('1','2'):
        if n==32: c.mux('r'+r,'rs'+r,regs,32)
        else:
            c.slice('rs'+r,6,0,4,'s%sl'%r); c.slice('rs'+r,6,5,5,'s%sh'%r)
            c.mux('r%sx'%r,'s%sl'%r,regs[:32],32); c.mux('r%sf'%r,'s%sl'%r,regs[32:],32)
            c.mux('r'+r,'s%sh'%r,['r%sx'%r,'r%sf'%r],32)
    return c
def m_immgen():
    c=Circ('ImmGen'); c.pin_in('instr',32); c.pin_in('sel',3); c.pin_out('imm',32)
    S=lambda lo,hi,n: c.slice('instr',32,lo,hi,n)
    S(20,31,'i12'); c.ext('immI','i12',12,32,'sign')
    S(7,11,'s_lo'); S(25,31,'s_hi'); c.pack('s12',[('s_lo',5),('s_hi',7)]); c.ext('immS','s12',12,32,'sign')
    c.const('z1',0,1); S(8,11,'b4_1'); S(25,30,'b10_5'); S(7,7,'b11'); S(31,31,'b12')
    c.pack('b13',[('z1',1),('b4_1',4),('b10_5',6),('b11',1),('b12',1)]); c.ext('immB','b13',13,32,'sign')
    c.const('z12',0,12); S(12,31,'u20'); c.pack('immU',[('z12',12),('u20',20)])
    S(21,30,'j10_1'); S(20,20,'j11'); S(12,19,'j19_12')
    c.pack('j21',[('z1',1),('j10_1',10),('j11',1),('j19_12',8),('b12',1)]); c.ext('immJ','j21',21,32,'sign')
    c.const('z32',0,32)
    c.mux('imm','sel',['immI','immS','immB','immU','immJ','z32','z32','z32'],32)
    return c
def m_branch():
    c=Circ('BranchUnit'); c.pin_in('a',32); c.pin_in('b',32); c.pin_in('f3',3); c.pin_out('cond',1)
    c.add('Comparator',{'width':32,'mode':'twosComplement'},['a','b',None,'eq','lts'])
    c.add('Comparator',{'width':32,'mode':'unsigned'},['a','b',None,None,'ltu'])
    for n in('eq','lts','ltu'): c.gate('NOT Gate','n'+n,[n])
    c.const('z',0,1)
    c.mux('cond','f3',['eq','neq','z','z','lts','nlts','ltu','nltu'],1)
    return c
def m_control():
    c=Circ('Control'); c.pin_in('instr',32); c.pin_out('ctrl',CW)
    c.slice('instr',32,2,6,'op5'); c.slice('instr',32,12,14,'f3'); c.slice('instr',32,25,31,'f7'); c.slice('instr',32,20,20,'b20')
    c.pack('caddr',[('op5',5),('f3',3),('f7',7),('b20',1)])
    c.add('ROM',{'addrWidth':16,'dataWidth':CW,'label':'CTRL','contents':ctrl_rom()},['caddr','crom'])
    # lenh hop le phai co instr[1:0]=11 (lenh 0x00000000 cua bong bong/reset khong duoc giai ma thanh LB)
    c.slice('instr',32,0,0,'q0'); c.slice('instr',32,1,1,'q1'); c.gate('AND Gate','qok',['q0','q1'])
    c.const('cz',0,CW); c.mux('ctrl','qok',['cz','crom'],CW)
    return c
def m_load():
    c=Circ('LoadUnit'); c.pin_in('din',32); c.pin_in('off',2); c.pin_in('f3',3); c.pin_out('v',32)
    c.const('z3',0,3); c.pack('sh',[('z3',3),('off',2)])
    c.add('Shifter',{'width':32,'shift':'lr'},['din','sh','x'])
    c.slice('x',32,0,7,'b'); c.slice('x',32,0,15,'h')
    c.ext('sb','b',8,32,'sign'); c.ext('zb','b',8,32); c.ext('sh16','h',16,32,'sign'); c.ext('zh','h',16,32)
    c.mux('v','f3',['sb','sh16','x','x','zb','zh','x','x'],32)
    return c
def m_store():
    c=Circ('StoreUnit'); c.pin_in('old',32); c.pin_in('wd',32); c.pin_in('off',2); c.pin_in('f3',3); c.pin_out('new',32)
    c.const('z3',0,3); c.pack('sh',[('z3',3),('off',2)])
    c.slice('f3',3,0,1,'sz')
    c.const('mb',0xff,32); c.const('mh',0xffff,32); c.const('mw',0xffffffff,32)
    c.mux('m0','sz',['mb','mh','mw','mw'],32)
    c.add('Shifter',{'width':32,'shift':'ll'},['m0','sh','mask'])
    c.add('Shifter',{'width':32,'shift':'ll'},['wd','sh','wds'])
    c.gate('NOT Gate','nmask',['mask'],32)
    c.gate('AND Gate','keep',['old','nmask'],32); c.gate('AND Gate','ins',['wds','mask'],32)
    c.gate('OR Gate','new',['keep','ins'],32)
    return c
def m_muldiv():
    """RV32M: MUL/MULH/MULHSU/MULHU dung Multiplier (3 che do dau), DIV/DIVU/REM/REMU dung Divider.
    Chia cho 0: thuong = 0xFFFFFFFF, du = a (dung chuan). Tran -2^31/-1: thuong = -2^31, du = 0 (Divider 64/32 bit cho ket qua dung)."""
    c=Circ('MulDiv'); c.pin_in('a',32); c.pin_in('b',32); c.pin_in('f3',3); c.pin_out('y',32)
    mh=os.environ.get('MUT')=='mulh'
    c.add('Multiplier',{'width':32,'mode':'unsigned'},['a','b','lo',None,'hiuu'])
    c.add('Multiplier',{'width':32,'mode':'unsigned' if mh else 'twosComplement'},['a','b',None,None,'hiss'])
    c.add('Multiplier',{'width':32,'mode':'signedUnsigned'},['a','b',None,None,'hisu'])
    c.slice('a',32,31,31,'a31'); c.ext('asx','a31',1,32,'sign'); c.const('z32',0,32); c.const('ones',0xffffffff,32)
    c.add('Divider',{'width':32,'mode':'twosComplement'},['a','b','qs','asx','rs'])
    c.add('Divider',{'width':32,'mode':'unsigned'},['a','b','qu','z32','ru'])
    c.eq('bz','b','z32',32)
    bz='z1' if os.environ.get('MUT')=='divz' else 'bz'
    if bz=='z1': c.const('z1',0,1)
    c.mux('qs2',bz,['qs','ones'],32); c.mux('qu2',bz,['qu','ones'],32)
    c.mux('rs2',bz,['rs','a'],32); c.mux('ru2',bz,['ru','a'],32)
    c.mux('y','f3',['lo','hiss','hisu','hiuu','qs2','qu2','rs2','ru2'],32)
    return c
def m_fpu():
    """Tap con RV32F tren cac linh kien FP Arithmetic cua Logisim (binary32)."""
    c=Circ('FPU'); c.pin_in('a',32); c.pin_in('b',32); c.pin_in('op',4); c.pin_in('rm',3); c.pin_out('y',32)
    c.add('FPAdder',{'fpwidth':32},['a','b','fadd',None])
    c.add('FPSubtractor',{'fpwidth':32},['a','b','fsub',None])
    c.add('FPMultiplier',{'fpwidth':32},['a','b','fmul',None])
    c.add('FPDivider',{'fpwidth':32},['a','b','fdiv',None,None])
    c.add('FPSquareRoot',{'fpwidth':32},['a','fsqrt',None])
    # sign-injection
    c.slice('a',32,0,30,'amag'); c.slice('a',32,31,31,'as'); c.slice('b',32,31,31,'bs')
    c.gate('NOT Gate','nbs',['bs']); c.gate('XOR Gate','xs',['as','bs'])
    c.slice('rm',3,0,1,'rm2'); c.slice('rm',3,0,0,'rm0')
    c.mux('sj','rm2',['bs','nbs','xs','bs'],1); c.pack('fsgnj',[('amag',31),('sj',1)])
    c.add('FPMinMax',{'fpwidth':32},['a','b','fmin','fmax',None]); c.mux('fminmax','rm0',['fmin','fmax'],32)
    c.add('FPComparator',{'fpwidth':32},['a','b',None,'feq','flt',None])
    c.gate('OR Gate','fle',['flt','feq']); c.const('z1',0,1)
    c.mux('cmp1','rm2',['fle','flt','feq','z1'],1); c.ext('fcmp','cmp1',1,32)
    for m in ('rint','truncate','floor','ceil','round'):
        c.add('FPToInt',{'width':32,'fpwidth':32,'mode':m},['a','ci_'+m,None])
    c.mux('fcvtw','rm',['ci_rint','ci_truncate','ci_floor','ci_ceil','ci_round','ci_rint','ci_rint','ci_rint'],32)
    c.add('IntToFP',{'width':32,'fpwidth':32,'mode':'twosComplement'},['a','fcvts',None])
    c.add('IntToFP',{'width':32,'fpwidth':32,'mode':'unsigned'},['a','fcvtsu',None])
    c.const('z32',0,32)
    c.mux('y','op',['fadd','fsub','fmul','fdiv','fsqrt','fsgnj','fminmax','fcmp','fcvtw','fcvtw','fcvts','fcvtsu','a','z32','z32','z32'],32)
    return c
def m_btb():
    """BTB 16 muc (chi so pc[5:2], tag = toan bo PC) + bo dem bao hoa 2 bit moi muc (BHT)."""
    c=Circ('BTB')
    for p,w in (('clk',1),('rpc',32),('we',1),('wpc',32),('wtgt',32),('wtk',1)): c.pin_in(p,w)
    c.pin_out('ptk',1); c.pin_out('ptgt',32)
    c.slice('rpc',32,2,5,'ri'); c.slice('wpc',32,2,5,'wi'); c.const('one',1,1)
    c.add('Decoder',{'select':4,'enable':'false'},['wd%d'%i for i in range(16)]+['wi'])
    # muc dang ghi: co san (present) + bo dem cu -> bo dem moi (ROM 16x2)
    c.mux('v_w','wi',['v%d'%i for i in range(16)],1); c.mux('tag_w','wi',['tag%d'%i for i in range(16)],32)
    c.mux('cnt_w','wi',['cnt%d'%i for i in range(16)],2)
    c.eq('tageq_w','tag_w','wpc',32); c.gate('AND Gate','present',['v_w','tageq_w'])
    tab=[]
    for a in range(16):
        cnt=a&3; tk=(a>>2)&1; pr=a>>3
        if pr: n=min(3,cnt+1) if tk else max(0,cnt-1)
        else: n=2 if tk else 1
        tab.append(n)
    c.pack('caddr',[('cnt_w',2),('wtk',1),('present',1)])
    c.add('ROM',{'addrWidth':4,'dataWidth':2,'label':'CNT_NEXT','contents':'addr/data: 4 2\n'+' '.join('%x'%v for v in tab)+'\n'},['caddr','cnt_n'])
    c.gate('OR Gate','alloc',['present','wtk']); c.gate('AND Gate','we2',['we','alloc'])
    for i in range(16):
        c.gate('AND Gate','e%d'%i,['we2','wd%d'%i])
        c.reg('v%d'%i,'one','clk',1,en='e%d'%i); c.reg('tag%d'%i,'wpc','clk',32,en='e%d'%i)
        c.reg('tgt%d'%i,'wtgt','clk',32,en='e%d'%i); c.reg('cnt%d'%i,'cnt_n','clk',2,en='e%d'%i)
    c.mux('v_r','ri',['v%d'%i for i in range(16)],1); c.mux('tag_r','ri',['tag%d'%i for i in range(16)],32)
    c.mux('ptgt','ri',['tgt%d'%i for i in range(16)],32); c.mux('cnt_r','ri',['cnt%d'%i for i in range(16)],2)
    c.eq('tageq_r','tag_r','rpc',32); c.slice('cnt_r',2,1,1,'c1')
    c.gate('AND Gate','ptk',['v_r','tageq_r','c1'])
    return c
def m_dcache():
    """D-cache direct-mapped 16 dong x 1 word, tag = word[9:4]; ghi xuyen (write-through) + cap phat khi ghi."""
    c=Circ('DCache')
    for p,w in (('clk',1),('addr',10),('wr',1),('wdata',32),('mdata',32),('fill',1)): c.pin_in(p,w)
    c.pin_out('hit',1); c.pin_out('data',32)
    c.slice('addr',10,0,3,'idx'); c.slice('addr',10,4,9,'tag'); c.const('one',1,1)
    c.add('Decoder',{'select':4,'enable':'false'},['d%d'%i for i in range(16)]+['idx'])
    fill='z1' if os.environ.get('MUT')=='nofill' else 'fill'
    if fill=='z1': c.const('z1',0,1)
    c.gate('OR Gate','lwe',['wr',fill]); c.mux('ld','wr',['mdata','wdata'],32)
    for i in range(16):
        c.gate('AND Gate','e%d'%i,['lwe','d%d'%i])
        c.reg('v%d'%i,'one','clk',1,en='e%d'%i); c.reg('t%d'%i,'tag','clk',6,en='e%d'%i); c.reg('l%d'%i,'ld','clk',32,en='e%d'%i)
    c.mux('v_r','idx',['v%d'%i for i in range(16)],1); c.mux('t_r','idx',['t%d'%i for i in range(16)],6)
    c.mux('data','idx',['l%d'%i for i in range(16)],32)
    c.eq('teq','t_r','tag',6); c.gate('AND Gate','hit',['v_r','teq'])
    return c
CSRS=[('mstatus',0x300),('mie',0x304),('mtvec',0x305),('mscratch',0x340),('mepc',0x341),('mcause',0x342),('mip',0x344),('cycle',0xC00),('mcycle',0xB00)]
def m_csr():
    """CSR may (Zicsr) + logic ngat: mstatus.MIE/MPIE, mie, mip, mtvec, mscratch, mepc, mcause, cycle."""
    c=Circ('CSRFile')
    for p,w in (('clk',1),('en',1),('we',1),('addr',12),('f3',3),('rs1v',32),('zimm',5),('mret',1),('trap',1),('epc',32),
                ('msip',1),('mtip',1),('meip',1),('cycles',32)): c.pin_in(p,w)
    c.pin_out('rdata',32); c.pin_out('mtvec',32); c.pin_out('mepc',32); c.pin_out('irq',1); c.pin_out('cause',32)
    c.const('z32',0,32); c.const('z1',0,1); c.const('one',1,1); c.const('z2',0,2); c.const('z3',0,3); c.const('k3',3,2)
    c.const('z19',0,19); c.const('z20',0,20); c.const('z4',0,4); c.const('z27',0,27)
    for n,a in CSRS:
        c.const('k_'+n,a,12); c.eq('is_'+n,'addr','k_'+n,12)
    c.gate('OR Gate','is_cyc',['is_cycle','is_mcycle'])
    # gia tri doc
    c.pack('v_mstatus',[('z3',3),('MIE',1),('z3',3),('MPIE',1),('z3',3),('k3',2),('z19',19)])
    c.pack('v_mie',[('z3',3),('MSIE',1),('z3',3),('MTIE',1),('z3',3),('MEIE',1),('z20',20)])
    c.pack('v_mip',[('z3',3),('msip',1),('z3',3),('mtip',1),('z3',3),('meip',1),('z20',20)])
    src=[('v_mstatus','is_mstatus'),('v_mie','is_mie'),('mtvec','is_mtvec'),('mscratch','is_mscratch'),('mepc','is_mepc'),
         ('mcause','is_mcause'),('v_mip','is_mip'),('cycles','is_cyc')]
    for v,s in src:
        c.ext('m_'+v,s,1,32,'sign'); c.gate('AND Gate','g_'+v,[v,'m_'+v],32)
    c.gate('OR Gate','rdata',['g_'+v for v,_ in src],32)
    # gia tri moi
    c.slice('f3',3,2,2,'isimm'); c.slice('f3',3,0,1,'cop')
    c.pack('zx',[('zimm',5),('z27',27)]); c.mux('src','isimm',['rs1v','zx'],32)
    c.gate('OR Gate','vor',['rdata','src'],32); c.gate('NOT Gate','nsrc',['src'],32); c.gate('AND Gate','vandn',['rdata','nsrc'],32)
    c.mux('new','cop',['rdata','src','vor','vandn'],32)
    c.gate('AND Gate','wen',['we','en'])
    for n in ('mstatus','mie','mtvec','mscratch','mepc','mcause'): c.gate('AND Gate','w_'+n,['wen','is_'+n])
    c.reg('mtvec','new','clk',32,en='w_mtvec'); c.reg('mscratch','new','clk',32,en='w_mscratch')
    c.slice('new',32,3,3,'n3'); c.slice('new',32,7,7,'n7'); c.slice('new',32,11,11,'n11')
    c.reg('MSIE','n3','clk',1,en='w_mie'); c.reg('MTIE','n7','clk',1,en='w_mie'); c.reg('MEIE','n11','clk',1,en='w_mie')
    c.gate('OR Gate','e_epc',['w_mepc','trap']); c.mux('d_mepc','trap',['new','epc'],32); c.reg('mepc','d_mepc','clk',32,en='e_epc')
    c.gate('OR Gate','e_cause',['w_mcause','trap']); c.mux('d_mcause','trap',['new','cause'],32); c.reg('mcause','d_mcause','clk',32,en='e_cause')
    # mstatus: trap > mret > csr write
    c.gate('NOT Gate','ntrap',['trap']); c.gate('AND Gate','mret_g',['mret','en','ntrap'])
    c.gate('OR Gate','e_ms',['w_mstatus','mret_g','trap'])
    c.mux('mie_a','mret_g',['n3','MPIE'],1); c.mux('d_MIE','trap',['mie_a','z1'],1)
    mpie_trap='z1' if os.environ.get('MUT')=='nompie' else 'MIE'
    c.mux('mpie_a','mret_g',['n7','one'],1); c.mux('d_MPIE','trap',['mpie_a',mpie_trap],1)
    c.reg('MIE','d_MIE','clk',1,en='e_ms'); c.reg('MPIE','d_MPIE','clk',1,en='e_ms')
    # ngat dang cho: uu tien MEI > MSI > MTI
    c.gate('AND Gate','pe_s',['msip','MSIE']); c.gate('AND Gate','pe_t',['mtip','MTIE']); c.gate('AND Gate','pe_e',['meip','MEIE'])
    c.gate('OR Gate','pany',['pe_s','pe_t','pe_e']); c.gate('AND Gate','irq',['MIE','pany'])
    c.const('c_s',0x80000003,32); c.const('c_t',0x80000007,32); c.const('c_e',0x8000000B,32)
    c.mux('cause_a','pe_s',['c_t','c_s'],32); c.mux('cause','pe_e',['cause_a','c_e'],32)
    return c
def m_mmio():
    """Thiet bi vao/ra anh xa bo nho tai 0x80000000: +0 LED, +4 SW, +8 UART_TX, +C UART_STATUS, +10 MSIP, +14 MTIMECMP, +18 MTIME."""
    c=Circ('MMIO')
    for p,w in (('clk',1),('addr',32),('we',1),('wdata',32),('sw',8),('cycles',32)): c.pin_in(p,w)
    for p,w in (('rdata',32),('isio',1),('led',8),('msip',1),('mtip',1),('tx_we',1),('tx_d',7)): c.pin_out(p,w)
    c.slice('addr',32,31,31,'isio'); c.slice('addr',32,2,4,'sel')
    c.add('Decoder',{'select':3,'enable':'false'},['s%d'%i for i in range(8)]+['sel'])
    c.gate('AND Gate','wio',['we','isio'])
    for i,n in ((0,'w_led'),(2,'tx_we'),(4,'w_msip'),(5,'w_cmp')): c.gate('AND Gate',n,['wio','s%d'%i])
    c.slice('wdata',32,0,7,'wd8'); c.slice('wdata',32,0,0,'wd0'); c.slice('wdata',32,0,6,'tx_d')
    c.reg('led','wd8','clk',8,en='w_led'); c.reg('msip','wd0','clk',1,en='w_msip')
    c.gate('NOT Gate','ncmp_d',['wdata'],32); c.reg('ncmp','ncmp_d','clk',32,en='w_cmp')   # luu ~mtimecmp => reset = 0xFFFFFFFF
    c.gate('NOT Gate','mtimecmp',['ncmp'],32)
    c.add('Comparator',{'width':32,'mode':'unsigned'},['cycles','mtimecmp',None,None,'tlt']); c.gate('NOT Gate','mtip',['tlt'])
    c.ext('r_led','led',8,32); c.ext('r_sw','sw',8,32); c.ext('r_msip','msip',1,32); c.const('z32',0,32); c.const('k1',1,32)
    c.mux('rdata','sel',['r_led','r_sw','z32','k1','r_msip','mtimecmp','cycles','z32'],32)
    return c
MODS_SINGLE=[m_alu,m_regfile,m_immgen,m_branch,m_control,m_load,m_store,m_muldiv]
MODS_PIPE=[m_alu,lambda: m_regfile(64),m_immgen,m_branch,m_control,m_load,m_store,m_muldiv,m_fpu,m_btb,m_dcache,m_csr,m_mmio]
# ================= top-level netlists =================
def counters(c,items):
    """items: list (ten, tin_hieu_tang) ; ten='cycles' tang moi chu ky"""
    c.grp='PerfCounters'
    c.const('c1',1,32); c.const('c0',0,32)
    for n,inc in items:
        if inc is None: c.add('Adder',{'width':32},[n,'c1',n+'_n']); c.reg(n,n+'_n','clk',32)
        else:
            c.mux(n+'_k',inc,['c0','c1'],32); c.add('Adder',{'width':32},[n,n+'_k',n+'_n']); c.reg(n,n+'_n','clk',32)
    c.grp='top'
def single(prog):
    c=Circ('main'); c.add('Clock',{},['clk']); counters(c,[('cycles',None)])
    c.reg('pc','pcnext','clk',32)
    c.slice('pc',32,2,11,'pcw')
    c.add('ROM',{'addrWidth':10,'dataWidth':32,'label':'IMEM','contents':prog},['pcw','instr'])
    c.grp='MainControl'; c.add('Control',{},{'instr':'instr','ctrl':'ctrl'})
    slice_ctrl(c,'ctrl','',only={'RegWrite','ASel','BSel','ALUOp','MemRead','MemWrite','ResSel','ImmSel','Branch','Jal','Jalr','Halt'})
    c.grp='InstrDecode'
    c.slice('instr',32,15,19,'rs1'); c.slice('instr',32,20,24,'rs2'); c.slice('instr',32,7,11,'rd'); c.slice('instr',32,12,14,'f3')
    c.grp='top'
    c.add('RegFile',{},dict(clk='clk',we='RegWrite',rs1='rs1',rs2='rs2',rd='rd',wd='wb',r1='r1',r2='r2'))
    c.add('ImmGen',{},dict(instr='instr',sel='ImmSel',imm='imm'))
    c.const('z32',0,32)
    c.mux('alua','ASel',['r1','pc','z32'],32); c.mux('alub','BSel',['r2','imm'],32)
    c.add('ALU',{},dict(a='alua',b='alub',op='ALUOp',y='y'))
    c.add('MulDiv',{},dict(a='r1',b='r2',f3='f3',y='md'))
    c.const('k4',4,32); c.add('Adder',{'width':32},['pc','k4','pc4']); c.add('Adder',{'width':32},['pc','imm','brt'])
    c.const('kmask',0xFFFFFFFE,32); c.gate('AND Gate','jalrt',['y','kmask'],32)
    c.add('BranchUnit',{},dict(a='r1',b='r2',f3='f3',cond='cond'))
    c.gate('AND Gate','btaken',['Branch','cond']); c.gate('OR Gate','taken',['btaken','Jal'])
    c.mux('pcn1','taken',['pc4','brt'],32); c.mux('pcnext','Jalr',['pcn1','jalrt'],32)
    c.mux('res','ResSel',['y','pc4','md','z32','z32','z32','z32','z32'],32)
    c.slice('y',32,2,11,'daddr'); c.const('one',1,1)
    c.slice('y',32,0,1,'boff')
    c.add('StoreUnit',{},dict(old='mraw',wd='r2',off='boff',f3='f3',new='mnew'))
    c.add('RAM',{'addrWidth':10,'dataWidth':32,'asyncread':'true','label':'DMEM'},['daddr','mraw','mnew','one','MemWrite','clk'])
    c.add('LoadUnit',{},dict(din='mraw',off='boff',f3='f3',v='mdata'))
    c.mux('wb','MemRead',['res','mdata'],32)
    c.pin_out('Halt',1,'halt'); c.pin_out('pc',32,'PC_out'); c.pin_out('cycles',32)
    return c
PIPE_OUT=[('w_Halt','halt',1),('pc','PC_out',32),('cycles','cycles',32),('instret','INSTRET',32),('stall','STALL',1),('redir','FLUSH',1),
          ('mstall','MSTALL',1),('br_cnt','BR_CNT',32),('br_miss','BR_MISS',32),('dc_hit','DC_HIT',32),('dc_miss','DC_MISS',32),('led','LED',8)]
def pipeline(prog):
    c=Circ('main'); c.add('Clock',{},['clk'])
    c.const('z1m',0,1); c.const('z32',0,32); c.const('one',1,1); c.const('zc',0,CW); c.const('k4',4,32)
    # ---- IF (+ du doan nhanh)
    c.reg('pc','pcnext','clk',32,en='pcen')
    c.add('Adder',{'width':32},['pc','k4','pc4f'])
    if BP:
        c.add('BTB',{},dict(clk='clk',rpc='pc',we='btb_we',wpc='e_pc',wtgt='e_target',wtk='e_actual',ptk='f_pt',ptgt='f_ptgt'))
        c.mux('pc_pred','f_pt',['pc4f','f_ptgt'],32)
    c.mux('pcnext','redir',['pc_pred' if BP else 'pc4f','redir_tgt'],32)
    c.slice('pc',32,2,11,'pcw')
    c.add('ROM',{'addrWidth':10,'dataWidth':32,'label':'IMEM','contents':prog},['pcw','f_instr'])
    c.mux('f_instr_q','z1m' if MUT=='noflush' else 'redir',['f_instr','z32'],32)
    if BP: c.mux('f_pt_q','redir',['f_pt','z1m'],1)
    c.grp='IF_ID'
    c.reg('d_pc','pc','clk',32,en='pcen'); c.reg('d_instr','f_instr_q','clk',32,en='pcen')
    if BP: c.reg('d_pt','f_pt_q','clk',1,en='pcen'); c.reg('d_ptgt','f_ptgt','clk',32,en='pcen')
    # ---- ID
    c.grp='MainControl'; c.add('Control',{},{'instr':'d_instr','ctrl':'d_ctrl'})
    slice_ctrl(c,'d_ctrl','d_',only={'ImmSel','UseRs1','UseRs2','MemWrite','RdF','Rs1F','Rs2F'})
    c.grp='InstrDecode'
    c.slice('d_instr',32,15,19,'d_rs1x'); c.slice('d_instr',32,20,24,'d_rs2x'); c.slice('d_instr',32,7,11,'d_rdx'); c.slice('d_instr',32,12,14,'d_f3')
    c.pack('d_rs1',[('d_rs1x',5),('d_Rs1F',1)]); c.pack('d_rs2',[('d_rs2x',5),('d_Rs2F',1)]); c.pack('d_rd',[('d_rdx',5),('d_RdF',1)])
    c.grp='top'
    c.add('RegFile64',{},dict(clk='clk',we='w_RegWrite',rs1='d_rs1',rs2='d_rs2',rd='w_rd',wd='w_data',r1='d_r1raw',r2='d_r2raw'))
    c.add('ImmGen',{},dict(instr='d_instr',sel='d_ImmSel',imm='d_imm'))
    c.grp='ForwardUnit'
    c.const('z6',0,6)
    def nz(x,o): c.eq(o+'_z',x,'z6',6); c.gate('NOT Gate',o,[o+'_z'])
    nz('w_rd','w_rdnz'); nz('m_rd','m_rdnz'); nz('e_rd','e_rdnz')
    for r in('1','2'):
        c.eq(f'wb_eq{r}','w_rd',f'd_rs{r}',6); c.gate('AND Gate',f'wb_byp{r}',[f'wb_eq{r}','w_RegWrite','w_rdnz'])
        c.eq(f'fm_eq{r}','m_rd',f'e_rs{r}',6); c.gate('AND Gate',f'fm{r}',[f'fm_eq{r}','m_RegWrite','m_rdnz'])
        c.eq(f'fw_eq{r}','w_rd',f'e_rs{r}',6); c.gate('AND Gate',f'fw{r}',[f'fw_eq{r}','w_RegWrite','w_rdnz'])
    c.grp='top'
    for r in('1','2'): c.mux(f'd_r{r}',f'wb_byp{r}',[f'd_r{r}raw','w_data'],32)
    c.grp='HazardUnit'
    c.eq('hz1r','e_rd','d_rs1',6); c.eq('hz2r','e_rd','d_rs2',6)
    c.gate('AND Gate','hz1',['hz1r','d_UseRs1'])
    if ADVFWD and MUT!='nosfwd_stall':
        c.gate('NOT Gate','d_nst',['d_MemWrite']); c.gate('AND Gate','hz2',['hz2r','d_UseRs2','d_nst'])   # store chi can rs2 o MEM -> khong stall
    else: c.gate('AND Gate','hz2',['hz2r','d_UseRs2'])
    c.gate('OR Gate','hz12',['hz1','hz2'])
    c.gate('AND Gate','stall',['e_MemRead','e_rdnz','z1m' if MUT=='nostall' else 'hz12'],1)
    c.gate('OR Gate','bubble',['stall','redir'])
    c.mux('d_ctrl_q','bubble',['d_ctrl','zc'],CW)
    if BP: c.mux('d_pt_q','bubble',['d_pt','z1m'],1)
    c.gate('NOT Gate','nstall',['stall']); c.gate('OR Gate','pcen0',['nstall','redir']); c.gate('AND Gate','pcen',['pcen0','nmstall'])
    c.grp='ID_EX'
    regs=[('ctrl',CW),('pc',32),('r1',32),('r2',32),('imm',32),('rs1',6),('rs2',6),('rd',6),('f3',3)]+([('pt',1),('ptgt',32)] if BP else [])
    for n,w in regs:
        c.reg('e_'+n,'d_'+n+('_q' if n in('ctrl','pt') else ''),'clk',w,en='nmstall')
    slice_ctrl(c,'e_ctrl','e_',only={'RegWrite','ASel','BSel','ALUOp','MemRead','ResSel','Branch','Jal','Jalr','Valid','Csr','Mret','FpOp'})
    # ---- EX
    c.grp='top'
    for r,o in (('1','fa'),('2','fb')):
        c.mux(o+'_w',f'fw{r}',[f'e_r{r}','w_data'],32); c.mux(o,'z1m' if MUT=='nofwd' else f'fm{r}',[o+'_w','m_res'],32)
    c.mux('alua','e_ASel',['fa','e_pc','z32'],32); c.mux('alub','e_BSel',['fb','e_imm'],32)
    c.add('ALU',{},dict(a='alua',b='alub',op='e_ALUOp',y='e_y'))
    c.add('MulDiv',{},dict(a='fa',b='fb',f3='e_f3',y='e_md'))
    c.add('FPU',{},dict(a='fa',b='fb',op='e_FpOp',rm='e_f3',y='e_fpu'))
    c.add('Adder',{'width':32},['e_pc','k4','e_pc4']); c.add('Adder',{'width':32},['e_pc','e_imm','e_brt'])
    c.const('kmask',0xFFFFFFFE,32); c.gate('AND Gate','e_jalrt',['e_y','kmask'],32)
    c.add('BranchUnit',{},dict(a='fa',b='fb',f3='e_f3',cond='e_cond'))
    c.grp='CSRUnit'
    c.slice('e_imm',32,0,11,'e_csra'); c.slice('e_rs1',6,0,4,'e_zimm')
    c.grp='top'
    c.add('CSRFile',{},dict(clk='clk',en='nmstall',we='csr_we',addr='e_csra',f3='e_f3',rs1v='fa',zimm='e_zimm',mret='e_Mret',trap='take',
          epc='e_pc',msip='msip',mtip='mtip',meip='IRQ',cycles='cycles',rdata='e_csr',mtvec='mtvec',mepc='mepc',irq='irq',cause='cause'))
    c.mux('e_res','e_ResSel',['e_y','e_pc4','e_md','e_csr','e_fpu','z32','z32','z32'],32)
    # ---- Redirect / ngat / du doan sai
    c.grp='RedirectUnit'
    c.gate('AND Gate','e_bt',['e_Branch','e_cond']); c.gate('OR Gate','e_actual',['e_bt','e_Jal','e_Jalr'])
    c.mux('e_target','e_Jalr',['e_brt','e_jalrt'],32)
    c.gate('AND Gate','take',['irq','e_Valid','nmstall'] if MUT!='noirq' else ['z1m','e_Valid']); c.gate('NOT Gate','ntake',['take'])
    if BP:
        c.gate('XOR Gate','dirmis',['e_actual','e_pt']); c.eq('tgteq','e_target','e_ptgt',32); c.gate('NOT Gate','tgtne',['tgteq'])
        c.gate('AND Gate','tgtmis',['e_actual','tgtne']); c.gate('OR Gate','mis',['dirmis','tgtmis'])
        c.mux('bp_tgt','e_actual',['e_pc4','e_target'],32)
        c.gate('OR Gate','e_isbr',['e_Branch','e_Jal','e_Jalr']); c.gate('AND Gate','btb_we',['e_isbr','ntake','nmstall'])
    misn='mis' if BP else 'e_actual'
    c.gate('AND Gate','e_mret_x',['e_Mret','ntake'])
    c.gate('OR Gate','redir',['take','e_mret_x',misn])
    c.mux('rt1','e_Mret',['bp_tgt' if BP else 'e_target','mepc'],32); c.mux('redir_tgt','take',['rt1','mtvec'],32)
    c.gate('AND Gate','csr_we',['e_Csr','ntake'])
    c.mux('e_ctrl_q','z1m' if MUT=='nosquash' else 'take',['e_ctrl','zc'],CW)
    c.gate('OR Gate','e_isbr2',['e_Branch','e_Jal','e_Jalr']); c.gate('AND Gate','br_ev',['e_isbr2','ntake','nmstall'])
    c.gate('AND Gate','mis_ev',[misn,'ntake','nmstall'])
    c.grp='EX_MEM'
    for q,d,w in (('m_ctrl','e_ctrl_q',CW),('m_res','e_res',32),('m_r2','fb',32),('m_rd','e_rd',6),('m_f3','e_f3',3),('m_rs2','e_rs2',6)):
        c.reg(q,d,'clk',w,en='nmstall')
    slice_ctrl(c,'m_ctrl','m_',only={'RegWrite','MemRead','MemWrite','Valid'})
    # ---- MEM
    c.grp='MemFwd'
    if ADVFWD and MUT!='nosfwd':
        c.eq('sf_eq','w_rd','m_rs2',6); c.gate('AND Gate','sfw',['m_MemWrite','w_RegWrite','w_rdnz','sf_eq'])
        c.mux('m_r2f','sfw',['m_r2','w_data'],32)
    else: c.gate('OR Gate','m_r2f',['m_r2','m_r2'],32)
    c.grp='top'
    c.slice('m_res',32,2,11,'daddr'); c.slice('m_res',32,0,1,'m_boff')
    c.add('StoreUnit',{},dict(old='m_mraw',wd='m_r2f',off='m_boff',f3='m_f3',new='m_mnew'))
    c.add('RAM',{'addrWidth':10,'dataWidth':32,'asyncread':'true','label':'DMEM'},['daddr','m_mraw','m_mnew','one','dmem_we','clk'])
    c.add('MMIO',{},dict(clk='clk',addr='m_res',we='io_we',wdata='m_r2f',sw='SW',cycles='cycles',rdata='io_data',isio='isio',led='led',
          msip='msip',mtip='mtip',tx_we='tx_we',tx_d='tx_d'))
    c.add('TTY',{'rows':8,'cols':32,'label':'UART_TX'},['z1m','clk','tx_we','tx_d'])
    if CACHE=='1':
        c.add('DCache',{},dict(clk='clk',addr='daddr',wr='c_wr',wdata='m_mnew',mdata='m_mraw',fill='c_fill',hit='c_hit',data='c_data'))
    c.grp='CacheCtrl'
    c.gate('NOT Gate','nio',['isio'])
    c.gate('AND Gate','dmem_we',['m_MemWrite','nio']); c.gate('AND Gate','io_we',['m_MemWrite','nmstall'])
    c.gate('AND Gate','c_rd',['m_MemRead','nio'])
    if CACHE=='1':
        c.gate('AND Gate','c_wr',['m_MemWrite','nio'])
        c.gate('NOT Gate','c_nhit',['c_hit']); c.gate('AND Gate','c_miss',['c_rd','c_nhit'])
        c.mux('m_cached','c_hit',['m_mraw','c_data'],32)
    else:
        c.gate('OR Gate','c_miss',['c_rd','c_rd'] if CACHE=='none' else ['z1m','z1m']); c.gate('OR Gate','m_cached',['m_mraw','m_mraw'],32)
    c.const('kP',MISS_P,2); c.const('k1_2',1,2); c.const('z2',0,2)
    c.eq('mc_done','mcnt','kP',2); c.gate('NOT Gate','mc_nd',['mc_done'])
    c.gate('AND Gate','mstall',['c_miss','mc_nd']); c.gate('AND Gate','c_fill',['c_miss','mc_done']); c.gate('NOT Gate','nmstall',['mstall'])
    c.add('Adder',{'width':2},['mcnt','k1_2','mcnt1']); c.mux('mcnt_n','mstall',['z2','mcnt1'],2); c.reg('mcnt','mcnt_n','clk',2)
    c.gate('NOT Gate','c_hitn_',['c_miss']); c.gate('AND Gate','dc_hit_ev',['c_rd','c_hitn_'])
    c.mux('m_src','isio',['m_cached','io_data'],32)
    c.grp='top'
    c.add('LoadUnit',{},dict(din='m_src',off='m_boff',f3='m_f3',v='m_mdata'))
    c.grp='MEM_WB'
    for q,d,w in (('w_ctrl','m_ctrl',CW),('w_res','m_res',32),('w_mdata','m_mdata',32),('w_rd','m_rd',6)): c.reg(q,d,'clk',w,en='nmstall')
    slice_ctrl(c,'w_ctrl','w_',only={'RegWrite','MemRead','Halt','Valid'})
    c.grp='top'
    c.mux('w_data','w_MemRead',['w_res','w_mdata'],32)
    c.grp='PerfCounters'; c.gate('AND Gate','ret_ev',['w_Valid','nmstall']); c.grp='top'
    counters(c,[('cycles',None),('instret','ret_ev'),('br_cnt','br_ev' if BP else 'br_ev'),('br_miss','mis_ev'),('dc_hit','dc_hit_ev'),('dc_miss','c_fill')])
    c.pin_in('SW',8); c.pin_in('IRQ',1)
    for n,l,w in PIPE_OUT: c.pin_out(n,w,l)
    return c
GROUPS={'single':['InstrDecode','MainControl','PerfCounters'],
 'pipeline':['IF_ID','InstrDecode','MainControl','HazardUnit','ForwardUnit','ID_EX','CSRUnit','RedirectUnit','EX_MEM','MemFwd','CacheCtrl','MEM_WB','PerfCounters']}
PIPEREGS={'IF_ID','ID_EX','EX_MEM','MEM_WB'}
COLS={'single':[
  ['pcn1','Clock','PerfCounters'],['pcnext'],['pc'],['pcw','pc4'],['instr'],['InstrDecode','MainControl'],['RegFile','ImmGen'],
  ['alua','alub','brt','BranchUnit'],['ALU','MulDiv','btaken'],['jalrt','taken','res','daddr','boff'],['StoreUnit'],['mraw'],['LoadUnit'],['wb','halt','PC_out','cycles']],
 'pipeline':[
  ['pcnext','Clock','PerfCounters','SW','IRQ'],['pc'],['pc4f','BTB'],['pc_pred','pcw'],['f_instr'],['f_instr_q','f_pt_q'],['IF_ID'],
  ['InstrDecode','MainControl','HazardUnit','ForwardUnit','CSRUnit'],['RegFile64','ImmGen'],['d_r1','d_r2'],['ID_EX'],
  ['fa_w','fb_w'],['fa','fb'],['alua','alub','e_pc4','e_brt','BranchUnit'],['ALU','MulDiv','FPU','CSRFile','e_jalrt'],['e_res','RedirectUnit'],
  ['EX_MEM'],['daddr','m_boff','MemFwd','StoreUnit'],['m_mraw','MMIO','DCache','UART_TX'],['CacheCtrl','LoadUnit'],['MEM_WB'],
  ['w_data','halt','PC_out','cycles','INSTRET','STALL','FLUSH','MSTALL','BR_CNT','BR_MISS','DC_HIT','DC_MISS','LED']]}
TITLES={'single':{0:'PC next',2:'PC',4:'IMEM',5:'Decode / Control',6:'RegFile / Imm',8:'ALU / MulDiv',11:'DMEM',13:'Write-back'},
 'pipeline':{0:'PC next / Counters',2:'IF + BTB',4:'IMEM',6:'IF/ID',7:'ID',10:'ID/EX',13:'EX',14:'ALU/M/F/CSR',16:'EX/MEM',18:'MEM: DMEM/D-cache/MMIO',20:'MEM/WB',21:'WB / outputs'}}
# ---------------- custom appearance ----------------
def strip(n):
    for p in('d_','e_','m_','w_','f_'):
        if n.startswith(p): n=n[2:]; break
    return n[:-2] if n.endswith('_q') else n
def make_app(name,pins,align=False):
    """pins: list (label,dir,width). Tra ve ports{label:(dx,dy,w)}, box, ham sinh <appear>"""
    ins=[p for p in pins if p[1]=='in' and p[0]!='clk']+[p for p in pins if p[1]=='in' and p[0]=='clk']
    outs=[p for p in pins if p[1]=='out']
    rows={}
    if align:
        keys=[]
        for p in outs:
            k=strip(p[0])
            if k not in keys: keys.append(k)
        rowof={k:i for i,k in enumerate(keys)}
        for p in outs: rows[p[0]]=rowof[strip(p[0])]
        nxt=len(keys); used=set()
        for p in ins:
            k=strip(p[0]); r=rowof.get(k)
            if p[0]!='clk' and r is not None and r not in used: rows[p[0]]=r; used.add(r)
            else:
                while nxt in used: nxt+=1
                rows[p[0]]=nxt; used.add(nxt); nxt+=1
    else:
        for i,p in enumerate(ins): rows[p[0]]=i
        for i,p in enumerate(outs): rows[p[0]]=i
    n=max(rows.values())+1
    lw=max([len(p[0]) for p in ins]+[0]); rw=max([len(p[0]) for p in outs]+[0])
    W=max(80,int((lw+rw)*6.6+30)+(10 if align else 0), int(len(name)*8+20)); W=(W+9)//10*10
    H=30+20*n
    ports={p[0]:((0 if p[1]=='in' else W),30+20*rows[p[0]],p[2]) for p in pins}
    def appear(items):
        loc={it['c'][1]['label']:it['loc'] for it in items if it['c'][0]=='Pin'}
        X,Y=50,50
        o=['<appear>',f'<rect fill="#f4f8ff" height="{H}" stroke="#000000" stroke-width="2" width="{W}" x="{X}" y="{Y}"/>',
           f'<text dominant-baseline="central" font-family="SansSerif" font-size="12" font-weight="bold" text-anchor="middle" x="{X+W//2}" y="{Y+12}">{name}</text>']
        for p in pins:
            dx,dy,w=ports[p[0]]; px,py=loc[p[0]]
            if p[1]=='in':
                o.append(f'<text dominant-baseline="central" font-family="SansSerif" font-size="10" text-anchor="start" x="{X+dx+5}" y="{Y+dy}">{p[0]}</text>')
                o.append(f'<circ-port dir="in" pin="{px},{py}" x="{X+dx}" y="{Y+dy}"/>')
            else:
                o.append(f'<text dominant-baseline="central" font-family="SansSerif" font-size="10" text-anchor="end" x="{X+dx-5}" y="{Y+dy}">{p[0]}</text>')
                o.append(f'<circ-port dir="out" pin="{px},{py}" x="{X+dx}" y="{Y+dy}"/>')
        o.append(f'<circ-anchor facing="east" x="{X}" y="{Y}"/>')
        o.append('</appear>'); return '\n'.join(o)
    return ports,(0,0,W,H),appear
def pins_of(circ):
    return [(a['label'],'in' if a['type']=='input' else 'out',a['width']) for k,a,*_ in circ.comps if k=='Pin']
def prep(circ,align=False):
    for comp in circ.comps:
        if comp[0]=='Pin':
            a=comp[1]
            if a['width']>1: a['radix']='16'
            a['labelloc']='north'
    ports,box,app=make_app(circ.name,pins_of(circ),align)
    layout.SUBPORTS[circ.name]=ports; layout.SUBBOX[circ.name]=box; lg.SUBPORTS[circ.name]=ports
    return app
def build(kind,prog,out,render=None):
    layout.SUBPORTS=lg.SUBPORTS
    mods=[f() for f in (MODS_SINGLE if kind=='single' else MODS_PIPE)]
    apps={m.name:prep(m) for m in mods}
    main=(single if kind=='single' else pipeline)(prog)
    for comp in main.comps:
        if comp[0] in('Pin','Clock','ROM','RAM','TTY'): comp[4]='top'
    top,subs=wire.partition(main,GROUPS[kind])
    for g in subs: apps[g.name]=prep(g,g.name in PIPEREGS)
    for t in top:
        if t[0] in [g.name for g in subs]: t[1]={}
        if t[0]=='Pin': t[1]['labelloc']='north'
    xs=[]; stats={}
    for c in mods+subs:
        x,_,st=layout.emit(c.name,c.comps,appear=apps[c.name]); xs.append(x); stats[c.name]=st
    x,_,st=layout.emit('main',top,columns=COLS[kind],titles=TITLES[kind]); stats['main']=st
    xml=lg.project([]).replace('\n\n</project>','\n</project>')
    body='\n'.join([x]+xs)
    xml=xml.replace('</options>\n','</options>\n'+body+'\n',1)
    open(out,'w').write(xml)
    return stats
if __name__=='__main__':
    if len(sys.argv)>3:
        ws=[w for w in open(sys.argv[3]).read().split()[4:]]
        prog='addr/data: 10 32\n'+' '.join(w.lstrip('0') or '0' for w in ws)+'\n'
    else: prog='addr/data: 10 32\n73\n'
    print(build(sys.argv[1],prog,sys.argv[2]))
