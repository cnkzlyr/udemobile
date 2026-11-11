package com.agy.uyapacici;

import android.app.ActivityManager;
import android.content.Context;
import android.net.Uri;

import org.tukaani.xz.XZInputStream;

import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * UYAP Mobil: resmi UYAP Doküman Editörü'nü Android'de Termux / X11 / Termux:API OLMADAN çalıştırır.
 *
 * Çalışma zamanı (APK içinde, assets/uyapmobil — scripts/uyapmobil_hazirla.py üretir):
 *   rt/glibc/ld-linux-aarch64.so.1 + glibc/X11 kitaplıkları (Termux glibc deposu, Android için derlenmiş)
 *   rt/jre (AdoptOpenJDK 14.0.2 aarch64, jlink) · rt/bin/uyapjava (libjvm.so'yu doğrudan yükler) · rt/fonts (Liberation)
 *   awt-patch14.jar (Caciocavallo: X sunucusu yerine bellekte ekran) · uyapmobil-kopru.jar (ekran + dokunma/klavye köprüsü)
 *   uyap-modern.jar (uyap-editor-modern: akıcı kaydırma, PDF yazı tipi düzeltmesi)
 *
 * Program glibc bağlayıcısıyla başlatılır:  ld-linux-aarch64.so.1 --library-path ... uyapjava libjvm.so [JVM seçenekleri] -- WPAppManager ...
 *
 * Resmi editör DAĞITILMAZ: ilk açılışta YALNIZCA rayp.adalet.gov.tr'den (resmi Linux paketi) indirilir ya da kullanıcının
 * seçtiği aynı paketten (.zip / .deb) kurulur; paketteki usr/share/UYAPEditor/*.jar dosyaları çıkarılır.
 */
public final class UyapMobil {
    public static final String EDITOR_ADRESI = "https://rayp.adalet.gov.tr/resimler/2/dosya/uyapeditor_5.4.20_amd64.zip";
    private static final String IZINLI_ON_EK = "https://rayp.adalet.gov.tr/";
    static final String ANA_SINIF = "tr.com.havelsan.uyap.system.editor.common.WPAppManager";

    public interface Ilerleme { void yaz(String m); }

    public static File kok(Context c) { return new File(c.getFilesDir(), "uyapmobil"); }
    static File rt(Context c) { return new File(kok(c), "rt"); }
    public static File editorDizini(Context c) { return new File(kok(c), "editor"); }
    public static File ev(Context c) { return new File(kok(c), "ev"); }
    public static File belgeler(Context c) { return new File(kok(c), "belgeler"); }
    static File ekranDosyasi(Context c) { return new File(kok(c), "ekran.bin"); }
    public static File gunluk(Context c) { return new File(kok(c), "editor.log"); }
    public static File yaziTipleri(Context c) { return new File(ev(c), ".fonts"); }

    public static boolean editorKurulu(Context c) {
        return new File(editorDizini(c), "editor_lib.jar").isFile() && new File(editorDizini(c), "editor_lib2.jar").isFile();
    }

    public static String editorSurumu(Context c) {
        File f = new File(editorDizini(c), "surum.txt");
        try { return f.isFile() ? AdaletServisi.okuMetin(f).trim() : ""; } catch (IOException e) { return ""; }
    }

    // ------------------------------------------------------------------------------------ çalışma zamanı
    /** assets/uyapmobil içeriğini sürüm değişince açar. */
    static synchronized void hazirla(Context c, Ilerleme il) throws IOException {
        File k = kok(c);
        k.mkdirs();
        String surum = new String(AdaletServisi.okuHepsi(c.getAssets().open("uyapmobil/surum.txt")), StandardCharsets.UTF_8).trim();
        File damga = new File(k, "rt.surum");
        File ld = new File(rt(c), "glibc/ld-linux-aarch64.so.1");
        if (damga.isFile() && AdaletServisi.okuMetin(damga).trim().equals(surum) && ld.canExecute()) return;
        il.yaz("UYAP Editör çalışma ortamı hazırlanıyor (Java 14, bir kez, ~20 sn)…");
        long t0 = System.currentTimeMillis();
        File gecici = new File(k, "rt.yeni");
        AdaletServisi.silOzyinelemeli(gecici);
        gecici.mkdirs();
        try (ZipInputStream z = new ZipInputStream(new BufferedInputStream(c.getAssets().open("uyapmobil/rt-arm64.zip"), 1 << 16))) {
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
        new File(gecici, "bin/uyapjava").setExecutable(true, true);
        AdaletServisi.silOzyinelemeli(rt(c));
        if (!gecici.renameTo(rt(c))) throw new IOException("çalışma ortamı yerleştirilemedi");
        for (String j : new String[]{"awt-patch14.jar", "uyapmobil-kopru.jar", "uyap-modern.jar"}) {
            try (InputStream in = c.getAssets().open("uyapmobil/" + j); OutputStream o = new FileOutputStream(new File(k, j))) {
                byte[] b = new byte[1 << 16];
                int n;
                while ((n = in.read(b)) > 0) o.write(b, 0, n);
            }
        }
        try (OutputStream o = new FileOutputStream(damga)) { o.write(surum.getBytes(StandardCharsets.UTF_8)); }
        Tani.yaz("uyapmobil", "çalışma ortamı açıldı (" + (System.currentTimeMillis() - t0) + " ms)");
    }

    // ------------------------------------------------------------------------------------ resmi editör kurulumu
    /** Resmi Linux paketini rayp.adalet.gov.tr'den indirip kurar. */
    public static String indirKur(Context c, Ilerleme il) throws Exception {
        if (!EDITOR_ADRESI.startsWith(IZINLI_ON_EK)) throw new IOException("izin verilmeyen adres");
        il.yaz("Resmi UYAP Editör indiriliyor (rayp.adalet.gov.tr, ~43 MB)…");
        HttpURLConnection h = (HttpURLConnection) new URL(EDITOR_ADRESI).openConnection();
        h.setConnectTimeout(20000);
        h.setReadTimeout(60000);
        h.setInstanceFollowRedirects(false);
        if (h.getResponseCode() != 200) throw new IOException("İndirme başarısız: HTTP " + h.getResponseCode());
        final long toplam = h.getContentLength();
        try (InputStream in = new SayacliAkis(h.getInputStream(), toplam, il)) {
            return paketKur(c, in, "uyapeditor.zip", il);
        } finally {
            h.disconnect();
        }
    }

    /** Kullanıcının seçtiği resmi paketten kurar (.zip: rayp paketi · .deb: içindeki Debian paketi). */
    public static String dosyadanKur(Context c, Uri uri, String ad, Ilerleme il) throws Exception {
        try (InputStream in = c.getContentResolver().openInputStream(uri)) {
            if (in == null) throw new IOException("dosya okunamadı");
            return paketKur(c, in, ad == null ? "paket.zip" : ad, il);
        }
    }

    private static String paketKur(Context c, InputStream in, String ad, Ilerleme il) throws Exception {
        File hedef = new File(kok(c), "editor.yeni");
        AdaletServisi.silOzyinelemeli(hedef);
        hedef.mkdirs();
        String[] surum = {""};
        int n;
        if (ad.toLowerCase(Locale.ROOT).endsWith(".deb")) {
            n = debKur(in, hedef, surum, il);
        } else {
            n = 0;
            ZipInputStream z = new ZipInputStream(new BufferedInputStream(in, 1 << 16));
            ZipEntry e;
            while ((e = z.getNextEntry()) != null) {
                String a = e.getName().toLowerCase(Locale.ROOT);
                if (!e.isDirectory() && a.startsWith("uyapeditor") && a.endsWith(".deb")) {
                    n = debKur(z, hedef, surum, il);
                    break;
                }
            }
        }
        if (n == 0 || !new File(hedef, "editor_lib.jar").isFile()) {
            AdaletServisi.silOzyinelemeli(hedef);
            throw new IOException("Pakette UYAP Editör dosyaları (usr/share/UYAPEditor/*.jar) bulunamadı.");
        }
        try (OutputStream o = new FileOutputStream(new File(hedef, "surum.txt"))) { o.write(surum[0].getBytes(StandardCharsets.UTF_8)); }
        AdaletServisi.silOzyinelemeli(editorDizini(c));
        if (!hedef.renameTo(editorDizini(c))) throw new IOException("editör yerleştirilemedi");
        il.yaz("UYAP Editör " + surum[0] + " kuruldu (" + n + " dosya).");
        Tani.yaz("uyapmobil", "editör kuruldu " + surum[0] + " · " + n + " jar");
        return surum[0];
    }

    /** .deb (ar arşivi) → data.tar.xz → usr/share/UYAPEditor/*.jar ; control'den sürüm. */
    private static int debKur(InputStream deb, File hedef, String[] surum, Ilerleme il) throws IOException {
        byte[] sihir = okuTam(deb, 8);
        if (!new String(sihir, StandardCharsets.US_ASCII).equals("!<arch>\n")) throw new IOException("Debian paketi değil");
        int sayi = 0;
        while (true) {
            byte[] bas = okuTamYaDaNull(deb, 60);
            if (bas == null) break;
            String ad = new String(bas, 0, 16, StandardCharsets.US_ASCII).trim();
            long boy = Long.parseLong(new String(bas, 48, 10, StandardCharsets.US_ASCII).trim());
            InputStream uye = new SinirliAkis(deb, boy);
            if (ad.startsWith("control.tar")) {
                // control.tar.gz/xz: sürüm bilgisi (Version:)
                InputStream ac = ad.endsWith(".xz") ? new XZInputStream(uye) : new java.util.zip.GZIPInputStream(uye);
                Tar.dolas(ac, (yol, akis, uzunluk) -> {
                    if (yol.endsWith("control")) {
                        String m = new String(okuTam(akis, (int) uzunluk), StandardCharsets.UTF_8);
                        java.util.regex.Matcher mt = java.util.regex.Pattern.compile("(?m)^Version:\\s*(\\S+)").matcher(m);
                        if (mt.find()) surum[0] = mt.group(1);
                    }
                });
            } else if (ad.startsWith("data.tar")) {
                il.yaz("UYAP Editör dosyaları çıkarılıyor…");
                InputStream ac = ad.endsWith(".xz") ? new XZInputStream(uye, -1) : new java.util.zip.GZIPInputStream(uye);
                final int[] n = {0};
                Tar.dolas(ac, (yol, akis, uzunluk) -> {
                    String y = yol.startsWith("./") ? yol.substring(2) : yol;
                    if (y.startsWith("usr/share/UYAPEditor/") && y.endsWith(".jar") && y.indexOf('/', 21) < 0) {
                        try (OutputStream o = new FileOutputStream(new File(hedef, y.substring(21)))) {
                            byte[] b = new byte[1 << 16];
                            long kalan = uzunluk;
                            while (kalan > 0) {
                                int r = akis.read(b, 0, (int) Math.min(b.length, kalan));
                                if (r < 0) throw new IOException("tar kısa");
                                o.write(b, 0, r);
                                kalan -= r;
                            }
                        }
                        n[0]++;
                    }
                });
                sayi = n[0];
            }
            uye.skip(Long.MAX_VALUE);
            while (((SinirliAkis) uye).kalan() > 0) if (uye.read() < 0) break;
            if ((boy & 1) == 1) deb.read();
        }
        return sayi;
    }

    static byte[] okuTam(InputStream in, int n) throws IOException {
        byte[] b = okuTamYaDaNull(in, n);
        if (b == null) throw new IOException("beklenmeyen dosya sonu");
        return b;
    }

    static byte[] okuTamYaDaNull(InputStream in, int n) throws IOException {
        byte[] b = new byte[n];
        int o = 0;
        while (o < n) {
            int r = in.read(b, o, n - o);
            if (r < 0) { if (o == 0) return null; throw new IOException("beklenmeyen dosya sonu"); }
            o += r;
        }
        return b;
    }

    /** En küçük tar okuyucu (ustar; uzun adlar için GNU 'L'). */
    static final class Tar {
        interface Ziyaretci { void dosya(String yol, InputStream akis, long uzunluk) throws IOException; }

        static void dolas(InputStream in, Ziyaretci z) throws IOException {
            String uzunAd = null;
            while (true) {
                byte[] b = okuTamYaDaNull(in, 512);
                if (b == null) return;
                boolean bos = true;
                for (byte x : b) if (x != 0) { bos = false; break; }
                if (bos) return;
                String ad = cstr(b, 0, 100);
                String onEk = cstr(b, 345, 155);
                if (!onEk.isEmpty()) ad = onEk + "/" + ad;
                long boy = Long.parseLong(cstr(b, 124, 12).trim().isEmpty() ? "0" : cstr(b, 124, 12).trim(), 8);
                char tur = (char) b[156];
                long dolgu = (512 - (boy % 512)) % 512;
                if (tur == 'L') {
                    uzunAd = new String(okuTam(in, (int) boy), StandardCharsets.UTF_8).replace("\0", "");
                    in.skip(dolgu);
                    continue;
                }
                if (uzunAd != null) { ad = uzunAd; uzunAd = null; }
                SinirliAkis s = new SinirliAkis(in, boy);
                if (tur == '0' || tur == 0) z.dosya(ad, s, boy);
                while (s.kalan() > 0) { if (s.skip(s.kalan()) <= 0 && s.read() < 0) break; }
                long d = dolgu;
                while (d > 0) { long k = in.skip(d); if (k <= 0) { if (in.read() < 0) break; k = 1; } d -= k; }
            }
        }

        private static String cstr(byte[] b, int o, int n) {
            int e = o;
            while (e < o + n && b[e] != 0) e++;
            return new String(b, o, e - o, StandardCharsets.UTF_8);
        }
    }

    static final class SinirliAkis extends InputStream {
        private final InputStream in;
        private long kalan;
        SinirliAkis(InputStream in, long n) { this.in = in; this.kalan = n; }
        long kalan() { return kalan; }
        @Override public int read() throws IOException {
            if (kalan <= 0) return -1;
            int r = in.read();
            if (r >= 0) kalan--;
            return r;
        }
        @Override public int read(byte[] b, int o, int n) throws IOException {
            if (kalan <= 0) return -1;
            int r = in.read(b, o, (int) Math.min(n, kalan));
            if (r > 0) kalan -= r;
            return r;
        }
        @Override public long skip(long n) throws IOException {
            long k = in.skip(Math.min(n, kalan));
            if (k > 0) kalan -= k;
            return k;
        }
        @Override public void close() { }
    }

    static final class SayacliAkis extends java.io.FilterInputStream {
        private final long toplam;
        private final Ilerleme il;
        private long okunan;
        private int sonYuzde = -1;
        SayacliAkis(InputStream in, long toplam, Ilerleme il) { super(in); this.toplam = toplam; this.il = il; }
        @Override public int read(byte[] b, int o, int n) throws IOException {
            int r = super.read(b, o, n);
            if (r > 0 && toplam > 0) {
                okunan += r;
                int y = (int) (okunan * 100 / toplam);
                if (y != sonYuzde) { sonYuzde = y; il.yaz("Resmi UYAP Editör indiriliyor… %" + y); }
            }
            return r;
        }
    }

    // ------------------------------------------------------------------------------------ başlatma
    /** Cihaz belleğine göre Java yığın sınırı (editör + açık belgeler). */
    static int bellekMb(Context c) {
        ActivityManager am = (ActivityManager) c.getSystemService(Context.ACTIVITY_SERVICE);
        ActivityManager.MemoryInfo mi = new ActivityManager.MemoryInfo();
        if (am != null) am.getMemoryInfo(mi);
        long top = mi.totalMem / (1024 * 1024);
        if (top >= 7000) return 1024;
        if (top >= 3500) return 768;
        return 512;
    }

    static void yaziTipiAyari(Context c) throws IOException {
        File fc = new File(kok(c), "fonts.conf");
        yaziTipleri(c).mkdirs();
        String x = "<?xml version=\"1.0\"?>\n<fontconfig>\n"
                + "  <dir>" + yaziTipleri(c).getAbsolutePath() + "</dir>\n"      // kullanıcının eklediği (ör. gerçek Times New Roman)
                + "  <dir>" + new File(rt(c), "fonts").getAbsolutePath() + "</dir>\n"
                + "  <cachedir>" + new File(c.getCacheDir(), "fontconfig").getAbsolutePath() + "</cachedir>\n"
                // Java'nın mantıksal yazı tipleri (Dialog/SansSerif/Serif/Monospaced) fontconfig'e "sans", "serif", "mono" adlarıyla
                // sorulur; varsayılan fontconfig ayarları (conf.d) olmadığı için takma adlar burada tanımlanır.
                + "  <alias><family>serif</family><prefer><family>Times New Roman</family><family>Liberation Serif</family></prefer></alias>\n"
                + "  <alias><family>sans-serif</family><prefer><family>Arial</family><family>Liberation Sans</family></prefer></alias>\n"
                + "  <alias><family>sans</family><prefer><family>Arial</family><family>Liberation Sans</family></prefer></alias>\n"
                + "  <alias><family>monospace</family><prefer><family>Courier New</family><family>Liberation Mono</family></prefer></alias>\n"
                + "  <alias><family>mono</family><prefer><family>Courier New</family><family>Liberation Mono</family></prefer></alias>\n"
                + "  <match target=\"pattern\"><test qual=\"all\" name=\"family\" compare=\"not_eq\"><string>Liberation Mono</string></test>"
                + "<edit name=\"family\" mode=\"append_last\"><string>Liberation Sans</string></edit></match>\n"
                + "  <alias><family>Times New Roman</family><accept><family>Liberation Serif</family></accept></alias>\n"
                + "  <alias><family>Arial</family><accept><family>Liberation Sans</family></accept></alias>\n"
                + "  <alias><family>Courier New</family><accept><family>Liberation Mono</family></accept></alias>\n"
                + "</fontconfig>\n";
        try (OutputStream o = new FileOutputStream(fc)) { o.write(x.getBytes(StandardCharsets.UTF_8)); }
    }

    /** Editör sürecini başlatır. dosya null ise boş belge. */
    /** Ortak depolamayı (/sdcard) okuyup yazma izni (targetSdk 28: klasik depolama izni, Android 6+ çalışma anında istenir). */
    static boolean depolamaIzniVar(Context c) {
        if (android.os.Build.VERSION.SDK_INT < 23) return true;
        return c.checkSelfPermission(android.Manifest.permission.WRITE_EXTERNAL_STORAGE) == android.content.pm.PackageManager.PERMISSION_GRANTED
                || c.checkSelfPermission(android.Manifest.permission.READ_EXTERNAL_STORAGE) == android.content.pm.PackageManager.PERMISSION_GRANTED;
    }

    static Process baslat(Context c, int genislik, int yukseklik, int port, String jeton, String dosya) throws IOException {
        File r = rt(c), k = kok(c), ev = ev(c), tmp = new File(c.getCacheDir(), "uyapmobil-tmp");
        ev.mkdirs();
        tmp.mkdirs();
        belgeler(c).mkdirs();
        yaziTipiAyari(c);
        StringBuilder cp = new StringBuilder();
        File[] jarlar = editorDizini(c).listFiles();
        if (jarlar != null) {
            java.util.Arrays.sort(jarlar);
            for (File j : jarlar) if (j.getName().endsWith(".jar")) { if (cp.length() > 0) cp.append(':'); cp.append(j.getAbsolutePath()); }
        }
        String jre = new File(r, "jre").getAbsolutePath();
        List<String> a = new ArrayList<>();
        a.add(new File(r, "glibc/ld-linux-aarch64.so.1").getAbsolutePath());
        a.add("--library-path");
        a.add(new File(r, "glibc").getAbsolutePath() + ":" + jre + "/lib:" + jre + "/lib/server");
        a.add(new File(r, "bin/uyapjava").getAbsolutePath());
        a.add(jre + "/lib/server/libjvm.so");
        // ---- JVM seçenekleri (JNI biçimi) ----
        a.add("-Xshare:off");                           // JDK 14 CDS arşivi 64K sayfa ile eşleşmeyebilir
        a.add("-Xms64m");
        a.add("-Xmx" + bellekMb(c) + "m");
        a.add("-XX:+UseSerialGC");
        a.add("-Dfile.encoding=UTF-8");
        a.add("-Dsun.jnu.encoding=UTF-8");
        a.add("-Duser.home=" + ev.getAbsolutePath());
        a.add("-Djava.io.tmpdir=" + tmp.getAbsolutePath());
        a.add("-Duser.language=tr");
        a.add("-Duser.country=TR");
        a.add("-Djava.class.path=" + cp);
        a.add("-Djdk.lang.Process.launchMechanism=VFORK");   // jspawnhelper glibc programı: kullanılmaz
        a.add("-Dawt.useSystemAAFontSettings=lcd");
        a.add("-Dswing.aatext=true");
        a.add("-Dcacio.managed.screensize=" + genislik + "x" + yukseklik);
        a.add("-Djava.awt.headless=false");
        a.add("--patch-module=java.desktop=" + new File(k, "awt-patch14.jar").getAbsolutePath());
        a.add("--add-reads=java.desktop=java.logging,ALL-UNNAMED");
        for (String o : new String[]{"java.desktop/java.awt", "java.desktop/javax.swing", "java.desktop/sun.font",
                "java.desktop/com.github.caciocavallosilano.cacio.ctc", "java.desktop/com.github.caciocavallosilano.cacio.peer.managed",
                "java.base/java.lang", "java.base/java.util"})
            a.add("--add-opens=" + o + "=ALL-UNNAMED");
        a.add("--add-exports=java.desktop/sun.awt=ALL-UNNAMED");
        a.add("-javaagent:" + new File(k, "uyap-modern.jar").getAbsolutePath() + "=dokuman");
        a.add("-javaagent:" + new File(k, "uyapmobil-kopru.jar").getAbsolutePath());
        a.add("-Duyapmobil.port=" + port);
        a.add("-Duyapmobil.jeton=" + jeton);
        a.add("-Duyapmobil.ekran=" + ekranDosyasi(c).getAbsolutePath());
        a.add("-Duyapmobil.gunluk=" + new File(k, "kopru.log").getAbsolutePath());
        // Aç / Kaydet pencereleri telefonun ortak depolamasında (/sdcard) başlasın (köprü: dosyaSeciciDepolamada).
        // Yalnızca depolama izni verildiyse: izinsiz klasör boş görünür.
        File depo = android.os.Environment.getExternalStorageDirectory();
        if (depo != null && depo.isDirectory() && depolamaIzniVar(c)) a.add("-Duyapmobil.depolama=" + depo.getAbsolutePath());
        a.add("-Duyapmobil.secici=android");   // Aç/Kaydet → Android'in kendi dosya seçicisi (Kopru.androidSecici)
        a.add("--");
        a.add(ANA_SINIF);
        a.add("getNewWPInstance");
        a.add(dosya != null && dosya.toLowerCase(Locale.ROOT).endsWith(".usf") ? "EDITOR_TYPE_TEMPLATE" : "EDITOR_TYPE_DOCUMENT");
        if (dosya != null) a.add(dosya);
        ProcessBuilder pb = new ProcessBuilder(a);
        pb.directory(ev);
        java.util.Map<String, String> env = pb.environment();
        env.remove("LD_PRELOAD");
        env.remove("LD_LIBRARY_PATH");
        env.put("HOME", ev.getAbsolutePath());
        env.put("TMPDIR", tmp.getAbsolutePath());
        env.put("LANG", "C.UTF-8");
        env.put("LC_ALL", "C.UTF-8");
        env.put("FONTCONFIG_FILE", new File(k, "fonts.conf").getAbsolutePath());
        env.put("JAVA_HOME", jre);
        env.remove("DISPLAY");
        env.remove("JAVA_TOOL_OPTIONS");
        pb.redirectErrorStream(true);
        Tani.yaz("uyapmobil", "başlatılıyor " + genislik + "x" + yukseklik + " · bellek " + bellekMb(c) + " MB · dosya=" + (dosya != null));
        return pb.start();
    }

    private UyapMobil() { }
}
