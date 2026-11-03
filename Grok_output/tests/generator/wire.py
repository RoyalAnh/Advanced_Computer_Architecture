"""Chia netlist phang thanh cac subcircuit theo tang (group) va ve mach main bang DAY THAT (wire)
theo kieu 'bus channel': moi khoi xep theo cot, moi net co 1 lane ngang rieng ben duoi."""
import lg, html
from lg import Circ, _cache, akey, LIB, SUBPORTS, SUBDIR

def ports_of(comp):
    kind,attrs,ports,loc,grp=comp[:5]; drv=comp[5] if len(comp)>5 else None
    res=[]
    if kind in LIB:
        ends=_cache[akey(kind,attrs)]
        for i,net in enumerate(ports):
            if net is None: continue
            e=ends[i]
            if drv is not None: d='out' if net in drv else 'in'
            else: d='out' if e[3]==2 else 'in'
            res.append((e[0],e[1],e[2],net,d))
    else:
        sp=SUBPORTS[kind]
        for lab,net in ports.items():
            if net is None: continue
            res.append((sp[lab][0],sp[lab][1],sp[lab][2],net,SUBDIR[kind][lab]))
    return res

def partition(c, groups):
    """c: Circ phang (moi comp co grp). groups: list ten group (khac 'top').
    Tra ve (top_comps, [Circ group...]) ; top_comps gom comp grp=='top' + instance cua group."""
    lg.query([akey(k,a) for k,a,*_ in c.comps if k in LIB])
    uses={}; drv={}; width={}; cdrv={}
    for comp in c.comps:
        for dx,dy,w,net,d in ports_of(comp):
            uses.setdefault(net,set()).add(comp[4]); width[net]=w
            if d=='out':
                drv[net]=comp[4]
                if comp[0]=='Constant': cdrv[net]=comp
    subs=[]; top=[x for x in c.comps if x[4]=='top']
    def dupconst(g,target):
        for net,cc in cdrv.items():
            if g in uses[net] and cc[4]!=g: target.append([cc[0],dict(cc[1]),list(cc[2]),None,g])
    dupconst('top',top)
    for g in groups:
        G=Circ(g); G.grp=g
        bnd_in=sorted(n for n in uses if g in uses[n] and n not in cdrv and drv.get(n)!=g)
        bnd_out=sorted(n for n in uses if drv.get(n)==g and n not in cdrv and len(uses[n])>1)
        for n in bnd_in: G.pin_in(n,width[n])
        for n in bnd_out: G.pin_out(n,width[n])
        for comp in c.comps:
            if comp[4]==g: G.add(comp[0],comp[1],comp[2]); 
            if comp[4]==g and len(comp)>5: G.comps[-1].append(comp[5])
        cs=[]; dupconst(g,cs)
        for cc in cs: G.add(cc[0],cc[1],cc[2])
        subs.append(G)
        top.append([g,{'label':'u_'+g},{n:n for n in bnd_in+bnd_out},None,'top'])
    return top,subs

