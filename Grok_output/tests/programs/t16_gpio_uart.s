# requires: IO
# expect_uart: "RV32 OK\n"
# expect_led: 0x3c
li s1,0x80000000
li s2,0x100
li t0,0x32335652
sw t0,0(s2)
li t0,0x0A4B4F20
sw t0,4(s2)
sw x0,8(s2)
loop:
lbu t0,0(s2)
beqz t0,done
sw t0,8(s1)
addi s2,s2,1
j loop
done:
li t0,0x3c
sw t0,0(s1)
lw a0,0(s1)
lw a1,4(s1)
lw a2,12(s1)
ecall
