package uyapmobil;

import java.awt.Color;
import java.awt.Composite;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.Graphics;
import java.awt.Graphics2D;
import java.awt.GraphicsConfiguration;
import java.awt.Image;
import java.awt.Paint;
import java.awt.Rectangle;
import java.awt.RenderingHints;
import java.awt.Shape;
import java.awt.Stroke;
import java.awt.font.FontRenderContext;
import java.awt.font.GlyphVector;
import java.awt.geom.AffineTransform;
import java.awt.geom.Point2D;
import java.awt.geom.Rectangle2D;
import java.awt.image.BufferedImage;
import java.awt.image.BufferedImageOp;
import java.awt.image.ImageObserver;
import java.awt.image.RenderedImage;
import java.awt.image.renderable.RenderableImage;
import java.text.AttributedCharacterIterator;
import java.util.List;
import java.util.Map;

/**
 * Sayfa süsleri için süzgeçli Graphics2D (3.29.0).
 *
 * Kağıt görünümünde belgenin metni ve resimleri HTML olarak çizilir. Resmi editörün sayfayı boyarken eklediği ama
 * belge modelinde olmayan süsler (filigran, e-imza doğrulama satırı, karekod, sayfa numarası, kenar işaretleri) ise
 * yalnızca motorun kendi çiziminde vardır. Motor sayfayı bu sarmalayıcıyla bir resme çizer; çizim çağrıları belgenin
 * yaprak görünümlerinin dikdörtgenlerine (yerleşim koordinatları) düşüyorsa atlanır:
 *   - metin: çapa noktası bir metin/alan dikdörtgeninde ve dönüşüm döndürmesizse (döndürülmüş filigran kalır)
 *   - resim: bir belge resmiyle aynı yer ve boyutta ise
 *   - çizgi/dolgu: tamamen bir dikdörtgenin içindeyse (altı çizili, alan kutusu, vurgu zemini)
 * Geri kalan her şey olduğu gibi çizilir.
 */
final class Suzgec extends Graphics2D {
    private final Graphics2D g;
    private final List<Rectangle> metin, resim;
    private final AffineTransform tabanTers;

    Suzgec(Graphics2D g, List<Rectangle> metin, List<Rectangle> resim, AffineTransform taban) {
        this.g = g;
        this.metin = metin;
        this.resim = resim;
        AffineTransform t;
        try { t = taban.createInverse(); } catch (Exception e) { t = new AffineTransform(); }
        this.tabanTers = t;
    }

    // ------------------------------------------------------------------------------------ süzgeç
    private Point2D yerlesim(double x, double y) {
        Point2D p = g.getTransform().transform(new Point2D.Double(x, y), null);
        return tabanTers.transform(p, null);
    }

    private boolean donuk() { AffineTransform t = g.getTransform(); return Math.abs(t.getShearX()) > 1e-6 || Math.abs(t.getShearY()) > 1e-6; }

    private boolean metinIcinde(double x, double y) {
        if (donuk()) return false;
        Point2D p = yerlesim(x + 1, y - 2);
        for (Rectangle r : metin) if (p.getX() >= r.x - 12 && p.getX() <= r.x + r.width + 1 && p.getY() >= r.y - 2 && p.getY() <= r.y + r.height + 2) return true;
        return false;
    }

    private boolean sekilIcinde(Shape s) {
        Rectangle2D b = s.getBounds2D();
        Point2D a = yerlesim(b.getMinX(), b.getMinY()), z = yerlesim(b.getMaxX(), b.getMaxY());
        double x0 = Math.min(a.getX(), z.getX()), y0 = Math.min(a.getY(), z.getY()), x1 = Math.max(a.getX(), z.getX()), y1 = Math.max(a.getY(), z.getY());
        for (Rectangle r : metin) if (x0 >= r.x - 2 && x1 <= r.x + r.width + 2 && y0 >= r.y - 3 && y1 <= r.y + r.height + 3) return true;
        for (Rectangle r : resim) if (x0 >= r.x - 2 && x1 <= r.x + r.width + 2 && y0 >= r.y - 2 && y1 <= r.y + r.height + 2) return true;
        return false;
    }

