"""Bo tri (layout) gon gang cho mach Logisim: cot theo luong du lieu, day ngan giua 2 cot ke nhau,
Tunnel co ten cho tin hieu xa / nguoc / dieu khien. Dung cho ca main lan cac subcircuit."""
import json, os, subprocess, html, math
import lg
from lg import LIB
G2='/workspace/btl/p4/geom.json'
_g=json.load(open(G2)) if os.path.exists(G2) else {}
def gkey(kind,attrs): return kind+'|'+';'.join(f'{k}={v}' for k,v in attrs.items() if k not in('label','contents','value','text','labelloc'))
def geom_query(pairs):
    need=sorted({gkey(k,a) for k,a in pairs if k in LIB and gkey(k,a) not in _g})
    if need:
        out=subprocess.run([lg.JAVA,'-Djava.awt.headless=true','-cp','/workspace/btl/logisim.jar:/workspace/btl/p4','PortQuery2'],input='\n'.join(need)+'\n',capture_output=True,text=True).stdout
        lines=[l for l in out.splitlines() if not l.startswith('[')]
        assert len(lines)==len(need),(out[-2000:],need)
        for k,l in zip(need,lines):
            assert not l.startswith(('ERR','BADVAL','OPTIONS')),(k,l)
            e,b=l.split('|')
            _g[k]=([tuple(map(int,p.split(','))) for p in e.split()],tuple(map(int,b.split(','))))
        json.dump(_g,open(G2,'w'))
SUBPORTS={}; SUBBOX={}; SUBDIR=lg.SUBDIR
TFONT='SansSerif plain 11'
def tlen(label): return int(math.ceil((len(label)*6+10)/10)*10)
def comp_ports(comp):
    kind,attrs,ports=comp[0],comp[1],comp[2]; drv=comp[5] if len(comp)>5 else None
    res=[]
    if kind in LIB:
        ends,b=_g[gkey(kind,attrs)]
        for i,net in enumerate(ports):
            if net is None: continue
            e=ends[i]
            if e[2]==0: continue
            d=('out' if net in drv else 'in') if drv is not None else ('out' if e[3]==2 else 'in')
            res.append([e[0],e[1],e[2],net,d])
        box=b
    else:
        sp=SUBPORTS[kind]
        for lab,net in ports.items():
            if net is None: continue
            res.append([sp[lab][0],sp[lab][1],sp[lab][2],net,SUBDIR[kind][lab]])
        box=SUBBOX[kind]
    bx,by,bw,bh=box
    for p in res:
        x,y=p[0],p[1]
        dl,dr,dt,db=abs(x-bx),abs(bx+bw-x),abs(y-by),abs(by+bh-y)
        m=min(dl,dr,dt,db)
        p.append('W' if m==dl else 'E' if m==dr else 'N' if m==dt else 'S')
    return res,box
def ckey(comp):
    kind,attrs=comp[0],comp[1]
    if kind=='Pin': return attrs['label']
    if kind not in LIB: return attrs.get('label','u_'+kind)[2:] if attrs.get('label','').startswith('u_') else kind
    if kind=='Clock': return 'Clock'
    ps,_=comp_ports(comp)
    outs=[p[3] for p in ps if p[4]=='out']
    return outs[0] if outs else attrs.get('label',kind+str(id(comp)))
def xmlcomp(kind,attrs,x,y):
    lib=f' lib="{LIB[kind]}"' if kind in LIB else ''
    return f'<comp{lib} loc="({x},{y})" name="{kind}">'+''.join(f'<a name="{k}" val="{html.escape(str(v))}"/>' if k!='contents' else f'<a name="contents">{html.escape(v)}</a>' for k,v in attrs.items())+'</comp>'
