package uyaptermux;

import java.awt.Component;
import java.awt.KeyboardFocusManager;
import java.io.File;
import java.io.FileWriter;
import java.io.PrintWriter;
import javax.swing.text.Caret;
import javax.swing.text.DefaultCaret;
import javax.swing.text.Highlighter;
import javax.swing.text.JTextComponent;

/** Ctrl+Shift+F11: odaktaki metin bileseninin imlec/secim durumunu ~/.uyap-editor/tani-secim.txt'ye yazar. */
final class Tani {
    private Tani() { }

    /** Yaprak paragraflari gezer; satir: PARAGRAF baslangic bitis y yukseklik "metin" */
    private static void paragraflar(JTextComponent t, PrintWriter w) {
        javax.swing.text.Document d = t.getDocument();
        java.util.List<javax.swing.text.Element> ps = new java.util.ArrayList<>();
        java.util.ArrayDeque<javax.swing.text.Element> yigin = new java.util.ArrayDeque<>();
        yigin.push(d.getDefaultRootElement());
        while (!yigin.isEmpty()) {
            javax.swing.text.Element e = yigin.pop();
            boolean yaprakParagraf = e.getElementCount() > 0 && e.getElement(0).isLeaf();
            if (yaprakParagraf) { ps.add(e); continue; }
            for (int i = e.getElementCount() - 1; i >= 0; i--) yigin.push(e.getElement(i));
        }
        ps.sort(java.util.Comparator.comparingInt(javax.swing.text.Element::getStartOffset));
        w.println("paragraf-sayisi: " + ps.size() + " bilesen-yukseklik: " + t.getHeight() + " genislik: " + t.getWidth());
        // gorunum agaci: sayfa gorunumlerinin olculeri (yakinlastirma / pt->px orani icin)
        try {
            javax.swing.text.View kok = t.getUI().getRootView(t);
            gorunumYaz(kok, 0, w, new int[]{0});
        } catch (Throwable ignored) { }
        for (javax.swing.text.Element p : ps) {
            try {
                java.awt.geom.Rectangle2D a = t.modelToView2D(p.getStartOffset());
                java.awt.geom.Rectangle2D b = t.modelToView2D(Math.max(p.getStartOffset(), p.getEndOffset() - 1));
                String m = d.getText(p.getStartOffset(), Math.min(30, p.getEndOffset() - p.getStartOffset())).replaceAll("\\s+", " ");
                // satir sayisi ve satir baslarinin y'leri (satir araligi = ardisik farklar)
                int satir = 0; StringBuilder ys = new StringBuilder();
                int o = p.getStartOffset();
                while (o < p.getEndOffset() && satir < 400) {
                    java.awt.geom.Rectangle2D r = t.modelToView2D(o);
                    if (satir < 6) ys.append(Math.round(r.getY())).append(',');
                    satir++;
                    int son = javax.swing.text.Utilities.getRowEnd(t, o);
                    if (son < o) break;
                    o = son + 1;
                }
                w.println("PARAGRAF\t" + p.getStartOffset() + "\t" + p.getEndOffset() + "\t" + Math.round(a.getY()) + "\t"
                        + Math.round(b.getY() + b.getHeight() - a.getY()) + "\t" + m + "\t" + satir + "\t" + ys);
            } catch (Exception ignored) { }
        }
    }

