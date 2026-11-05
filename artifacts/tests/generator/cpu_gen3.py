import os
import lg, subprocess, sys, os, wire, layout
from lg import Circ
# ---------- control table ----------
ADD,SUB,SLL,SLT,SLTU,XOR,SRL,SRA,OR,AND=range(10)
IMM_I,IMM_S,IMM_B,IMM_U,IMM_J=range(5)
CTRL_FIELDS=[('RegWrite',1),('ASel',2),('BSel',1),('ALUOp',4),('MemRead',1),('MemWrite',1),('ResPC4',1),('ImmSel',3),('Branch',1),('Jal',1),('Jalr',1),('Halt',1),('UseRs1',1),('UseRs2',1)]
CW=sum(w for _,w in CTRL_FIELDS)
def cword(**kv):
    v=0;b=0
    for n,w in CTRL_FIELDS: v|=(kv.get(n,0)&((1<<w)-1))<<b; b+=w
    return v
def ctrl_rom():
    t=[0]*512
    for a in range(512):
        op=(a&31)<<2|3; f3=(a>>5)&7; f7=(a>>8)&1
        c=0
        if op==0x33:
            alu={(0,0):ADD,(0,1):SUB,(1,0):SLL,(2,0):SLT,(3,0):SLTU,(4,0):XOR,(5,0):SRL,(5,1):SRA,(6,0):OR,(7,0):AND}.get((f3,f7))
            if alu is not None: c=cword(RegWrite=1,ALUOp=alu,UseRs1=1,UseRs2=1)
        elif op==0x13:
            alu={0:ADD,2:SLT,3:SLTU,4:XOR,6:OR,7:AND,1:SLL,5:SRA if f7 else SRL}[f3]
            c=cword(RegWrite=1,BSel=1,ALUOp=alu,ImmSel=IMM_I,UseRs1=1)
        elif op==0x03 and f3 in(0,1,2,4,5): c=cword(RegWrite=1,BSel=1,ALUOp=ADD,MemRead=1,ImmSel=IMM_I,UseRs1=1)
        elif op==0x23 and f3 in(0,1,2): c=cword(BSel=1,ALUOp=ADD,MemWrite=1,ImmSel=IMM_S,UseRs1=1,UseRs2=1)
        elif op==0x63 and f3 not in(2,3): c=cword(Branch=1,ImmSel=IMM_B,UseRs1=1,UseRs2=1)
        elif op==0x6f: c=cword(RegWrite=1,ResPC4=1,Jal=1,ImmSel=IMM_J)
        elif op==0x67 and f3==0: c=cword(RegWrite=1,BSel=1,ALUOp=ADD,ResPC4=1,Jalr=1,ImmSel=IMM_I,UseRs1=1)
        elif op==0x37: c=cword(RegWrite=1,ASel=2,BSel=1,ALUOp=ADD,ImmSel=IMM_U)
        elif op==0x17: c=cword(RegWrite=1,ASel=1,BSel=1,ALUOp=ADD,ImmSel=IMM_U)
        elif op==0x73: c=cword(Halt=1)
        t[a]=c
    return 'addr/data: 9 %d\n'%CW+' '.join('%x'%x for x in t)+'\n'
def slice_ctrl(c,word,prefix):
    b=0
    for n,w in CTRL_FIELDS: c.slice(word,CW,b,b+w-1,prefix+n); b+=w
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
def m_regfile():
    c=Circ('RegFile')
    for n,w in (('clk',1),('we',1),('rs1',5),('rs2',5),('rd',5),('wd',32)): c.pin_in(n,w)
    c.pin_out('r1',32); c.pin_out('r2',32)
    c.add('Decoder',{'select':5,'enable':'false'},['dec%d'%i for i in range(32)]+['rd'])
    c.const('x0',0,32)
    for i in range(1,32):
        c.gate('AND Gate','en%d'%i,['we','dec%d'%i])
        c.reg('x%d'%i,'wd','clk',32,en='en%d'%i)
    regs=['x%d'%i for i in range(32)]
    c.mux('r1','rs1',regs,32); c.mux('r2','rs2',regs,32)
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
    c.slice('instr',32,2,6,'op5'); c.slice('instr',32,12,14,'f3'); c.slice('instr',32,30,30,'f7b')
    c.pack('caddr',[('op5',5),('f3',3),('f7b',1)])
    c.add('ROM',{'addrWidth':9,'dataWidth':CW,'label':'CTRL','contents':ctrl_rom()},['caddr','ctrl'])
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
MODS=[m_alu,m_regfile,m_immgen,m_branch,m_control,m_load,m_store]
# ================= top-level netlists (khong con quat 31 chan debug) =================
def cycle_counter(c):
    c.grp='CycleCounter'
    c.const('c1',1,32); c.add('Adder',{'width':32},['cycles','c1','cycles_n']); c.reg('cycles','cycles_n','clk',32)
    c.grp='top'
