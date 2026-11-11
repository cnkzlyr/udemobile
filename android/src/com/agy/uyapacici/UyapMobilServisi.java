package com.agy.uyapacici;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.os.FileObserver;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Locale;

/**
 * UYAP Mobil ön plan servisi: resmi UYAP Editör'ün Java sürecini çalıştırır (ekran açık olmasa da belge kaybolmaz),
 * köprüye bağlanır (dokunma/klavye komutları, pano bildirimi) ve kaydedilen belgeleri geldikleri yere geri yazar.
 *
 * Belge akışı: başka uygulamadan (dosya yöneticisi, WhatsApp, Celse, tarayıcı) gelen .udf/.usf → belgeler/ klasörüne
 * kopyalanır → editörde açılır. Editör kaydedince (CLOSE_WRITE) dosya, yazılabiliyorsa kaynağına (content://) geri yazılır,
 * yazılamıyorsa (ör. WhatsApp) İndirilenler/UYAP klasörüne kaydedilir.
 */
public class UyapMobilServisi extends Service {
    private static final String KANAL = "uyapmobil";
    private static final int BILDIRIM = 7311;
    static final String EK_DOSYA = "dosya", EK_W = "w", EK_H = "h";

    private static volatile UyapMobilServisi ornek;
    private static volatile String durum = "";
    private static volatile Dinleyici dinleyici;

    private Process java;
    private volatile OutputStream denetim;
    private final Object yazKilidi = new Object();
    private int port;
    private String jeton;
    private int genislik, yukseklik;
    private FileObserver gozcu;
    private final Handler ana = new Handler(Looper.getMainLooper());

    public interface Dinleyici {
        void durum(String m);
        void hazir(int w, int h);
        void kapandi(String neden);
        /** Ön plandaki belge penceresinin başlığı (belge adı ve yolu içerir). */
        void baslik(String t);
        /** Editörün menü ağacı (Kopru.menuGonder, JSON). */
        void menu(String json);
        /** Editör bir Aç/Kaydet penceresi açtı: Android seçicisini göster, yanıtı {@link #seciciYanit} ile ver. */
        void dosyaIste(int no, boolean kaydet, String ad, String uzantilar);
    }

    /** Android seçicisinin sonucu: yol null → vazgeçildi; swing → Android seçicisi yok, editörün kendi penceresi kalsın. */
    public static void seciciYanit(int no, String yol, boolean swing) {
        if (swing) gonder("SK " + no);
        else if (yol == null) gonder("SF " + no);
        else gonder("SF " + no + " " + android.util.Base64.encodeToString(yol.getBytes(StandardCharsets.UTF_8), android.util.Base64.NO_WRAP));
    }

    private static String b64coz(String s) {
        return new String(android.util.Base64.decode(s, android.util.Base64.DEFAULT), StandardCharsets.UTF_8);
    }

    // ------------------------------------------------------------------------------------ dış arayüz
    /** Editörü (gerekirse) başlatır; dosya verilirse açar (çalışıyorsa aynı editörde). */
    public static void ac(Context c, String dosya, int w, int h) {
        Intent i = new Intent(c, UyapMobilServisi.class);
        if (dosya != null) i.putExtra(EK_DOSYA, dosya);
        i.putExtra(EK_W, w);
        i.putExtra(EK_H, h);
        if (Build.VERSION.SDK_INT >= 26) c.startForegroundService(i); else c.startService(i);
    }

    public static void kapat(Context c) { c.stopService(new Intent(c, UyapMobilServisi.class)); }

    public static boolean calisiyor() { UyapMobilServisi s = ornek; return s != null && s.java != null && canli(s.java); }

    public static boolean bagli() { UyapMobilServisi s = ornek; return s != null && s.denetim != null; }

    public static int[] ekranBoyutu() { UyapMobilServisi s = ornek; return s == null ? null : new int[]{s.genislik, s.yukseklik}; }

    public static void dinleyiciAyarla(Dinleyici d) {
        dinleyici = d;
        if (d != null) {
            d.durum(durum);
            UyapMobilServisi s = ornek;
            if (s != null && s.denetim != null) d.hazir(s.genislik, s.yukseklik);
        }
    }

