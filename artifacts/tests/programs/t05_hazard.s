# hazard: RAW lien tiep (forward EX/MEM, MEM/WB), load-use, store sau load, flush
addi x1, x0, 3
addi x2, x1, 4        # forward EX->EX : 7
add  x3, x1, x2       # forward ca 2: 10
add  x4, x3, x3       # 20
sub  x5, x4, x1       # MEM/WB forward: 17
sw   x5, 0(x0)
lw   x6, 0(x0)
add  x7, x6, x6       # load-use stall: 34
lw   x8, 0(x0)
sw   x8, 4(x0)        # load -> store
lw   x9, 4(x0)
beq  x9, x5, t1       # load-use + branch
addi x10, x0, 1       # bi flush
t1:
addi x11, x0, 2
jal  x12, t2
addi x13, x0, 1       # bi flush
addi x13, x0, 1       # bi flush
t2:
addi x0, x0, 5        # ghi x0 khong duoc forward
add  x14, x0, x11     # 2
addi x15, x0, 1
addi x15, x15, 1
addi x15, x15, 1      # 3 (chuoi phu thuoc)
lw   x16, 4(x0)
lw   x17, 4(x0)
add  x18, x16, x17    # 34
ecall
