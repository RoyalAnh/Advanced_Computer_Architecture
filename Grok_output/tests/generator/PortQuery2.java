import com.cburch.logisim.tools.*;
import com.cburch.logisim.data.*;
import com.cburch.logisim.comp.*;
import java.io.*;
import java.util.*;
public class PortQuery2 {
  public static void main(String[] a) throws Exception {
    Library[] libs = { new com.cburch.logisim.std.wiring.WiringLibrary(), new com.cburch.logisim.std.gates.GatesLibrary(),
      new com.cburch.logisim.std.plexers.PlexersLibrary(), new com.cburch.logisim.std.arith.ArithmeticLibrary(),
      new com.cburch.logisim.std.memory.MemoryLibrary(), new com.cburch.logisim.std.arith.floating.FPArithmeticLibrary(), new com.cburch.logisim.std.io.IoLibrary() };
    Map<String,ComponentFactory> f = new HashMap<>();
    for (Library l: libs) for (Tool t: l.getTools()) if (t instanceof AddTool at) f.put(t.getName(), at.getFactory());
    BufferedReader r = new BufferedReader(new InputStreamReader(System.in));
    String line;
    while ((line = r.readLine()) != null) {
      if (line.isBlank()) continue;
      String[] p = line.split("\\|", -1);
      ComponentFactory cf = f.get(p[0]);
      if (cf == null) { System.out.println("ERR nofactory " + p[0]); continue; }
      AttributeSet as = cf.createAttributeSet();
      if (p.length > 1 && !p[1].isEmpty()) for (String kv: p[1].split(";")) {
        String k = kv.substring(0, kv.indexOf('=')), v = kv.substring(kv.indexOf('=')+1);
        boolean ok=false;
        for (Attribute<?> at: new ArrayList<>(as.getAttributes())) if (at.getName().equals(k)) { setA(as, at, v); ok=true; }
        if(!ok) System.err.println("WARN no attr "+k+" on "+p[0]);
      }
      if(System.getenv("ATTRS")!=null){for(Attribute<?> at: as.getAttributes()) System.out.print(at.getName()+"="+as.getValue(at)+"; ");System.out.println();}
      Component c = cf.createComponent(Location.create(0,0,false), as);
      StringBuilder sb = new StringBuilder();
      for (EndData e: c.getEnds()) sb.append(e.getLocation().getX()).append(',').append(e.getLocation().getY()).append(',')
        .append(e.getWidth().getWidth()).append(',').append(e.getType()).append(' ');
      Bounds b=c.getBounds(); sb.append("| ").append(b.getX()).append(",").append(b.getY()).append(",").append(b.getWidth()).append(",").append(b.getHeight()); System.out.println(sb.toString().trim());
    }
  }
  @SuppressWarnings("unchecked") static <V> void setA(AttributeSet as, Attribute<V> at, String v){ try{ as.setValue(at, at.parse(v)); }catch(Exception ex){ try{ Object[] o=(Object[])at.getClass().getMethod("getOptions").invoke(at); StringBuilder b=new StringBuilder("OPTIONS "+at.getName()+":"); for(Object x:o) b.append(" ").append(((AttributeOption)x).getValue()); System.out.println(b);}catch(Exception e2){System.out.println("BADVAL "+at.getName());} } }
}