    /**
     * Köprüye komut (M/D/U/W/T/K/Y/O/X). Bağlı değilse sessizce düşer.
     * Dokunma olayları ana (arayüz) iş parçacığından gelir: soket yazımı ana iş parçacığında yapılırsa Android
     * NetworkOnMainThreadException ile uygulamayı kapatır (3.19.0'da editöre ilk dokunuşta çökme). Komutlar kuyruğa
     * alınır, ayrı bir iş parçacığı sırayla yazar (sıra korunur).
     */
    public static void gonder(String komut) {
        UyapMobilServisi s = ornek;
        if (s == null || s.denetim == null) return;
        s.kuyruk.offer(komut);
    }

    private final java.util.concurrent.LinkedBlockingQueue<String> kuyruk = new java.util.concurrent.LinkedBlockingQueue<>();
    private volatile Thread yazici;

    private void yaziciBaslat() {
        if (yazici != null) return;
        Thread t = new Thread(() -> {
            try {
                while (true) {
                    String k = kuyruk.take();
                    OutputStream o = denetim;
                    if (o == null) continue;
                    StringBuilder sb = new StringBuilder(k).append('\n');
                    String ek;
                    while ((ek = kuyruk.poll()) != null) sb.append(ek).append('\n');   // birikenleri tek yazımda gönder
                    try {
                        synchronized (yazKilidi) { o.write(sb.toString().getBytes(StandardCharsets.UTF_8)); o.flush(); }
                    } catch (IOException e) {
                        denetim = null;
                    }
                }
            } catch (InterruptedException ignored) { }
        }, "uyapmobil-yazici");
        t.setDaemon(true);
        t.start();
        yazici = t;
    }

    static String hex(byte[] b) {
        StringBuilder sb = new StringBuilder(b.length * 2);
        for (byte x : b) sb.append(Character.forDigit((x >> 4) & 15, 16)).append(Character.forDigit(x & 15, 16));
        return sb.toString();
    }

    static byte[] unhex(String s) {
        byte[] b = new byte[s.length() / 2];
        for (int i = 0; i < b.length; i++) b[i] = (byte) Integer.parseInt(s.substring(2 * i, 2 * i + 2), 16);
        return b;
    }

    private static void durumYaz(String m) {
        durum = m;
        Tani.yaz("uyapmobil", m);
        Dinleyici d = dinleyici;
        if (d != null) d.durum(m);
    }

    // ------------------------------------------------------------------------------------ yaşam döngüsü
    @Override public IBinder onBind(Intent intent) { return null; }

    @Override public void onCreate() {
        super.onCreate();
        ornek = this;
        Tani.baglam(this);
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        startForeground(BILDIRIM, bildirim("UYAP Editör"));
        final String dosya = intent != null ? intent.getStringExtra(EK_DOSYA) : null;
        final int w = intent != null ? intent.getIntExtra(EK_W, 1280) : 1280;
        final int h = intent != null ? intent.getIntExtra(EK_H, 800) : 800;
        if (java != null && canli(java)) {
            if (dosya != null) {
                if (denetim != null) gonder("O " + hex(dosya.getBytes(StandardCharsets.UTF_8)));
                else bekleyenDosya = dosya;
            }
            return START_NOT_STICKY;
        }
        new Thread(() -> calistir(dosya, w, h), "uyapmobil-baslat").start();
        return START_NOT_STICKY;
    }

    private volatile String bekleyenDosya;

