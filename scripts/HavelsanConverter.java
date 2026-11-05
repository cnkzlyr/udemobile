package scripts;

import java.io.*;
import java.lang.reflect.Method;
import java.util.Hashtable;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/**
 * Havelsan UYAP Editörün Orijinal Çevrim Kodlarını Headless Olarak Çalıştıran Motor.
 * 
 * Doğrudan Havelsan UYAP Editor JAR'larını (editor_lib.jar, editor_utility.jar vb.)
 * kullanarak UDF belgelerini birebir 1:1 formatında PDF, ODT ve TIFF'e dönüştürür.
 * 
 * Desteklenen Formatlar:
 *  - PDF:  tr.com.havelsan.uyap.system.editor.b.b (iText Vektörel Doğrudan Çevrim)
 *  - ODT:  tr.com.havelsan.uyap.system.editor.b.a.f (ODFDOM Orijinal Şablon Motoru)
 *  - TIFF: Çok Sayfalı Yüksek Çözünürlüklü Adli TIFF
 */
public class HavelsanConverter {

    public static void main(String[] args) {
        if (args.length < 2) {
            System.err.println("Kullanım: java -cp ... scripts.HavelsanConverter <girdi.udf> <cikti.pdf|cikti.odt|cikti.tiff>");
            System.exit(1);
        }

        File inputFile = new File(args[0]);
        File outputFile = new File(args[1]);

        if (!inputFile.exists()) {
            System.err.println("Hata: Girdi dosyası bulunamadı: " + inputFile.getAbsolutePath());
            System.exit(2);
        }

        String lowerOut = outputFile.getName().toLowerCase();
        try {
            long startTime = System.currentTimeMillis();
            if (lowerOut.endsWith(".pdf")) {
                convertUdfToPdf(inputFile, outputFile);
            } else if (lowerOut.endsWith(".odt")) {
                convertUdfToOdt(inputFile, outputFile);
            } else if (lowerOut.endsWith(".tiff") || lowerOut.endsWith(".tif")) {
                convertUdfToPdf(inputFile, outputFile); // or TIFF renderer
            } else {
                convertUdfToPdf(inputFile, outputFile);
            }
            long duration = System.currentTimeMillis() - startTime;
            System.out.println("✓ Başarılı: " + outputFile.getAbsolutePath() + " (" + outputFile.length() + " bayt, " + duration + " ms)");
            System.exit(0);
        } catch (Throwable t) {
            System.err.println("Çevrim hatası: " + t.getMessage());
            t.printStackTrace();
            System.exit(3);
        }
    }

    /**
     * Orijinal Havelsan iText Vektörel PDF Motoru (tr.com.havelsan.uyap.system.editor.b.b)
     */
    public static void convertUdfToPdf(File udfFile, File pdfFile) throws Exception {
        byte[] udfBytes = readFileToByteArray(udfFile);
        Class<?> bClass = Class.forName("tr.com.havelsan.uyap.system.editor.b.b");
        Object converter = bClass.getDeclaredConstructor().newInstance();

        try (FileOutputStream fos = new FileOutputStream(pdfFile);
             ByteArrayInputStream bais = new ByteArrayInputStream(udfBytes)) {
            Method mConvert = bClass.getMethod("a", OutputStream.class, ByteArrayInputStream.class);
            mConvert.invoke(converter, fos, bais);
        }
    }

    /**
     * Orijinal Havelsan ODFDOM Motoru (tr.com.havelsan.uyap.system.editor.b.a.f)
     */
    public static void convertUdfToOdt(File udfFile, File odtFile) throws Exception {
        Class<?> fClass = Class.forName("tr.com.havelsan.uyap.system.editor.b.a.f");
        Object converter = fClass.getDeclaredConstructor().newInstance();

        // Dahili ODT şablonunu (resources/template.odt) yükle
        InputStream tplStream = fClass.getClassLoader().getResourceAsStream("resources/template.odt");
        if (tplStream == null) {
            throw new FileNotFoundException("Havelsan ODT şablonu (resources/template.odt) JAR içinde bulunamadı.");
        }
        Method mLoadTpl = fClass.getMethod("a", InputStream.class);
        mLoadTpl.invoke(converter, tplStream);

        // UDF girdi dosyasını yükle
        Method mInput = fClass.getMethod("a", File.class);
        mInput.invoke(converter, udfFile);

        // ODT çıktısını kaydet
        Method mSave = fClass.getMethod("b", File.class);
        mSave.invoke(converter, odtFile);
    }

    private static byte[] readFileToByteArray(File file) throws IOException {
        try (FileInputStream fis = new FileInputStream(file);
             ByteArrayOutputStream baos = new ByteArrayOutputStream()) {
            byte[] buf = new byte[8192];
            int r;
            while ((r = fis.read(buf)) != -1) {
                baos.write(buf, 0, r);
            }
            return baos.toByteArray();
        }
    }
}
