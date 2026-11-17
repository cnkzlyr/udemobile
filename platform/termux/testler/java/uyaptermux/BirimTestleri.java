package uyaptermux;

import java.io.File;
import java.nio.file.Files;
import java.util.HashMap;
import java.util.Map;

/** Basit birim testleri (JUnit gerekmez):  bash testler/java_testleri.sh */
public final class BirimTestleri {
    private static int hata = 0;

    private static void esit(Object beklenen, Object gercek, String ad) {
        boolean ok = beklenen == null ? gercek == null : beklenen.equals(gercek);
        System.out.println((ok ? "  ok   " : "  HATA ") + ad + (ok ? "" : "  beklenen=" + beklenen + " gercek=" + gercek));
        if (!ok) hata++;
    }

    public static void main(String[] a) throws Exception {
        // .usf -> sablon editoru
        esit("EDITOR_TYPE_TEMPLATE", Baslatici.uyapArgumanlari("/x/Sablon.USF")[1], ".usf sablon");
        esit("EDITOR_TYPE_DOCUMENT", Baslatici.uyapArgumanlari("/x/a.udf")[1], ".udf dokuman");
        esit(2, Baslatici.uyapArgumanlari(null).length, "bos belge");
        // java surum ayristirma (UYAP'in a() metoduyla ayni kural)
        esit(8, Baslatici.javaAnaSurum("1.8.0_402"), "1.8");
        esit(11, Baslatici.javaAnaSurum("11.0.22"), "11");
        esit(21, Baslatici.javaAnaSurum("21.0.12.1"), "21");
        esit(17, Baslatici.javaAnaSurum("17-internal"), "17-internal");
        // olcek
        esit(1.2, Baslatici.olcekHesapla("1.2", 96), "elle 1.2");
        esit(1.5, Baslatici.olcekHesapla("1,5", 96), "virgullu");
        esit(3.0, Baslatici.olcekHesapla("9", 96), "ust sinir");
        esit(1.5, Baslatici.olcekHesapla("otomatik", 144), "otomatik 144 dpi");
        esit(1.0, Baslatici.olcekHesapla("otomatik", 72), "otomatik alt sinir");
        esit(1.0, Baslatici.olcekHesapla("otomatik", 0), "dpi bilinmiyor");
        // tema
        esit("com.formdev.flatlaf.FlatDarculaLaf", Baslatici.lafSinifi("koyu"), "koyu");
        esit("com.formdev.flatlaf.themes.FlatMacLightLaf", Baslatici.lafSinifi("macos-acik"), "macos");
        esit(null, Baslatici.lafSinifi("sistem"), "sistem");
        esit("com.formdev.flatlaf.FlatIntelliJLaf", Baslatici.lafSinifi("bilinmeyen"), "varsayilan");
        // tek ornek: jetonsuz/yanlis jetonlu istek reddedilir
        esit("ERR", TekOrnek.isle(null, "abc"), "bos satir");
        esit("ERR", TekOrnek.isle("yanlis\tPING", "abc"), "yanlis jeton");
        esit("OK", TekOrnek.isle("abc\tPING", "abc"), "PING");
        esit("ERR", TekOrnek.isle("abc\tOPEN\t", "abc"), "bos yol");
        esit("ERR", TekOrnek.isle("abc\tSIL\t/x", "abc"), "bilinmeyen komut");
        // PDF yazi tipi karsiligi
        Map<String, Object> y = new HashMap<>();
        y.put("DejaVu Serif", 1);
        y.put("liberation serif", 2);
        esit("liberation serif", PdfYaziTipi.timesKarsiligi(y), "Liberation > DejaVu");
        y.put("Times New Roman", 3);
        esit("Times New Roman", PdfYaziTipi.timesKarsiligi(y), "gercek Times");
        esit(null, PdfYaziTipi.timesKarsiligi(new HashMap<>()), "hicbiri");
        // INI: yorumlar ve sira korunur, yeni anahtar dogru bolume girer
        File f = File.createTempFile("ayar", ".ini");
        Files.write(f.toPath(), "# yorum\n\n[arayuz]\ntema = acik   ; acik | koyu\nolcek = 1.2\nvurgu = #C0392B\n\n[java]\nyol = \n".getBytes("UTF-8"));
        KontrolMerkezi.Ini ini = KontrolMerkezi.Ini.oku(f);
        esit("acik", ini.al("arayuz", "tema", "?"), "ini oku");
        esit("?", ini.al("arayuz", "yok", "?"), "ini varsayilan");
        esit("#C0392B", ini.al("arayuz", "vurgu", "?"), "ini renk");
        ini.koy("arayuz", "tema", "koyu");
        ini.koy("arayuz", "dokunmatik", "evet");
        ini.koy("eimza", "aktif", "hayir");
        ini.yaz(f);
        String s = new String(Files.readAllBytes(f.toPath()), "UTF-8");
        esit(true, s.startsWith("# yorum\n"), "yorum korundu");
        esit(true, s.contains("[arayuz]\ntema = koyu\nolcek = 1.2\nvurgu = #C0392B\ndokunmatik = evet\n\n[java]"), "bolum ici ekleme");
        esit(true, s.endsWith("[eimza]\naktif = hayir\n"), "yeni bolum");
        f.delete();

        // Tek Alt engeli
        java.lang.reflect.Constructor<TekAltEngeli> kc = TekAltEngeli.class.getDeclaredConstructor();
        kc.setAccessible(true);
        TekAltEngeli t = kc.newInstance();
        int P = java.awt.event.KeyEvent.KEY_PRESSED, R = java.awt.event.KeyEvent.KEY_RELEASED;
        int ALT = java.awt.event.KeyEvent.VK_ALT, SOL = java.awt.event.KeyEvent.KEY_LOCATION_LEFT;
        int SAG = java.awt.event.KeyEvent.KEY_LOCATION_RIGHT, D = java.awt.event.KeyEvent.VK_D;
        esit(true, t.isle(P, ALT, SOL, false), "tek Alt basilisi yutulur");
        esit(true, t.isle(R, ALT, SOL, false), "tek Alt birakilisi yutulur");
        t.isle(P, ALT, SOL, false);
        esit(false, t.isle(P, D, 1, false), "Alt+D: D gecer");
        esit(false, t.isle(R, D, 1, false), "Alt+D: D birakilisi gecer");
        t.isle(R, ALT, SOL, false);
        esit(false, t.isle(P, ALT, SAG, false), "sag Alt (AltGr) gecer");
        esit(false, t.isle(R, ALT, SAG, false), "sag Alt birakilisi gecer");
        esit(false, t.isle(P, java.awt.event.KeyEvent.VK_ALT_GRAPH, 1, false), "VK_ALT_GRAPH gecer");
        esit(false, t.isle(P, ALT, SOL, true), "Ctrl+Alt gecer");
        esit(false, t.isle(P, java.awt.event.KeyEvent.VK_A, 1, false), "normal harf gecer");

        System.out.println(hata == 0 ? "HEPSI GECTI" : hata + " TEST BASARISIZ");
        System.exit(hata == 0 ? 0 : 1);
    }
}
