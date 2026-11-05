package scripts;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;

import java.io.*;
import java.lang.reflect.Method;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;

/**
 * Havelsan UYAP Editörün Orijinal Çevrim Kodlarını Headless Olarak Çalıştıran Motor.
 * 
 * Doğrudan Havelsan UYAP Editor JAR'larını (editor_lib.jar, editor_utility.jar vb.)
 * kullanarak UDF belgelerini birebir 1:1 formatında PDF, ODT ve TIFF'e dönüştürür.
 * 
 * Modlar:
 *  1) CLI Modu: java ... scripts.HavelsanConverter <girdi.udf> <cikti.pdf|cikti.odt>
 *  2) HTTP Sunucu Modu: java ... scripts.HavelsanConverter --serve [port] (Varsayılan port: 5976)
 *     CanEditor (Tauri / Web) ile 1:1 doğrudan entegrasyon sağlar.
 */
public class HavelsanConverter {

    public static final int DEFAULT_PORT = 5976;

    public static void main(String[] args) {
        if (args.length == 0 || (args.length == 1 && args[0].equals("--serve"))) {
            int port = (args.length == 2) ? Integer.parseInt(args[1]) : DEFAULT_PORT;
            startHeadlessServer(port);
            return;
        }

        if (args[0].equals("--serve")) {
            int port = (args.length >= 2) ? Integer.parseInt(args[1]) : DEFAULT_PORT;
            startHeadlessServer(port);
            return;
        }

        if (args.length < 2) {
            System.err.println("Kullanım (CLI): java -cp ... scripts.HavelsanConverter <girdi.udf> <cikti.pdf|cikti.odt>");
            System.err.println("Kullanım (Sunucu): java -cp ... scripts.HavelsanConverter --serve [5976]");
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
        byte[] pdfBytes = convertUdfBytesToPdf(udfBytes);
        try (FileOutputStream fos = new FileOutputStream(pdfFile)) {
            fos.write(pdfBytes);
        }
    }

    public static byte[] convertUdfBytesToPdf(byte[] udfBytes) throws Exception {
        Class<?> bClass = Class.forName("tr.com.havelsan.uyap.system.editor.b.b");
        Object converter = bClass.getDeclaredConstructor().newInstance();

        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        try (ByteArrayInputStream bais = new ByteArrayInputStream(udfBytes)) {
            Method mConvert = bClass.getMethod("a", OutputStream.class, ByteArrayInputStream.class);
            mConvert.invoke(converter, baos, bais);
        }
        return baos.toByteArray();
    }

    /**
     * Orijinal Havelsan ODFDOM Motoru (tr.com.havelsan.uyap.system.editor.b.a.f)
     */
    public static void convertUdfToOdt(File udfFile, File odtFile) throws Exception {
        byte[] udfBytes = readFileToByteArray(udfFile);
        byte[] odtBytes = convertUdfBytesToOdt(udfBytes);
        try (FileOutputStream fos = new FileOutputStream(odtFile)) {
            fos.write(odtBytes);
        }
    }

    public static byte[] convertUdfBytesToOdt(byte[] udfBytes) throws Exception {
        File tmpUdf = File.createTempFile("tmp_udf_", ".udf");
        File tmpOdt = File.createTempFile("tmp_odt_", ".odt");
        try {
            try (FileOutputStream fos = new FileOutputStream(tmpUdf)) {
                fos.write(udfBytes);
            }

            Class<?> fClass = Class.forName("tr.com.havelsan.uyap.system.editor.b.a.f");
            Object converter = fClass.getDeclaredConstructor().newInstance();

            InputStream tplStream = fClass.getClassLoader().getResourceAsStream("resources/template.odt");
            if (tplStream == null) {
                throw new FileNotFoundException("Havelsan ODT şablonu (resources/template.odt) JAR içinde bulunamadı.");
            }
            Method mLoadTpl = fClass.getMethod("a", InputStream.class);
            mLoadTpl.invoke(converter, tplStream);

            Method mInput = fClass.getMethod("a", File.class);
            mInput.invoke(converter, tmpUdf);

            Method mSave = fClass.getMethod("b", File.class);
            mSave.invoke(converter, tmpOdt);

            return readFileToByteArray(tmpOdt);
        } finally {
            tmpUdf.delete();
            tmpOdt.delete();
        }
    }

    /**
     * CanEditor (Tauri / WebView) Entegrasyonu İçin Yerel Headless HTTP Sunucusu (Port 5976)
     */
    public static void startHeadlessServer(int port) {
        try {
            HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", port), 0);

            // POST /api/v1/convert?format=pdf|odt
            server.createContext("/api/v1/convert", new HttpHandler() {
                @Override
                public void handle(HttpExchange exchange) throws IOException {
                    // CORS Başlıkları
                    exchange.getResponseHeaders().set("Access-Control-Allow-Origin", "*");
                    exchange.getResponseHeaders().set("Access-Control-Allow-Methods", "POST, OPTIONS");
                    exchange.getResponseHeaders().set("Access-Control-Allow-Headers", "*");

                    if ("OPTIONS".equalsIgnoreCase(exchange.getRequestMethod())) {
                        exchange.sendResponseHeaders(204, -1);
                        return;
                    }

                    if (!"POST".equalsIgnoreCase(exchange.getRequestMethod())) {
                        byte[] msg = "Method not allowed".getBytes(StandardCharsets.UTF_8);
                        exchange.sendResponseHeaders(405, msg.length);
                        try (OutputStream os = exchange.getResponseBody()) { os.write(msg); }
                        return;
                    }

                    String query = exchange.getRequestURI().getQuery();
                    String format = "pdf";
                    if (query != null && query.contains("format=")) {
                        for (String part : query.split("&")) {
                            if (part.startsWith("format=")) {
                                format = part.substring("format=".length()).toLowerCase();
                            }
                        }
                    }

                    byte[] inputBytes = readStreamToByteArray(exchange.getRequestBody());
                    if (inputBytes == null || inputBytes.length == 0) {
                        byte[] err = "Empty body".getBytes(StandardCharsets.UTF_8);
                        exchange.sendResponseHeaders(400, err.length);
                        try (OutputStream os = exchange.getResponseBody()) { os.write(err); }
                        return;
                    }

                    try {
                        byte[] resultBytes;
                        String mime;
                        if ("odt".equals(format)) {
                            resultBytes = convertUdfBytesToOdt(inputBytes);
                            mime = "application/vnd.oasis.opendocument.text";
                        } else {
                            resultBytes = convertUdfBytesToPdf(inputBytes);
                            mime = "application/pdf";
                        }

                        exchange.getResponseHeaders().set("Content-Type", mime);
                        exchange.sendResponseHeaders(200, resultBytes.length);
                        try (OutputStream os = exchange.getResponseBody()) {
                            os.write(resultBytes);
                        }
                    } catch (Throwable t) {
                        String errMsg = "Conversion error: " + t.getMessage();
                        byte[] errBytes = errMsg.getBytes(StandardCharsets.UTF_8);
                        exchange.sendResponseHeaders(500, errBytes.length);
                        try (OutputStream os = exchange.getResponseBody()) { os.write(errBytes); }
                    }
                }
            });

            // GET /api/v1/status
            server.createContext("/api/v1/status", new HttpHandler() {
                @Override
                public void handle(HttpExchange exchange) throws IOException {
                    exchange.getResponseHeaders().set("Access-Control-Allow-Origin", "*");
                    exchange.getResponseHeaders().set("Content-Type", "application/json");
                    byte[] resp = "{\"status\":\"ok\",\"engine\":\"Havelsan UYAP Headless Engine\"}".getBytes(StandardCharsets.UTF_8);
                    exchange.sendResponseHeaders(200, resp.length);
                    try (OutputStream os = exchange.getResponseBody()) { os.write(resp); }
                }
            });

            server.setExecutor(null);
            server.start();
            System.out.println("✓ Havelsan UYAP Headless Çevrim Sunucusu Aktif: http://127.0.0.1:" + port);
        } catch (IOException e) {
            System.err.println("Sunucu başlatma hatası: " + e.getMessage());
        }
    }

    private static byte[] readStreamToByteArray(InputStream is) throws IOException {
        try (ByteArrayOutputStream baos = new ByteArrayOutputStream()) {
            byte[] buf = new byte[8192];
            int r;
            while ((r = is.read(buf)) != -1) {
                baos.write(buf, 0, r);
            }
            return baos.toByteArray();
        }
    }

    private static byte[] readFileToByteArray(File file) throws IOException {
        try (FileInputStream fis = new FileInputStream(file)) {
            return readStreamToByteArray(fis);
        }
    }
}
