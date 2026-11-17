package uyaptermux;

import java.awt.AWTEvent;
import java.awt.Frame;
import java.awt.Toolkit;
import java.awt.event.KeyEvent;
import java.awt.event.WindowEvent;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import javax.swing.JOptionPane;
import javax.swing.SwingUtilities;
import javax.swing.UIManager;

/**
 * UYAP Dokuman Editoru icin Termux/Linux baslaticisi (ue.py tarafindan derlenip calistirilir).
 *
 * Ayarlar -D ile gelir (ue.py ~/.config/uyap-termux/ayarlar.ini'den okur):
 *   uyap.tema      acik | koyu | macos-acik | macos-koyu | sistem
 *   uyap.vurgu     #RRGGBB (FlatLaf vurgu rengi; bos = temanin kendi rengi)
 *   olcek          ue.py tum pencereyi sun.java2d.uiScale ile olcekler (serit, belge ve menuler birlikte; serit
 *                  kirpilmaz). FlatLaf kendi olcegini EKLEMEZ (cift olcekleme olmasin diye flatlaf.uiScale=1).
 *   uyap.dokunmatik true: kalin kaydirma cubuklari, daha genis tiklama alanlari
 *   uyap.kaydirma  true/false (akici kaydirma; calisirken F9 ile ac/kapa)
 *   uyap.hz        hedef kare hizi (varsayilan: ekranin yenileme hizi, en az 60)
 *   uyap.java.taklit  true: JDK 15+ uzerinde UYAP'in "Java 6-14 arasi olmali" kontrolunu acilis
 *                  ve imzalama (F7) oncesi kontrolu de gecer: oturum boyunca 11 gosterilir (jar degistirilmez;
 *                  gercek surum uyap.gercek.java.version'da). Acilista geri yazmak icin: uyap.java.taklit=acilis
 *   uyap.alt.menu  false (varsayilan): tek basina basilip birakilan Alt, editorun kisayol harflerini (KeyTips)
 *                  ve menu odagini ACMAZ; Alt+harf kombinasyonlari ve AltGr (Turkce @, €, ...) etkilenmez
 *   uyap.instance.dir  tek-ornek servisinin durum klasoru (bos = kapali)
 *   eimza.dir      Termux USB CCID koprusunun durum klasoru (bos = e-imza saglayicisi yuklenmez)
 *
 * Argumanlar: acilacak .udf/.usf dosyalari. .usf -> Sablon Editoru, digerleri -> Dokuman Editoru.
 */
public final class Baslatici {
    static final String UYAP_ANA = "tr.com.havelsan.uyap.system.editor.common.WPAppManager";
    static final String WM_SINIFI = "uyap-editor";

    private Baslatici() { }

    public static void main(String[] args) throws Exception {
        eimzaSaglayicisi();
        wmSinifi();
        String gercekSurum = javaSurumunuTaklitEt();
        temaUygula();
        if (Boolean.parseBoolean(System.getProperty("uyap.kaydirma", "true"))) {
            AkiciKaydirma.kur();
        }
        kisayollar();
        if (Boolean.parseBoolean(System.getProperty("uyap.dosya.modern", "true"))) DosyaSecici.kur();
        else DosyaSecici.turkceMetinler();
        if (!Boolean.parseBoolean(System.getProperty("uyap.alt.menu", "false"))) TekAltEngeli.kur();
        PdfYaziTipi.baslat();
        // UYAP surumu hem acilista hem her imzalamada (WPAppManager.a()) kontrol ediyor: kalici tutulur
        if (gercekSurum != null && "acilis".equalsIgnoreCase(System.getProperty("uyap.java.taklit"))) gercekSurumuGeriYaz(gercekSurum);

        String ilk = args.length > 0 ? args[0] : null;
        Class<?> c = Class.forName(UYAP_ANA);
        c.getMethod("main", String[].class).invoke(null, (Object) uyapArgumanlari(ilk));
        TekOrnek.baslat();
        for (int i = 1; i < args.length; i++) belgeAc(args[i]);
    }

    /** .usf sablon editorunde, digerleri dokuman editorunde acilir. */
    static String[] uyapArgumanlari(String yol) {
        if (yol == null || yol.isEmpty()) return new String[]{"getNewWPInstance", "EDITOR_TYPE_DOCUMENT"};
        String tur = yol.toLowerCase(Locale.ROOT).endsWith(".usf") ? "EDITOR_TYPE_TEMPLATE" : "EDITOR_TYPE_DOCUMENT";
        return new String[]{"getNewWPInstance", tur, yol};
    }

