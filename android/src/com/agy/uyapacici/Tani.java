package com.agy.uyapacici;

import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.hardware.usb.UsbDevice;
import android.hardware.usb.UsbEndpoint;
import android.hardware.usb.UsbInterface;
import android.hardware.usb.UsbManager;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.Settings;
import android.util.Log;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * 🐞 Ayrıntılı tanı günlüğü (Adalet E-İmza / e-imza kartı / USB). Kullanıcı başlatır, durdurup paylaşır.
 *
 * Dosya: İndirilenler/CanEditor/tani/eimza_tani_TARİH.log (WhatsApp/e-posta ile gönderilebilir).
 * YAZILMAZ: PIN, APDU içerikleri (yalnızca uzunluk ve durum kelimesi SW), imzalanan belge metni.
 * Açıkken resmi Adalet E-İmza da ayrıntılı (DEBUG) günlükle başlatılır.
 */
public final class Tani {
    private static final String TAG = "CanEditorTani";
    private static volatile File dosya;
    private static volatile Context app;
    private static final Object KILIT = new Object();
    private static final SimpleDateFormat ZAMAN = new SimpleDateFormat("HH:mm:ss.SSS", Locale.ROOT);

    private Tani() { }

    public static void baglam(Context c) { if (c != null && app == null) app = c.getApplicationContext(); }

    public static boolean acik() {
        if (dosya != null) return true;
        Context c = app;
        if (c == null) return false;
        File isaret = new File(c.getFilesDir(), "tani_acik.txt");
        if (!isaret.exists()) return false;
        try { dosya = new File(AdaletServisi.okuMetin(isaret).trim()); } catch (IOException e) { return false; }
        return true;
    }

    public static File dosya() { return acik() ? dosya : null; }

