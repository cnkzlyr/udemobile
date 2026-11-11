package uyapmobil;

import java.awt.Color;
import java.awt.EventQueue;
import java.awt.Window;
import java.awt.image.BufferedImage;
import java.util.Base64;
import java.util.IdentityHashMap;
import java.util.Map;
import javax.swing.Icon;
import javax.swing.text.AttributeSet;
import javax.swing.text.Document;
import javax.swing.text.Element;
import javax.swing.text.JTextComponent;
import javax.swing.text.StyleConstants;

/**
 * Anlık mobil görünüm (3.24.0).
 *
 * Resmi editörün BELLEKTEKİ belgesi (DocumentEx: section › header/paragraph/footer › content/space/tab/field/image,
 * UDF'nin kendi yapısı) HTML'e çevrilip Android'e gönderilir; Android onu telefon genişliğinde satır kırarak gösterir.
 * Kaydetme / dönüştürme YOK: belge, imzalar ve dosya olduğu gibi kalır. Belge değişince (DocumentListener) ve imleç
 * oynayınca (CaretListener) görünüm hemen güncellenir. Mobil görünümde dokunulan yerin karakter konumu "MK" ile gelir,
 * imleç orijinal editörde oraya konur; klavyeyle yazılanlar zaten orijinal editöre gider.
 *
 *   MM 1|0           mobil görünümü aç / kapat
 *   MK <a> [<b>]     imleci a'ya koy (b verilirse a..b seçili)
 *   → MOBIL <base64 html> <imleç> <seçim-sonu>   tam içerik
 *   → MKARET <imleç> <seçim-sonu>                yalnızca imleç
 */
final class Mobil {
    private Mobil() { }

    private static volatile boolean acik;
    private static JTextComponent bagli;
    private static Document bagliBelge;
    private static final javax.swing.Timer gecikme = new javax.swing.Timer(250, e -> gonder());
    private static final Map<Object, String> resimler = new IdentityHashMap<>();
    private static final javax.swing.event.DocumentListener dl = new javax.swing.event.DocumentListener() {
        @Override public void insertUpdate(javax.swing.event.DocumentEvent e) { degisti(); }
        @Override public void removeUpdate(javax.swing.event.DocumentEvent e) { degisti(); }
        @Override public void changedUpdate(javax.swing.event.DocumentEvent e) { degisti(); }
    };
    private static final javax.swing.event.CaretListener cl = e -> { if (acik && !gecikme.isRunning()) imlecGonder(); };

    static {
        gecikme.setRepeats(false);
        // ön plandaki belge değişince (başka pencere) yeniden bağlan
        new javax.swing.Timer(700, e -> { if (acik) bagla(); }).start();
    }

    static void kip(boolean ac) {
        if (ac && !acik) resimleriUnut();
        acik = ac;
        if (ac) { bagla(); gonder(); }
    }

    private static void degisti() { if (acik) gecikme.restart(); }

    private static JTextComponent onMetin() {
        JTextComponent son = null;
        java.awt.Frame on = null;
        for (Window w : Window.getWindows())
            if (w instanceof java.awt.Frame && w.isShowing() && !w.getClass().getName().startsWith("com.github.caciocavallosilano")
                    && (on == null || w.isFocused() || w.isActive())) on = (java.awt.Frame) w;
        if (on != null) son = Kopru.metinBilesenAc(on);
        return son;
    }

    private static void bagla() {
        JTextComponent m = onMetin();
        if (m == null) return;
        if (m != bagli || m.getDocument() != bagliBelge) {
            if (bagli != null) { bagli.removeCaretListener(cl); if (bagliBelge != null) bagliBelge.removeDocumentListener(dl); }
            bagli = m;
            bagliBelge = m.getDocument();
            m.addCaretListener(cl);
            bagliBelge.addDocumentListener(dl);
            gonder();
        }
    }

    static void imlec(int a, int b) {
        JTextComponent m = bagli != null ? bagli : onMetin();
        if (m == null) return;
        int n = m.getDocument().getLength();
        a = Math.max(0, Math.min(n, a));
        if (b >= 0 && b != a) { m.setCaretPosition(a); m.moveCaretPosition(Math.max(0, Math.min(n, b))); }
        else m.setCaretPosition(a);
        m.requestFocusInWindow();
        try {   // sayfa görünümü de aynı yere kaysın
            java.awt.Rectangle r = m.modelToView(a);
            if (r != null) m.scrollRectToVisible(r);
        } catch (Exception ignored) { }
    }

    private static void imlecGonder() {
        JTextComponent m = bagli;
        if (m == null) return;
        Kopru.bildir("MKARET " + m.getCaret().getMark() + " " + m.getCaret().getDot());
    }

    private static void gonder() {
        JTextComponent m = bagli;
        if (!acik || m == null) return;
        try {
            String h = html(m.getDocument());
            Kopru.bildir("MOBIL " + Base64.getEncoder().encodeToString(h.getBytes(java.nio.charset.StandardCharsets.UTF_8))
                    + " " + m.getCaret().getMark() + " " + m.getCaret().getDot());
        } catch (Throwable e) {
            Kopru.LOG.println("[uyapmobil] mobil görünüm: " + e);
        }
    }

