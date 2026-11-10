package com.agy.uyapacici;

import android.content.Context;

import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.jar.JarFile;
import java.util.jar.Manifest;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * Resmi Adalet E-İmza uygulamasını Adalet Bakanlığı'nın KENDİ sunucusundan indirir ve kurar.
 * UdeMobile resmi uygulamayı dağıtmaz; telefon onu cdn.uyap.gov.tr'den alır (yalnızca bu adresten, HTTPS).
 *
 * Sürüm bilgisi: https://cdn.uyap.gov.tr/framework/public/latest.json (resmi uygulamanın kendi güncelleme adresi).
 * Paket: macOS (aarch64) .zip içindeki "eimza-tray-*.jar" (tüm platformlarda aynı Java uygulaması; zip Android'de
 * ek kütüphane olmadan açılabilir). Elle seçilen .zip / .jar da kabul edilir.
 */
public final class AdaletKurulum {
    public static final String SURUM_ADRESI = "https://cdn.uyap.gov.tr/framework/public/latest.json";
    private static final String IZINLI_ON_EK = "https://cdn.uyap.gov.tr/";

    public interface Ilerleme { void yaz(String s); }

    private AdaletKurulum() { }

    public static File dizin(Context c) { return new File(c.getFilesDir(), "adalet"); }

    public static File jarDosyasi(Context c) { return new File(dizin(c), "eimza-tray.jar"); }

    public static String kuruluSurum(Context c) {
        File f = new File(dizin(c), "surum.txt");
        try { return f.exists() ? AdaletServisi.okuMetin(f).trim() : null; } catch (IOException e) { return null; }
    }

    /** {sürüm, indirme adresi, değişiklik notu} */
    public static String[] sonSurum() throws Exception {
        JSONObject j = new JSONObject(new String(indirHepsi(SURUM_ADRESI, 1 << 20), "UTF-8"));
        JSONObject r = j.getJSONObject("releases");
        JSONObject m = r.optJSONObject("mac_arm");
        if (m == null) m = r.getJSONObject("mac_intel");
        String url = m.getString("downloadUrl");
        if (!url.startsWith(IZINLI_ON_EK)) throw new IOException("Beklenmeyen indirme adresi: " + url);
        return new String[]{m.optString("latestVersion", "?"), url, m.optString("changelog", "")};
    }

    /** İnternetten (Adalet'in sunucusu) indirip kurar. */
    public static String indirKur(Context c, Ilerleme ilerleme0) throws Exception {
        Tani.baglam(c);
        final Ilerleme ilerleme = m -> { Tani.yaz("kurulum", m); ilerleme0.yaz(m); };
        String[] s = sonSurum();
        Tani.yaz("kurulum", "son sürüm " + s[0] + " · " + s[1]);
        ilerleme.yaz("Adalet E-İmza " + s[0] + " indiriliyor (cdn.uyap.gov.tr, ~80 MB)…");
        HttpURLConnection h = (HttpURLConnection) new URL(s[1]).openConnection();
        h.setConnectTimeout(20000);
        h.setReadTimeout(60000);
        h.setInstanceFollowRedirects(false);
        Tani.yaz("kurulum", "HTTP " + h.getResponseCode() + " · boyut=" + h.getContentLength());
        if (h.getResponseCode() != 200) throw new IOException("İndirme başarısız: HTTP " + h.getResponseCode());
        long toplam = h.getContentLength();
        try (InputStream in = new SayacliAkis(h.getInputStream(), toplam, ilerleme)) {
            return zipdenKur(c, in);
        } finally {
            h.disconnect();
        }
    }

    /** Seçilen dosyadan kurar: .zip (macOS paketi) ya da doğrudan .jar. */
    public static String dosyadanKur(Context c, InputStream in, String ad) throws Exception {
        if (ad != null && ad.toLowerCase().endsWith(".jar")) {
            File gecici = new File(dizin(c), "eimza-tray.jar.tmp");
            dizin(c).mkdirs();
            try (OutputStream o = new FileOutputStream(gecici)) { kopyala(in, o); }
            return yerlestir(c, gecici);
        }
        return zipdenKur(c, in);
    }

