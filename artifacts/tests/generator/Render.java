import com.cburch.logisim.file.*;
import com.cburch.logisim.circuit.*;
import com.cburch.logisim.comp.*;
import com.cburch.logisim.data.*;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.File;
import java.util.*;
public class Render {
  // java Render file.circ outprefix scale [circuit...]
  public static void main(String[] a) throws Exception {
    Loader l = new Loader(null);
    LogisimFile f = l.openLogisimFile(new File(a[0]));
    double sc = Double.parseDouble(a[2]);
    Set<String> want = new HashSet<>(Arrays.asList(a).subList(3, a.length));
    for (Circuit c : f.getCircuits()) {
      if (!want.isEmpty() && !want.contains(c.getName())) continue;
      BufferedImage tmp = new BufferedImage(10,10,BufferedImage.TYPE_INT_RGB);
      Bounds b = c.getBounds(tmp.getGraphics());
      int W=(int)((b.getWidth()+40)*sc), H=(int)((b.getHeight()+40)*sc);
      BufferedImage img = new BufferedImage(W, H, BufferedImage.TYPE_INT_RGB);
      Graphics2D g = img.createGraphics();
      g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
      g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
      g.setColor(Color.WHITE); g.fillRect(0,0,W,H);
      g.scale(sc, sc); g.translate(-b.getX()+20, -b.getY()+20);
      g.setColor(Color.BLACK);
      com.cburch.logisim.proj.Project proj = new com.cburch.logisim.proj.Project(f);
      CircuitState st = proj.getCircuitState(c);
      ComponentDrawContext ctx = new ComponentDrawContext(null, c, st, g, g, true);
      try { c.draw(ctx, Collections.emptySet()); } catch (Exception e) { System.err.println("draw err "+c.getName()+": "+e); }
      javax.imageio.ImageIO.write(img, "png", new File(a[1]+c.getName()+".png"));
      System.out.println(c.getName()+" "+b.getWidth()+"x"+b.getHeight());
    }
    System.exit(0);
  }
}
