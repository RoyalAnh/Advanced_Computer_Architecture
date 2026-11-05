# lw/sw, lw lien tiep, store/load nhieu dia chi
addi x1, x0, 100
addi x2, x0, -5
sw   x1, 0(x0)
sw   x2, 4(x0)
addi x3, x0, 64
sw   x1, 8(x3)          # mem[72]
sw   x2, -4(x3)         # mem[60]
lw   x4, 0(x0)
lw   x5, 4(x0)
lw   x6, 8(x3)
lw   x7, -4(x3)
add  x8, x4, x5         # 95
lw   x9, 0(x0)
lw   x10, 0(x0)
sw   x8, 12(x0)
lw   x11, 12(x0)
ecall
