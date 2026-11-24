package app.eimza.mobile;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Date;
import java.util.Deque;
import java.util.List;
import java.util.Locale;

/**
 * Thread-safe centralized diagnostic logging and TXT export engine.
 * Records structured system, USB CCID, smart card APDU, and signing events.
 * Fully sanitized: NEVER logs PINs, private keys, or unmasked sensitive credentials.
 */
public final class DiagnosticLogger {
    public enum Level { DEBUG, INFO, WARN, ERROR }
    public enum Tag { USB, CARD, DRIVER, APDU, CERT, PIN, SIGN, WEB, APP, SYSTEM }

    public static final class LogEntry {
        public final long timestamp;
        public final Level level;
        public final Tag tag;
        public final String message;
        public final String detail;

        LogEntry(Level level, Tag tag, String message, String detail) {
            this.timestamp = System.currentTimeMillis();
            this.level = level;
            this.tag = tag;
            this.message = sanitize(message);
            this.detail = detail == null ? "" : sanitize(detail);
        }

        public String formattedTime() {
            return new SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS", Locale.ROOT).format(new Date(timestamp));
        }

        @Override
        public String toString() {
            StringBuilder sb = new StringBuilder();
            sb.append("[").append(formattedTime()).append("] ");
            sb.append("[").append(level.name()).append("] ");
            sb.append("[").append(tag.name()).append("] ");
            sb.append(message);
            if (!detail.isEmpty()) {
                sb.append(" | ").append(detail);
            }
            return sb.toString();
        }
    }

    private static final int MAX_BUFFER_SIZE = 1200;
    private static final Deque<LogEntry> BUFFER = new ArrayDeque<>(MAX_BUFFER_SIZE);
    private static final Object LOCK = new Object();

    private DiagnosticLogger() { }

    public static void d(Tag tag, String message) { log(Level.DEBUG, tag, message, null); }
    public static void i(Tag tag, String message) { log(Level.INFO, tag, message, null); }
    public static void w(Tag tag, String message) { log(Level.WARN, tag, message, null); }
    public static void e(Tag tag, String message, Throwable t) {
        String detail = "";
        if (t != null) {
            StringWriter sw = new StringWriter();
            t.printStackTrace(new PrintWriter(sw));
            detail = sw.toString();
        }
        log(Level.ERROR, tag, message, detail);
    }

    public static void log(Level level, Tag tag, String message, String detail) {
        LogEntry entry = new LogEntry(level, tag, message, detail);
        synchronized (LOCK) {
            if (BUFFER.size() >= MAX_BUFFER_SIZE) {
                BUFFER.pollFirst();
            }
            BUFFER.addLast(entry);
        }
    }

    public static List<LogEntry> getEntries(Tag filterTag) {
        synchronized (LOCK) {
            List<LogEntry> list = new ArrayList<>();
            for (LogEntry e : BUFFER) {
                if (filterTag == null || e.tag == filterTag) {
                    list.add(e);
                }
            }
            return list;
        }
    }

    public static void clear() {
        synchronized (LOCK) {
            BUFFER.clear();
        }
    }

    /**
     * Sanitizes strings to prevent sensitive credentials (PINs, passwords, plain TCKNs)
     * from appearing in diagnostic logs.
     */
    public static String sanitize(String text) {
        if (text == null) return "";
        // Mask 11-digit Turkish National ID numbers (TCKN): 12345678901 -> 123*****01
        String result = text.replaceAll("(?<!\\d)(\\d{3})\\d{6}(\\d{2})(?!\\d)", "$1******$2");
        // Remove PIN / secret contents if accidentally passed
        result = result.replaceAll("(?i)(pin[=:]\\s*)[0-9a-zA-Z]{4,8}", "$1[GİZLENDİ]");
        result = result.replaceAll("(?i)(password[=:]\\s*)[^&\\s]+", "$1[GİZLENDİ]");
        return result;
    }

