# byte/halfword: SB SH LB LH LBU LHU + cac offset khong chia het 4
li   x1, 0x87654321
sw   x1, 0(x0)
lb   x2, 0(x0)        # 0x21
lb   x3, 3(x0)        # 0x87 -> sign: 0xffffff87
lbu  x4, 3(x0)        # 0x87
lh   x5, 2(x0)        # 0x8765 -> 0xffff8765
lhu  x6, 2(x0)        # 0x8765
lh   x7, 0(x0)        # 0x4321
lbu  x8, 1(x0)        # 0x43
li   x9, 0xAABBCCDD
sb   x9, 5(x0)        # mem[4] = 0x0000DD00
sh   x9, 10(x0)       # mem[8] = 0xCCDD0000
sb   x9, 12(x0)
sb   x1, 13(x0)       # mem[12]=0x000021DD
sh   x1, 14(x0)       # mem[12]=0x432121DD
lw   x10, 4(x0)
lw   x11, 8(x0)
lw   x12, 12(x0)
addi x13, x0, 16
sb   x9, 1(x13)       # base+offset: mem[16]=0x0000DD00
lb   x14, 1(x13)      # load-use voi byte (sign): 0xffffffdd
add  x15, x14, x14
sh   x15, 2(x13)      # mem[16]=0xFFBADD00
lhu  x16, 2(x13)
lw   x17, 16(x0)
sw   x0, 0(x0)
sb   x3, 0(x0)        # chi ghi 1 byte
lw   x18, 0(x0)       # 0x00000087
ecall
