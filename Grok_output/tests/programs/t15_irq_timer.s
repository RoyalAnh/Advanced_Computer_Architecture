# requires: CSR IO
# timing_dependent (so vong cho ngat phu thuoc thoi gian -> khong so INSTRET/BR_CNT)
# Ngat timer: mtimecmp = mtime+50, cho ngat; handler tat timer (mtimecmp=-1), dem so lan
la t0,handler
csrw mtvec,t0
li t0,0x80
csrw mie,t0
li s1,0x80000000
li s0,0
lw t1,24(s1)
addi t1,t1,50
sw t1,20(s1)
csrsi mstatus,8
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
csrci mstatus,8
csrr a0,mcause
li t0,-1
lw a1,20(s1)
li t1,0
ecall
handler:
li t2,-1
sw t2,20(s1)
addi s0,s0,1
csrr s2,mcause
mret
