def build(kind,prog,out,render=None):
    layout.SUBPORTS=lg.SUBPORTS
    mods=[f() for f in (MODS_SINGLE if kind=='single' else MODS_PIPE)]
    apps={m.name:prep(m) for m in mods}
    main=(single if kind=='single' else pipeline)(prog)
    for comp in main.comps:
        if comp[0] in('Pin','Clock','ROM','RAM','TTY'): comp[4]='top'
    top,subs=wire.partition(main,GROUPS[kind])
    for g in subs: apps[g.name]=prep(g,g.name in PIPEREGS)
    for t in top:
        if t[0] in [g.name for g in subs]: t[1]={}
        if t[0]=='Pin': t[1]['labelloc']='north'
    xs=[]; stats={}
    for c in mods+subs:
        x,_,st=layout.emit(c.name,c.comps,appear=apps[c.name]); xs.append(x); stats[c.name]=st
    x,_,st=layout.emit('main',top,columns=COLS[kind],titles=TITLES[kind]); stats['main']=st
    xml=lg.project([]).replace('\n\n</project>','\n</project>')
    body='\n'.join([x]+xs)
    xml=xml.replace('</options>\n','</options>\n'+body+'\n',1)
    open(out,'w').write(xml)
    return stats
if __name__=='__main__':
    if len(sys.argv)>3:
        ws=[w for w in open(sys.argv[3]).read().split()[4:]]
        prog='addr/data: 10 32\n'+' '.join(w.lstrip('0') or '0' for w in ws)+'\n'
    else: prog='addr/data: 10 32\n73\n'
    print(build(sys.argv[1],prog,sys.argv[2]))
