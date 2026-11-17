package com.agy.uyapacici;

import android.content.Context;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * Hukuk Asistanı sunucusu (asistan/sunucu.py) Android'de — TERMUX OLMADAN.
 *
 * UYAP Mobil'in Java için kullandığı yöntemin aynısı: APK'daki assets/asistan/asistan-rt-arm64.zip
 * (scripts/asistan_android_hazirla.py) içinde standart Linux aarch64 CPython, manylinux tekerlekleri ve
 * Termux glibc'si bulunur; Python bu glibc'nin yükleyicisiyle (ld-linux-aarch64.so.1) doğrudan başlatılır.
 * targetSdkVersion 28 olduğu için uygulama dizininden çalıştırma serbesttir.
 *
 * Sunucu yalnızca 127.0.0.1:8765'e bağlanır; eşleştirme anahtarı uygulama verisinde üretilir ve editörün
 * JS köprüsüne (asistanBaglanti) verilir — kullanıcı bir şey girmez.
 * Android'de tarayıcı otomasyonu yoktur: UETS / UYAP indirme görevleri masaüstü uygulamasında çalışır
 * (sunucu bunları "kullanılamaz" olarak bildirir). Ajanda, evrak kataloğu, A4 ve defter burada çalışır.
 */
final class AsistanServisi {
    static final int PORT = 8765;
    private static final String VARLIK = "asistan/asistan-rt-arm64.zip";
    private static final String PY = "python3.12";
    private static Process surec;

    private AsistanServisi() { }

    static File kok(Context c) { return new File(c.getFilesDir(), "asistan"); }
    static File rt(Context c) { return new File(kok(c), "rt"); }
    static File veri(Context c) { return new File(kok(c), "veri"); }

    /** Pakette asistan çalışma zamanı var mı (eski/küçük derlemelerde olmayabilir). */
    static boolean pakette(Context c) {
        try (InputStream in = c.getAssets().open("asistan/surum.txt")) { return in != null; } catch (IOException e) { return false; }
    }

    /** Çalışma zamanını sürüm değişince açar (UyapMobil.hazirla ile aynı desen). */
    static synchronized void hazirla(Context c) throws IOException {
        File k = kok(c);
        k.mkdirs();
        String surum = new String(AdaletServisi.okuHepsi(c.getAssets().open("asistan/surum.txt")), StandardCharsets.UTF_8).trim();
        File damga = new File(k, "rt.surum");
        File ld = new File(rt(c), "glibc/ld-linux-aarch64.so.1");
        if (damga.isFile() && AdaletServisi.okuMetin(damga).trim().equals(surum) && ld.canExecute()) return;
        long t0 = System.currentTimeMillis();
        File gecici = new File(k, "rt.yeni");
        AdaletServisi.silOzyinelemeli(gecici);
        gecici.mkdirs();
        try (ZipInputStream z = new ZipInputStream(new BufferedInputStream(c.getAssets().open(VARLIK), 1 << 16))) {
            ZipEntry e;
            byte[] tampon = new byte[1 << 16];
            while ((e = z.getNextEntry()) != null) {
                String ad = e.getName();
                if (ad.contains("..")) continue;
                File f = new File(gecici, ad);
                if (e.isDirectory()) { f.mkdirs(); continue; }
                f.getParentFile().mkdirs();
                try (OutputStream o = new FileOutputStream(f)) {
                    int n;
                    while ((n = z.read(tampon)) > 0) o.write(tampon, 0, n);
                }
            }
        }
        new File(gecici, "glibc/ld-linux-aarch64.so.1").setExecutable(true, true);
        new File(gecici, "python/bin/" + PY).setExecutable(true, true);
        AdaletServisi.silOzyinelemeli(rt(c));
        if (!gecici.renameTo(rt(c))) throw new IOException("asistan çalışma ortamı yerleştirilemedi");
        try (OutputStream o = new FileOutputStream(damga)) { o.write(surum.getBytes(StandardCharsets.UTF_8)); }
        Tani.yaz("asistan", "çalışma ortamı açıldı (" + (System.currentTimeMillis() - t0) + " ms)");
    }

    /** Eşleştirme anahtarı: ilk açılışta üretilir, uygulama verisinde saklanır. */
    static synchronized String anahtar(Context c) throws IOException {
        File f = new File(kok(c), "anahtar");
        if (f.isFile()) {
            String k = AdaletServisi.okuMetin(f).trim();
            if (!k.isEmpty()) return k;
        }
        byte[] b = new byte[24];
        new SecureRandom().nextBytes(b);
        String k = android.util.Base64.encodeToString(b, android.util.Base64.URL_SAFE | android.util.Base64.NO_WRAP | android.util.Base64.NO_PADDING);
        kok(c).mkdirs();
        try (OutputStream o = new FileOutputStream(f)) { o.write(k.getBytes(StandardCharsets.UTF_8)); }
        return k;
    }

