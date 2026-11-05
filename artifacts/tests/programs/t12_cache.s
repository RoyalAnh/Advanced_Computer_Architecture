# D-cache: duyet mang 2 lan (lan 2 hit), roi truy cap xung dot cung index (miss)
li s0,0x200
li t0,0
li t1,16
init:
slli t2,t0,2
add t2,t2,s0
sw t0,0(t2)
addi t0,t0,1
blt t0,t1,init
li a0,0
li t3,2
pass:
li t0,0
loop:
slli t2,t0,2
add t2,t2,s0
lw t4,0(t2)
add a0,a0,t4
addi t0,t0,1
blt t0,t1,loop
addi t3,t3,-1
bnez t3,pass
li s1,0x40
lw a1,0(x0)
lw a2,0(s1)
lw a3,0(x0)
lw a4,0(s1)
sw a0,0(s1)
lw a5,0(s1)
li s3,0x300
lw a6,0(s3)
lw a7,0(s3)
ecall