def emit_wired(name, columns, consts_local=True, text=None):
    """columns: list of list of comps (top-level). Tra ve XML circuit voi day that."""
    lg.query([akey(k,a) for col in columns for k,a,*_ in col if k in LIB])
    out=[f'<circuit name="{name}">',f'<a name="circuit" val="{name}"/>']
    wires=set()
    def W(x1,y1,x2,y2):
        if (x1,y1)==(x2,y2): return
        if (x1,y1)>(x2,y2): x1,y1,x2,y2=x2,y2,x1,y1
        wires.add((x1,y1,x2,y2))
    # constant dat truc tiep len chan (khong can day)
    allcomps=[c for col in columns for c in col]
    cnets={c[2][0]:c for c in allcomps if c[0]=='Constant'}
    columns=[[c for c in col if c[0]!='Constant'] for col in columns]
    # kich thuoc cot
    info=[]
    for col in columns:
        items=[]
        for comp in col:
            ps=ports_of(comp); xs=[p[0] for p in ps]; ys=[p[1] for p in ps]
            items.append((comp,ps,min(xs),max(xs),min(ys),max(ys)))
        info.append(items)
    def side(it,p):
        comp,ps,x0,x1=it[:4]
        if x0==x1:  # 1 chan: pin/clock
            return 'W' if (comp[0]=='Pin' and comp[1].get('type')=='output') else 'E'
        return 'W' if p[0]==x0 else 'E'
    # dem chan moi phia
    netcount={}
    for items in info:
        for it in items:
            for p in it[1]: netcount[p[3]]=netcount.get(p[3],0)+1
    routed=lambda n: netcount.get(n,0)>=2 and n not in cnets
    x=100; place=[]; ymax=0
    nE_prev=0
    for ci,items in enumerate(info):
        nW=sum(1 for it in items for p in it[1] if side(it,p)=='W' and routed(p[3]))
        x+=10*(nE_prev+nW)+60 if ci else 0
        y=100; wmax=0; pl=[]
        for it in items:
            comp,ps,x0,x1,y0,y1=it
            body_w=(x1-x0) or (110 if comp[0]=='Pin' else 30)
            ax=x-x0 if not(x0==x1 and side(it,ps[0])=='E') else x+body_w
            ay=y-y0
            pl.append((comp,ps,ax,ay,it)); 
            h=(y1-y0)+(80 if comp[0]=='Pin' else 60)
            y+=h; wmax=max(wmax,body_w)
        ymax=max(ymax,y); place.append((x,wmax,pl))
        x+=wmax
        nE_prev=sum(1 for it in items for p in it[1] if side(it,p)=='E' and routed(p[3]))
    # gan cot stub
    pts={}  # net -> list (x,y) diem tren lane
    lane_y0=ymax+100
    for ci,(cx,wmax,pl) in enumerate(place):
        E_=[];W_=[]
        for comp,ps,ax,ay,it in pl:
            for p in ps:
                px,py=ax+p[0],ay+p[1]
                if p[3] in cnets and consts_local:
                    cc=cnets[p[3]]; out.append(comp_xml(cc[0],cc[1],px,py)); continue
                if not routed(p[3]): continue
                (W_ if side(it,p)=='W' else E_).append((py,px,p[3]))
        # E: cang thap (py lon) cang gan; W: tuong tu
        for k,(py,px,n) in enumerate(sorted(E_,reverse=True)):
            sx=cx+wmax+10*(k+1); W(px,py,sx,py); pts.setdefault(n,[]).append((sx,py))
        for k,(py,px,n) in enumerate(sorted(W_,reverse=True)):
            sx=cx-10*(k+1); W(sx,py,px,py); pts.setdefault(n,[]).append((sx,py))
    # lane
    nets=sorted(pts,key=lambda n:min(p[0] for p in pts[n]))
    for i,n in enumerate(nets):
        ly=lane_y0+20*i
        xs=sorted(set(p[0] for p in pts[n]))
        for sx,py in pts[n]: W(sx,py,sx,ly)
        for a,b in zip(xs,xs[1:]): W(a,ly,b,ly)
        out.append(f'<comp lib="9" loc="({xs[0]-10-4*len(n)},{ly+5})" name="Text"><a name="text" val="{html.escape(n)}"/></comp>')
    for comp,ps,ax,ay,it in [q for _,_,pl in place for q in pl]:
        out.append(comp_xml(comp[0],comp[1],ax,ay))
    for (x1,y1,x2,y2) in sorted(wires): out.append(f'<wire from="({x1},{y1})" to="({x2},{y2})"/>')
    for (tx,ty,t) in (text or []): out.append(f'<comp lib="9" loc="({tx},{ty})" name="Text"><a name="text" val="{html.escape(t)}"/></comp>')
    out.append('</circuit>')
    return '\n'.join(out)

def comp_xml(kind,attrs,x,y):
    lib=f' lib="{LIB[kind]}"' if kind in LIB else ''
    return f'<comp{lib} loc="({x},{y})" name="{kind}">'+''.join(f'<a name="{k}" val="{html.escape(str(v))}"/>' if k!='contents' else f'<a name="contents">{html.escape(v)}</a>' for k,v in attrs.items())+'</comp>'
