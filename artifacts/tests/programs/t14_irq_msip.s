# requires: CSR IO
# timing_dependent (so vong cho ngat phu thuoc thoi gian -> khong so INSTRET/BR_CNT)
# Ngat phan mem (MSIP qua MMIO 0x80000010), handler xoa msip, mret; tro lai cho vong doi co
la t0,handler
csrw mtvec,t0
li t0,8
csrw mie,t0
csrsi mstatus,8
li s1,0x80000000
li s0,0
li t1,1
sw t1,16(s1)
li s5,0
li s6,0
wait:
addi s5,s5,1
addi s6,s6,1
beqz s0,wait
nop
sub s7,s5,s6
li s5,0
li s6,0
csrr a0,mcause
csrr a1,mstatus
csrr a2,mie
csrr a3,mtvec
li t0,0x55
csrw mscratch,t0
csrrs a4,mscratch,t1
csrrc a5,mscratch,t0
csrrwi a6,mscratch,9
csrr a7,mscratch
ecall
handler:
sw x0,16(s1)
addi s0,s0,1
csrr s2,mcause
mret
