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
    /** 1: mobil (yeniden akış), 2: kağıt (motorun sayfa/satır/kelime konumlarıyla birebir) */
    private static volatile int tur = 1;
    private static JTextComponent bagli;
    private static Document bagliBelge;
    private static final javax.swing.Timer gecikme = new javax.swing.Timer(250, e -> gonder());
    private static final Map<Object, String> resimler = new IdentityHashMap<>();
    private static final javax.swing.event.DocumentListener dl = new javax.swing.event.DocumentListener() {
        @Override public void insertUpdate(javax.swing.event.DocumentEvent e) { kirlet(e, e.getOffset(), e.getOffset() + e.getLength()); degisti(); }
        @Override public void removeUpdate(javax.swing.event.DocumentEvent e) { kirlet(e, e.getOffset(), e.getOffset()); degisti(); }
        @Override public void changedUpdate(javax.swing.event.DocumentEvent e) { kirlet(e, e.getOffset(), e.getOffset() + e.getLength()); degisti(); }
    };

    // ------------------------------------------------------------------------------------ artımlı güncelleme
    /*
     * Her tuşta bütün belgeyi baştan üretmek telefonda 1–2 sn (büyük belgede çok daha fazla) sürüyordu. Belge üst düzey
     * öğelere (üst bilgi, paragraf, tablo, alt bilgi) bölünür; her öğenin HTML'i / kağıt satırları önbellekte tutulur.
     * Ofsetler öğenin başına GÖRELİ yazılır (data-o), öğenin başlangıcı ayrıca gönderilir (taban): öğe yalnızca kaydıysa
     * yeniden üretilmez. Belge olayları yalnızca etkilenen öğeleri geçersiz kılar; yeni/silinen öğeler kimlikten anlaşılır.
     */
    private static final Map<Element, String> mobilOnb = new IdentityHashMap<>();
    private static final Map<Element, Object[]> kagitOnb = new IdentityHashMap<>();   // {y, h, json}
    private static final Map<Element, Integer> kimlik = new IdentityHashMap<>();
    private static int sonKimlik;

    private static int kimlikVer(Element e) {
        Integer k = kimlik.get(e);
        if (k == null) { k = ++sonKimlik; kimlik.put(e, k); }
        return k;
    }

    private static void kirlet(javax.swing.event.DocumentEvent ev, int a, int b) {
        try {
            Element kok = ev.getDocument().getDefaultRootElement();
            int i0 = kok.getElementIndex(Math.max(0, a)), i1 = kok.getElementIndex(Math.max(a, b));
            for (int i = Math.max(0, i0 - 1); i <= Math.min(kok.getElementCount() - 1, i1 + 1); i++) {
                Element e = kok.getElement(i);
                mobilOnb.remove(e);
                kagitOnb.remove(e);
            }
        } catch (Throwable ignored) { }
    }

    /** Önbellek her sıfırlandığında artar: görünüm eski düğümleri atar (kimlikler baştan başlar). */
    private static int nesil;

    private static void onbellekSifirla() {
        nesil++;
        stiller.clear();
        stilIndeks.clear();
        stilGonderilen = 0;
        mobilOnb.clear();
        kagitOnb.clear();
        kimlik.clear();
    }
    private static final javax.swing.event.CaretListener cl = e -> { if (acik && !gecikme.isRunning()) imlecGonder(); };

    static {
        gecikme.setRepeats(false);
        // ön plandaki belge değişince (başka pencere) yeniden bağlan
        new javax.swing.Timer(700, e -> { if (acik) bagla(); }).start();
    }

    static void kip(boolean ac) { kip(ac ? 1 : 0); }

    static void kip(int t) {
        boolean ac = t > 0;
        if (ac && (!acik || t != tur)) { resimleriUnut(); onbellekSifirla(); }
        if (ac) tur = t;
        gecikme.setInitialDelay(tur == 2 ? 140 : 110);
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
            onbellekSifirla();
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
        Kopru.bildir("MKARET " + m.getCaret().getMark() + " " + m.getCaret().getDot() + konum(m, m.getCaret().getDot()));
    }

    /*
     * Editörün kendi yakınlaştırması (UYAP Editör 5.4.20'de %98): bileşen koordinatları (modelToView/viewToModel)
     * yerleşim (View) koordinatlarının z katıdır. Kağıt görünümü yerleşim koordinatlarıyla çizildiği için dokunma ve
     * imleç z ile dönüştürülür; aksi hâlde sapma belgenin sonuna doğru büyüyordu (sayfa 4'te ~80 nokta).
     */
    private static double zoom = 1;

    @SuppressWarnings("deprecation")
    private static void zoomOlc(JTextComponent m) {
        try {
            javax.swing.text.View sec = m.getUI().getRootView(m).getView(0);
            java.awt.Rectangle alan = new java.awt.Rectangle(0, 0, m.getWidth(), m.getHeight());
            java.util.List<Double> o = new java.util.ArrayList<>();
            for (int i = sec.getViewCount() - 1; i >= 0 && o.size() < 9; i -= Math.max(1, sec.getViewCount() / 12)) {
                java.awt.Rectangle r = sec.getChildAllocation(i, alan).getBounds();
                if (r.y < 300) continue;
                java.awt.Rectangle mv = m.modelToView(sec.getView(i).getStartOffset());
                if (mv != null) o.add(mv.y / (double) r.y);
            }
            if (!o.isEmpty()) {
                java.util.Collections.sort(o);
                double z = o.get(o.size() / 2);
                if (z > 0.2 && z < 5) zoom = Math.round(z * 100) / 100.0;
            }
        } catch (Throwable ignored) { }
    }

    /** İmlecin yerleşim koordinatları: " x y yükseklik" (kağıt görünümünde imleç buraya çizilir). */
    @SuppressWarnings("deprecation")
    private static String konum(JTextComponent m, int o) {
        try {
            java.awt.Rectangle r = m.modelToView(o);
            if (r != null) return " " + Math.round(r.x / zoom) + " " + Math.round(r.y / zoom) + " " + Math.max(10, Math.round(r.height / zoom));
        } catch (Exception ignored) { }
        return "";
    }

    /** MP x y [x2 y2]: kağıt görünümünde dokunulan motor koordinatı → imleç (ikinci nokta: seçim). */
    @SuppressWarnings("deprecation")
    static void nokta(int x, int y, int x2, int y2) {
        JTextComponent m = bagli != null ? bagli : onMetin();
        if (m == null) return;
        int a = m.viewToModel(new java.awt.Point((int) Math.round(x * zoom), (int) Math.round(y * zoom)));
        if (a < 0) return;
        if (x2 >= 0) {
            int b = m.viewToModel(new java.awt.Point((int) Math.round(x2 * zoom), (int) Math.round(y2 * zoom)));
            m.setCaretPosition(a);
            if (b >= 0) m.moveCaretPosition(b);
        } else m.setCaretPosition(a);
        m.requestFocusInWindow();
        try { java.awt.Rectangle r = m.modelToView(m.getCaret().getDot()); if (r != null) m.scrollRectToVisible(r); } catch (Exception ignored) { }
    }

    private static void gonder() {
        JTextComponent m = bagli;
        if (!acik || m == null) return;
        long t0 = System.nanoTime();
        try {
            String son = " " + m.getCaret().getMark() + " " + m.getCaret().getDot() + konum(m, m.getCaret().getDot());
            String j = tur == 2 ? kagit(m) : mobilBloklar(m.getDocument());
            Kopru.bildir((tur == 2 ? "MKAGIT " : "MOBIL ") + Base64.getEncoder().encodeToString(j.getBytes(java.nio.charset.StandardCharsets.UTF_8)) + son);
            long ms = (System.nanoTime() - t0) / 1000000;
            if (ms > 150) Kopru.LOG.println("[süre] " + (tur == 2 ? "kağıt " : "mobil ") + ms + " ms, " + j.length() + " bayt");
        } catch (Throwable e) {
            Kopru.LOG.println("[uyapmobil] mobil görünüm: " + e);
            e.printStackTrace(Kopru.LOG);
        }
    }

    /** Mobil: [[kimlik, taban, "html" | 0]...] — 0: önceki HTML'i kullan. */
    private static String mobilBloklar(Document d) {
        Element kok = d.getDefaultRootElement();
        StringBuilder sb = new StringBuilder("{\"g\":" + nesil + ",\"B\":[");
        for (int i = 0; i < kok.getElementCount(); i++) {
            Element e = kok.getElement(i);
            if (i > 0) sb.append(',');
            sb.append('[').append(kimlikVer(e)).append(',').append(e.getStartOffset()).append(',');
            String h = mobilOnb.get(e);
            if (h != null) { sb.append("0]"); continue; }
            StringBuilder b = new StringBuilder();
            taban = e.getStartOffset();
            sonStil = null;
            oge(b, d, e);
            h = b.toString();
            mobilOnb.put(e, h);
            jsonDize(sb, h);
            sb.append(']');
        }
        return sb.append("]}").toString();
    }

    /** Göreli ofset tabanı (yazılan öğenin başlangıcı). */
    private static int taban;

    // ------------------------------------------------------------------------------------ kağıt görünümü
    /*
     * Motorun kendi yerleşimi (View ağacı) okunur: her satır (yaprak görünümlerden oluşan satır görünümü) ve
     * satırdaki her kelime/boşluk/alan/resim parçasının motor koordinatı. Koordinatlar punto cinsindendir (1 birim = 1 pt).
     * Sayfa: PageFormat (A4 595,28 × 841,89; kenar boşlukları) ve sayfa adımı (sayfa yüksekliği + aralık) motorun sayfa
     * yöneticisinden; üst/alt bilgi her sayfaya kopyalanır. Böylece satır kırılımı, iki yana yaslama, sekmeler ve sayfa
     * sonları resmi editörle birebir aynıdır; metin HTML olduğu için her yakınlaştırmada keskindir.
     *
     * JSON: {"pw","ph","px","pitch","n","L":[[y,h,bölge,[[x,w,ofset,"metin","css",punto]...]]...],"I":[[x,y,w,h,"resim"]...]}
     * bölge: 0 gövde, 1 üst bilgi, 2 alt bilgi.
     */
    private static final class Sayfa { double pw = 595.28, ph = 841.89, ml = 70.87; int pitch = 861; }

    private static Sayfa sayfaBul(javax.swing.text.View sec) {
        Sayfa s = new Sayfa();
        Object tutan = null;
        java.awt.print.PageFormat pf = null;
        java.util.List<Object> kuyruk = new java.util.ArrayList<>();
        kuyruk.add(sec);
        for (int d = 0; d < 3 && pf == null; d++) {
            java.util.List<Object> sonraki = new java.util.ArrayList<>();
            for (Object o : kuyruk) {
                for (Class<?> c = o.getClass(); c != null && c != Object.class; c = c.getSuperclass())
                    for (java.lang.reflect.Field f : c.getDeclaredFields()) {
                        if (java.lang.reflect.Modifier.isStatic(f.getModifiers()) || f.getType().isPrimitive()) continue;
                        try {
                            f.setAccessible(true);
                            Object v = f.get(o);
                            if (v instanceof java.awt.print.PageFormat && pf == null) { pf = (java.awt.print.PageFormat) v; tutan = o; }
                            else if (v != null && v.getClass().getName().startsWith("tr.com.havelsan") && !(v instanceof java.awt.Component)
                                    && !(v instanceof javax.swing.text.View)) sonraki.add(v);
                        } catch (Throwable ignored) { }
                    }
                if (pf != null) break;
            }
            kuyruk = sonraki;
        }
        if (pf == null) return s;
        s.pw = pf.getWidth();
        s.ph = pf.getHeight();
        s.ml = pf.getImageableX();
        int sh = (int) Math.round(s.ph), en = -1;
        for (Class<?> c = tutan.getClass(); c != null && c != Object.class; c = c.getSuperclass())
            for (java.lang.reflect.Field f : c.getDeclaredFields())
                if (f.getType() == int.class && !java.lang.reflect.Modifier.isStatic(f.getModifiers())) {
                    try {
                        f.setAccessible(true);
                        int v = f.getInt(tutan);
                        if (v > sh && v <= sh + 80 && (en < 0 || v < en)) en = v;   // sayfa yüksekliği + aralık
                    } catch (Throwable ignored) { }
                }
        if (en > 0) s.pitch = en; else s.pitch = sh + 20;
        return s;
    }

    private static String kagit(JTextComponent m) {
        javax.swing.text.View kok = m.getUI().getRootView(m);
        javax.swing.text.View sec = kok.getViewCount() > 0 ? kok.getView(0) : kok;
        java.awt.Rectangle alan = new java.awt.Rectangle(0, 0, m.getWidth(), m.getHeight());
        Sayfa s = sayfaBul(sec);
        zoomOlc(m);
        Document d = m.getDocument();
        StringBuilder B = new StringBuilder();
        int solX = Integer.MAX_VALUE, enAlt = 0;
        for (int i = 0; i < sec.getViewCount(); i++) {
            javax.swing.text.View v = sec.getView(i);
            java.awt.Shape a;
            try { a = sec.getChildAllocation(i, alan); } catch (Exception ex) { continue; }
            if (a == null) continue;
            java.awt.Rectangle r = a.getBounds();
            Element e = v.getElement();
            String ad = e == null ? "" : e.getName();
            int bolge = "header".equals(ad) ? 1 : "footer".equals(ad) ? 2 : 0;
            if (bolge == 0) {
                if ("paragraph".equals(ad) && r.width > 100 && r.x < solX) solX = r.x;
                enAlt = Math.max(enAlt, r.y + r.height);
            }
            Object[] o = kagitOnb.get(e);
            // önbellek geçerli: öğe değişmedi, yüksekliği aynı ve (eski/yeni) bir sayfa sınırını aşmıyor
            // önbellek geçerli: öğe değişmedi ve ya hiç kaymadı ya da (eski/yeni konumda) sayfa sınırını aşmıyor
            boolean gecerli = o != null && (int) o[1] == r.height
                    && ((int) o[0] == r.y || (bolge == 0 && tekSayfa((int) o[0], r.height, s.pitch) && tekSayfa(r.y, r.height, s.pitch)));
            if (B.length() > 0) B.append(',');
            B.append('[').append(kimlikVer(e)).append(',').append(r.y).append(',').append(r.height).append(',').append(bolge)
                    .append(',').append(e.getStartOffset()).append(',');
            if (gecerli) { B.append("0]"); continue; }
            StringBuilder L = new StringBuilder(), I = new StringBuilder();
            taban = e.getStartOffset();
            gez(d, v, a, r.y, L, I, 0);
            String j = "{\"L\":[" + L + "],\"I\":[" + I + "]}";
            kagitOnb.put(e, new Object[]{r.y, r.height, j});
            B.append(j).append(']');
        }
        double px = solX == Integer.MAX_VALUE ? 0 : solX - s.ml;
        int n = Math.max(1, (enAlt - 1) / s.pitch + 1);
        StringBuilder S = new StringBuilder();
        for (int i = stilGonderilen; i < stiller.size(); i++) { if (S.length() > 0) S.append(','); jsonDize(S, stiller.get(i)); }
        int s0 = stilGonderilen;
        stilGonderilen = stiller.size();
        return "{\"g\":" + nesil + ",\"S0\":" + s0 + ",\"S\":[" + S + "],\"pw\":" + s.pw + ",\"ph\":" + s.ph + ",\"px\":" + px + ",\"pitch\":" + s.pitch + ",\"n\":" + n + ",\"B\":[" + B + "]}";
    }

    /** Kağıt: biçim tablosu (her kelimede tekrarlanmasın); yalnızca yeni biçimler gönderilir. */
    private static final java.util.List<String> stiller = new java.util.ArrayList<>();
    private static final Map<String, Integer> stilIndeks = new java.util.HashMap<>();
    private static int stilGonderilen;

    private static int stilNo(String st) {
        Integer i = stilIndeks.get(st);
        if (i == null) { i = stiller.size(); stiller.add(st); stilIndeks.put(st, i); }
        return i;
    }

    private static boolean tekSayfa(int y, int h, int pitch) { return y / pitch == (y + Math.max(0, h - 1)) / pitch; }

    /** Satırları topla: y öğenin üstüne göre (oy), ofsetler tabana göre göreli. */
    private static void gez(Document d, javax.swing.text.View v, java.awt.Shape a, int oy, StringBuilder L, StringBuilder I, int derinlik) {
        if (v == null || a == null || derinlik > 30) return;
        int n = v.getViewCount();
        if (n == 0) return;
        boolean satir = true;
        for (int i = 0; i < n; i++) if (v.getView(i).getViewCount() > 0) { satir = false; break; }
        java.awt.Rectangle r = a.getBounds();
        if (!satir) {
            for (int i = 0; i < n; i++) {
                java.awt.Shape c;
                try { c = v.getChildAllocation(i, a); } catch (Exception e) { continue; }
                gez(d, v.getView(i), c, oy, L, I, derinlik + 1);
            }
            return;
        }
        StringBuilder P = new StringBuilder();
        for (int i = 0; i < n; i++) {
            javax.swing.text.View y = v.getView(i);
            java.awt.Shape c;
            try { c = v.getChildAllocation(i, a); } catch (Exception e) { continue; }
            if (c == null) continue;
            java.awt.Rectangle q = c.getBounds();
            Element e = y.getElement();
            AttributeSet at = e.getAttributes();
            String en = e.getName();
            Object resim = ozellik(at, "imageData");
            if ("image".equals(en) || StyleConstants.getIcon(at) != null) {
                if (resim == null) resim = StyleConstants.getIcon(at);
                if (I.length() > 0) I.append(',');
                I.append('[').append(q.x).append(',').append(q.y - oy).append(',').append(q.width).append(',').append(q.height)
                        .append(",\"").append(resimNo(resim)).append("\"]");
                continue;
            }
            int s0 = y.getStartOffset(), s1 = y.getEndOffset();
            String t;
            try { t = d.getText(s0, s1 - s0); } catch (Exception ex) { continue; }
            t = t.replace("\n", "").replace("\t", "");
            if (t.isEmpty()) continue;
            if (P.length() > 0) P.append(',');
            P.append('[').append(q.x).append(',').append(q.width).append(',').append(s0 - taban).append(',');
            jsonDize(P, t);
            P.append(',');
            P.append(stilNo(stil(at, "field".equals(en)).replaceAll("font-size:[^;]*;", "")));
            P.append(',').append(Math.max(1, StyleConstants.getFontSize(at))).append(']');
        }
        if (L.length() > 0) L.append(',');
        L.append('[').append(r.y - oy).append(',').append(r.height).append(",[").append(P).append("]]");
    }

    private static void jsonDize(StringBuilder sb, String t) {
        sb.append('"');
        for (int i = 0; i < t.length(); i++) {
            char c = t.charAt(i);
            if (c == '"' || c == '\\') sb.append('\\').append(c);
            else if (c < 0x20) sb.append(String.format("\\u%04x", (int) c));
            else sb.append(c);
        }
        sb.append('"');
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
        sb.append("<p data-o=\"").append(e.getStartOffset() - taban).append("\" style=\"");
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
            sb.append("<img data-o=\"").append(s0 - taban).append("\" data-r=\"").append(no).append("\" style=\"");
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
            sb.append("<span data-o=\"").append(s0 - taban).append("\"");
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
