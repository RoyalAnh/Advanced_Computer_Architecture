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
