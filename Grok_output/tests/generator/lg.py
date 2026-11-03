# Mini netlist -> Logisim-evolution .circ generator (every port tied to a named Tunnel)
import subprocess, json, os, html
JAVA='/workspace/btl/jdk/bin/java'; CP='/workspace/btl/logisim.jar:/workspace/btl/p4'
LIB={'Pin':0,'Tunnel':0,'Constant':0,'Splitter':0,'Clock':0,'Bit Extender':0,
 'AND Gate':1,'OR Gate':1,'NOT Gate':1,'XOR Gate':1,'Multiplexer':2,'Decoder':2,
 'Adder':3,'Subtractor':3,'Comparator':3,'Shifter':3,'Register':5,'ROM':5,'RAM':5,'Multiplier':3,'Divider':3,
 'FPAdder':4,'FPSubtractor':4,'FPMultiplier':4,'FPDivider':4,'FPSquareRoot':4,'FPComparator':4,'FPMinMax':4,'FPToInt':4,'IntToFP':4,'TTY':6}
CACHE='/workspace/btl/p4/ports.json'
_cache=json.load(open(CACHE)) if os.path.exists(CACHE) else {}
def akey(kind,attrs): return kind+'|'+';'.join(f'{k}={v}' for k,v in attrs.items() if k not in('label','contents','value','facing_','text'))
def query(keys):
    need=[k for k in keys if k not in _cache]
    if need:
        out=subprocess.run([JAVA,'-Djava.awt.headless=true','-cp',CP,'PortQuery'],input='\n'.join(need)+'\n',capture_output=True,text=True).stdout
        lines=[l for l in out.splitlines() if not l.startswith('[') ]
        assert len(lines)==len(need),(out,need)
        for k,l in zip(need,lines):
            assert not l.startswith(('ERR','BADVAL','OPTIONS')),(k,l)
            _cache[k]=[tuple(int(x) if i<3 else int(x) for i,x in enumerate(p.split(','))) for p in l.split()]
        json.dump(_cache,open(CACHE,'w'))
SUBDIR={}  # circuit -> {label:'in'/'out'}
SUBPORTS={}  # circuit name -> {pinlabel:(dx,dy,width)}
class Circ:
    def __init__(s,name):
        s.name=name; s.comps=[]; s.n=0; s.widths={}; s.grp='top'
    def _pos(s):
        i=s.n; s.n+=1
        return (400+ (i%25)*500, 400+(i//25)*500)
    def add(s,kind,attrs=None,ports=(),loc=None):
        """ports: list of net names (or None) in end order"""
        attrs=dict(attrs or {}); loc=loc or s._pos()
        s.comps.append([kind,attrs,dict(ports) if isinstance(ports,dict) else list(ports),loc,s.grp]); return s
    def emit(s):
        query([akey(k,a) for k,a,p,l,*_ in s.comps if k in LIB])
        out=[f'<circuit name="{s.name}">','<a name="circuit" val="%s"/>'%s.name]
        for kind,attrs,ports,(x,y),*_ in s.comps:
            if kind in LIB:
                ends=_cache[akey(kind,attrs)]
                lib=f' lib="{LIB[kind]}"'
            else:
                sp=SUBPORTS[kind]; ends=None; lib=''
            out.append(f'<comp{lib} loc="({x},{y})" name="{kind}">'+''.join(f'<a name="{k}" val="{html.escape(str(v))}"/>' if k!='contents' else f'<a name="contents">{html.escape(v)}</a>' for k,v in attrs.items())+'</comp>')
            if ends is not None:
                assert len(ports)<=len(ends),(kind,attrs,ports,len(ends))
                pl=[(ends[i][0],ends[i][1],ends[i][2],net) for i,net in enumerate(ports)]
            else:
                pl=[(sp[lab][0],sp[lab][1],sp[lab][2],net) for lab,net in (ports.items() if isinstance(ports,dict) else [])]
            for dx,dy,w,net in pl:
                if net is None or w==0: continue
                pw=s.widths.setdefault(net,w)
                assert pw==w,(s.name,net,pw,w,kind,attrs)
                out.append(f'<comp lib="0" loc="({x+dx},{y+dy})" name="Tunnel"><a name="label" val="{net}"/><a name="width" val="{w}"/></comp>')
        out.append('</circuit>'); return '\n'.join(out)
    # helpers
    def const(s,net,val,w): return s.add('Constant',{'width':w,'value':hex(val&((1<<w)-1))},[net])
    def pin_in(s,net,w):
        SUBDIR.setdefault(s.name,{})[net]='in'; return s.add('Pin',{'width':w,'label':net,'type':'input','facing':'east'},[net])
    def pin_out(s,net,w,label=None):
        SUBDIR.setdefault(s.name,{})[label or net]='out'; return s.add('Pin',{'width':w,'label':label or net,'type':'output','facing':'west'},[net])
    def slice(s,src,w,lo,hi,dst):
        n=hi-lo+1
        if n==w: s.add('Splitter',{'incoming':w,'fanout':1,**{f'bit{i}':0 for i in range(w)}},[src,dst]); s.comps[-1].append({dst}); return s
        a={'incoming':w,'fanout':2}
        for i in range(w): a[f'bit{i}']=1 if lo<=i<=hi else 0
        s.add('Splitter',a,[src,None,dst]); s.comps[-1].append({dst}); return s
    def pack(s,dst,parts):
        """parts LSB-first: list of (net,width)"""
        w=sum(p[1] for p in parts); a={'incoming':w,'fanout':len(parts)}; b=0
        for gi,(n,pw) in enumerate(parts):
            for _ in range(pw): a[f'bit{b}']=gi; b+=1
        s.add('Splitter',a,[dst]+[p[0] for p in parts]); s.comps[-1].append({dst}); return s
    def mux(s,out,sel,ins,w):
        k=max(1,(len(ins)-1).bit_length()); ins=list(ins)+[None]*((1<<k)-len(ins))
        return s.add('Multiplexer',{'width':w,'select':k},ins+[sel,out])
    def gate(s,kind,out,ins,w=1):
        if kind=='NOT Gate': return s.add(kind,{'width':w},[out,ins[0]])
        return s.add(kind,{'width':w,'inputs':len(ins)},[out]+list(ins))
    def reg(s,q,d,clk,w,en=None,clr=None): return s.add('Register',{'width':w},[q,d,clk,clr,en])
    def ext(s,out,inp,iw,ow,t='zero'): return s.add('Bit Extender',{'in_width':iw,'out_width':ow,'type':t},[out,inp])
    def eq(s,out,a,b,w): return s.add('Comparator',{'width':w,'mode':'unsigned'},[a,b,None,out,None])
def project(circs,main='main'):
    libs='''<lib desc="#Wiring" name="0"/><lib desc="#Gates" name="1"/><lib desc="#Plexers" name="2"/><lib desc="#Arithmetic" name="3"/><lib desc="#FPArithmetic" name="4"/><lib desc="#Memory" name="5"/><lib desc="#I/O" name="6"/><lib desc="#Base" name="9"/>'''
    return f'<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n<project source="5.0.0" version="1.0">\n{libs}\n<main name="{main}"/>\n<options><a name="gateUndefined" val="ignore"/><a name="simlimit" val="10000"/><a name="simrand" val="0"/></options>\n'+'\n'.join(c.emit() for c in circs)+'\n</project>\n'
