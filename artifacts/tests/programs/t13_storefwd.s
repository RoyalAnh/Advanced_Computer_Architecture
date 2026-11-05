# load -> store phu thuoc ngay sau (forward MEM->MEM, khong stall)
li s0,0x100
li t0,11
li t1,22
sw t0,0(s0)
sw t1,4(s0)
lw a0,0(s0)
sw a0,8(s0)
lw a1,4(s0)
sh a1,12(s0)
lw a2,8(s0)
sb a2,13(s0)
lw a3,12(s0)
sw a3,16(s0)
lw a4,16(s0)
add a5,a4,a0
ecall
