addi x1, x0, 5      # 0x00
addi x2, x0, 3      # 0x04
add  x3, x1, x2     # 8
sub  x4, x1, x2     # 2
and  x5, x1, x2     # 1
or   x6, x1, x2     # 7
xor  x7, x1, x2     # 6
slt  x8, x2, x1     # 1
sll  x9, x1, x2     # 40
addi x10, x0, -8    # 0xfffffff8
sra  x11, x10, x2   # 0xffffffff
srl  x12, x10, x2   # 0x1fffffff
sw x3, 0(x0)
sw x4, 4(x0)
sw x5, 8(x0)
sw x6, 12(x0)
sw x7, 16(x0)
sw x8, 20(x0)
sw x9, 24(x0)
sw x10, 28(x0)
sw x11, 32(x0)
sw x12, 36(x0)
lw x13, 0(x0)
addi x13, x13, 1    # 9
sw x13, 40(x0)
addi x14, x14, 1    # loop
bne x14, x1, -4
sw x14, 44(x0)      # 5
jal x15, 8
addi x16, x0, 99    # should be skipped
sw x15, 48(x0)      # return addr = 0x74
sw x16, 52(x0)      # 0
slti x17, x10, 0    # 1
xori x18, x1, 0xff  # 0xfa
slli x19, x1, 4     # 0x50
srai x20, x10, 1    # 0xfffffffc
sw x17, 56(x0)
sw x18, 60(x0)
sw x19, 64(x0)
sw x20, 68(x0)