    /** Calisan editorde yeni pencere/belge acar (tek-ornek servisi ve ek argumanlar icin). */
    static void belgeAc(final String yol) {
        SwingUtilities.invokeLater(() -> {
            try {
                Class<?> c = Class.forName(UYAP_ANA);
                String[] a = uyapArgumanlari(yol);
                try {
                    // WPAppManager.a(String[]) yeni pencereyi mevcut JVM'de acar (main ise sureci yeniden kurar)
                    Method m = c.getDeclaredMethod("a", String[].class);
                    m.setAccessible(true);
                    m.invoke(null, (Object) a);
                } catch (NoSuchMethodException e) {
                    c.getMethod("main", String[].class).invoke(null, (Object) a);
                }
                Frame[] fr = Frame.getFrames();
                for (int i = fr.length - 1; i >= 0; i--) {
                    if (fr[i].isVisible()) {
                        if ((fr[i].getExtendedState() & Frame.ICONIFIED) != 0) fr[i].setExtendedState(Frame.NORMAL);
                        fr[i].toFront();
                        break;
                    }
                }
            } catch (Throwable t) {
                System.out.println("[UYAP] belge acilamadi: " + yol + " -> " + t);
            }
        });
    }

    // ------------------------------------------------------------------ e-imza
    private static void eimzaSaglayicisi() {
        String d = System.getProperty("eimza.dir");
        if (d == null || d.isEmpty()) return;
        try {
            Class<?> pc = Class.forName("eimza.TermuxCcidProvider");
            java.security.Provider p = (java.security.Provider) pc.getDeclaredConstructor().newInstance();
            java.security.Security.addProvider(p);
            System.setProperty("javax.smartcardio.TerminalFactory.DefaultType", "TermuxCCID");
            System.out.println("[EIMZA] Termux CCID saglayicisi etkin: " + d);
        } catch (Throwable t) {
            System.out.println("[EIMZA] saglayici yuklenemedi: " + t);
        }
    }

    // ------------------------------------------------------------------ X11 pencere sinifi
    /** XFCE/fluxbox gorev cubugunda pencereler "UYAP Editor" simgesiyle gruplansin (StartupWMClass). */
    private static void wmSinifi() {
        try {
            Toolkit.getDefaultToolkit();
            Class<?> xtk = Class.forName("sun.awt.X11.XToolkit");
            Field f = xtk.getDeclaredField("awtAppClassName");
            f.setAccessible(true);
            f.set(null, WM_SINIFI);
        } catch (Throwable ignored) {
            // X11 disi ya da --add-opens yok: onemsiz
        }
    }

    // ------------------------------------------------------------------ Java surum kontrolu
    static int javaAnaSurum(String v) {
        if (v == null || v.isEmpty()) return 0;
        if (v.startsWith("1.")) v = v.substring(2);
        int i = 0;
        while (i < v.length() && Character.isDigit(v.charAt(i))) i++;
        try { return Integer.parseInt(v.substring(0, i)); } catch (NumberFormatException e) { return 0; }
    }

    /** @return gercek surum (taklit yapildiysa) ya da null */
    private static String javaSurumunuTaklitEt() {
        String v = System.getProperty("java.version");
        if (javaAnaSurum(v) <= 14) return null;
        String t = System.getProperty("uyap.java.taklit", "true");
        if (!Boolean.parseBoolean(t) && !"acilis".equalsIgnoreCase(t)) return null;
        System.setProperty("uyap.gercek.java.version", v);
        System.setProperty("java.version", "11.0.99");
        System.out.println("[UYAP] Java " + v + ": editorun 6-14 surum kontrolu (acilis + imzalama) icin 11 gosteriliyor.");
        return v;
    }

    private static void gercekSurumuGeriYaz(final String v) {
        final boolean[] bitti = {false};
        Toolkit.getDefaultToolkit().addAWTEventListener(e -> {
            if (!bitti[0] && e.getID() == WindowEvent.WINDOW_OPENED) {
                bitti[0] = true;
                System.setProperty("java.version", v);
            }
        }, AWTEvent.WINDOW_EVENT_MASK);
    }

    // ------------------------------------------------------------------ tema / olcek
    static double olcekHesapla(String ayar, int dpi) {
        if (ayar != null && !ayar.isEmpty() && !"otomatik".equalsIgnoreCase(ayar)) {
            try {
                double d = Double.parseDouble(ayar.replace(',', '.'));
                return Math.max(0.75, Math.min(3.0, d));
            } catch (NumberFormatException ignored) { }
        }
        if (dpi <= 0) return 1.0;
        double d = Math.round(dpi / 96.0 * 4) / 4.0;   // 0.25'lik adimlar
        return Math.max(1.0, Math.min(3.0, d));
    }

    static String lafSinifi(String tema) {
        switch (tema == null ? "" : tema.toLowerCase(Locale.ROOT)) {
            case "koyu": return "com.formdev.flatlaf.FlatDarculaLaf";
            case "macos-acik": return "com.formdev.flatlaf.themes.FlatMacLightLaf";
            case "macos-koyu": return "com.formdev.flatlaf.themes.FlatMacDarkLaf";
            case "sistem": return null;
            default: return "com.formdev.flatlaf.FlatIntelliJLaf";
        }
    }

