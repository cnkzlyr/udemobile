package uyap;

import java.io.*;
import java.lang.reflect.Method;
import java.nio.file.Files;

/**
 * UYAP Doküman Editörü Resmi Vektörel Dışa Aktarım Köprüsü
 *
 * UYAP Doküman Editörünün kendi orijinal jar kütüphanelerindeki
 * (editor_lib.jar, jai_hvl.jar, jdom.jar vb.) dahili sınıfları kullanarak
 * UDF (.udf) dosyalarını birebir orijinal vektör görünümüyle PDF ve ODT
 * formatlarına dönüştürür.
 */
public class UyapVectorExporter {

    public static boolean exportToPdf(File inUdf, File outPdf) {
        if (!inUdf.exists() || !inUdf.canRead()) {
            System.err.println("[HATA] Giriş UDF dosyası okunamıyor: " + inUdf.getAbsolutePath());
            return false;
        }

        try {
            byte[] bytes = Files.readAllBytes(inUdf.toPath());
            ByteArrayInputStream bais = new ByteArrayInputStream(bytes);
            
            // Hedef dizini garanti et
            File parent = outPdf.getParentFile();
            if (parent != null && !parent.exists()) {
                parent.mkdirs();
            }

            try (FileOutputStream fos = new FileOutputStream(outPdf)) {
                Class<?> bClass = Class.forName("tr.com.havelsan.uyap.system.editor.b.b");
                Object bObj = bClass.getDeclaredConstructor().newInstance();
                Method m = bClass.getMethod("a", OutputStream.class, ByteArrayInputStream.class);
                m.invoke(bObj, fos, bais);
            }

            if (outPdf.exists() && outPdf.length() > 0) {
                System.out.println("[BAŞARILI] PDF oluşturuldu (" + outPdf.length() + " bayt): " + outPdf.getAbsolutePath());
                return true;
            } else {
                System.err.println("[HATA] PDF çıktısı boş veya oluşturulamadı!");
                return false;
            }
        } catch (Throwable t) {
            System.err.println("[HATA] UDF -> PDF dönüştürme hatası: " + t.getMessage());
            t.printStackTrace(System.err);
            return false;
        }
    }

    public static boolean exportToOdt(File inUdf, File outOdt) {
        if (!inUdf.exists() || !inUdf.canRead()) {
            System.err.println("[HATA] Giriş UDF dosyası okunamıyor: " + inUdf.getAbsolutePath());
            return false;
        }

        try {
            File parent = outOdt.getParentFile();
            if (parent != null && !parent.exists()) {
                parent.mkdirs();
            }

            // 1. UDF dosyasından DocumentEx modelini yükle
            Class<?> loClass = Class.forName("tr.com.havelsan.uyap.system.editor.common.gui.lo");
            Method loadDocM = loClass.getMethod("a", InputStream.class);
            Object docEx;
            try (FileInputStream fis = new FileInputStream(inUdf)) {
                docEx = loadDocM.invoke(null, fis);
            }

            if (docEx == null) {
                System.err.println("[HATA] DocumentEx nesnesi oluşturulamadı.");
                return false;
            }

            // 2. DocumentEx'i UYAP'ın XML formatında serileştir
            Class<?> jClass = Class.forName("tr.com.havelsan.uyap.system.editor.common.text.J");
            Object jObj = jClass.getDeclaredConstructor().newInstance();
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            Method saveXmlM = jClass.getMethod("b", Class.forName("tr.com.havelsan.uyap.system.editor.common.text.DocumentEx"), OutputStream.class);
            saveXmlM.invoke(jObj, docEx, baos);

            // 3. OdfToolkit tabanlı UYAP ODT motorunu çalıştır
            Class<?> fClass = Class.forName("tr.com.havelsan.uyap.system.editor.b.a.f");
            Object fObj = fClass.getDeclaredConstructor().newInstance();
            Method fa = fClass.getMethod("a", ByteArrayOutputStream.class);
            fa.invoke(fObj, baos);

            Method fb = fClass.getMethod("b", File.class);
            fb.invoke(fObj, outOdt);

            if (outOdt.exists() && outOdt.length() > 0) {
                System.out.println("[BAŞARILI] ODT oluşturuldu (" + outOdt.length() + " bayt): " + outOdt.getAbsolutePath());
                return true;
            } else {
                System.err.println("[HATA] ODT çıktısı boş veya oluşturulamadı!");
                return false;
            }
        } catch (Throwable t) {
            System.err.println("[HATA] UDF -> ODT dönüştürme hatası: " + t.getMessage());
            t.printStackTrace(System.err);
            return false;
        }
    }

    public static void main(String[] args) {
        if (args.length < 2) {
            System.out.println("Kullanım: java uyap.UyapVectorExporter <pdf|odt> <giris.udf> [cikis_dosyasi]");
            System.exit(1);
        }

        String mode = args[0].toLowerCase();
        File inUdf = new File(args[1]);
        if (!inUdf.exists()) {
            System.err.println("[HATA] Giriş dosyası bulunamadı: " + inUdf.getAbsolutePath());
            System.exit(2);
        }

        String outPath;
        if (args.length >= 3) {
            outPath = args[2];
        } else {
            String name = inUdf.getAbsolutePath();
            int dotIdx = name.lastIndexOf('.');
            String base = (dotIdx > 0) ? name.substring(0, dotIdx) : name;
            outPath = base + "." + mode;
        }

        File outFile = new File(outPath);
        boolean success = false;
        if ("pdf".equals(mode)) {
            success = exportToPdf(inUdf, outFile);
        } else if ("odt".equals(mode)) {
            success = exportToOdt(inUdf, outFile);
        } else {
            System.err.println("[HATA] Bilinmeyen mod: " + mode + " (desteklenen: pdf, odt)");
            System.exit(3);
        }

        System.exit(success ? 0 : 1);
    }
}
