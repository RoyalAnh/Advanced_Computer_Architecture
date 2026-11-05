#!/usr/bin/env python3
"""Chay 9 chuong trinh test tren ban Verilog viet tay (iverilog) va so voi mo hinh vang trong run_tests.py.
Dung: python run_verilog_tests.py [--root <thu muc chua run_tests.py, asm.py va tests/>]"""
import sys,os,re,glob,subprocess,argparse,tempfile,shutil
HERE=os.path.dirname(os.path.abspath(__file__))
ap=argparse.ArgumentParser(); ap.add_argument('--root',default=os.path.abspath(os.path.join(HERE,'..','..')))
ap.add_argument('--tests',default=None,help='thu muc chua *.s (mac dinh <root>/artifacts/tests/programs hoac <root>/tests)')
g=ap.parse_args()
sys.path.insert(0,g.root); import asm, run_tests
td=g.tests or next(d for d in (os.path.join(g.root,'artifacts','tests','programs'),os.path.join(g.root,'tests')) if glob.glob(os.path.join(d,'*.s')))
iv=shutil.which('iverilog'); assert iv,'can iverilog trong PATH'
tmp=tempfile.mkdtemp()
for k,d in (('single',[]),('pipeline',['-DPIPE'])):
    subprocess.run(['iverilog','-g2012',*d,'-o',os.path.join(tmp,k+'.vvp'),os.path.join(HERE,'tb.v'),os.path.join(HERE,f'rv32i_{k}.v')],check=True,cwd=HERE)
tot=ok=0
for t in sorted(glob.glob(os.path.join(td,'*.s'))):
    words,_,_=asm.assemble(open(t,encoding='utf-8').read())
    hx=os.path.join(tmp,'p.hex'); open(hx,'w').write('\n'.join(f'{w:08x}' for w in words)+'\n')
    gx,gmem,_,gn=run_tests.golden(words)
    for k in ('single','pipeline'):
        o=subprocess.run(['vvp','-n',os.path.join(tmp,k+'.vvp'),'+hex='+hx],capture_output=True,text=True).stdout
        x={int(a):int(b,16) for a,b in re.findall(r'^x(\d+) ([0-9a-f]+)$',o,re.M)}
        m={int(a):int(b,16) for a,b in re.findall(r'^m(\d+) ([0-9a-f]+)$',o,re.M)}
        h=re.search(r'HALT (\d) cycles=(\d+)',o)
        errs=[f'x{r}={x.get(r,0):#x} != {gx[r]:#x}' for r in range(1,32) if x.get(r,0)!=gx[r]]
        errs+=[f'mem[{a*4}]' for a in set(m)|set(gmem) if m.get(a,0)!=gmem.get(a,0)]
        if not h or h.group(1)!='1': errs.append('khong halt')
        tot+=1; ok+=not errs
        print(f"[{'PASS' if not errs else 'FAIL'}] {os.path.basename(t):16s} {k:9s} lenh={gn:4d} chu_ky={h.group(2) if h else '?':>4s}"+('' if not errs else ' '+'; '.join(errs[:5])))
print(f'Tong: {ok}/{tot} PASS')
