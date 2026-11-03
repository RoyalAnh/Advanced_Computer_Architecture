# R-type va I-type ALU (ca so am)
addi x1, x0, 25        # 25
addi x2, x0, -7        # -7
add  x3, x1, x2        # 18
sub  x4, x1, x2        # 32
sub  x5, x2, x1        # -32
and  x6, x1, x2
or   x7, x1, x2
xor  x8, x1, x2
addi x9, x0, 3
sll  x10, x1, x9       # 200
srl  x11, x2, x9       # logical
sra  x12, x2, x9       # -1
slt  x13, x2, x1       # 1
slt  x14, x1, x2       # 0
sltu x15, x2, x1       # 0 (0xFFFFFFF9 > 25)
sltu x16, x1, x2       # 1
andi x17, x2, 0x0F0
ori  x18, x1, -256
xori x19, x1, -1
slli x20, x1, 28
srli x21, x2, 4
srai x22, x2, 1
slti x23, x2, -6       # 1
sltiu x24, x1, 26      # 1
sltiu x25, x2, 5       # 0
slti x26, x1, -1       # 0
add  x0, x1, x1        # x0 van = 0
add  x27, x0, x0
ecall
