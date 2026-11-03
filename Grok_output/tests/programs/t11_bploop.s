# Vong lap long nhau: BTB+BHT 2-bit du doan dung nhanh lap -> it flush
li s0,0
li t0,0
li t2,20
outer:
li t1,0
li t3,6
inner:
add s0,s0,t1
addi t1,t1,1
blt t1,t3,inner
addi t0,t0,1
bne t0,t2,outer
mv a0,s0
ecall
