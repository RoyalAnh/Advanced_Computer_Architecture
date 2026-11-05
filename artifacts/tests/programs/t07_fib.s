# chuong trinh tong hop: Fibonacci 12 so vao bo nho, roi doc lai tong
addi x1, x0, 0
addi x2, x0, 1
addi x3, x0, 0      # dia chi
addi x4, x0, 12
fib:
sw   x1, 0(x3)
add  x5, x1, x2
addi x1, x2, 0
addi x2, x5, 0
addi x3, x3, 4
addi x4, x4, -1
bne  x4, x0, fib
addi x6, x0, 0
addi x3, x0, 0
addi x4, x0, 12
sum:
lw   x7, 0(x3)
add  x6, x6, x7
addi x3, x3, 4
addi x4, x4, -1
bnez x4, sum        # x6 = 232
ecall