    private static String zipdenKur(Context c, InputStream in) throws Exception {
        dizin(c).mkdirs();
        File gecici = new File(dizin(c), "eimza-tray.jar.tmp");
        boolean bulundu = false;
        try (ZipInputStream z = new ZipInputStream(new BufferedInputStream(in, 1 << 16))) {
            ZipEntry e;
            while ((e = z.getNextEntry()) != null) {
                String ad = e.getName();
                String kisa = ad.substring(ad.lastIndexOf('/') + 1);
                if (!e.isDirectory() && !ad.contains("__MACOSX") && kisa.startsWith("eimza-tray") && kisa.endsWith(".jar")) {
                    try (OutputStream o = new FileOutputStream(gecici)) { kopyala(z, o); }
                    bulundu = true;
                    break;
                }
            }
        }
        if (!bulundu) throw new IOException("Pakette Adalet E-İmza uygulaması (eimza-tray-*.jar) bulunamadı.");
        return yerlestir(c, gecici);
    }

    /** Jar'ı doğrular (Spring Boot + Adalet E-İmza ana sınıfı) ve yerine koyar. Döner: sürüm. */
    private static String yerlestir(Context c, File gecici) throws IOException {
        String surum;
        try (JarFile j = new JarFile(gecici)) {
            Manifest m = j.getManifest();
            String bas = m != null ? m.getMainAttributes().getValue("Start-Class") : null;
            if (bas == null || !bas.startsWith("tr.gov.adalet.service.framework.adalet.eimza.eimzatray")) {
                gecici.delete();
                throw new IOException("Seçilen dosya resmi Adalet E-İmza uygulaması değil.");
            }
            surum = m.getMainAttributes().getValue("Implementation-Version");
            Tani.yaz("kurulum", "jar doğrulandı: " + bas + " sürüm " + surum + " (" + gecici.length() + " bayt)");
        }
        File hedef = jarDosyasi(c);
        if (hedef.exists() && !hedef.delete()) throw new IOException("Eski sürüm silinemedi");
        if (!gecici.renameTo(hedef)) throw new IOException("Kurulum dosyası yerleştirilemedi");
        try (OutputStream o = new FileOutputStream(new File(dizin(c), "surum.txt"))) {
            o.write((surum == null ? "?" : surum).getBytes("UTF-8"));
        }
        return surum;
    }

    // ------------------------------------------------------------------------------------ yardımcılar
    static byte[] indirHepsi(String adres, int enCok) throws IOException {
        if (!adres.startsWith(IZINLI_ON_EK)) throw new IOException("İzin verilmeyen adres");
        HttpURLConnection h = (HttpURLConnection) new URL(adres).openConnection();
        h.setConnectTimeout(15000);
        h.setReadTimeout(30000);
        try (InputStream in = h.getInputStream()) {
            byte[] b = AdaletServisi.okuHepsi(in);
            if (b.length > enCok) throw new IOException("cevap çok büyük");
            return b;
        } finally {
            h.disconnect();
        }
    }

    static void kopyala(InputStream in, OutputStream o) throws IOException {
        byte[] b = new byte[1 << 16];
        int n;
        while ((n = in.read(b)) > 0) o.write(b, 0, n);
    }

    private static final class SayacliAkis extends java.io.FilterInputStream {
        private final long toplam;
        private final Ilerleme ilerleme;
        private long okunan;
        private int sonYuzde = -1;

        SayacliAkis(InputStream in, long toplam, Ilerleme ilerleme) {
            super(in);
            this.toplam = toplam;
            this.ilerleme = ilerleme;
        }

        @Override public int read(byte[] b, int off, int len) throws IOException {
            int n = super.read(b, off, len);
            if (n > 0) say(n);
            return n;
        }

        @Override public int read() throws IOException {
            int n = super.read();
            if (n >= 0) say(1);
            return n;
        }

        private void say(int n) {
            okunan += n;
            if (toplam > 0) {
                int y = (int) (okunan * 100 / toplam);
                if (y != sonYuzde && y % 5 == 0) {
                    sonYuzde = y;
                    ilerleme.yaz("İndiriliyor… %" + y + " (" + (okunan >> 20) + "/" + (toplam >> 20) + " MB)");
                }
            }
        }
    }
}