FACE={'E':'west','W':'east','S':'north','N':'south'}
CFACE={'W':'east','E':'west','S':'north','N':'south'}
def emit(name,comps,columns=None,titles=None,force_tunnel=(),appear=None,maxtries=60):
    geom_query([(c[0],c[1]) for c in comps]+[('Constant',{'width':c[1]['width'],'facing':f}) for c in comps if c[0]=='Constant' for f in ('east','north','south','west')])
    consts=[c for c in comps if c[0]=='Constant']
    cnet={c[2][0]:c for c in consts}
    items=[]
    for c in comps:
        if c[0]=='Constant': continue
        ps,box=comp_ports(c); items.append(dict(c=c,ps=ps,box=box,key=ckey(c)))
    ends={}
    for i,it in enumerate(items):
        for p in it['ps']:
            if p[3] in cnet: continue
            ends.setdefault(p[3],[]).append((i,p))
    nets={n:e for n,e in ends.items() if len(e)>=2}
    # ---- cot
    if columns:
        bykey={}
        for i,it in enumerate(items): bykey.setdefault(it['key'],[]).append(i)
        cols=[]
        for spec in columns:
            col=[]
            for k in spec: col+=bykey.pop(k,[])
            cols.append(col)
        left=[k for k,v in bykey.items() if v]
        assert not left,(name,'chua xep cot:',left)
    else:
        drvof={}
        for i,it in enumerate(items):
            for p in it['ps']:
                if p[4]=='out': drvof[p[3]]=i
        lvl={}; st=set()
        def L(i):
            if i in lvl: return lvl[i]
            it=items[i]
            if it['c'][0]=='Pin' and it['c'][1].get('type')=='input': lvl[i]=0; return 0
            if i in st: return 0
            st.add(i); v=1
            for p in it['ps']:
                if p[4]=='in' and p[3] in drvof and p[3] not in cnet: v=max(v,L(drvof[p[3]])+1)
            st.discard(i); lvl[i]=v; return v
        for i in range(len(items)): L(i)
        mx=max([v for i,v in lvl.items() if not (items[i]['c'][0]=='Pin')]+[0])+1
        for i,it in enumerate(items):
            if it['c'][0]=='Pin' and it['c'][1].get('type')=='output': lvl[i]=mx
        cols=[[i for i in range(len(items)) if lvl[i]==k] for k in range(mx+1)]
        cols=[c for c in cols if c]
    colof={i:ci for ci,col in enumerate(cols) for i in col}
    forced=set(force_tunnel)
    for attempt in range(maxtries):
        # ---- quyet dinh direct/tunnel
        direct={}
        for n,e in nets.items():
            if n in forced or n=='clk': continue
            drv=[(i,p) for i,p in e if p[4]=='out']; snk=[(i,p) for i,p in e if p[4]!='out']
            if len(drv)!=1 or not snk or len(snk)>4: continue
            di,dp=drv[0]
            if dp[5]!='E': continue
            if all(colof[i]==colof[di]+1 and p[5]=='W' for i,p in snk): direct[n]=colof[di]
        # ---- tunnel/const stagger per item side
        def stag(it):
            res={}  # port idx -> (offset,len,kind)
            for side in 'EWNS':
                ps=[(k,p) for k,p in enumerate(it['ps']) if p[5]==side and (p[3] in cnet or (p[3] in nets and p[3] not in direct))]
                horiz=side in 'EW'
                ps.sort(key=lambda kp: kp[1][1] if horiz else kp[1][0])
                placed=[]
                for k,p in ps:
                    if p[3] in cnet:
                        cc=cnet[p[3]]; _,cb=_g[gkey('Constant',{'width':cc[1]['width'],'facing':'east'})]
                        ln=cb[2]+4; fixed=False
                    else: ln=tlen(p[3]) if horiz else tlen(p[3]); fixed=False
                    pos=p[1] if horiz else p[0]
                    off=0
                    while True:
                        ok=all(not(abs(pos-q)<(20 if horiz else 20) and not(off>=o2+l2+6 or off+ln+6<=o2)) for q,o2,l2 in placed)
                        if ok or fixed: break
                        off+=10
                    off=int(math.ceil(off/10)*10)
                    placed.append((pos,off,ln)); res[k]=(off,ln)
            return res
        for it in items: it['st']=stag(it)
        def zone(it,side): return max([o+l for k,(o,l) in it['st'].items() if it['ps'][k][5]==side]+[0])
        # ---- dat vi tri
        ncols=len(cols)
        chan=[0]*ncols
        for n,ci in direct.items(): chan[ci]+=1
        colw=[max([items[i]['box'][2] for i in col]+[0]) for col in cols]
        R=[max([zone(items[i],'E')+items[i]['box'][2] for i in col]+[0]) for ci,col in enumerate(cols)]
        Wz=[max([zone(items[i],'W') for i in col]+[0]) for col in cols]
        colx=[]; x=60
        for ci in range(ncols):
            x+=Wz[ci]; x=int(math.ceil(x/10)*10); colx.append(x)
            x+=R[ci]
            x+= (20+10*chan[ci]+20) if chan[ci] else 30
        # Ez da gom phan hut cua item hep; cot ke tiep bat dau sau kenh
        for ci,col in enumerate(cols):
            y=80 if titles else 40
            for i in col:
                it=items[i]; bx,by,bw,bh=it['box']
                top=y+zone(it,'N')+(20 if it['c'][0]=='Pin' else 0)
                it['loc']=(colx[ci]-bx, int(math.ceil((top-by)/10)*10))
                y=it['loc'][1]+by+bh+zone(it,'S')+30
        # ---- sinh day / tunnel
        wires=[]; tun=[]; cpl=[]; pts=[]
        def W_(a,b,n):
            if a!=b: wires.append((a,b,n))
        for i,it in enumerate(items):
            lx,ly=it['loc']
            for k,p in enumerate(it['ps']):
                px,py=lx+p[0],ly+p[1]; pts.append((px,py,p[3]))
                if k not in it['st']: continue
                off,ln=it['st'][k]; s=p[5]
                dx,dy={'E':(1,0),'W':(-1,0),'N':(0,-1),'S':(0,1)}[s]
                tx,ty=px+dx*off,py+dy*off
                W_((px,py),(tx,ty),p[3])
                if p[3] in cnet:
                    cc=cnet[p[3]]; a=dict(cc[1]); a['facing']=CFACE[s]; cpl.append(xmlcomp('Constant',a,tx,ty)); pts.append((tx,ty,p[3]))
                else:
                    tun.append((tx,ty,p[3],p[2],FACE[s])); pts.append((tx,ty,p[3]))
        # direct
        bycol={}
        for n,ci in direct.items(): bycol.setdefault(ci,[]).append(n)
        for ci,ns in bycol.items():
            x0=colx[ci]+R[ci]+20
            def sy(n):
                (di,dp),=[(i,p) for i,p in nets[n] if p[4]=='out']; return items[di]['loc'][1]+dp[1]
            def ty_(n): return min(items[i]['loc'][1]+p[1] for i,p in nets[n] if p[4]!='out')
            ns.sort(key=lambda n:(ty_(n)>sy(n), sy(n) if ty_(n)>sy(n) else -sy(n)))
            for k,n in enumerate(ns):
                tx=x0+10*k
                ys=[]
                for i,p in nets[n]:
                    px,py=items[i]['loc'][0]+p[0],items[i]['loc'][1]+p[1]
                    W_((px,py),(tx,py),n); ys.append(py)
                ys=sorted(set(ys))
                for a,b in zip(ys,ys[1:]): W_((tx,a),(tx,b),n)
                if len(set(ys))==1: pass
        # ---- kiem tra xung dot
        bad=set()
        segs=[(min(a,b),max(a,b),n) for a,b,n in wires]
        allpts=pts+[(a[0],a[1],n) for a,b,n in wires]+[(b[0],b[1],n) for a,b,n in wires]
        def on(pt,s):
            (x1,y1),(x2,y2),_=s; x,y=pt
            if x1==x2: return x==x1 and y1<=y<=y2
            return y==y1 and x1<=x<=x2
        for s in segs:
            for x,y,n in allpts:
                if n!=s[2] and on((x,y),s): bad.add(s[2]); bad.add(n)
        for a in range(len(segs)):
            for b in range(a+1,len(segs)):
                s,t=segs[a],segs[b]
                if s[2]==t[2]: continue
                if s[0][0]==s[1][0]==t[0][0]==t[1][0] and not(s[1][1]<t[0][1] or t[1][1]<s[0][1]): bad|={s[2],t[2]}
                if s[0][1]==s[1][1]==t[0][1]==t[1][1] and not(s[1][0]<t[0][0] or t[1][0]<s[0][0]): bad|={s[2],t[2]}
        tl={}
        for tx,ty,n,w,f in tun: tl.setdefault((tx,ty),set()).add(n)
        for k,v in tl.items():
            if len(v)>1: raise RuntimeError((name,'tunnel trung vi tri',k,v))
        newf={n for n in bad if n in direct}
        if not bad: break
        if not newf:
            raise RuntimeError((name,'xung dot khong sua duoc',sorted(bad)[:20]))
        forced|=newf
    else: raise RuntimeError((name,'qua so lan thu'))
    out=[f'<circuit name="{name}">',f'<a name="circuit" val="{name}"/>']
    if appear: out.append(appear(items))
    for it in items: out.append(xmlcomp(it['c'][0],it['c'][1],*it['loc']))
    out+=cpl
    for tx,ty,n,w,f in tun: out.append(f'<comp lib="0" loc="({tx},{ty})" name="Tunnel"><a name="facing" val="{f}"/><a name="label" val="{html.escape(n)}"/><a name="width" val="{w}"/><a name="labelfont" val="{TFONT}"/></comp>')
    for a,b,n in sorted(set(wires)): out.append(f'<wire from="({a[0]},{a[1]})" to="({b[0]},{b[1]})"/>')
    if titles:
        for ci,t in titles.items():
            if ci < len(colx) and t: out.append(f'<comp lib="9" loc="({colx[ci]+colw[ci]//2},30)" name="Text"><a name="text" val="{html.escape(t)}"/><a name="font" val="SansSerif bold 16"/></comp>')
    out.append('</circuit>')
    stats=dict(direct=len(direct),tunnels=len(tun),wires=len(wires),forced=len(forced))
    return '\n'.join(out),items,stats
