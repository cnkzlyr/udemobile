package uyaptermux;

import java.io.File;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * PDF disa aktariminda Times New Roman duzeltmesi (uyap-editor-modern PdfFontFixer'dan uyarlandi).
 *
 * UYAP'in ic iText yazi tipi eslemecisi (tr.com.havelsan.uyap.system.editor.b.b) Linux/Termux'ta yazi tipi
 * klasorlerini taramadigi icin Times New Roman bulunamaz ve PDF'e Helvetica olarak cikar. Bu sinif
 * eslemeciye Termux ve kullanici yazi tipi klasorlerini kaydeder, Times takma adlarini en yakin serif
 * yazi tipine (Times New Roman > Liberation Serif > Tinos > DejaVu Serif ...) baglar.
 * Yansima (reflection) ile calisir; editor surumu degisip siniflar bulunamazsa sessizce devre disi kalir.
 */
final class PdfYaziTipi {
    private static volatile boolean basladi;

    private PdfYaziTipi() { }

    static void baslat() {
        if (basladi) return;
        basladi = true;
        Thread t = new Thread(() -> {
            try {
                Thread.sleep(400);   // ilk pencerenin acilisini geciktirme
                duzelt();
            } catch (Throwable ignored) { }
        }, "uyap-pdf-yazitipi");
        t.setDaemon(true);
        t.setPriority(Thread.NORM_PRIORITY - 1);
        t.start();
    }

    static List<String> klasorler() {
        List<String> d = new ArrayList<>();
        String home = System.getProperty("user.home", "");
        String gercekHome = System.getenv("HOME");   // editor -Duser.home=Download ile calisir
        String prefix = System.getenv("PREFIX");
        if (prefix != null && !prefix.isEmpty()) d.add(prefix + "/share/fonts");
        d.add("/data/data/com.termux/files/usr/share/fonts");
        for (String h : new String[]{gercekHome, home}) {
            if (h == null || h.isEmpty()) continue;
            d.add(h + "/.fonts");
            d.add(h + "/.local/share/fonts");
        }
        d.add("/usr/share/fonts");
        d.add("/usr/local/share/fonts");
        d.add("/system/fonts");
        return d;
    }

    @SuppressWarnings("unchecked")
    private static void duzelt() throws Exception {
        Class<?> b;
        try {
            b = Class.forName("tr.com.havelsan.uyap.system.editor.b.b");
        } catch (ClassNotFoundException e) {
            return;
        }
        Object eslemeci = null;
        for (Method m : b.getDeclaredMethods()) {
            if (Modifier.isStatic(m.getModifiers()) && m.getParameterCount() == 0) {
                String r = m.getReturnType().getName();
                if (r.contains("editor.b") || r.contains("FontMapper")) {
                    m.setAccessible(true);
                    eslemeci = m.invoke(null);
                    break;
                }
            }
        }
        if (eslemeci == null) return;
        Method tara = null;
        for (Method m : eslemeci.getClass().getMethods()) {
            if (m.getParameterCount() == 1 && m.getParameterTypes()[0] == String.class && m.getReturnType() == int.class) {
                tara = m;
                break;
            }
        }
        if (tara == null) return;
        int toplam = 0;
        for (String k : klasorler()) {
            File f = new File(k);
            if (f.isDirectory()) {
                try { toplam += (Integer) tara.invoke(eslemeci, f.getAbsolutePath()); } catch (Throwable ignored) { }
            }
        }
        Map<String, String> takma = null;
        Map<String, Object> yazitipleri = null;
        for (Field f : eslemeci.getClass().getDeclaredFields()) {
            if (!Map.class.isAssignableFrom(f.getType())) continue;
            f.setAccessible(true);
            Map<?, ?> m = (Map<?, ?>) f.get(eslemeci);
            if (m == null || m.isEmpty()) continue;
            if (m.values().iterator().next() instanceof String) takma = (Map<String, String>) m;
            else yazitipleri = (Map<String, Object>) m;
        }
        String hedef = timesKarsiligi(yazitipleri);
        if (takma != null && hedef != null) {
            for (String ad : new String[]{"Times New Roman", "TimesRoman", "Times-Roman", "Times"}) takma.putIfAbsent(ad, hedef);
        }
        System.out.println("[UYAP] PDF yazi tipleri: " + toplam + " yazi tipi kaydedildi; Times -> " + (hedef == null ? "(bulunamadi)" : hedef));
    }

    static String timesKarsiligi(Map<String, ?> yazitipleri) {
        if (yazitipleri == null) return null;
        String[] tercih = {"Times New Roman", "TimesNewRomanPSMT", "Liberation Serif", "Tinos", "Nimbus Roman",
                "FreeSerif", "DejaVu Serif", "Noto Serif"};
        for (String t : tercih) {
            for (String k : yazitipleri.keySet()) {
                if (k.equalsIgnoreCase(t)) return k;
            }
        }
        return null;
    }
}