def single(prog):
    c=Circ('main'); c.add('Clock',{},['clk']); cycle_counter(c)
    c.reg('pc','pcnext','clk',32)
    c.slice('pc',32,2,11,'pcw')
    c.add('ROM',{'addrWidth':10,'dataWidth':32,'label':'IMEM','contents':prog},['pcw','instr'])
    c.grp='MainControl'; c.add('Control',{},{'instr':'instr','ctrl':'ctrl'}); slice_ctrl(c,'ctrl','')
    c.grp='InstrDecode'
    c.slice('instr',32,15,19,'rs1'); c.slice('instr',32,20,24,'rs2'); c.slice('instr',32,7,11,'rd'); c.slice('instr',32,12,14,'f3')
    c.grp='top'
    c.add('RegFile',{},dict(clk='clk',we='RegWrite',rs1='rs1',rs2='rs2',rd='rd',wd='wb',r1='r1',r2='r2'))
    c.add('ImmGen',{},dict(instr='instr',sel='ImmSel',imm='imm'))
    c.const('z32',0,32)
    c.mux('alua','ASel',['r1','pc','z32'],32); c.mux('alub','BSel',['r2','imm'],32)
    c.add('ALU',{},dict(a='alua',b='alub',op='ALUOp',y='y'))
    c.const('k4',4,32); c.add('Adder',{'width':32},['pc','k4','pc4']); c.add('Adder',{'width':32},['pc','imm','brt'])
    c.const('kmask',0xFFFFFFFE,32); c.gate('AND Gate','jalrt',['y','kmask'],32)
    c.add('BranchUnit',{},dict(a='r1',b='r2',f3='f3',cond='cond'))
    c.gate('AND Gate','btaken',['Branch','cond']); c.gate('OR Gate','taken',['btaken','Jal'])
    c.mux('pcn1','taken',['pc4','brt'],32); c.mux('pcnext','Jalr',['pcn1','jalrt'],32)
    c.mux('res','ResPC4',['y','pc4'],32)
    c.slice('y',32,2,11,'daddr'); c.const('one',1,1)
    c.slice('y',32,0,1,'boff')
    c.add('StoreUnit',{},dict(old='mraw',wd='r2',off='boff',f3='f3',new='mnew'))
    c.add('RAM',{'addrWidth':10,'dataWidth':32,'asyncread':'true','label':'DMEM'},['daddr','mraw','mnew','one','MemWrite','clk'])
    c.add('LoadUnit',{},dict(din='mraw',off='boff',f3='f3',v='mdata'))
    c.mux('wb','MemRead',['res','mdata'],32)
    c.pin_out('Halt',1,'halt'); c.pin_out('pc',32,'PC_out'); c.pin_out('cycles',32)
    return c