    private static void temaUygula() {
        String tema = System.getProperty("uyap.tema", "acik");
        String laf = lafSinifi(tema);
        boolean dokunmatik = Boolean.parseBoolean(System.getProperty("uyap.dokunmatik", "false"));
        int dpi = 0;
        try { dpi = Toolkit.getDefaultToolkit().getScreenResolution(); } catch (Throwable ignored) { }
        if (System.getProperty("flatlaf.uiScale") == null) System.setProperty("flatlaf.uiScale", "1");
        System.out.println("[UYAP] tema=" + tema + " olcek=" + System.getProperty("sun.java2d.uiScale", "1") + " (ekran " + dpi + " dpi)"
                + (dokunmatik ? " dokunmatik" : ""));
        if (laf == null) {
            try { UIManager.setLookAndFeel(UIManager.getSystemLookAndFeelClassName()); } catch (Exception ignored) { }
            return;
        }
        try {
            String vurgu = System.getProperty("uyap.vurgu", "").trim();
            if (vurgu.matches("#[0-9A-Fa-f]{6}")) {
                Map<String, String> ek = new HashMap<>();
                ek.put("@accentColor", vurgu);
                Class<?> fl = Class.forName("com.formdev.flatlaf.FlatLaf");
                fl.getMethod("setGlobalExtraDefaults", Map.class).invoke(null, ek);
            }
            UIManager.setLookAndFeel(laf);
            UIManager.put("Button.arc", 10);
            UIManager.put("Component.arc", 10);
            UIManager.put("ProgressBar.arc", 10);
            UIManager.put("TextComponent.arc", 8);
            UIManager.put("ScrollBar.showButtons", false);
            UIManager.put("ScrollBar.thumbArc", 999);
            UIManager.put("ScrollBar.thumbInsets", new java.awt.Insets(2, 2, 2, 2));
            UIManager.put("ScrollBar.width", dokunmatik ? 22 : 14);
            UIManager.put("TabbedPane.showTabSeparators", true);
            UIManager.put("Component.focusWidth", 1);
            UIManager.put("Table.showVerticalLines", false);
            UIManager.put("FileChooser.useSystemExtensionHiding", false);
            if (dokunmatik) {
                UIManager.put("Button.margin", new java.awt.Insets(6, 14, 6, 14));
                UIManager.put("Menu.margin", new java.awt.Insets(6, 8, 6, 8));
                UIManager.put("MenuItem.margin", new java.awt.Insets(6, 8, 6, 8));
                UIManager.put("Tree.rowHeight", 30);
                UIManager.put("Table.rowHeight", 30);
            }
        } catch (Throwable t) {
            System.out.println("[UYAP] FlatLaf yuklenemedi (" + t + "); sistem gorunumu kullaniliyor.");
            try { UIManager.setLookAndFeel(UIManager.getSystemLookAndFeelClassName()); } catch (Exception ignored) { }
        }
    }

    // ------------------------------------------------------------------ kisayollar
    /** F9: akici kaydirmayi ac/kapa. Ctrl+Shift+F12: UYAP-Termux hakkinda. */
    private static void kisayollar() {
        Toolkit.getDefaultToolkit().addAWTEventListener(ev -> {
            if (ev.getID() != KeyEvent.KEY_PRESSED) return;
            KeyEvent k = (KeyEvent) ev;
            if (k.getKeyCode() == KeyEvent.VK_F9 && k.getModifiersEx() == 0) {
                boolean acik = AkiciKaydirma.degistir();
                System.out.println("[UYAP] akici kaydirma " + (acik ? "ACIK" : "KAPALI"));
                k.consume();
            } else if (k.getKeyCode() == KeyEvent.VK_F11 && k.isControlDown() && k.isShiftDown()) {
                k.consume();
                Tani.yaz();
            } else if (k.getKeyCode() == KeyEvent.VK_F12 && k.isControlDown() && k.isShiftDown()) {
                k.consume();
                SwingUtilities.invokeLater(() -> JOptionPane.showMessageDialog(null,
                        "<html><b>UYAP-Termux Pro</b><br>Java " + System.getProperty("uyap.gercek.java.version",
                                System.getProperty("java.version")) + "<br>Akici kaydirma: "
                                + (AkiciKaydirma.acikMi() ? "acik" : "kapali") + " (F9)<br>"
                                + "Ayarlar: ~/.config/uyap-termux/ayarlar.ini</html>",
                        "UYAP-Termux", JOptionPane.INFORMATION_MESSAGE));
            }
        }, AWTEvent.KEY_EVENT_MASK);
    }
}
