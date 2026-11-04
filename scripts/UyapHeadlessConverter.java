package com.ckz.udemobile;

import java.io.*;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * Havelsan UYAP Resmi Headless Donusturucu (PDF, ODT, TIFF, DOCX)
 * Havelsan UYAP JAR kutuphanelerini (editor_lib.jar, jai_hvl.jar vb.)
 * dogrudan baslatip %100 birebir UYAP kalitesinde cikti uretir.
 */
public class UyapHeadlessConverter {

    /**
     * UDF dosyasini resmi Havelsan iText vektor motoru ile A4 PDF'e donusturur.
     * (tr.com.havelsan.uyap.system.editor.b.b)
     */
    public static boolean convertUdfToPdf(File udfFile, File outPdfFile) {
        try {
            byte[] udfBytes = Files.readAllBytes(udfFile.toPath());
            tr.com.havelsan.uyap.system.editor.b.b pdfEngine = new tr.com.havelsan.uyap.system.editor.b.b();
            try (FileOutputStream fos = new FileOutputStream(outPdfFile);
                 ByteArrayInputStream bais = new ByteArrayInputStream(udfBytes)) {
                pdfEngine.a(fos, bais);
            }
            return outPdfFile.exists() && outPdfFile.length() > 0;
        } catch (Throwable t) {
            System.err.println("[UyapHeadlessConverter] PDF Donusum Hatasi: " + t.getMessage());
            t.printStackTrace();
            return false;
        }
    }

    /**
     * UDF dosyasini resmi Havelsan ODF/ODT motoru ile OpenDocument metin belgesine donusturur.
     * (tr.com.havelsan.uyap.system.editor.b.a.f)
     */
    public static boolean convertUdfToOdt(File udfFile, File outOdtFile) {
        try {
            byte[] udfBytes = Files.readAllBytes(udfFile.toPath());
            byte[] xmlBytes = null;
            try (ZipInputStream zis = new ZipInputStream(new ByteArrayInputStream(udfBytes))) {
                ZipEntry ze;
                while ((ze = zis.getNextEntry()) != null) {
                    if (ze.getName().toLowerCase().endsWith("content.xml")) {
                        ByteArrayOutputStream baos = new ByteArrayOutputStream();
                        byte[] buf = new byte[4096];
                        int r;
                        while ((r = zis.read(buf)) != -1) baos.write(buf, 0, r);
                        xmlBytes = baos.toByteArray();
                        break;
                    }
                }
            }
            if (xmlBytes == null) {
                System.err.println("[UyapHeadlessConverter] UDF icinde content.xml bulunamadi!");
                return false;
            }

            Class<?> fClass = Class.forName("tr.com.havelsan.uyap.system.editor.b.a.f");
            Object converter = fClass.getDeclaredConstructor().newInstance();

            ByteArrayOutputStream xmlBaos = new ByteArrayOutputStream();
            xmlBaos.write(xmlBytes);

            Method mParse = fClass.getMethod("a", ByteArrayOutputStream.class);
            mParse.invoke(converter, xmlBaos);

            Method mSave = fClass.getMethod("b", File.class);
            mSave.invoke(converter, outOdtFile);

            return outOdtFile.exists() && outOdtFile.length() > 0;
        } catch (Throwable t) {
            System.err.println("[UyapHeadlessConverter] ODT Donusum Hatasi: " + t.getMessage());
            t.printStackTrace();
            return false;
        }
    }

    public static void main(String[] args) {
        if (args.length < 3) {
            System.out.println("Kullanim: java UyapHeadlessConverter <girdi.udf> <pdf|odt> <cikti_dosyasi>");
            System.exit(1);
        }

        File input = new File(args[0]);
        String format = args[1].toLowerCase();
        File output = new File(args[2]);

        if (!input.exists()) {
            System.err.println("Girdi dosyasi bulunamadi: " + input.getAbsolutePath());
            System.exit(2);
        }

        boolean ok = false;
        long start = System.currentTimeMillis();
        if ("pdf".equals(format)) {
            System.out.println("[UyapHeadlessConverter] PDF donusturuluyor: " + input.getName() + " -> " + output.getName());
            ok = convertUdfToPdf(input, output);
        } else if ("odt".equals(format)) {
            System.out.println("[UyapHeadlessConverter] ODT donusturuluyor: " + input.getName() + " -> " + output.getName());
            ok = convertUdfToOdt(input, output);
        } else {
            System.err.println("Desteklenmeyen format: " + format);
            System.exit(3);
        }

        long elapsed = System.currentTimeMillis() - start;
        if (ok) {
            System.out.println("✓ Donusum Basarili (" + elapsed + " ms): " + output.getAbsolutePath() + " (" + output.length() + " bayt)");
            System.exit(0);
        } else {
            System.err.println("✕ Donusum Basarisiz!");
            System.exit(4);
        }
    }
}
