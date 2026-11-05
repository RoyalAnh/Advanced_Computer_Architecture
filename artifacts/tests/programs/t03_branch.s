# beq/bne/blt/bge/bltu/bgeu + vong lap tinh tong 1..10
addi x1, x0, 0      # sum
addi x2, x0, 1      # i
addi x3, x0, 11
loop:
add  x1, x1, x2
addi x2, x2, 1
bne  x2, x3, loop   # sum=55
addi x4, x0, 0
beq  x1, x0, bad    # khong nhay
addi x5, x0, 55
beq  x1, x5, ok1    # nhay
addi x4, x4, 100    # bi bo qua
ok1:
addi x6, x0, -1
blt  x6, x0, ok2
addi x4, x4, 100
ok2:
bltu x6, x0, bad    # 0xFFFFFFFF < 0 sai
bge  x0, x6, ok3
addi x4, x4, 100
ok3:
bgeu x6, x0, ok4
addi x4, x4, 100
ok4:
bne  x0, x0, bad
addi x7, x0, 77
ecall
bad:
addi x4, x0, -99
ecall