    /**
     * Generates a comprehensive, human-readable TXT diagnostic report.
     */
    public static String buildDiagnosticReport(Context context, SignerBackend backend, UsbCcidProbe probe) {
        StringBuilder sb = new StringBuilder();
        String dateStr = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss (z)", Locale.ROOT).format(new Date());

        sb.append("================================================================================\n");
        sb.append("                  E-İMZA ONE — SİSTEM VE TANI DETAY RAPORU                     \n");
        sb.append("================================================================================\n");
        sb.append("Oluşturulma Zamanı : ").append(dateStr).append("\n");
        sb.append("Uygulama Sürümü    : E-İmza One v0.3.1 (versionCode 36)\n");
        sb.append("Cihaz Modeli       : ").append(Build.MANUFACTURER).append(" ").append(Build.MODEL).append("\n");
        sb.append("Android Sürümü     : Android ").append(Build.VERSION.RELEASE)
                .append(" (API ").append(Build.VERSION.SDK_INT).append(")\n");
        sb.append("İşlemci / Mimari   : ").append(Build.SUPPORTED_ABIS != null && Build.SUPPORTED_ABIS.length > 0
                ? Build.SUPPORTED_ABIS[0] : "Bilinmiyor").append("\n");
        sb.append("================================================================================\n\n");

        sb.append("--------------------------------------------------------------------------------\n");
        sb.append("1. USB CCID DONANIM VE OKUYUCU BİLGİSİ\n");
        sb.append("--------------------------------------------------------------------------------\n");
        if (probe != null) {
            String reader = probe.activeReaderName();
            sb.append("Aktif Okuyucu      : ").append(reader != null ? reader : "Bağlı okuyucu yok").append("\n");
            byte[] atr = probe.activeAtr();
            if (atr != null && atr.length > 0) {
                sb.append("ATR (Hex)          : ").append(bytesToHex(atr)).append("\n");
                sb.append("ATR Uzunluğu       : ").append(atr.length).append(" bayt\n");
            } else {
                sb.append("ATR                : Henüz okunmadı veya kart takılı değil\n");
            }
        } else {
            sb.append("USB CCID Servisi   : Başlatılmadı\n");
        }
        sb.append("\n");

        sb.append("--------------------------------------------------------------------------------\n");
        sb.append("2. AKILLI KART VE SÜRÜCÜ DURUMU\n");
        sb.append("--------------------------------------------------------------------------------\n");
        if (backend != null) {
            sb.append("Sürücü Adı         : ").append(backend.displayName()).append("\n");
            sb.append("Sürücü Kimliği     : ").append(backend.id()).append("\n");
            sb.append("Sürücü Durumu      : ").append(backend.state().name()).append("\n");
            if (backend instanceof AkisSignerBackend) {
                AkisSignerBackend akis = (AkisSignerBackend) backend;
                sb.append("Kart Tanı Detayı   : ").append(akis.cardFailureDetail()).append("\n");
                sb.append("Tespit Edilen Token: ").append(akis.detectedTokenDisplayName()).append("\n");
            }
        } else {
            sb.append("Kart Sürücüsü      : Hazır değil\n");
        }
        sb.append("\n");

        sb.append("--------------------------------------------------------------------------------\n");
        sb.append("3. SERTİFİKA VE KİMLİK LİSTESİ\n");
        sb.append("--------------------------------------------------------------------------------\n");
        if (backend != null) {
            try {
                List<SignerBackend.CertificateSummary> certs = backend.certificates();
                if (certs.isEmpty()) {
                    sb.append("Kartta uygun imza sertifikası bulunamadı.\n");
                } else {
                    sb.append("Bulunan Sertifika Sayısı: ").append(certs.size()).append("\n\n");
                    for (int i = 0; i < certs.size(); i++) {
                        SignerBackend.CertificateSummary c = certs.get(i);
                        sb.append("  [").append(i + 1).append("] Sertifika ID : ").append(c.id).append("\n");
                        sb.append("      Konu (Subject) : ").append(sanitize(c.label)).append("\n");
                        sb.append("      Bitiş Tarihi   : ").append(c.validUntil).append("\n");
                    }
                }
            } catch (Exception e) {
                sb.append("Sertifikalar listelenirken hata oluştu: ").append(e.getMessage()).append("\n");
            }
        } else {
            sb.append("Sürücü oturumu açılmadığı için sertifikalar sorgulanamadı.\n");
        }
        sb.append("\n");

        sb.append("--------------------------------------------------------------------------------\n");
        sb.append("4. AYRINTILI OLAY VE İŞLEM LOGLARI (Kronolojik Sıra)\n");
        sb.append("--------------------------------------------------------------------------------\n");
        List<LogEntry> entries;
        synchronized (LOCK) {
            entries = new ArrayList<>(BUFFER);
        }
        if (entries.isEmpty()) {
            sb.append("Henüz kayıtlı olay bulunmuyor.\n");
        } else {
            for (LogEntry entry : entries) {
                sb.append(entry.toString()).append("\n");
            }
        }

        sb.append("\n================================================================================\n");
        sb.append("                           RAPOR SONU / END OF REPORT                           \n");
        sb.append("================================================================================\n");
        return sb.toString();
    }

