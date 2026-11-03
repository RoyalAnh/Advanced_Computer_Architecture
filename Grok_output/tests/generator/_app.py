# ---------------- custom appearance ----------------
def strip(n):
    for p in('d_','e_','m_','w_','f_'):
        if n.startswith(p): n=n[2:]; break
    return n[:-2] if n.endswith('_q') else n
def make_app(name,pins,align=False):
    """pins: list (label,dir,width). Tra ve ports{label:(dx,dy,w)}, box, ham sinh <appear>"""
    ins=[p for p in pins if p[1]=='in' and p[0]!='clk']+[p for p in pins if p[1]=='in' and p[0]=='clk']
    outs=[p for p in pins if p[1]=='out']
    rows={}
    if align:
        keys=[]
        for p in outs:
            k=strip(p[0])
            if k not in keys: keys.append(k)
        rowof={k:i for i,k in enumerate(keys)}
        for p in outs: rows[p[0]]=rowof[strip(p[0])]
        nxt=len(keys); used=set()
        for p in ins:
            k=strip(p[0]); r=rowof.get(k)
            if p[0]!='clk' and r is not None and r not in used: rows[p[0]]=r; used.add(r)
            else:
                while nxt in used: nxt+=1
                rows[p[0]]=nxt; used.add(nxt); nxt+=1
    else:
        for i,p in enumerate(ins): rows[p[0]]=i
        for i,p in enumerate(outs): rows[p[0]]=i
    n=max(rows.values())+1
    lw=max([len(p[0]) for p in ins]+[0]); rw=max([len(p[0]) for p in outs]+[0])
    W=max(80,int((lw+rw)*6.6+30)+(10 if align else 0), int(len(name)*8+20)); W=(W+9)//10*10
    H=30+20*n
    ports={p[0]:((0 if p[1]=='in' else W),30+20*rows[p[0]],p[2]) for p in pins}
    def appear(items):
        loc={it['c'][1]['label']:it['loc'] for it in items if it['c'][0]=='Pin'}
        X,Y=50,50
        o=['<appear>',f'<rect fill="#f4f8ff" height="{H}" stroke="#000000" stroke-width="2" width="{W}" x="{X}" y="{Y}"/>',
           f'<text dominant-baseline="central" font-family="SansSerif" font-size="12" font-weight="bold" text-anchor="middle" x="{X+W//2}" y="{Y+12}">{name}</text>']
        for p in pins:
            dx,dy,w=ports[p[0]]; px,py=loc[p[0]]
            if p[1]=='in':
                o.append(f'<text dominant-baseline="central" font-family="SansSerif" font-size="10" text-anchor="start" x="{X+dx+5}" y="{Y+dy}">{p[0]}</text>')
                o.append(f'<circ-port dir="in" pin="{px},{py}" x="{X+dx}" y="{Y+dy}"/>')
            else:
                o.append(f'<text dominant-baseline="central" font-family="SansSerif" font-size="10" text-anchor="end" x="{X+dx-5}" y="{Y+dy}">{p[0]}</text>')
                o.append(f'<circ-port dir="out" pin="{px},{py}" x="{X+dx}" y="{Y+dy}"/>')
        o.append(f'<circ-anchor facing="east" x="{X}" y="{Y}"/>')
        o.append('</appear>'); return '\n'.join(o)
    return ports,(0,0,W,H),appear
def pins_of(circ):
    return [(a['label'],'in' if a['type']=='input' else 'out',a['width']) for k,a,*_ in circ.comps if k=='Pin']
def prep(circ,align=False):
    for comp in circ.comps:
        if comp[0]=='Pin':
            a=comp[1]
            if a['width']>1: a['radix']='16'
            a['labelloc']='north'
    ports,box,app=make_app(circ.name,pins_of(circ),align)
    layout.SUBPORTS[circ.name]=ports; layout.SUBBOX[circ.name]=box; lg.SUBPORTS[circ.name]=ports
    return app