    /** Android'deki başlatma komutu: scripts/asistan_android_hazirla.py android_komutu() ile AYNI. */
    static List<String> pythonKomutu(Context c) {
        File r = rt(c);
        List<String> a = new ArrayList<>();
        a.add(new File(r, "glibc/ld-linux-aarch64.so.1").getAbsolutePath());
        a.add("--library-path");
        a.add(new File(r, "glibc").getAbsolutePath() + ":" + new File(r, "python/lib").getAbsolutePath());
        a.add(new File(r, "python/bin/" + PY).getAbsolutePath());
        return a;
    }

    /** Process.isAlive() API 26 ister; minSdk 21 için exitValue() ile denetlenir. */
    private static boolean yasiyor(Process p) {
        if (p == null) return false;
        try { p.exitValue(); return false; } catch (IllegalThreadStateException e) { return true; }
    }

    static boolean ayakta() {
        try {
            HttpURLConnection h = (HttpURLConnection) new URL("http://127.0.0.1:" + PORT + "/api/merhaba").openConnection();
            h.setConnectTimeout(800);
            h.setReadTimeout(1500);
            try (InputStream in = h.getInputStream()) {
                return new String(AdaletServisi.okuHepsi(in), StandardCharsets.UTF_8).contains("CanEditor Hukuk Asistan");
            } finally {
                h.disconnect();
            }
        } catch (IOException e) {
            return false;
        }
    }

    private static synchronized void baslat(Context c, String anahtar) throws IOException {
        if (yasiyor(surec)) return;
        File r = rt(c), v = veri(c), tmp = new File(c.getCacheDir(), "asistan-tmp");
        v.mkdirs();
        tmp.mkdirs();
        List<String> a = pythonKomutu(c);
        a.add(new File(r, "app/sunucu.py").getAbsolutePath());
        a.add("--port");
        a.add(String.valueOf(PORT));
        ProcessBuilder pb = new ProcessBuilder(a);
        pb.directory(v);
        Map<String, String> env = pb.environment();
        env.remove("LD_PRELOAD");
        env.remove("LD_LIBRARY_PATH");
        env.put("HOME", v.getAbsolutePath());
        env.put("TMPDIR", tmp.getAbsolutePath());
        env.put("LANG", "C.UTF-8");
        env.put("LC_ALL", "C.UTF-8");
        env.put("PYTHONHOME", new File(r, "python").getAbsolutePath());
        env.put("PYTHONPATH", new File(r, "site").getAbsolutePath());
        env.put("PYTHONDONTWRITEBYTECODE", "1");
        env.put("PYTHONIOENCODING", "utf-8");
        // CPython'un OpenSSL'i Android sertifika deposunu bilmez: certifi paketi kullanılır
        env.put("SSL_CERT_FILE", new File(r, "site/certifi/cacert.pem").getAbsolutePath());
        env.put("CANASISTAN_VERI", v.getAbsolutePath());
        env.put("CANASISTAN_ANAHTAR", anahtar);
        env.put("CANASISTAN_ANDROID", "1");
        env.put("UYAP_VERI_DIZINI", new File(v, "uyap").getAbsolutePath());
        env.put("CANASISTAN_PYTHON_KOMUT", new JSONArray(pythonKomutu(c)).toString());
        pb.redirectErrorStream(true);
        pb.redirectOutput(new File(v, "sunucu.log"));
        surec = pb.start();
        Tani.yaz("asistan", "sunucu başlatıldı");
    }

    /**
     * Editörün JS köprüsü bunu çağırır (iş parçacığı: JavaBridge, UI değil — beklemek serbesttir).
     * Dönüş: {"port":8765,"anahtar":"…"} ya da {"hata":"…"}.
     */
    static String baglanti(Context c) {
        JSONObject j = new JSONObject();
        try {
            if (!pakette(c)) {
                j.put("hata", "Bu APK derlemesinde asistan çalışma ortamı yok.");
                return j.toString();
            }
            String k = anahtar(c);
            if (!ayakta()) {
                hazirla(c);
                baslat(c, k);
                long son = System.currentTimeMillis() + 45000;   // ilk açılışta Python ~birkaç sn
                while (!ayakta()) {
                    if (surec != null && !yasiyor(surec)) {
                        j.put("hata", "Asistan sunucusu kapandı (kod " + surec.exitValue() + "). Ayrıntı: " + new File(veri(c), "sunucu.log"));
                        return j.toString();
                    }
                    if (System.currentTimeMillis() > son) {
                        j.put("hata", "Asistan sunucusu yanıt vermedi.");
                        return j.toString();
                    }
                    Thread.sleep(250);
                }
            }
            j.put("port", PORT);
            j.put("anahtar", k);
        } catch (Exception e) {
            Tani.yaz("asistan", "bağlantı hatası: " + e);
            try { j.put("hata", String.valueOf(e.getMessage())); } catch (Exception ignored) { }
        }
        return j.toString();
    }
}
