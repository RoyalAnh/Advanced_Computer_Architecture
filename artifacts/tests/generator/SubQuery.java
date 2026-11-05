import com.cburch.logisim.file.*;
import com.cburch.logisim.circuit.*;
import com.cburch.logisim.data.*;
import com.cburch.logisim.instance.*;
import java.io.File;
import java.util.*;
public class SubQuery {
  public static void main(String[] a) throws Exception {
    Loader l = new Loader(null);
    LogisimFile f = l.openLogisimFile(new File(a[0]));
    for (Circuit c : f.getCircuits()) {
      Map<Location, Instance> m = c.getAppearance().getPortOffsets(Direction.EAST);
      StringBuilder sb = new StringBuilder(c.getName());
      for (var e : m.entrySet()) {
        Instance pin = e.getValue();
        sb.append(" ").append(pin.getAttributeValue(StdAttr.LABEL)).append(",").append(e.getKey().getX()).append(",").append(e.getKey().getY())
          .append(",").append(pin.getAttributeValue(StdAttr.WIDTH).getWidth());
      }
      System.out.println(sb);
    }
    System.exit(0);
  }
}