    /**
     * Copies the full diagnostic report to Android clipboard and displays a Toast.
     */
    public static void copyReportToClipboard(Context context, String report) {
        try {
            ClipboardManager clipboard = (ClipboardManager) context.getSystemService(Context.CLIPBOARD_SERVICE);
            if (clipboard != null) {
                ClipData clip = ClipData.newPlainText("E-İmza One Tanı Raporu", report);
                clipboard.setPrimaryClip(clip);
                Toast.makeText(context, "Tanı raporu panoya kopyalandı!", Toast.LENGTH_SHORT).show();
            }
        } catch (Exception e) {
            Toast.makeText(context, "Panoya kopyalanamadı: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    /**
     * Saves the full diagnostic report as a .txt file on device storage (Documents or App Dir).
     */
    public static File saveReportToFile(Context context, String report) {
        try {
            String filename = "eimza-one-debug-"
                    + new SimpleDateFormat("yyyyMMdd-HHmmss", Locale.ROOT).format(new Date()) + ".txt";

            File targetDir = null;
            if (Environment.MEDIA_MOUNTED.equals(Environment.getExternalStorageState())) {
                targetDir = context.getExternalFilesDir(Environment.DIRECTORY_DOCUMENTS);
                if (targetDir == null) {
                    targetDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
                }
            }
            if (targetDir == null || (!targetDir.exists() && !targetDir.mkdirs())) {
                targetDir = context.getFilesDir();
            }

            File file = new File(targetDir, filename);
            try (FileOutputStream fos = new FileOutputStream(file);
                 OutputStreamWriter osw = new OutputStreamWriter(fos, StandardCharsets.UTF_8)) {
                osw.write(report);
                osw.flush();
            }
            i(Tag.APP, "Tanı raporu dosyaya kaydedildi: " + file.getAbsolutePath());
            return file;
        } catch (Exception e) {
            e(Tag.APP, "Tanı raporu dosyaya kaydedilemedi", e);
            return null;
        }
    }

    /**
     * Opens the Android system Share sheet (ACTION_SEND) to share the TXT report via WhatsApp, Email, Drive, etc.
     */
    public static void shareReport(Activity activity, String report) {
        try {
            Intent intent = new Intent(Intent.ACTION_SEND);
            intent.setType("text/plain");
            intent.putExtra(Intent.EXTRA_SUBJECT, "E-İmza One Detaylı Tanı ve Hata Raporu");
            intent.putExtra(Intent.EXTRA_TEXT, report);
            activity.startActivity(Intent.createChooser(intent, "Tanı Raporunu Paylaş"));
        } catch (Exception e) {
            Toast.makeText(activity, "Paylaşım başlatılamadı: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    private static String bytesToHex(byte[] bytes) {
        if (bytes == null) return "";
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) {
            sb.append(String.format(Locale.ROOT, "%02X ", b & 0xFF));
        }
        return sb.toString().trim();
    }
}
