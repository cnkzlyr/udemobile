package uyap;

import java.io.*;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * UYAP UDF -> PDF Toplu Vektörel Dönüştürücü (Official Havelsan Engine)
 * Av. Can Kızılyar - naps-uyap-thunar-tools & udemobile motorlarından uyarlanmıştır.
 * TrueType Font Gömme (Embedded Times New Roman, Arial vb.) desteklidir.
 */
/*
 * UYAP Evrak Yöneticisi - UDF -> PDF dönüştürücü
 * Copyright (c) 2026 Av. Can KIZILYAR. Tüm hakları saklıdır.
 */
public class UdfBatchPdfConverter {

    private static final PrintStream CONSOLE = System.out;

    public static void main(String[] args) throws Exception {
        String targetPathStr = null;
        boolean forceOverwrite = false;

        for (String arg : args) {
            if ("--force".equalsIgnoreCase(arg) || "-f".equalsIgnoreCase(arg)) {
                forceOverwrite = true;
            } else if (!arg.startsWith("-")) {
                targetPathStr = arg;
            }
        }

        if (targetPathStr == null) {
            if (new File("/sdcard/Download/UYAP_Indirilenler").exists()) {
                targetPathStr = "/sdcard/Download/UYAP_Indirilenler";
            } else if (new File("../UYAP_Indirilenler").exists()) {
                targetPathStr = "../UYAP_Indirilenler";
            } else if (new File("UYAP_Indirilenler").exists()) {
                targetPathStr = "UYAP_Indirilenler";
            } else {
                targetPathStr = ".";
            }
        }

        File target = new File(targetPathStr);
        if (!target.exists()) {
            CONSOLE.println("[HATA] Belirtilen dosya veya dizin bulunamadı: " + targetPathStr);
            System.exit(1);
        }

        // 1. Havelsan FontMapper'ını Termux & Android sistem fontlarıyla başlat
        initHavelsanFonts();

        List<File> allUdfs = new ArrayList<>();
        if (target.isFile()) {
            if (target.getName().toLowerCase().endsWith(".udf")) {
                allUdfs.add(target);
            }
        } else {
            CONSOLE.println("==================================================================");
            CONSOLE.println("    UYAP UDF -> PDF Vektörel Dönüştürücü (Havelsan + TrueType)");
            CONSOLE.println("==================================================================");
            CONSOLE.println("[*] Dizin taranıyor: " + target.getAbsolutePath());
            scanDirectory(target, allUdfs);
            CONSOLE.println("[✓] Toplam bulunan UDF sayısı: " + allUdfs.size() + " adet");
        }

        List<File> toConvert = new ArrayList<>();
        int alreadyExistsCount = 0;
        for (File udf : allUdfs) {
            String p = udf.getAbsolutePath();
            String pdfPath = p.substring(0, p.lastIndexOf('.')) + ".pdf";
            File pdfFile = new File(pdfPath);
            if (!forceOverwrite && pdfFile.exists() && pdfFile.length() > 0) {
                alreadyExistsCount++;
            } else {
                toConvert.add(udf);
            }
        }

        if (allUdfs.size() > 1) {
            CONSOLE.println("[✓] Zaten mevcut PDF sayısı   : " + alreadyExistsCount + " adet (atlandı)");
            CONSOLE.println("[*] Dönüştürülecek yeni UDF  : " + toConvert.size() + " adet");
            if (forceOverwrite) {
                CONSOLE.println("[!] Zorunlu mod (--force) aktif: Mevcut PDF'ler Times New Roman ile yenileniyor.");
            }
            CONSOLE.println("------------------------------------------------------------------");
        }

        if (toConvert.isEmpty()) {
            CONSOLE.println("[✓] Bütün UDF dosyalarının PDF kopyaları zaten mevcut! İşlem tamamlandı.");
            return;
        }

        // Havelsan debug loglarını sustur
        PrintStream devNull = new PrintStream(new OutputStream() {
            @Override public void write(int b) {}
            @Override public void write(byte[] b, int off, int len) {}
        });
        System.setOut(devNull);
        System.setErr(devNull);

        Class<?> bClass = Class.forName("tr.com.havelsan.uyap.system.editor.b.b");

        // FontMapper yapılandırması: Times New Roman ve sistem fontlarını kaydet ve PDF'e göm (embedded=true)
        try {
            Method getMapper = bClass.getDeclaredMethod("a");
            getMapper.setAccessible(true);
            Object cObj = getMapper.invoke(null);

            Class<?> cClass = Class.forName("tr.com.havelsan.uyap.system.editor.b.c");
            Method regDir = cClass.getMethod("a", String.class);

            // Android & Linux Font Dizinleri
            regDir.invoke(cObj, "/data/data/com.termux/files/home/.fonts/microsoft");
            regDir.invoke(cObj, "/data/data/com.termux/files/home/.fonts");
            regDir.invoke(cObj, "/system/fonts");
            regDir.invoke(cObj, "/data/data/com.termux/files/usr/share/fonts");

            // Paketle gelen / kullanıcının belirttiği font dizinleri (UYAP_FONT_DIR, ';' veya ':' ile ayrılmış)
            String extra = System.getenv("UYAP_FONT_DIR");
            if (extra != null) {
                for (String dir : extra.split(java.util.regex.Pattern.quote(File.pathSeparator))) {
                    if (!dir.trim().isEmpty() && new File(dir.trim()).isDirectory()) regDir.invoke(cObj, dir.trim());
                }
            }
            // Linux / macOS sistem fontları
            String home = System.getProperty("user.home", "");
            for (String dir : new String[]{"/usr/share/fonts", "/usr/local/share/fonts", home + "/.fonts",
                    home + "/.local/share/fonts", "/Library/Fonts", "/System/Library/Fonts", home + "/Library/Fonts"}) {
                if (new File(dir).isDirectory()) regDir.invoke(cObj, dir);
            }

            // Windows Font Dizinleri (Times New Roman, Arial, Calibri, vs.)
            String winDir = System.getenv("WINDIR");
            if (winDir != null && !winDir.trim().isEmpty()) {
                regDir.invoke(cObj, winDir + "\\Fonts");
            } else {
                regDir.invoke(cObj, "C:\\Windows\\Fonts");
            }
            String userProfile = System.getenv("USERPROFILE");
            if (userProfile != null && !userProfile.trim().isEmpty()) {
                regDir.invoke(cObj, userProfile + "\\AppData\\Local\\Microsoft\\Windows\\Fonts");
            }

            Method getA = cClass.getMethod("a");
            java.util.HashMap map = (java.util.HashMap) getA.invoke(cObj);

            Class<?> dClass = Class.forName("tr.com.havelsan.uyap.system.editor.b.d");
            for (java.lang.reflect.Field f : dClass.getFields()) {
                if (f.getType() == boolean.class) {
                    for (Object dObj : map.values()) {
                        f.setBoolean(dObj, true); // embedded = true: Türkçe karakterler ve TrueType fontu PDF içine göm
                    }
                    break;
                }
            }
        } catch (Throwable ignored) {}

        Method mConvert = bClass.getMethod("a", OutputStream.class, ByteArrayInputStream.class);

        int threads = Math.min(6, Math.max(2, Runtime.getRuntime().availableProcessors()));
        if (allUdfs.size() > 1) {
            CONSOLE.println("[*] " + threads + " iş parçacığı (threads) ile vektörel çevrim başlatılıyor...");
        }

        ExecutorService executor = Executors.newFixedThreadPool(threads);
        AtomicInteger successCounter = new AtomicInteger(0);
        AtomicInteger failCounter = new AtomicInteger(0);
        AtomicInteger processedCounter = new AtomicInteger(0);

        int totalToConvert = toConvert.size();
        long startTime = System.currentTimeMillis();

        List<Future<?>> futures = new ArrayList<>(totalToConvert);

        for (File udf : toConvert) {
            futures.add(executor.submit(() -> {
                try {
                    String p = udf.getAbsolutePath();
                    String pdfPath = p.substring(0, p.lastIndexOf('.')) + ".pdf";
                    File pdfFile = new File(pdfPath);

                    byte[] bytes = Files.readAllBytes(udf.toPath());
                    if (bytes.length == 0) {
                        failCounter.incrementAndGet();
                        return;
                    }

                    // comments.xml varsa headless ClassCastException hatasını önlemek için in-memory ayıkla
                    try {
                        boolean hasComments = false;
                        try (java.util.zip.ZipInputStream zis = new java.util.zip.ZipInputStream(new ByteArrayInputStream(bytes))) {
                            java.util.zip.ZipEntry ze;
                            while ((ze = zis.getNextEntry()) != null) {
                                if ("comments.xml".equalsIgnoreCase(ze.getName())) {
                                    hasComments = true;
                                    break;
                                }
                            }
                        }
                        if (hasComments) {
                            ByteArrayOutputStream cleaned = new ByteArrayOutputStream(bytes.length);
                            try (java.util.zip.ZipInputStream zis2 = new java.util.zip.ZipInputStream(new ByteArrayInputStream(bytes));
                                 java.util.zip.ZipOutputStream zos2 = new java.util.zip.ZipOutputStream(cleaned)) {
                                java.util.zip.ZipEntry ze2;
                                byte[] buf = new byte[8192];
                                while ((ze2 = zis2.getNextEntry()) != null) {
                                    if ("comments.xml".equalsIgnoreCase(ze2.getName())) continue;
                                    zos2.putNextEntry(new java.util.zip.ZipEntry(ze2.getName()));
                                    int n;
                                    while ((n = zis2.read(buf)) > 0) zos2.write(buf, 0, n);
                                    zos2.closeEntry();
                                }
                            }
                            bytes = cleaned.toByteArray();
                        }
                    } catch (Throwable ignored) {}

                    Object bObj = bClass.getDeclaredConstructor().newInstance();
                    try (FileOutputStream fos = new FileOutputStream(pdfFile);
                         ByteArrayInputStream bais = new ByteArrayInputStream(bytes)) {
                        mConvert.invoke(bObj, fos, bais);
                    }

                    if (pdfFile.exists() && pdfFile.length() > 0) {
                        successCounter.incrementAndGet();
                    } else {
                        failCounter.incrementAndGet();
                    }
                } catch (Throwable t) {
                    failCounter.incrementAndGet();
                } finally {
                    int done = processedCounter.incrementAndGet();
                    if (allUdfs.size() > 1 && (done % 50 == 0 || done == totalToConvert)) {
                        long elapsed = System.currentTimeMillis() - startTime;
                        double sec = Math.max(0.1, elapsed / 1000.0);
                        double rate = done / sec;
                        double pct = (done * 100.0) / totalToConvert;
                        CONSOLE.printf("  [%d / %d] (%%%.1f) - Başarılı: %d | Hata: %d | Hız: %.1f evrak/sn\n",
                                done, totalToConvert, pct, successCounter.get(), failCounter.get(), rate);
                    }
                }
            }));
        }

        for (Future<?> f : futures) {
            try {
                f.get();
            } catch (Exception ignored) {}
        }

        executor.shutdown();
        long totalElapsed = System.currentTimeMillis() - startTime;
        double totalSec = totalElapsed / 1000.0;

        if (allUdfs.size() > 1) {
            CONSOLE.println("------------------------------------------------------------------");
            CONSOLE.printf("[✓] TAMAMLANDI: %d PDF başarıyla oluşturuldu, %d hata (Süre: %.1f sn)\n",
                    successCounter.get(), failCounter.get(), totalSec);
            CONSOLE.println("==================================================================");
        } else if (successCounter.get() > 0) {
            String p = allUdfs.get(0).getAbsolutePath();
            CONSOLE.println("[✓] PDF oluşturuldu: " + p.substring(0, p.lastIndexOf('.')) + ".pdf");
        }
    }

