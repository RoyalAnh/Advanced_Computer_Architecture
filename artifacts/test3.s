addi x1, x0, 0x123
sw x1, 0(x0)       # w0=0x123
addi x2, x0, 0x77
sw x2, 4(x0)       # w1=0x77
lw x3, 0(x0)
lw x4, 4(x0)
addi x0, x0, 0
lw x5, 4(x0)
sw x3, 16(x0)      # w4 exp 0x123
sw x4, 20(x0)      # w5 exp 0x77
sw x5, 24(x0)      # w6 exp 0x77