    private void calistir(String dosya, int w, int h) {
        try {
            UyapMobil.hazirla(this, UyapMobilServisi::durumYaz);
            if (!UyapMobil.editorKurulu(this)) { durumYaz("Resmi UYAP Editör kurulu değil."); kapandi("kurulu değil"); return; }
            genislik = w;
            yukseklik = h;
            byte[] r = new byte[16];
            new SecureRandom().nextBytes(r);
            jeton = hex(r);
            try (ServerSocket ss = new ServerSocket(0, 1, InetAddress.getByName("127.0.0.1"))) { port = ss.getLocalPort(); }
            File ekran = UyapMobil.ekranDosyasi(this);
            ekran.delete();
            belgeGozcusu();
            durumYaz("UYAP Editör açılıyor (Java 14)…");
            // Belge komut satırıyla verilmez: resmi editör açılışta "Son sürümlerde yapılan güncellemeler" penceresini
            // gösterdiğinde argümandaki belgeyi atlıyor. Köprü hazır olunca "O" komutuyla açılır (güvenilir).
            if (dosya != null) bekleyenDosya = dosya;
            eskiSureciKapat();
            java = UyapMobil.baslat(this, w, h, port, jeton, null);
            pidYaz(java);
            final Process p = java;
            Thread g = new Thread(() -> gunlukPompasi(p), "uyapmobil-gunluk");
            g.setDaemon(true);
            g.start();
            // köprü portu açılana kadar bekle (ilk açılış: JIT + editörün kendi yüklemesi)
            long son = System.currentTimeMillis() + 180_000;
            Socket s = null;
            while (System.currentTimeMillis() < son && canli(p)) {
                try {
                    s = new Socket();
                    s.connect(new InetSocketAddress("127.0.0.1", port), 500);
                    break;
                } catch (IOException e) {
                    try { s.close(); } catch (IOException ignored) { }
                    s = null;
                    Thread.sleep(400);
                }
            }
            if (s == null) {
                durumYaz(canli(p) ? "UYAP Editör yanıt vermiyor." : "UYAP Editör kapandı (kod " + p.exitValue() + "). Menü > Günlük");
                kapandi("başlamadı");
                return;
            }
            OutputStream o = s.getOutputStream();
            o.write(("AUTH " + jeton + "\n").getBytes(StandardCharsets.UTF_8));
            o.flush();
            final BufferedReader in = new BufferedReader(new InputStreamReader(s.getInputStream(), StandardCharsets.UTF_8));
            String ilk = in.readLine();
            if (!"OK".equals(ilk)) { durumYaz("köprü yetkilendirmesi başarısız"); kapandi("köprü"); return; }
            denetim = o;
            yaziciBaslat();
            durumYaz("Hazır");
            Dinleyici d = dinleyici;
            if (d != null) d.hazir(w, h);
            if (bekleyenDosya != null) {
                final String b = bekleyenDosya;
                bekleyenDosya = null;
                ana.postDelayed(() -> gonder("O " + hex(b.getBytes(StandardCharsets.UTF_8))), 1500);   // ana pencere kurulsun
            }
            String satir;
            while ((satir = in.readLine()) != null) bildirimIsle(satir);
        } catch (Exception e) {
            Tani.hata("uyapmobil", "başlatma", e);
            durumYaz("Hata: " + e.getMessage());
        } finally {
            denetim = null;
        }
        Process p = java;
        if (p != null) {
            try { p.waitFor(); } catch (InterruptedException ignored) { }
            durumYaz("UYAP Editör kapandı.");
        }
        kapandi("süreç bitti");
        ana.post(this::stopSelf);
    }

    /** Uygulama çöküp yeniden açıldıysa önceki Java süreci sahipsiz kalmış olabilir: kapatılır (aynı kullanıcı kimliği). */
    private void eskiSureciKapat() {
        File f = new File(UyapMobil.kok(this), "java.pid");
        try {
            if (f.isFile()) {
                int pid = Integer.parseInt(AdaletServisi.okuMetin(f).trim());
                if (pid > 1 && new File("/proc/" + pid + "/cmdline").isFile()) {
                    String cmd = new String(AdaletServisi.okuHepsi(new FileInputStream("/proc/" + pid + "/cmdline")), StandardCharsets.UTF_8);
                    if (cmd.contains("uyapjava")) {
                        android.os.Process.killProcess(pid);
                        Tani.yaz("uyapmobil", "önceki Java süreci kapatıldı (pid " + pid + ")");
                        Thread.sleep(300);
                    }
                }
            }
        } catch (Exception ignored) { }
        f.delete();
    }