    private static void initHavelsanFonts() {
        try {
            Class<?> bClass = Class.forName("tr.com.havelsan.uyap.system.editor.b.b");
            Method getMapper = bClass.getDeclaredMethod("a");
            getMapper.setAccessible(true);
            Object cObj = getMapper.invoke(null);

            Class<?> cClass = Class.forName("tr.com.havelsan.uyap.system.editor.b.c");
            Method regDir = cClass.getMethod("a", String.class);

            String extraDirs = System.getenv("UYAP_FONT_DIR");
            String homeDir = System.getProperty("user.home", "");
            String[] fontDirs = {
                extraDirs != null ? extraDirs.split(java.util.regex.Pattern.quote(File.pathSeparator))[0] : "",
                "/usr/share/fonts", "/usr/local/share/fonts", homeDir + "/.fonts", homeDir + "/.local/share/fonts",
                "/Library/Fonts", "/System/Library/Fonts", homeDir + "/Library/Fonts",
                "/data/data/com.termux/files/home/.fonts/microsoft",
                "/data/data/com.termux/files/home/.fonts",
                "/system/fonts",
                "/data/data/com.termux/files/usr/share/fonts"
            };

            int totalLoaded = 0;
            for (String dir : fontDirs) {
                try {
                    File d = new File(dir);
                    if (d.exists() && d.isDirectory()) {
                        totalLoaded += (int) regDir.invoke(cObj, dir);
                    }
                } catch (Exception ignored) {}
            }

            // Bütün fontlarda TrueType embedded = true bayrağını aktif et
            Method getA = cClass.getMethod("a");
            HashMap<?, ?> map = (HashMap<?, ?>) getA.invoke(cObj);

            Class<?> dClass = Class.forName("tr.com.havelsan.uyap.system.editor.b.d");
            Field embeddedField = null;
            for (Field f : dClass.getFields()) {
                if (f.getType() == boolean.class) {
                    embeddedField = f;
                    break;
                }
            }

            if (embeddedField != null && map != null) {
                for (Object dObj : map.values()) {
                    try {
                        embeddedField.setBoolean(dObj, true);
                    } catch (Exception ignored) {}
                }
            }

            // Alias tanımları: Serif / Times / Roman -> Times New Roman
            Method aliasMethod = cClass.getMethod("a", String.class, String.class);
            aliasMethod.invoke(cObj, "Serif", "Times New Roman");
            aliasMethod.invoke(cObj, "TimesRoman", "Times New Roman");
            aliasMethod.invoke(cObj, "Times", "Times New Roman");
            aliasMethod.invoke(cObj, "SansSerif", "Arial");
            aliasMethod.invoke(cObj, "Dialog", "Arial");
            aliasMethod.invoke(cObj, "Calibri", "Arial");

        } catch (Throwable t) {
            // Font yüklenemezse orijinal akış bozulmasın
        }
    }

    private static void scanDirectory(File dir, List<File> list) {
        File[] files = dir.listFiles();
        if (files == null) return;
        for (File f : files) {
            if (f.isDirectory()) {
                scanDirectory(f, list);
            } else if (f.getName().toLowerCase().endsWith(".udf")) {
                list.add(f);
            }
        }
    }
}
