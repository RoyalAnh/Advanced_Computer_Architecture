# load theo sau la lenh KHONG thuc su dung rs (truong rs trung rd cua load) -> khong can stall
addi x5, x0, 7
sw   x5, 0(x0)
lw   x5, 0(x0)
addi x6, x0, 5        # truong rs2 (imm[4:0]) = 5 trung x5 -> truoc day stall thua
lw   x5, 0(x0)
lui  x7, 0x28         # truong rs1 (bit 15-19) = 5 -> truoc day stall thua
lw   x5, 0(x0)
auipc x8, 0x28        # tuong tu
lw   x5, 0(x0)
jal  x9, l1           # JAL: rs1 field = imm bits
l1:
lw   x5, 0(x0)
addi x10, x5, 1       # load-use that: VAN phai stall -> 8
lw   x5, 0(x0)
sw   x5, 4(x0)        # store dung rs2 = x5: van stall
lw   x11, 4(x0)
blt  x0, x11, l2      # load-use + blt
addi x12, x0, 99
l2:
bge  x11, x0, l3
addi x12, x0, 98
l3:
bltu x0, x11, l4
addi x12, x0, 97
l4:
bgeu x0, x11, l5      # khong nhay
addi x13, x0, 1
l5:
ecall
