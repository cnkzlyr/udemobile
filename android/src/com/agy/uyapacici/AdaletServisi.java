package com.agy.uyapacici;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import android.provider.Settings;
import android.util.Log;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * 🏛️ Adalet E-İmza (Termux'suz): gömülü Java 21'de RESMİ Adalet E-İmza uygulamasını çalıştırır.
 *
 *  - Java: APK içindeki assets/eimza/jre-arm64.zip ilk açılışta uygulama klasörüne çıkarılır.
 *  - Resmi uygulama: Adalet'in sunucusundan indirilir (AdaletKurulum); APK'da dağıtılmaz.
 *  - Ekran yok: Swing pencereleri Caciocavallo ile bellekte çizilir (awt-patch.jar).
 *  - Kart: USB CCID köprüsü (CcidKopru) + ajan (eimza-agent.jar) javax.smartcardio'yu okuyucuya bağlar.
 *  - PIN: sayfa göndermezse Android penceresi (PinEkrani) açılır.
 *  - Chrome'daki UYAP portalı 127.0.0.1:5975'e bağlanır (resmi uygulamadaki gibi).
 * Ön plan servisi olarak çalışır (Android arka planda kapatmasın); bildirimden durdurulabilir.
 */
public class AdaletServisi extends Service implements CcidKopru.PinSaglayici {
    private static final String TAG = "AdaletServisi";
    public static final String EYLEM_DURDUR = "com.agy.uyapacici.ADALET_DURDUR";
    public static final int PORT = 5975;
    private static final String KANAL = "adalet_eimza";
    private static final int BILDIRIM = 5975;

    private static volatile String durum = "Kapalı";
    private static volatile AdaletServisi ornek;

    private CcidKopru kopru;
    private Process java;
    private volatile boolean calis;
    private Thread izleyici;

    // ------------------------------------------------------------------------------------ dışarıdan
    public static void baslat(Context c) {
        Intent i = new Intent(c, AdaletServisi.class);
        if (Build.VERSION.SDK_INT >= 26) c.startForegroundService(i); else c.startService(i);
    }

    public static void durdur(Context c) {
        c.stopService(new Intent(c, AdaletServisi.class));
    }

    public static String durum() { return durum; }

    public static boolean calisiyor() { return ornek != null && ornek.calis; }

    /** 127.0.0.1:5975 cevap veriyor mu (resmi uygulama hazır mı)? */
    public static boolean portAcik() {
        try (Socket s = new Socket()) {
            s.connect(new InetSocketAddress("127.0.0.1", PORT), 700);
            return true;
        } catch (IOException e) {
            return false;
        }
    }

    public static File eimzaDizini(Context c) { return new File(c.getFilesDir(), "eimza"); }

    public static File gunluk(Context c) { return new File(eimzaDizini(c), "adalet.log"); }

    // ------------------------------------------------------------------------------------ servis
    @Override public IBinder onBind(Intent intent) { return null; }

    @Override
    public void onCreate() {
        super.onCreate();
        ornek = this;
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && EYLEM_DURDUR.equals(intent.getAction())) {
            stopSelf();
            return START_NOT_STICKY;
        }
        startForeground(BILDIRIM, bildirim("Başlatılıyor…"));
        if (!calis) {
            calis = true;
            izleyici = new Thread(new Runnable() { @Override public void run() { dongu(); } }, "adalet-izleyici");
            izleyici.start();
        }
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        calis = false;
        if (izleyici != null) izleyici.interrupt();
        javaDurdur();
        if (kopru != null) kopru.durdur();
        durum = "Kapalı";
        ornek = null;
        super.onDestroy();
    }

    private void dongu() {
        int hata = 0;
        while (calis) {
            try {
                File jar = AdaletKurulum.jarDosyasi(this);
                if (!jar.exists()) {
                    durumYaz("Resmi uygulama kurulu değil: UdeMobile > Adalet E-İmza > Kur");
                    Thread.sleep(5000);
                    continue;
                }
                File jre = jreHazirla();
                if (kopru == null) {
                    kopru = new CcidKopru(this, eimzaDizini(this), this);
                    kopru.baslat();
                }
                if (java == null || !canli(java)) {
                    durumYaz("Adalet E-İmza başlatılıyor…");
                    java = javaBaslat(jre, jar);
                    long son = System.currentTimeMillis() + 120000;
                    while (calis && canli(java) && !portAcik() && System.currentTimeMillis() < son) Thread.sleep(700);
                    if (!canli(java)) {
                        hata++;
                        durumYaz("Adalet E-İmza kapandı (günlük: Adalet E-İmza > Günlük). Yeniden deneniyor…");
                        Thread.sleep(Math.min(60000, 3000L * hata));
                        java = null;
                        continue;
                    }
                    hata = 0;
                }
                String okuyucu = kopru.okuyucuAdi();
                durumYaz(portAcik() ? "Çalışıyor · 127.0.0.1:" + PORT + (okuyucu != null ? " · " + okuyucu : " · e-imza okuyucusu takılı değil")
                        : "Adalet E-İmza yanıt vermiyor, bekleniyor…");
                Thread.sleep(4000);
            } catch (InterruptedException e) {
                return;
            } catch (Exception e) {
                Log.e(TAG, "hata", e);
                durumYaz("Hata: " + e.getMessage());
                try { Thread.sleep(5000); } catch (InterruptedException ie) { return; }
            }
        }
    }

    private static boolean canli(Process p) {
        try { p.exitValue(); return false; } catch (IllegalThreadStateException e) { return true; }
    }

    private void javaDurdur() {
        if (java != null) {
            java.destroy();
            try { if (Build.VERSION.SDK_INT >= 26) java.waitFor(3, TimeUnit.SECONDS); } catch (InterruptedException ignored) { }
            if (Build.VERSION.SDK_INT >= 26 && canli(java)) java.destroyForcibly();
            java = null;
        }
    }

    // ------------------------------------------------------------------------------------ Java
    /** assets/eimza içeriğini (JRE + ajan + AWT yaması) sürüm değişince yeniden açar. Döner: JRE klasörü. */
    private File jreHazirla() throws IOException {
        File kok = new File(getFilesDir(), "java");
        String surum = assetMetin("eimza/surum.txt").trim();
        File damga = new File(kok, "surum.txt");
        File jre = new File(kok, "jre");
        if (damga.exists() && surum.equals(okuMetin(damga).trim()) && new File(jre, "bin/java").exists()) return jre;
        durumYaz("Java hazırlanıyor (ilk açılış, ~1 dk)…");
        silOzyinelemeli(kok);
        jre.mkdirs();
        try (ZipInputStream z = new ZipInputStream(getAssets().open("eimza/jre-arm64.zip"))) {
            ZipEntry e;
            byte[] buf = new byte[1 << 16];
            while ((e = z.getNextEntry()) != null) {
                File f = new File(jre, e.getName());
                if (!f.getCanonicalPath().startsWith(jre.getCanonicalPath() + File.separator)) continue;   // zip yolu kaçağı
                if (e.isDirectory()) { f.mkdirs(); continue; }
                f.getParentFile().mkdirs();
                try (OutputStream o = new FileOutputStream(f)) {
                    int n;
                    while ((n = z.read(buf)) > 0) o.write(buf, 0, n);
                }
            }
        }
        for (String yurut : new String[]{"bin/java", "bin/keytool", "lib/jspawnhelper", "lib/jexec"}) {
            File f = new File(jre, yurut);
            if (f.exists()) f.setExecutable(true, true);
        }
        assetKopyala("eimza/eimza-agent.jar", new File(kok, "eimza-agent.jar"));
        assetKopyala("eimza/awt-patch.jar", new File(kok, "awt-patch.jar"));
        try (OutputStream o = new FileOutputStream(damga)) { o.write(surum.getBytes("UTF-8")); }
        return jre;
    }

    private Process javaBaslat(File jre, File jar) throws IOException {
        File kok = new File(getFilesDir(), "java");
        File ev = new File(getFilesDir(), "adalet-ev");
        File tmp = new File(getCacheDir(), "adalet-tmp");
        File eimza = eimzaDizini(this);
        ev.mkdirs(); tmp.mkdirs(); eimza.mkdirs();
        File fc = new File(eimza, "fonts.conf");
        try (OutputStream o = new FileOutputStream(fc)) {
            o.write(("<?xml version=\"1.0\"?>\n<fontconfig>\n  <dir>/system/fonts</dir>\n  <cachedir>"
                    + new File(getCacheDir(), "fontconfig").getAbsolutePath() + "</cachedir>\n</fontconfig>\n").getBytes("UTF-8"));
        }
        List<String> k = new ArrayList<>();
        k.add(new File(jre, "bin/java").getAbsolutePath());
        k.add("-Xms32m"); k.add("-Xmx384m"); k.add("-XX:+UseSerialGC"); k.add("-XX:-UsePerfData");
        k.add("-Dfile.encoding=UTF-8");
        k.add("-Duser.home=" + ev.getAbsolutePath());
        k.add("-Djava.io.tmpdir=" + tmp.getAbsolutePath());
        k.add("--add-opens=java.smartcardio/sun.security.smartcardio=ALL-UNNAMED");
        k.add("--add-exports=jdk.crypto.cryptoki/sun.security.pkcs11.wrapper=ALL-UNNAMED");
        k.add("-jar"); k.add(jar.getAbsolutePath());
        ProcessBuilder pb = new ProcessBuilder(k);
        pb.directory(ev);
        Map<String, String> env = pb.environment();
        String lib = new File(jre, "lib").getAbsolutePath();
        env.put("LD_LIBRARY_PATH", lib + ":" + lib + "/server");
        env.put("JAVA_HOME", jre.getAbsolutePath());
        env.put("HOME", ev.getAbsolutePath());
        env.put("TMPDIR", tmp.getAbsolutePath());
        env.put("EIMZA_DIR", eimza.getAbsolutePath());
        env.put("FONTCONFIG_FILE", fc.getAbsolutePath());
        env.remove("DISPLAY");
        // Ajan ve AWT yaması JAVA_TOOL_OPTIONS ile verilir: uygulamanın kart tarayan ALT Java süreçlerine de geçer.
        env.put("JAVA_TOOL_OPTIONS", "-javaagent:" + new File(kok, "eimza-agent.jar").getAbsolutePath()
                + " -Deimza.dir=" + eimza.getAbsolutePath()
                + " --patch-module=java.desktop=" + new File(kok, "awt-patch.jar").getAbsolutePath()
                + " --add-opens=java.desktop/java.awt=ALL-UNNAMED -Djava.awt.headless=false"
                + " -Djdk.lang.Process.launchMechanism=FORK");
        File log = gunluk(this);
        if (log.length() > 3_000_000) log.delete();
        pb.redirectErrorStream(true);
        final Process p = pb.start();
        final File gunlukDosyasi = log;
        Thread t = new Thread(new Runnable() {      // çıktı günlüğe (ProcessBuilder.Redirect Android 8 öncesinde yok)
            @Override public void run() {
                try (InputStream in = p.getInputStream(); OutputStream o = new FileOutputStream(gunlukDosyasi, true)) {
                    byte[] b = new byte[8192];
                    int n;
                    while ((n = in.read(b)) > 0) { o.write(b, 0, n); o.flush(); }
                } catch (IOException ignored) { }
            }
        }, "adalet-gunluk");
        t.setDaemon(true);
        t.start();
        return p;
    }

    // ------------------------------------------------------------------------------------ PIN
    private volatile String pinSonuc;
    private volatile CountDownLatch pinBekle;

    /** Köprüden gelen PIN isteği: Android penceresi açılır, 120 sn beklenir. */
    @Override
    public String pinIste(String baslik) {
        synchronized (this) {
            pinSonuc = null;
            pinBekle = new CountDownLatch(1);
            Intent i = new Intent(this, PinEkrani.class).putExtra(PinEkrani.EXTRA_BASLIK, baslik)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
            boolean dogrudan = Build.VERSION.SDK_INT < 29 || Settings.canDrawOverlays(this);
            if (dogrudan) {
                try { startActivity(i); } catch (Exception e) { dogrudan = false; }
            }
            if (!dogrudan || Build.VERSION.SDK_INT >= 29) pinBildirimi(i);   // arka planda pencere açılamazsa bildirim
            try {
                pinBekle.await(120, TimeUnit.SECONDS);
            } catch (InterruptedException ignored) { }
            NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
            if (nm != null) nm.cancel(BILDIRIM + 1);
            String s = pinSonuc;
            pinSonuc = null;
            return s;
        }
    }

    static void pinGeldi(String pin) {
        AdaletServisi s = ornek;
        if (s != null && s.pinBekle != null) {
            s.pinSonuc = pin;
            s.pinBekle.countDown();
        }
    }

    private void pinBildirimi(Intent i) {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm == null) return;
        kanal(nm);
        PendingIntent pi = PendingIntent.getActivity(this, 2, i, PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0));
        Notification.Builder b = Build.VERSION.SDK_INT >= 26 ? new Notification.Builder(this, KANAL) : new Notification.Builder(this);
        b.setSmallIcon(android.R.drawable.ic_lock_lock).setContentTitle("E-imza PIN bekleniyor")
                .setContentText("PIN girmek için dokunun").setContentIntent(pi).setFullScreenIntent(pi, true)
                .setAutoCancel(true).setPriority(Notification.PRIORITY_MAX).setCategory(Notification.CATEGORY_CALL);
        nm.notify(BILDIRIM + 1, b.build());
    }

    // ------------------------------------------------------------------------------------ bildirim
    private void durumYaz(String s) {
        if (s.equals(durum)) return;
        durum = s;
        Log.i(TAG, s);
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm != null && calis) nm.notify(BILDIRIM, bildirim(s));
    }

    private void kanal(NotificationManager nm) {
        if (Build.VERSION.SDK_INT >= 26 && nm.getNotificationChannel(KANAL) == null) {
            NotificationChannel ch = new NotificationChannel(KANAL, "Adalet E-İmza", NotificationManager.IMPORTANCE_HIGH);
            ch.setDescription("UYAP e-imza servisi ve PIN istekleri");
            nm.createNotificationChannel(ch);
        }
    }

    private Notification bildirim(String metin) {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm != null) kanal(nm);
        int f = Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0;
        PendingIntent ac = PendingIntent.getActivity(this, 0, new Intent(this, AdaletActivity.class), f);
        PendingIntent dur = PendingIntent.getService(this, 1, new Intent(this, AdaletServisi.class).setAction(EYLEM_DURDUR), f);
        Notification.Builder b = Build.VERSION.SDK_INT >= 26 ? new Notification.Builder(this, KANAL) : new Notification.Builder(this);
        b.setSmallIcon(android.R.drawable.ic_lock_idle_lock).setContentTitle("🏛️ Adalet E-İmza").setContentText(metin)
                .setStyle(new Notification.BigTextStyle().bigText(metin)).setOngoing(true).setContentIntent(ac)
                .addAction(android.R.drawable.ic_menu_close_clear_cancel, "Durdur", dur).setOnlyAlertOnce(true);
        if (Build.VERSION.SDK_INT >= 26) b.setChannelId(KANAL);
        return b.build();
    }

    // ------------------------------------------------------------------------------------ dosya
    private String assetMetin(String ad) throws IOException {
        try (InputStream in = getAssets().open(ad)) { return new String(okuHepsi(in), "UTF-8"); }
    }

    private void assetKopyala(String ad, File hedef) throws IOException {
        try (InputStream in = getAssets().open(ad); OutputStream o = new FileOutputStream(hedef)) {
            byte[] b = new byte[1 << 16];
            int n;
            while ((n = in.read(b)) > 0) o.write(b, 0, n);
        }
    }

    static String okuMetin(File f) throws IOException {
        try (InputStream in = new java.io.FileInputStream(f)) { return new String(okuHepsi(in), "UTF-8"); }
    }

    static byte[] okuHepsi(InputStream in) throws IOException {
        java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
        byte[] b = new byte[1 << 16];
        int n;
        while ((n = in.read(b)) > 0) bo.write(b, 0, n);
        return bo.toByteArray();
    }

    static void silOzyinelemeli(File f) {
        File[] c = f.listFiles();
        if (c != null) for (File x : c) silOzyinelemeli(x);
        f.delete();
    }

    /** Uygulama içinden (editör e-imzası) resmi servise istek. Origin gönderilmez (CORS tarayıcıya özgü). */
    public static String istek(String yontem, String yol, String govdeJson) throws IOException {
        HttpURLConnection c = (HttpURLConnection) new URL("http://127.0.0.1:" + PORT + yol).openConnection();
        c.setRequestMethod(yontem);
        c.setConnectTimeout(3000);
        c.setReadTimeout(180000);              // PIN girilene kadar bekleyebilir
        if (govdeJson != null) {
            c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/json");
            try (OutputStream o = c.getOutputStream()) { o.write(govdeJson.getBytes("UTF-8")); }
        }
        InputStream in = c.getResponseCode() < 400 ? c.getInputStream() : c.getErrorStream();
        try { return in == null ? "" : new String(okuHepsi(in), "UTF-8"); } finally { c.disconnect(); }
    }
}
