import sys,re
s=open('../RiscVComputer_T5.circ').read()
rom=open(sys.argv[1]).read().strip()
s=re.sub(r'(<a name="contents">)addr/data: 8 32\n[^<]*(</a>)',lambda m:m[1]+rom+'\n'+m[2],s,count=1)
bits=''.join('<a name="bit%d" val="%d"/>'%(i,1 if i==8 else (0 if i<8 else 2)) for i in range(32))
j=s.index('</circuit>')
add=f'''<comp lib="0" loc="(3000,100)" name="Tunnel"><a name="facing" val="east"/><a name="label" val="PC"/><a name="width" val="32"/></comp>
<comp lib="0" loc="(3000,100)" name="Pin"><a name="facing" val="west"/><a name="type" val="output"/><a name="label" val="PC_out"/><a name="width" val="32"/></comp>
<comp lib="0" loc="(3000,400)" name="Tunnel"><a name="facing" val="east"/><a name="label" val="PC"/><a name="width" val="32"/></comp>
<comp lib="0" loc="(3000,400)" name="Splitter"><a name="fanout" val="3"/><a name="incoming" val="32"/>{bits}</comp>
<comp lib="0" loc="(3020,390)" name="Pin"><a name="facing" val="west"/><a name="type" val="output"/><a name="label" val="halt"/></comp>
'''
open(sys.argv[2],'w').write(s[:j]+add+s[j:])