def pipeline(prog):
    MUT=os.environ.get('MUT','')
    c=Circ('main'); c.add('Clock',{},['clk']); cycle_counter(c)
    c.const('z1m',0,1); c.const('z32',0,32); c.const('one',1,1); c.const('zc',0,CW); c.const('k4',4,32)
    # ---- IF
    c.reg('pc','pcnext','clk',32,en='pcen')
    c.add('Adder',{'width':32},['pc','k4','pc4f'])
    c.mux('pcnext','flush',['pc4f','e_target'],32)
    c.slice('pc',32,2,11,'pcw')
    c.add('ROM',{'addrWidth':10,'dataWidth':32,'label':'IMEM','contents':prog},['pcw','f_instr'])
    c.mux('f_instr_q','z1m' if MUT=='noflush' else 'flush',['f_instr','z32'],32)
    c.grp='IF_ID'
    c.reg('d_pc','pc','clk',32,en='pcen'); c.reg('d_instr','f_instr_q','clk',32,en='pcen')
    # ---- ID
    c.grp='MainControl'; c.add('Control',{},{'instr':'d_instr','ctrl':'d_ctrl'}); slice_ctrl(c,'d_ctrl','d_')
    c.grp='InstrDecode'
    c.slice('d_instr',32,15,19,'d_rs1'); c.slice('d_instr',32,20,24,'d_rs2'); c.slice('d_instr',32,7,11,'d_rd'); c.slice('d_instr',32,12,14,'d_f3')
    c.grp='top'
    c.add('RegFile',{},dict(clk='clk',we='w_RegWrite',rs1='d_rs1',rs2='d_rs2',rd='w_rd',wd='w_data',r1='d_r1raw',r2='d_r2raw'))
    c.add('ImmGen',{},dict(instr='d_instr',sel='d_ImmSel',imm='d_imm'))
    c.grp='ForwardUnit'
    c.const('z5',0,5)
    def nz(x,o): c.eq(o+'_z',x,'z5',5); c.gate('NOT Gate',o,[o+'_z'])
    nz('w_rd','w_rdnz'); nz('m_rd','m_rdnz'); nz('e_rd','e_rdnz')
    for r in('1','2'):
        c.eq(f'wb_eq{r}','w_rd',f'd_rs{r}',5); c.gate('AND Gate',f'wb_byp{r}',[f'wb_eq{r}','w_RegWrite','w_rdnz'])
        c.eq(f'fm_eq{r}','m_rd',f'e_rs{r}',5); c.gate('AND Gate',f'fm{r}',[f'fm_eq{r}','m_RegWrite','m_rdnz'])
        c.eq(f'fw_eq{r}','w_rd',f'e_rs{r}',5); c.gate('AND Gate',f'fw{r}',[f'fw_eq{r}','w_RegWrite','w_rdnz'])
    c.grp='top'
    for r in('1','2'): c.mux(f'd_r{r}',f'wb_byp{r}',[f'd_r{r}raw','w_data'],32)
    c.grp='HazardUnit'
    c.eq('hz1r','e_rd','d_rs1',5); c.eq('hz2r','e_rd','d_rs2',5)
    c.gate('AND Gate','hz1',['hz1r','d_UseRs1']); c.gate('AND Gate','hz2',['hz2r','d_UseRs2']); c.gate('OR Gate','hz12',['hz1','hz2'])
    c.gate('AND Gate','stall',['e_MemRead','e_rdnz','z1m' if MUT=='nostall' else 'hz12'],1)
    c.gate('OR Gate','bubble',['stall','flush'])
    c.mux('d_ctrl_q','bubble',['d_ctrl','zc'],CW)
    c.gate('NOT Gate','nstall',['stall']); c.gate('OR Gate','pcen',['nstall','flush'])
    c.grp='ID_EX'
    for n,w in (('ctrl',CW),('pc',32),('r1',32),('r2',32),('imm',32),('rs1',5),('rs2',5),('rd',5),('f3',3)):
        c.reg('e_'+n,'d_ctrl_q' if n=='ctrl' else 'd_'+n,'clk',w)
    slice_ctrl(c,'e_ctrl','e_')
    # ---- EX
    c.grp='top'
    for r,o in (('1','fa'),('2','fb')):
        c.mux(o+'_w',f'fw{r}',[f'e_r{r}','w_data'],32); c.mux(o,'z1m' if MUT=='nofwd' else f'fm{r}',[o+'_w','m_res'],32)
    c.mux('alua','e_ASel',['fa','e_pc','z32'],32); c.mux('alub','e_BSel',['fb','e_imm'],32)
    c.add('ALU',{},dict(a='alua',b='alub',op='e_ALUOp',y='e_y'))
    c.add('Adder',{'width':32},['e_pc','k4','e_pc4']); c.add('Adder',{'width':32},['e_pc','e_imm','e_brt'])
    c.const('kmask',0xFFFFFFFE,32); c.gate('AND Gate','e_jalrt',['e_y','kmask'],32)
    c.add('BranchUnit',{},dict(a='fa',b='fb',f3='e_f3',cond='e_cond'))
    c.gate('AND Gate','e_bt',['e_Branch','e_cond']); c.gate('OR Gate','flush',['e_bt','e_Jal','e_Jalr'],1)
    c.mux('e_target','e_Jalr',['e_brt','e_jalrt'],32)
    c.mux('e_res','e_ResPC4',['e_y','e_pc4'],32)
    c.grp='EX_MEM'
    c.reg('m_ctrl','e_ctrl','clk',CW); c.reg('m_res','e_res','clk',32); c.reg('m_r2','fb','clk',32); c.reg('m_rd','e_rd','clk',5); c.reg('m_f3','e_f3','clk',3)
    slice_ctrl(c,'m_ctrl','m_')
    c.grp='top'
    c.slice('m_res',32,2,11,'daddr'); c.slice('m_res',32,0,1,'m_boff')
    c.add('StoreUnit',{},dict(old='m_mraw',wd='m_r2',off='m_boff',f3='m_f3',new='m_mnew'))
    c.add('RAM',{'addrWidth':10,'dataWidth':32,'asyncread':'true','label':'DMEM'},['daddr','m_mraw','m_mnew','one','m_MemWrite','clk'])
    c.add('LoadUnit',{},dict(din='m_mraw',off='m_boff',f3='m_f3',v='m_mdata'))
    c.grp='MEM_WB'
    c.reg('w_ctrl','m_ctrl','clk',CW); c.reg('w_res','m_res','clk',32); c.reg('w_mdata','m_mdata','clk',32); c.reg('w_rd','m_rd','clk',5)
    slice_ctrl(c,'w_ctrl','w_')
    c.grp='top'
    c.mux('w_data','w_MemRead',['w_res','w_mdata'],32)
    c.pin_out('w_Halt',1,'halt'); c.pin_out('stall',1,'STALL'); c.pin_out('flush',1,'FLUSH'); c.pin_out('pc',32,'PC_out'); c.pin_out('cycles',32)
    return c
