# lui / auipc / li (gia lenh) - tuy chon nhung re
lui   x1, 0x12345
auipc x2, 0
auipc x3, 1
li    x4, 0xDEADBEEF
li    x5, -2048
addi  x6, x1, 0x678
ecall
