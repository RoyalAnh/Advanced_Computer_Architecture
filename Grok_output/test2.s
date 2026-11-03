addi x1, x0, 5
addi x2, x0, 3
addi x10, x0, -8
sw x1, 0(x0)        # w0 = 5
lw x3, 0(x0)        # x3 = 5
sw x3, 4(x0)        # w1 = 5 expected
addi x4, x3, 0
sw x4, 8(x0)        # w2 = 5
sll x5, x1, x2
sw x5, 12(x0)       # w3 = 40 (0x28)
sltu x6, x10, x1
sw x6, 16(x0)       # w4 = 0
sltu x7, x1, x10
sw x7, 20(x0)       # w5 = 1
andi x8, x10, 0xf
sw x8, 24(x0)       # w6 = 8
ori x9, x1, 0x30
sw x9, 28(x0)       # w7 = 0x35
sltiu x11, x1, 6
sw x11, 32(x0)      # w8 = 1
beq x1, x2, 8       # not taken
addi x12, x0, 7
sw x12, 36(x0)      # w9 = 7
srli x13, x10, 28
sw x13, 40(x0)      # w10 = 0xf
lw x14, 12(x0)
sw x14, 44(x0)      # w11 = 0x28