    private void pidYaz(Process p) {
        try {
            java.lang.reflect.Field fl = p.getClass().getDeclaredField("pid");
            fl.setAccessible(true);
            int pid = fl.getInt(p);
            try (OutputStream o = new FileOutputStream(new File(UyapMobil.kok(this), "java.pid"))) { o.write(String.valueOf(pid).getBytes(StandardCharsets.UTF_8)); }
        } catch (Exception ignored) { }
    }

    private void kapandi(String neden) {
        Dinleyici d = dinleyici;
        if (d != null) d.kapandi(neden);
    }

    /** Köprüden gelen bildirimler: PANO <hex> (editörde kopyalanan metin Android panosuna). */
    private void bildirimIsle(String satir) {
        if (satir.startsWith("BASLIK ")) {
            final String t = b64coz(satir.substring(7).trim());
            Dinleyici d = dinleyici;
            if (d != null) ana.post(() -> d.baslik(t));
            return;
        }
        if (satir.startsWith("MENU ")) {
            final String j = b64coz(satir.substring(5).trim());
            Dinleyici d = dinleyici;
            if (d != null) ana.post(() -> d.menu(j));
            return;
        }
        if (satir.startsWith("SEC ")) {
            String[] p = satir.split(" ", -1);
            final int no = Integer.parseInt(p[1]);
            final boolean kaydet = "kaydet".equals(p[2]);
            final String ad = p.length > 3 ? b64coz(p[3]) : "", uz = p.length > 4 ? b64coz(p[4]) : "";
            Dinleyici d = dinleyici;
            if (d == null) { seciciYanit(no, null, true); return; }
            ana.post(() -> d.dosyaIste(no, kaydet, ad, uz));
            return;
        }
        if (satir.startsWith("PANO ")) {
            final String m = new String(unhex(satir.substring(5).trim()), StandardCharsets.UTF_8);
            ana.post(() -> {
                ClipboardManager cm = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
                if (cm != null) cm.setPrimaryClip(ClipData.newPlainText("UYAP Editör", m));
            });
        }
    }