    /** Yeni günlük başlatır; cihaz/izin/USB özetini yazar. Döner: günlük dosyası. */
    public static File baslat(Context c) {
        baglam(c);
        File dizin = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "CanEditor/tani");
        if (!dizin.mkdirs() && !dizin.isDirectory()) {
            File alt = c.getExternalFilesDir("tani");
            dizin = alt != null ? alt : new File(c.getFilesDir(), "tani");
            dizin.mkdirs();
        }
        File f = new File(dizin, "eimza_tani_" + new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.ROOT).format(new Date()) + ".log");
        synchronized (KILIT) {
            dosya = f;
            try (OutputStream o = new FileOutputStream(new File(c.getFilesDir(), "tani_acik.txt"))) {
                o.write(f.getAbsolutePath().getBytes("UTF-8"));
            } catch (IOException ignored) { }
        }
        yaz("=== CanEditor e-imza tanı günlüğü başladı ===");
        ozet(c);
        return f;
    }

    public static File durdur(Context c) {
        baglam(c);
        File f = dosya();
        yaz("=== tanı günlüğü durduruldu ===");
        synchronized (KILIT) {
            dosya = null;
            new File(c.getFilesDir(), "tani_acik.txt").delete();
        }
        return f;
    }

    public static void yaz(String alan, String mesaj) { yaz("[" + alan + "] " + mesaj); }

    public static void yaz(String satir) {
        Log.d(TAG, satir);
        File f = dosya();
        if (f == null) return;
        synchronized (KILIT) {
            try (OutputStream o = new FileOutputStream(f, true)) {
                o.write((ZAMAN.format(new Date()) + " " + satir + "\n").getBytes("UTF-8"));
            } catch (IOException ignored) { }
        }
    }

    public static void hata(String alan, String mesaj, Throwable t) {
        StringBuilder sb = new StringBuilder(mesaj).append(": ").append(t);
        StackTraceElement[] st = t.getStackTrace();
        for (int i = 0; i < Math.min(8, st.length); i++) sb.append("\n      at ").append(st[i]);
        if (t.getCause() != null) sb.append("\n    sebep: ").append(t.getCause());
        yaz(alan, sb.toString());
    }

    /** Cihaz, sürüm, izinler, kurulum ve USB cihazları. */
    public static void ozet(Context c) {
        try {
            PackageInfo pi = c.getPackageManager().getPackageInfo(c.getPackageName(), 0);
            yaz("cihaz", Build.MANUFACTURER + " " + Build.MODEL + " · Android " + Build.VERSION.RELEASE + " (API " + Build.VERSION.SDK_INT
                    + ") · ABI " + (Build.SUPPORTED_ABIS.length > 0 ? Build.SUPPORTED_ABIS[0] : "?"));
            yaz("uygulama", "CanEditor " + pi.versionName + " (" + pi.versionCode + ") · hedef SDK " + c.getApplicationInfo().targetSdkVersion);
        } catch (Exception e) { yaz("uygulama", "bilgi alınamadı: " + e); }
        if (Build.VERSION.SDK_INT >= 23) yaz("izin", "diğer uygulamaların üzerinde göster (PIN penceresi): " + Settings.canDrawOverlays(c));
        if (Build.VERSION.SDK_INT >= 33) yaz("izin", "bildirim: " + (c.checkSelfPermission("android.permission.POST_NOTIFICATIONS") == 0));
        yaz("adalet", "resmi uygulama: " + (AdaletKurulum.jarDosyasi(c).exists()
                ? "kurulu, sürüm " + AdaletKurulum.kuruluSurum(c) + " (" + AdaletKurulum.jarDosyasi(c).length() + " bayt)" : "KURULU DEĞİL"));
        File jre = new File(c.getFilesDir(), "java/jre/bin/java");
        yaz("adalet", "gömülü Java: " + (jre.exists() ? "çıkarılmış (" + jre.getAbsolutePath() + ", çalıştırılabilir=" + jre.canExecute() + ")" : "henüz çıkarılmamış"));
        yaz("adalet", "servis çalışıyor=" + AdaletServisi.calisiyor() + " · durum=" + AdaletServisi.durum());
        usbListesi(c);
    }

    public static void usbListesi(Context c) {
        UsbManager um = (UsbManager) c.getSystemService(Context.USB_SERVICE);
        if (um == null) { yaz("usb", "UsbManager yok (cihaz USB host desteklemiyor?)"); return; }
        if (um.getDeviceList().isEmpty()) { yaz("usb", "takılı USB cihazı YOK (OTG bağlantısını/kabloyu kontrol edin)"); return; }
        for (UsbDevice d : um.getDeviceList().values()) {
            StringBuilder sb = new StringBuilder();
            sb.append(String.format(Locale.ROOT, "%s VID=%04X PID=%04X sınıf=%02X ad=%s üretici=%s izin=%s",
                    d.getDeviceName(), d.getVendorId(), d.getProductId(), d.getDeviceClass(),
                    Build.VERSION.SDK_INT >= 21 ? d.getProductName() : "?", Build.VERSION.SDK_INT >= 21 ? d.getManufacturerName() : "?",
                    um.hasPermission(d)));
            for (int i = 0; i < d.getInterfaceCount(); i++) {
                UsbInterface f = d.getInterface(i);
                sb.append(String.format(Locale.ROOT, "\n      arayüz %d sınıf=%02X alt=%02X protokol=%02X", f.getId(), f.getInterfaceClass(),
                        f.getInterfaceSubclass(), f.getInterfaceProtocol()));
                for (int k = 0; k < f.getEndpointCount(); k++) {
                    UsbEndpoint e = f.getEndpoint(k);
                    sb.append(String.format(Locale.ROOT, " [uç 0x%02X tip=%d mps=%d]", e.getAddress(), e.getType(), e.getMaxPacketSize()));
                }
            }
            sb.append("  → köprü için ").append(CcidKopru.ccidArayuzu(d) != null ? "UYGUN (CCID)" : "uygun değil");
            yaz("usb", sb.toString());
        }
    }

    /** Günlüğü paylaşma penceresi (WhatsApp, e-posta...). */
    public static void paylas(Context c, File f) {
        if (f == null || !f.exists()) return;
        Uri u = Uri.parse("content://" + CanFileProvider.AUTHORITY + f.getAbsolutePath());
        Intent i = new Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_STREAM, u)
                .putExtra(Intent.EXTRA_SUBJECT, "CanEditor e-imza tanı günlüğü").addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        c.startActivity(Intent.createChooser(i, "Tanı günlüğünü gönder").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
    }
}