    private static void gorunumYaz(javax.swing.text.View v, int derinlik, PrintWriter w, int[] sayac) {
        if (v == null || derinlik > 3 || sayac[0]++ > 40) return;
        w.println("GORUNUM\t" + derinlik + "\t" + v.getClass().getName() + "\tX=" + v.getPreferredSpan(javax.swing.text.View.X_AXIS)
                + "\tY=" + v.getPreferredSpan(javax.swing.text.View.Y_AXIS) + "\tcocuk=" + v.getViewCount());
        if (derinlik == 1) {   // belge gorunumunun TUM paragraf cocuklari: model birimi (pt) yukseklik + metin
            for (int i = 0; i < v.getViewCount(); i++) {
                javax.swing.text.View c = v.getView(i);
                String m = "";
                try {
                    int s0 = c.getStartOffset(), s1 = Math.min(c.getEndOffset(), s0 + 30);
                    m = c.getDocument().getText(s0, s1 - s0).replaceAll("\\s+", " ");
                } catch (Exception ignored) { }
                StringBuilder sat = new StringBuilder();
                for (int k = 0; k < Math.min(c.getViewCount(), 8); k++) {
                    javax.swing.text.View rv = c.getView(k);
                    sat.append(Math.round(rv.getPreferredSpan(javax.swing.text.View.Y_AXIS) * 10) / 10.0);
                    // satirdaki parcalarin yazi tipi boyutlari
                    StringBuilder fs = new StringBuilder();
                    for (int q = 0; q < Math.min(rv.getViewCount(), 6); q++) {
                        javax.swing.text.AttributeSet as = rv.getView(q).getAttributes();
                        if (as != null) {
                            java.awt.Font fo = javax.swing.text.StyleContext.getDefaultStyleContext().getFont(as);
                            java.awt.FontMetrics fmx = c.getContainer().getFontMetrics(fo);
                            fs.append(fo.getFamily()).append(fo.isBold() ? "B" : "").append(fo.isItalic() ? "I" : "")
                              .append(fo.getSize()).append("h").append(fmx.getHeight()).append('/');
                        }
                    }
                    sat.append('[').append(fs).append("] ");
                }
                w.println("PVIEW\t" + i + "\t" + c.getPreferredSpan(javax.swing.text.View.Y_AXIS) + "\t" + c.getClass().getSimpleName() + "\t" + m + "\t" + c.getViewCount() + "\t" + sat);
            }
            return;
        }
        for (int i = 0; i < Math.min(3, v.getViewCount()); i++) gorunumYaz(v.getView(i), derinlik + 1, w, sayac);
    }

    private static void etiketTopla(java.awt.Component c, java.util.List<String> out) {
        if (c instanceof javax.swing.JLabel) {
            String t = ((javax.swing.JLabel) c).getText();
            if (t != null && t.matches("(?s).*(Sayfa|Paragraf|Karakter)\\s*:.*")) out.add(t.trim());
        }
        if (c instanceof java.awt.Container) {
            for (java.awt.Component k : ((java.awt.Container) c).getComponents()) etiketTopla(k, out);
        }
    }

    static void yaz() {
        String d = System.getProperty("uyap.instance.dir", System.getenv().getOrDefault("HOME", ".") + "/.uyap-editor");
        File f = new File(d, "tani-secim.txt");
        try (PrintWriter w = new PrintWriter(new FileWriter(f, true))) {
            KeyboardFocusManager km = KeyboardFocusManager.getCurrentKeyboardFocusManager();
            Component c = km.getFocusOwner();
            w.println("---- " + new java.util.Date() + "  java " + System.getProperty("java.version"));
            w.println("odak penceresi: " + (km.getFocusedWindow() == null ? null : km.getFocusedWindow().getClass().getName()));
            w.println("odak: " + (c == null ? null : c.getClass().getName()));
            // durum cubugu (Sayfa : x / N, Paragraf, Karakter ...) — Havelsan sayfalamasiyla karsilastirma icin
            for (java.awt.Window win : java.awt.Window.getWindows()) {
                if (!win.isShowing()) continue;
                java.util.List<String> etiketler = new java.util.ArrayList<>();
                etiketTopla(win, etiketler);
                if (!etiketler.isEmpty()) w.println("durum: " + String.join(" | ", etiketler));
            }
            if (c instanceof JTextComponent) {
                JTextComponent t = (JTextComponent) c;
                Caret car = t.getCaret();
                w.println("secim: " + t.getSelectionStart() + "-" + t.getSelectionEnd()
                        + " renk=" + t.getSelectionColor() + " secimMetniRengi=" + t.getSelectedTextColor());
                w.println("imlec: " + (car == null ? null : car.getClass().getName())
                        + " secimGorunur=" + (car != null && car.isSelectionVisible())
                        + " gorunur=" + (car != null && car.isVisible())
                        + (car instanceof DefaultCaret ? " guncelleme=" + ((DefaultCaret) car).getUpdatePolicy() : ""));
                Highlighter h = t.getHighlighter();
                w.println("vurgulayici: " + (h == null ? null : h.getClass().getName())
                        + " vurgular=" + (h == null ? 0 : h.getHighlights().length));
                if (h != null) for (Highlighter.Highlight x : h.getHighlights()) {
                    w.println("   " + x.getStartOffset() + "-" + x.getEndOffset() + " " + x.getPainter().getClass().getName());
                }
                // -Duyap.tani.paragraf=true: her paragrafin ekran konumu (Havelsan ile sayfalama karsilastirmasi icin)
                if (Boolean.getBoolean("uyap.tani.paragraf")) paragraflar(t, w);
            }
        } catch (Throwable e) {
            System.err.println("[UYAP] tani yazilamadi: " + e);
        }
    }
}