    private boolean resimAyni(double x, double y, double w, double h) {
        Point2D a = yerlesim(x, y), z = yerlesim(x + w, y + h);
        for (Rectangle r : resim)
            if (Math.abs(a.getX() - r.x) < 4 && Math.abs(a.getY() - r.y) < 4 && Math.abs(z.getX() - (r.x + r.width)) < 4 && Math.abs(z.getY() - (r.y + r.height)) < 4) return true;
        return false;
    }

    // ------------------------------------------------------------------------------------ metin
    @Override public void drawString(String s, int x, int y) { if (!metinIcinde(x, y)) { tani("drawString", s, x, y); g.drawString(s, x, y); } }
    @Override public void drawString(String s, float x, float y) { if (!metinIcinde(x, y)) { tani("drawString(f)", s, x, y); g.drawString(s, x, y); } }
    @Override public void drawString(AttributedCharacterIterator it, int x, int y) { if (!metinIcinde(x, y)) g.drawString(it, x, y); }
    @Override public void drawString(AttributedCharacterIterator it, float x, float y) { if (!metinIcinde(x, y)) g.drawString(it, x, y); }
    @Override public void drawChars(char[] d, int o, int l, int x, int y) { if (!metinIcinde(x, y)) g.drawChars(d, o, l, x, y); }
    @Override public void drawBytes(byte[] d, int o, int l, int x, int y) { if (!metinIcinde(x, y)) g.drawBytes(d, o, l, x, y); }
    @Override public void drawGlyphVector(GlyphVector gv, float x, float y) { if (!metinIcinde(x, y)) { tani("glyph", "#" + gv.getNumGlyphs(), x, y); g.drawGlyphVector(gv, x, y); } }
    static boolean TANI;
    private void tani(String t, String m, double x, double y) {
        if (!TANI) return;
        Point2D p = yerlesim(x, y);
        Rectangle en = null; double ed = 1e9;
        for (Rectangle r : metin) { double d = Math.abs(r.x - p.getX()) + Math.abs(r.y + r.height / 2.0 - p.getY()); if (d < ed) { ed = d; en = r; } }
        Kopru.LOG.println("[süzgeç] " + t + " «" + (m.length() > 20 ? m.substring(0, 20) : m) + "» yerleşim=" + Math.round(p.getX()) + "," + Math.round(p.getY()) + " tr=" + g.getTransform() + " en yakın=" + en);
    }

