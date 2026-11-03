"""Xuat VHDL/Verilog tu mach Logisim (khong sua file goc): chen boardmap TERASIC_DE0 map moi output pin cua main sang 'open'."""
import re,sys,shutil,subprocess,os
src,dst=sys.argv[1],sys.argv[2]
x=open(src,encoding='utf-8').read()
main=x.split('<circuit name="main">')[1].split('</circuit>')[0]
labs=re.findall(r'name="Pin">(?:(?!</comp>).)*?<a name="label" val="([^"]+)"',main,re.S)
bm='<boardmap boardname="TERASIC_DE0">'+''.join(f'<mc key="/{l}" open="open"/>' for l in labs)+'</boardmap>\n'
i=x.index('<circuit name="main">'); j=x.index('</circuit>',i)
x=x[:j]+bm+x[j:]
open(dst,'w',encoding='utf-8').write(x)
print(len(labs),'pins mapped')