GROUPS={'single':['InstrDecode','MainControl','CycleCounter'],
 'pipeline':['IF_ID','InstrDecode','MainControl','HazardUnit','ForwardUnit','ID_EX','EX_MEM','MEM_WB','CycleCounter']}
PIPEREGS={'IF_ID','ID_EX','EX_MEM','MEM_WB'}
COLS={'single':[
  ['pcn1','Clock','CycleCounter'],['pcnext'],['pc'],['pcw','pc4'],['instr'],['InstrDecode','MainControl'],['RegFile','ImmGen'],
  ['alua','alub','brt','BranchUnit'],['ALU','btaken'],['jalrt','taken','res','daddr','boff'],['StoreUnit'],['mraw'],['LoadUnit'],['wb','halt','PC_out','cycles']],
 'pipeline':[
  ['pcnext','Clock','CycleCounter'],['pc'],['pc4f','pcw'],['f_instr'],['f_instr_q'],['IF_ID'],
  ['InstrDecode','MainControl','HazardUnit','ForwardUnit'],['RegFile','ImmGen'],['d_r1','d_r2'],['ID_EX'],
  ['fa_w','fb_w'],['fa','fb'],['alua','alub','e_brt','e_pc4','BranchUnit'],['ALU','e_bt'],['e_jalrt','e_res','flush','e_target'],
  ['EX_MEM'],['daddr','m_boff','StoreUnit'],['m_mraw'],['LoadUnit'],['MEM_WB'],['w_data','halt','STALL','FLUSH','PC_out','cycles']]}
TITLES={'single':{0:'PC next',2:'PC',4:'IMEM',5:'Decode / Control',6:'RegFile / Imm',8:'ALU',11:'DMEM',13:'Write-back'},
 'pipeline':{0:'PC next',2:'IF',3:'IMEM',5:'IF/ID',7:'ID',9:'ID/EX',12:'EX',15:'EX/MEM',17:'MEM (DMEM)',19:'MEM/WB',20:'WB'}}
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
    mods=[f() for f in MODS]
    apps={m.name:prep(m) for m in mods}
    main=(single if kind=='single' else pipeline)(prog)
    for comp in main.comps:
        if comp[0] in('Pin','Clock','ROM','RAM'): comp[4]='top'
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
    prog=open(sys.argv[3]).read() if len(sys.argv)>3 else 'addr/data: 10 32\n73\n'
    print(build(sys.argv[1],prog,sys.argv[2]))