    // ------------------------------------------------------------------------------------ resim
    private int iw(Image i) { return i.getWidth(null); }
    private int ih(Image i) { return i.getHeight(null); }
    @Override public boolean drawImage(Image i, AffineTransform t, ImageObserver o) {
        Rectangle2D b = t.createTransformedShape(new Rectangle(0, 0, iw(i), ih(i))).getBounds2D();
        return resimAyni(b.getX(), b.getY(), b.getWidth(), b.getHeight()) || g.drawImage(i, t, o);
    }
    @Override public void drawImage(BufferedImage i, BufferedImageOp op, int x, int y) { if (!resimAyni(x, y, i.getWidth(), i.getHeight())) g.drawImage(i, op, x, y); }
    @Override public void drawRenderedImage(RenderedImage i, AffineTransform t) {
        Rectangle2D b = t.createTransformedShape(new Rectangle(0, 0, i.getWidth(), i.getHeight())).getBounds2D();
        if (!resimAyni(b.getX(), b.getY(), b.getWidth(), b.getHeight())) g.drawRenderedImage(i, t);
    }
    @Override public void drawRenderableImage(RenderableImage i, AffineTransform t) { g.drawRenderableImage(i, t); }
    @Override public boolean drawImage(Image i, int x, int y, ImageObserver o) { if (resimAyni(x, y, iw(i), ih(i))) return true; tani("img", iw(i) + "x" + ih(i), x, y); return g.drawImage(i, x, y, o); }
    @Override public boolean drawImage(Image i, int x, int y, int w, int h, ImageObserver o) { if (resimAyni(x, y, w, h)) return true; tani("img2", w + "x" + h, x, y); return g.drawImage(i, x, y, w, h, o); }
    @Override public boolean drawImage(Image i, int x, int y, Color c, ImageObserver o) { return resimAyni(x, y, iw(i), ih(i)) || g.drawImage(i, x, y, c, o); }
    @Override public boolean drawImage(Image i, int x, int y, int w, int h, Color c, ImageObserver o) { return resimAyni(x, y, w, h) || g.drawImage(i, x, y, w, h, c, o); }
    @Override public boolean drawImage(Image i, int dx1, int dy1, int dx2, int dy2, int sx1, int sy1, int sx2, int sy2, ImageObserver o) {
        return resimAyni(Math.min(dx1, dx2), Math.min(dy1, dy2), Math.abs(dx2 - dx1), Math.abs(dy2 - dy1)) || g.drawImage(i, dx1, dy1, dx2, dy2, sx1, sy1, sx2, sy2, o);
    }
    @Override public boolean drawImage(Image i, int dx1, int dy1, int dx2, int dy2, int sx1, int sy1, int sx2, int sy2, Color c, ImageObserver o) {
        return resimAyni(Math.min(dx1, dx2), Math.min(dy1, dy2), Math.abs(dx2 - dx1), Math.abs(dy2 - dy1)) || g.drawImage(i, dx1, dy1, dx2, dy2, sx1, sy1, sx2, sy2, c, o);
    }

    // ------------------------------------------------------------------------------------ şekiller
    @Override public void draw(Shape s) { if (!sekilIcinde(s)) g.draw(s); }
    @Override public void fill(Shape s) { if (!sekilIcinde(s)) { if (TANI) { Rectangle2D b = s.getBounds2D(); tani("fill " + s.getClass().getSimpleName(), Math.round(b.getWidth()) + "x" + Math.round(b.getHeight()), b.getX(), b.getMaxY()); } g.fill(s); } }
    @Override public void drawLine(int x1, int y1, int x2, int y2) { if (!sekilIcinde(new Rectangle(Math.min(x1, x2), Math.min(y1, y2), Math.abs(x2 - x1), Math.abs(y2 - y1)))) g.drawLine(x1, y1, x2, y2); }
    @Override public void fillRect(int x, int y, int w, int h) { if (!sekilIcinde(new Rectangle(x, y, w, h))) g.fillRect(x, y, w, h); }
    @Override public void drawRect(int x, int y, int w, int h) { if (!sekilIcinde(new Rectangle(x, y, w, h))) g.drawRect(x, y, w, h); }
    @Override public void clearRect(int x, int y, int w, int h) { g.clearRect(x, y, w, h); }
    @Override public void drawRoundRect(int x, int y, int w, int h, int aw, int ah) { if (!sekilIcinde(new Rectangle(x, y, w, h))) g.drawRoundRect(x, y, w, h, aw, ah); }
    @Override public void fillRoundRect(int x, int y, int w, int h, int aw, int ah) { if (!sekilIcinde(new Rectangle(x, y, w, h))) g.fillRoundRect(x, y, w, h, aw, ah); }
    @Override public void drawOval(int x, int y, int w, int h) { g.drawOval(x, y, w, h); }
    @Override public void fillOval(int x, int y, int w, int h) { g.fillOval(x, y, w, h); }
    @Override public void drawArc(int x, int y, int w, int h, int s, int a) { g.drawArc(x, y, w, h, s, a); }
    @Override public void fillArc(int x, int y, int w, int h, int s, int a) { g.fillArc(x, y, w, h, s, a); }
    @Override public void drawPolyline(int[] x, int[] y, int n) { g.drawPolyline(x, y, n); }
    @Override public void drawPolygon(int[] x, int[] y, int n) { g.drawPolygon(x, y, n); }
    @Override public void fillPolygon(int[] x, int[] y, int n) { g.fillPolygon(x, y, n); }
    @Override public void copyArea(int x, int y, int w, int h, int dx, int dy) { g.copyArea(x, y, w, h, dx, dy); }

