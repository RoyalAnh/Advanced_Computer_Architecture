import re,sys
R=lambda s:int(s.strip().lstrip('x'))
def enc(op,a):
  if op in('add','sub','and','or','xor','slt','sltu','sll','srl','sra'):
    f3={'add':0,'sub':0,'sll':1,'slt':2,'sltu':3,'xor':4,'srl':5,'sra':5,'or':6,'and':7}[op]
    f7=0x20 if op in('sub','sra') else 0
    rd,rs1,rs2=map(R,a); return f7<<25|rs2<<20|rs1<<15|f3<<12|rd<<7|0x33
  if op in('addi','andi','ori','xori','slti','sltiu','slli','srli','srai'):
    f3={'addi':0,'slli':1,'slti':2,'sltiu':3,'xori':4,'srli':5,'srai':5,'ori':6,'andi':7}[op]
    rd,rs1=R(a[0]),R(a[1]);im=int(a[2],0)&0xfff
    if op=='srai': im|=0x400
    return im<<20|rs1<<15|f3<<12|rd<<7|0x13
  if op=='lw':
    rd=R(a[0]);m=re.match(r'(-?\w+)\((\w+)\)',a[1]);im=int(m[1],0)&0xfff
    return im<<20|R(m[2])<<15|2<<12|rd<<7|0x03
  if op=='sw':
    rs2=R(a[0]);m=re.match(r'(-?\w+)\((\w+)\)',a[1]);im=int(m[1],0)&0xfff;rs1=R(m[2])
    return (im>>5)<<25|rs2<<20|rs1<<15|2<<12|(im&31)<<7|0x23
  if op in('beq','bne'):
    rs1,rs2=R(a[0]),R(a[1]);im=int(a[2],0)&0x1fff;f3=0 if op=='beq' else 1
    return ((im>>12)&1)<<31|((im>>5)&63)<<25|rs2<<20|rs1<<15|f3<<12|((im>>1)&15)<<8|((im>>11)&1)<<7|0x63
  if op=='jal':
    rd=R(a[0]);im=int(a[1],0)&0x1fffff
    return ((im>>20)&1)<<31|((im>>1)&0x3ff)<<21|((im>>11)&1)<<20|((im>>12)&0xff)<<12|rd<<7|0x6f
  raise Exception(op)
out=[]
for l in open(sys.argv[1]):
  l=l.split('#')[0].strip()
  if not l: continue
  op,_,rest=l.partition(' ');out.append(enc(op,[x.strip() for x in rest.split(',')]))
print('addr/data: 8 32\n'+' '.join('%x'%w for w in out))