    // ------------------------------------------------------------------------------------ belge → HTML
    static String html(Document d) {
        StringBuilder sb = new StringBuilder(d.getLength() * 3 + 1024);
        Element kok = d.getDefaultRootElement();
        oge(sb, d, kok);
        return sb.toString();
    }

    private static void oge(StringBuilder sb, Document d, Element e) {
        String ad = e.getName() == null ? "" : e.getName();
        switch (ad) {
            case "paragraph": paragraf(sb, d, e); return;
            case "header": sb.append("<header>"); cocuklar(sb, d, e); sb.append("</header>"); return;
            case "footer": sb.append("<footer>"); cocuklar(sb, d, e); sb.append("</footer>"); return;
            case "table": sb.append("<table>"); cocuklar(sb, d, e); sb.append("</table>"); return;
            case "row": sb.append("<tr>"); cocuklar(sb, d, e); sb.append("</tr>"); return;
            case "cell": sb.append("<td>"); cocuklar(sb, d, e); sb.append("</td>"); return;
            default:
                if (e.isLeaf()) { parca(sb, d, e); return; }
                cocuklar(sb, d, e);
        }
    }

    private static void cocuklar(StringBuilder sb, Document d, Element e) {
        for (int i = 0; i < e.getElementCount(); i++) oge(sb, d, e.getElement(i));
    }

    private static Object ozellik(AttributeSet a, String ad) {
        for (AttributeSet s = a; s != null; s = s.getResolveParent()) {
            java.util.Enumeration<?> n = s.getAttributeNames();
            while (n.hasMoreElements()) {
                Object k = n.nextElement();
                if (ad.equals(String.valueOf(k))) return s.getAttribute(k);
            }
        }
        return null;
    }

    private static float sayi(Object o) {
        if (o instanceof Number) return ((Number) o).floatValue();
        try { return o == null ? 0 : Float.parseFloat(String.valueOf(o)); } catch (Exception e) { return 0; }
    }

    private static void paragraf(StringBuilder sb, Document d, Element e) {
        AttributeSet a = e.getAttributes();
        int hiza = StyleConstants.getAlignment(a);
        float sol = StyleConstants.getLeftIndent(a), sag = StyleConstants.getRightIndent(a), ilk = StyleConstants.getFirstLineIndent(a);
        float ust = StyleConstants.getSpaceAbove(a), alt = StyleConstants.getSpaceBelow(a);
        float asili = sayi(ozellik(a, "Hanging"));
        float satir = StyleConstants.getLineSpacing(a);
        sb.append("<p data-o=\"").append(e.getStartOffset()).append("\" style=\"");
        sb.append("text-align:").append(hiza == 1 ? "center" : hiza == 2 ? "right" : hiza == 3 ? "justify" : "left").append(';');
        // girintiler telefonda ölçeklenir (--g); asılı girinti: ilk satır sola, diğerleri içeride
        float solToplam = sol + asili;
        if (solToplam > 0) sb.append("padding-left:calc(").append(solToplam).append("pt*var(--g));");
        if (sag > 0) sb.append("padding-right:calc(").append(sag).append("pt*var(--g));");
        float girinti = ilk - asili;
        if (girinti != 0) sb.append("text-indent:calc(").append(girinti).append("pt*var(--g));");
        if (ust > 0) sb.append("margin-top:").append(ust).append("pt;");
        if (alt > 0) sb.append("margin-bottom:").append(alt).append("pt;");
        if (satir > 0) sb.append("line-height:").append(1.2f + satir).append(';');
        sb.append("\">");
        int bas = sb.length();
        cocuklar(sb, d, e);
        if (sb.length() == bas) sb.append("&#8203;");
        sb.append("</p>");
    }

    private static void parca(StringBuilder sb, Document d, Element e) {
        AttributeSet a = e.getAttributes();
        int s0 = e.getStartOffset(), s1 = e.getEndOffset();
        Object resim = ozellik(a, "imageData");
        if (resim == null) resim = StyleConstants.getIcon(a);
        if (resim != null && "image".equals(e.getName()) || StyleConstants.getIcon(a) != null) {
            String no = resimNo(resim);
            float g = sayi(ozellik(a, "width")), y = sayi(ozellik(a, "height"));
            sb.append("<img data-o=\"").append(s0).append("\" data-r=\"").append(no).append("\" style=\"");
            if (g > 0) sb.append("width:").append(g).append("pt;");
            if (y > 0) sb.append("height:").append(y).append("pt;");
            sb.append("\">");
            return;
        }
        String t;
        try { t = d.getText(s0, s1 - s0); } catch (Exception ex) { return; }
        if (t.endsWith("\n")) t = t.substring(0, t.length() - 1);
        if (t.isEmpty()) return;
        String st = stil(a, "field".equals(e.getName()));
        // aynı biçimli ve bitişik parçalar tek <span>'de birleşir (kelime/boşluk öğeleri ayrı ayrı gelir)
        if (st.equals(sonStil) && s0 == sonSon && sb.length() == sonUzunluk) {
            sb.setLength(sb.length() - 7);       // "</span>"
            kacis(sb, t);
            sb.append("</span>");
        } else {
            sb.append("<span data-o=\"").append(s0).append("\"");
            if (!st.isEmpty()) sb.append(" style=\"").append(st).append('"');
            sb.append('>');
            kacis(sb, t);
            sb.append("</span>");
        }
        sonStil = st;
        sonSon = s0 + t.length();
        sonUzunluk = sb.length();
    }