    // ------------------------------------------------------------------------------------ durum (aynen aktar)
    @Override public Graphics create() { return new Suzgec((Graphics2D) g.create(), metin, resim, ters(tabanTers)); }
    private static AffineTransform ters(AffineTransform t) { try { return t.createInverse(); } catch (Exception e) { return new AffineTransform(); } }
    @Override public boolean hit(Rectangle r, Shape s, boolean onStroke) { return g.hit(r, s, onStroke); }
    @Override public GraphicsConfiguration getDeviceConfiguration() { return g.getDeviceConfiguration(); }
    @Override public void setComposite(Composite c) { g.setComposite(c); }
    @Override public void setPaint(Paint p) { g.setPaint(p); }
    @Override public void setStroke(Stroke s) { g.setStroke(s); }
    @Override public void setRenderingHint(RenderingHints.Key k, Object v) { g.setRenderingHint(k, v); }
    @Override public Object getRenderingHint(RenderingHints.Key k) { return g.getRenderingHint(k); }
    @Override public void setRenderingHints(Map<?, ?> m) { g.setRenderingHints(m); }
    @Override public void addRenderingHints(Map<?, ?> m) { g.addRenderingHints(m); }
    @Override public RenderingHints getRenderingHints() { return g.getRenderingHints(); }
    @Override public void translate(int x, int y) { g.translate(x, y); }
    @Override public void translate(double x, double y) { g.translate(x, y); }
    @Override public void rotate(double t) { g.rotate(t); }
    @Override public void rotate(double t, double x, double y) { g.rotate(t, x, y); }
    @Override public void scale(double x, double y) { g.scale(x, y); }
    @Override public void shear(double x, double y) { g.shear(x, y); }
    @Override public void transform(AffineTransform t) { g.transform(t); }
    @Override public void setTransform(AffineTransform t) { g.setTransform(t); }
    @Override public AffineTransform getTransform() { return g.getTransform(); }
    @Override public Paint getPaint() { return g.getPaint(); }
    @Override public Composite getComposite() { return g.getComposite(); }
    @Override public void setBackground(Color c) { g.setBackground(c); }
    @Override public Color getBackground() { return g.getBackground(); }
    @Override public Stroke getStroke() { return g.getStroke(); }
    @Override public void clip(Shape s) { g.clip(s); }
    @Override public FontRenderContext getFontRenderContext() { return g.getFontRenderContext(); }
    @Override public Color getColor() { return g.getColor(); }
    @Override public void setColor(Color c) { g.setColor(c); }
    @Override public void setPaintMode() { g.setPaintMode(); }
    @Override public void setXORMode(Color c) { g.setXORMode(c); }
    @Override public Font getFont() { return g.getFont(); }
    @Override public void setFont(Font f) { g.setFont(f); }
    @Override public FontMetrics getFontMetrics(Font f) { return g.getFontMetrics(f); }
    @Override public Rectangle getClipBounds() { return g.getClipBounds(); }
    @Override public void clipRect(int x, int y, int w, int h) { g.clipRect(x, y, w, h); }
    @Override public void setClip(int x, int y, int w, int h) { g.setClip(x, y, w, h); }
    @Override public Shape getClip() { return g.getClip(); }
    @Override public void setClip(Shape s) { g.setClip(s); }
    @Override public void dispose() { g.dispose(); }
}