    private void gunlukPompasi(Process p) {
        File log = UyapMobil.gunluk(this);
        if (log.length() > 4_000_000) log.delete();
        try (InputStream in = p.getInputStream(); OutputStream o = new FileOutputStream(log, true)) {
            BufferedReader r = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8));
            String satir;
            while ((satir = r.readLine()) != null) {
                o.write((satir + "\n").getBytes(StandardCharsets.UTF_8));
                if (Tani.acik()) Tani.yaz("uyap-java", satir);
            }
        } catch (IOException ignored) { }
    }

    static boolean canli(Process p) {
        try { p.exitValue(); return false; } catch (IllegalThreadStateException e) { return true; }
    }

    @Override public void onDestroy() {
        if (gozcu != null) gozcu.stopWatching();
        Process p = java;
        if (p != null) p.destroy();
        ornek = null;
        super.onDestroy();
    }

    // ------------------------------------------------------------------------------------ belgeleri kaynağa geri yazma
    private static SharedPreferences kaynaklar(Context c) { return c.getSharedPreferences("uyapmobil_kaynak", MODE_PRIVATE); }

    /** Gelen belgenin asıl yerini (content:// ya da dosya) hatırla: kaydedince oraya da yazılır. */
    /**
     * İçe alınan (telefondan açılan) belgenin uygulama klasörüne kopyalanması da dosya gözcüsünü tetikliyordu: belge
     * daha açılmadan "Kaydedildi: İndirilenler/UYAP/…" deniyor ve İndirilenler'e gereksiz kopya yazılıyordu. Kopyalanan
     * dosyanın boyu/zamanı not edilir; gözcü aynı hâli görürse yok sayar (yalnızca editör gerçekten kaydedince yazılır).
     */
    static final java.util.Map<String, Long> ICE_ALINAN = new java.util.concurrent.ConcurrentHashMap<>();

    static void iceAlindi(File f) { ICE_ALINAN.put(f.getAbsolutePath(), f.lastModified() * 31 + f.length()); }

    static void kaynakKaydet(Context c, File yerel, Uri kaynak, boolean yazilabilir) {
        kaynaklar(c).edit().putString(yerel.getAbsolutePath(), (yazilabilir ? "w|" : "r|") + kaynak).apply();
    }

    private void belgeGozcusu() {
        if (gozcu != null) return;
        final File dizin = UyapMobil.belgeler(this);
        dizin.mkdirs();
        gozcu = new FileObserver(dizin.getAbsolutePath(), FileObserver.CLOSE_WRITE | FileObserver.MOVED_TO) {
            @Override public void onEvent(int olay, String ad) {
                if (ad == null) return;
                String a = ad.toLowerCase(Locale.ROOT);
                if (ad.startsWith(".")) return;
                final File f = new File(dizin, ad);
                // UDF/USF/PDF her zaman; diğerleri (ODT, Android seçicisiyle "Farklı kaydet") yalnızca asıl yeri biliniyorsa
                boolean bilinen = a.endsWith(".udf") || a.endsWith(".usf") || a.endsWith(".pdf");
                if (!bilinen && kaynaklar(UyapMobilServisi.this).getString(f.getAbsolutePath(), null) == null) return;
                ana.postDelayed(() -> geriYaz(f), 600);   // editör yazmayı bitirsin
            }
        };
        gozcu.startWatching();
    }

    private void geriYaz(File f) {
        if (!f.isFile() || f.length() == 0) return;
        Long ice = ICE_ALINAN.get(f.getAbsolutePath());
        if (ice != null && ice == f.lastModified() * 31 + f.length()) return;   // yalnızca içe alındı, değişmedi
        ICE_ALINAN.remove(f.getAbsolutePath());
        String k = kaynaklar(this).getString(f.getAbsolutePath(), null);
        String mesaj;
        try {
            if (k != null && k.startsWith("w|")) {
                Uri u = Uri.parse(k.substring(2));
                if ("file".equals(u.getScheme())) kopyala(f, new FileOutputStream(new File(u.getPath())));
                else kopyala(f, getContentResolver().openOutputStream(u, "wt"));
                mesaj = "✓ Kaydedildi (asıl dosyaya): " + f.getName();
            } else {
                File d = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "UYAP");
                d.mkdirs();
                File h = new File(d, f.getName());
                kopyala(f, new FileOutputStream(h));
                mesaj = "✓ Kaydedildi: İndirilenler/UYAP/" + f.getName();
                try { android.media.MediaScannerConnection.scanFile(this, new String[]{h.getAbsolutePath()}, null, null); } catch (Exception ignored) { }
            }
        } catch (Exception e) {
            Tani.hata("uyapmobil", "geri yazma " + f.getName(), e);
            mesaj = "Kaydedilen belge kaynağına yazılamadı: " + e.getMessage();
        }
        final String m = mesaj;
        durumYaz(m);
        ana.post(() -> android.widget.Toast.makeText(this, m, android.widget.Toast.LENGTH_SHORT).show());
    }

    private static void kopyala(File f, OutputStream o) throws IOException {
        if (o == null) throw new IOException("yazılamıyor");
        try (InputStream in = new FileInputStream(f); OutputStream out = o) {
            byte[] b = new byte[1 << 16];
            int n;
            while ((n = in.read(b)) > 0) out.write(b, 0, n);
        }
    }

    // ------------------------------------------------------------------------------------ bildirim
    private Notification bildirim(String metin) {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= 26 && nm != null && nm.getNotificationChannel(KANAL) == null) {
            NotificationChannel ch = new NotificationChannel(KANAL, "UYAP Editör", NotificationManager.IMPORTANCE_LOW);
            nm.createNotificationChannel(ch);
        }
        Intent ac = new Intent(this, UyapMobilActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        int bayrak = Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0;
        PendingIntent pi = PendingIntent.getActivity(this, 0, ac, bayrak);
        Notification.Builder b = Build.VERSION.SDK_INT >= 26 ? new Notification.Builder(this, KANAL) : new Notification.Builder(this);
        return b.setContentTitle("UYAP Editör çalışıyor").setContentText(metin).setSmallIcon(android.R.drawable.ic_menu_edit)
                .setOngoing(true).setContentIntent(pi).build();
    }
}
