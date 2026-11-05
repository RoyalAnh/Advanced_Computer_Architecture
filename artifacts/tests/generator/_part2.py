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