    private static String sonStil;
    private static int sonSon = -1, sonUzunluk = -1;

    private static String stil(AttributeSet a, boolean alan) {
        StringBuilder s = new StringBuilder();
        String f = StyleConstants.getFontFamily(a);
        if (f != null && !f.isEmpty() && !"Dialog".equals(f)) s.append("font-family:'").append(f.replace("'", "")).append("',").append(yedekAile(f)).append(';');
        int boy = StyleConstants.getFontSize(a);
        if (boy > 0 && boy != 12) s.append("font-size:").append(boy).append("pt;");
        if (StyleConstants.isBold(a)) s.append("font-weight:bold;");
        if (StyleConstants.isItalic(a)) s.append("font-style:italic;");
        boolean alti = StyleConstants.isUnderline(a), ustu = StyleConstants.isStrikeThrough(a);
        if (alti || ustu) s.append("text-decoration:").append(alti ? "underline " : "").append(ustu ? "line-through" : "").append(';');
        if (StyleConstants.isSubscript(a)) s.append("vertical-align:sub;font-size:smaller;");
        if (StyleConstants.isSuperscript(a)) s.append("vertical-align:super;font-size:smaller;");
        Object on = a.getAttribute(StyleConstants.Foreground);
        if (on instanceof Color && !Color.BLACK.equals(on)) s.append("color:").append(renk((Color) on)).append(';');
        Object arka = a.getAttribute(StyleConstants.Background);
        if (arka instanceof Color && !Color.WHITE.equals(arka)) s.append("background:").append(renk((Color) arka)).append(';');
        if (alan) s.append("background:rgba(26,115,232,.08);border-bottom:1px dotted rgba(26,115,232,.5);");
        return s.toString();
    }

    private static String yedekAile(String f) {
        String k = f.toLowerCase(java.util.Locale.ROOT);
        if (k.contains("courier") || k.contains("mono")) return "'Liberation Mono',monospace";
        if (k.contains("arial") || k.contains("helvet") || k.contains("verdana") || k.contains("tahoma") || k.contains("sans")) return "'Liberation Sans',sans-serif";
        return "'Liberation Serif',serif";
    }

    private static String renk(Color c) { return String.format("#%02x%02x%02x", c.getRed(), c.getGreen(), c.getBlue()); }

    private static void kacis(StringBuilder sb, String t) {
        for (int i = 0; i < t.length(); i++) {
            char c = t.charAt(i);
            switch (c) {
                case '<': sb.append("&lt;"); break;
                case '>': sb.append("&gt;"); break;
                case '&': sb.append("&amp;"); break;
                case '"': sb.append("&quot;"); break;
                default: sb.append(c);
            }
        }
    }

    /** Resimler bir kez gönderilir ("MRESIM <no> <png base64>"); HTML yalnızca numarasını taşır. */
    private static final java.util.Set<String> gonderilen = new java.util.HashSet<>();

    private static String resimNo(Object o) {
        String png = resimPng(o);
        String no = Integer.toHexString(png.hashCode()) + Integer.toHexString(png.length());
        if (gonderilen.add(no)) Kopru.bildir("MRESIM " + no + " " + png);
        return no;
    }

    /** Android yeniden bağlanınca (görünüm yeniden kuruldu) resimler yeniden gönderilsin. */
    static void resimleriUnut() { gonderilen.clear(); }

    private static String resimPng(Object o) {
        String v = resimler.get(o);
        if (v != null) return v;
        try {
            BufferedImage im;
            if (o instanceof BufferedImage) im = (BufferedImage) o;
            else if (o instanceof java.awt.Image) {
                java.awt.Image i = (java.awt.Image) o;
                im = new BufferedImage(Math.max(1, i.getWidth(null)), Math.max(1, i.getHeight(null)), BufferedImage.TYPE_INT_ARGB);
                im.getGraphics().drawImage(i, 0, 0, null);
            } else if (o instanceof Icon) {
                Icon ic = (Icon) o;
                im = new BufferedImage(Math.max(1, ic.getIconWidth()), Math.max(1, ic.getIconHeight()), BufferedImage.TYPE_INT_ARGB);
                ic.paintIcon(null, im.getGraphics(), 0, 0);
            } else return "";
            java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
            javax.imageio.ImageIO.write(im, "png", bo);
            v = Base64.getEncoder().encodeToString(bo.toByteArray());
        } catch (Throwable e) { v = ""; }
        if (resimler.size() > 64) resimler.clear();
        resimler.put(o, v);
        return v;
    }
}
