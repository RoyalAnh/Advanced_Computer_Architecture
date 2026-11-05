# jal / jalr: goi ham, tra ve, jalr voi offset, bit 0 bi xoa
addi x10, x0, 5
jal  x1, double      # x1 = 8
addi x11, x10, 0     # 10
jal  x0, skip
addi x11, x0, -1     # bi bo qua
skip:
addi x5, x0, 32      # target o dia chi 32
jalr x6, 1(x5)       # (32+1)&~1 = 32 (xoa bit 0), x6 = pc+4 = 28
addi x12, x0, -1     # bi bo qua
target:
addi x12, x0, 42     # pc=32
addi x13, x6, 0
ecall
double:
add  x10, x10, x10
jalr x0, 0(x1)
