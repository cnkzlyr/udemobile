package com.ckz.udemobile;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;

import java.io.*;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.Executors;

import tr.gov.uyap.mimza.client.main.MobilImzaSigner;
import tr.gov.uyap.system.mimza.dvo.HashResult;
import tr.gov.uyap.system.mimza.dvo.SignatureResult;

import tr.gov.tubitak.uekae.esya.api.cmssignature.signature.BaseSignedData;
import tr.gov.tubitak.uekae.esya.api.asn.cms.*;
import tr.gov.tubitak.uekae.esya.api.asn.x509.*;

public class UdeMobileServer {
    private static final int PORT = 5976;
    private static MobilImzaSigner mimzaSigner;

    public static void main(String[] args) throws Exception {
        mimzaSigner = new MobilImzaSigner();

        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", PORT), 0);
        server.setExecutor(Executors.newCachedThreadPool());

        // CORS ve JSON başlıkları ekleyen handler
        server.createContext("/health", new HealthHandler());
        server.createContext("/api/v1/mimza/status", new MimzaStatusHandler());
        server.createContext("/api/v1/mimza/init", new MimzaInitHandler());
        server.createContext("/api/v1/mimza/poll", new MimzaPollHandler());
        server.createContext("/api/v1/signature/combine", new SignatureCombineHandler());

        server.start();
        System.out.println("✓ UdeMobileServer 127.0.0.1:" + PORT + " üzerinde hazır!");
        while (true) {
            try {
                Thread.sleep(60000);
            } catch (InterruptedException ignored) {}
        }
    }

    private static void sendJsonResponse(HttpExchange exchange, int statusCode, String jsonResponse) throws IOException {
        byte[] bytes = jsonResponse.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json; charset=UTF-8");
        exchange.getResponseHeaders().set("Access-Control-Allow-Origin", "*");
        exchange.getResponseHeaders().set("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
        exchange.getResponseHeaders().set("Access-Control-Allow-Headers", "Content-Type");

        if ("OPTIONS".equalsIgnoreCase(exchange.getRequestMethod())) {
            exchange.sendResponseHeaders(204, -1);
            return;
        }

        exchange.sendResponseHeaders(statusCode, bytes.length);
        try (OutputStream os = exchange.getResponseBody()) {
            os.write(bytes);
        }
    }

    private static String readRequestBody(HttpExchange exchange) throws IOException {
        try (InputStream is = exchange.getRequestBody();
             ByteArrayOutputStream baos = new ByteArrayOutputStream()) {
            byte[] buf = new byte[4096];
            int r;
            while ((r = is.read(buf)) != -1) baos.write(buf, 0, r);
            return new String(baos.toByteArray(), StandardCharsets.UTF_8);
        }
    }

    // JSON string değer okuyucu (kaçış karakterlerini \/ \" \\ \n \\uXXXX doğru çözer)
    private static String getJsonString(String json, String key) {
        String search = "\"" + key + "\"";
        int idx = json.indexOf(search);
        if (idx == -1) return "";
        int colon = json.indexOf(":", idx + search.length());
        if (colon == -1) return "";
        int valStart = json.indexOf("\"", colon);
        if (valStart == -1) return "";
        StringBuilder sb = new StringBuilder();
        for (int i = valStart + 1; i < json.length(); i++) {
            char c = json.charAt(i);
            if (c == '"') break;
            if (c == '\\' && i + 1 < json.length()) {
                char n = json.charAt(++i);
                switch (n) {
                    case 'n': sb.append('\n'); break;
                    case 'r': sb.append('\r'); break;
                    case 't': sb.append('\t'); break;
                    case 'b': sb.append('\b'); break;
                    case 'f': sb.append('\f'); break;
                    case 'u':
                        if (i + 4 < json.length()) {
                            try {
                                sb.append((char) Integer.parseInt(json.substring(i + 1, i + 5), 16));
                                i += 4;
                            } catch (Exception e) { sb.append(n); }
                        }
                        break;
                    default: sb.append(n); // \" \\ \/
                }
            } else {
                sb.append(c);
            }
        }
        return sb.toString();
    }

    // Toleranslı Base64 çözücü (satır sonu/boşluk/kaçış artıklarını yok sayar)
    private static byte[] decodeB64(String s) {
        return Base64.getMimeDecoder().decode(s == null ? "" : s.trim());
    }

    // Mobil imza işlemleri: apTransId -> sonuç (getSignature bloklayıcı olduğu için arka planda çalışır)
    static class PendingSign {
        volatile boolean done = false;
        volatile String json = null;
        final long created = System.currentTimeMillis();
    }
    private static final Map<String, PendingSign> PENDING = new java.util.concurrent.ConcurrentHashMap<>();

    private static void startSignatureWorker(final String apTransId) {
        final PendingSign ps = new PendingSign();
        PENDING.put(apTransId, ps);
        // eski kayıtları temizle
        long now = System.currentTimeMillis();
        PENDING.entrySet().removeIf(e -> now - e.getValue().created > 15 * 60 * 1000L);
        new Thread(() -> {
            String out;
            try {
                System.out.println("[MImza] getSignature bekleniyor -> " + apTransId);
                SignatureResult res = mimzaSigner.getSignature("Evrak Mobil Imza Talebi", apTransId);
                byte[] data = res.getData();
                int code = res.getResultCode();
                String msg = res.getMessage() != null ? res.getMessage() : "";
                System.out.println("[MImza] getSignature sonuç -> Code: " + code + " len: " + (data == null ? 0 : data.length) + " Msg: " + msg);
                if (data != null && data.length > 0) {
                    // UYAP editörü gibi: içerik gömülü (attached) gelen CMS'den içeriği ayır (detached)
                    try {
                        BaseSignedData bsd = new BaseSignedData(data);
                        bsd.detachContent();
                        data = bsd.getEncoded();
                    } catch (Exception de) {
                        System.out.println("[MImza] detachContent uyarı: " + de);
                    }
                    String signerName = res.getSignerName() != null ? res.getSignerName() : "";
                    String idNo = res.getIdentityNo() != null ? res.getIdentityNo() : "";
                    String sigDate = res.getSignatureDate() != null ? res.getSignatureDate() : "";
                    out = "{\"status\":\"SUCCESS\",\"resultCode\":0,\"signedData\":" + quote(Base64.getEncoder().encodeToString(data))
                        + ",\"signerName\":" + quote(signerName) + ",\"identityNo\":" + quote(idNo)
                        + ",\"signatureDate\":" + quote(sigDate) + ",\"message\":" + quote(msg) + "}";
                } else {
                    out = "{\"status\":\"ERROR\",\"resultCode\":" + code + ",\"message\":"
                        + quote(msg.isEmpty() ? "Mobil imza onaylanmadı veya zaman aşımına uğradı." : msg) + "}";
                }
            } catch (Exception e) {
                e.printStackTrace();
                out = "{\"status\":\"ERROR\",\"message\":" + quote("Mobil imza servis hatası: " + e.getMessage()) + "}";
            }
            ps.json = out;
            ps.done = true;
        }, "mimza-" + apTransId).start();
    }

    private static int getJsonInt(String json, String key, int defVal) {
        String search = "\"" + key + "\"";
        int idx = json.indexOf(search);
        if (idx == -1) return defVal;
        int colon = json.indexOf(":", idx + search.length());
        if (colon == -1) return defVal;
        int i = colon + 1;
        while (i < json.length() && (Character.isWhitespace(json.charAt(i)) || json.charAt(i) == '\"')) i++;
        int start = i;
        while (i < json.length() && (Character.isDigit(json.charAt(i)) || json.charAt(i) == '-')) i++;
        try {
            return Integer.parseInt(json.substring(start, i));
        } catch (Exception e) {
            return defVal;
        }
    }

    private static String quote(String s) {
        if (s == null) return "\"\"";
        return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r") + "\"";
    }

    // --- HANDLERS ---

    static class HealthHandler implements HttpHandler {
        public void handle(HttpExchange exchange) throws IOException {
            sendJsonResponse(exchange, 200, "{\"status\":\"OK\",\"service\":\"UdeMobileServer\"}");
        }
    }

    static class MimzaStatusHandler implements HttpHandler {
        public void handle(HttpExchange exchange) throws IOException {
            try {
                Calendar cal = mimzaSigner.getServerTime();
                String timeStr = (cal != null) ? cal.getTime().toString() : "null";
                sendJsonResponse(exchange, 200, "{\"status\":\"SUCCESS\",\"serverTime\":" + quote(timeStr) + "}");
            } catch (Exception e) {
                sendJsonResponse(exchange, 500, "{\"status\":\"ERROR\",\"message\":" + quote(e.getMessage()) + "}");
            }
        }
    }

    static class MimzaInitHandler implements HttpHandler {
        public void handle(HttpExchange exchange) throws IOException {
            if ("OPTIONS".equalsIgnoreCase(exchange.getRequestMethod())) {
                sendJsonResponse(exchange, 204, "");
                return;
            }
            try {
                String body = readRequestBody(exchange);
                String base64Content = getJsonString(body, "content");
                String msisdn = getJsonString(body, "msisdn").replaceAll("[^0-9]", "");
                int operator = getJsonInt(body, "operator", 1); // 1: Turkcell, 2: Vodafone, 3: Turk Telekom

                if (msisdn.startsWith("90") && msisdn.length() == 12) {
                    msisdn = msisdn.substring(2);
                }
                if (msisdn.startsWith("0") && msisdn.length() == 11) {
                    msisdn = msisdn.substring(1);
                }

                if (base64Content.isEmpty()) {
                    sendJsonResponse(exchange, 400, "{\"status\":\"ERROR\",\"message\":\"İçerik (content) boş olamaz.\"}");
                    return;
                }
                if (msisdn.length() != 10) {
                    sendJsonResponse(exchange, 400, "{\"status\":\"ERROR\",\"message\":\"Geçerli bir 10 haneli GSM numarası giriniz (örn: 5xxxxxxxxx).\"}");
                    return;
                }

                byte[] contentBytes = decodeB64(base64Content);
                System.out.println("[MImza] getHash başlatılıyor -> GSM: " + msisdn + " Op: " + operator);

                HashResult res = mimzaSigner.getHash(contentBytes, msisdn, operator);
                int code = res.getResultCode();
                String msg = res.getMessage() != null ? res.getMessage() : "";
                String fingerPrint = res.getFingerPrint() != null ? res.getFingerPrint() : "";
                String apTransId = res.getApTransId() != null ? res.getApTransId() : "";

                System.out.println("[MImza] getHash sonuç -> Code: " + code + " FP: " + fingerPrint + " TransId: " + apTransId + " Msg: " + msg);

                if (code == 0 && !apTransId.isEmpty()) {
                    startSignatureWorker(apTransId);
                    sendJsonResponse(exchange, 200, "{\"status\":\"SUCCESS\",\"resultCode\":0,\"fingerPrint\":" 
                        + quote(fingerPrint) + ",\"apTransId\":" + quote(apTransId) + ",\"message\":" + quote(msg) + "}");
                } else {
                    String userMsg = msg;
                    if (msg.contains("UNKNOWN_CLIENT")) {
                        userMsg = msisdn + " numaralı hatta bu operatörde aktif bir Mobil İmza bulunamadı!";
                    }
                    sendJsonResponse(exchange, 200, "{\"status\":\"ERROR\",\"resultCode\":" + code + ",\"message\":" + quote(userMsg) + "}");
                }
            } catch (Exception e) {
                e.printStackTrace();
                sendJsonResponse(exchange, 500, "{\"status\":\"ERROR\",\"message\":" + quote(e.getMessage()) + "}");
            }
        }
    }

    static class MimzaPollHandler implements HttpHandler {
        public void handle(HttpExchange exchange) throws IOException {
            if ("OPTIONS".equalsIgnoreCase(exchange.getRequestMethod())) {
                sendJsonResponse(exchange, 204, "");
                return;
            }
            try {
                String body = readRequestBody(exchange);
                String apTransId = getJsonString(body, "apTransId");
                if (apTransId.isEmpty()) {
                    sendJsonResponse(exchange, 400, "{\"status\":\"ERROR\",\"message\":\"apTransId eksik.\"}");
                    return;
                }

                PendingSign ps = PENDING.get(apTransId);
                if (ps == null) {
                    sendJsonResponse(exchange, 200, "{\"status\":\"ERROR\",\"message\":\"Bu mobil imza işlemi bulunamadı (servis yeniden başlatılmış olabilir). Lütfen tekrar deneyin.\"}");
                } else if (!ps.done) {
                    sendJsonResponse(exchange, 200, "{\"status\":\"WAITING\",\"message\":\"Kullanıcı onayı bekleniyor...\"}");
                } else {
                    PENDING.remove(apTransId);
                    sendJsonResponse(exchange, 200, ps.json);
                }
            } catch (Exception e) {
                e.printStackTrace();
                sendJsonResponse(exchange, 500, "{\"status\":\"ERROR\",\"message\":" + quote(e.getMessage()) + "}");
            }
        }
    }

    static class SignatureCombineHandler implements HttpHandler {
        public void handle(HttpExchange exchange) throws IOException {
            if ("OPTIONS".equalsIgnoreCase(exchange.getRequestMethod())) {
                sendJsonResponse(exchange, 204, "");
                return;
            }
            try {
                String body = readRequestBody(exchange);
                String existingB64 = getJsonString(body, "existingSgn");
                String newB64 = getJsonString(body, "newSgn");

                if (newB64.isEmpty()) {
                    sendJsonResponse(exchange, 400, "{\"status\":\"ERROR\",\"message\":\"newSgn boş olamaz.\"}");
                    return;
                }
                if (existingB64.isEmpty()) {
                    sendJsonResponse(exchange, 200, "{\"status\":\"SUCCESS\",\"combinedSgn\":" + quote(newB64) + "}");
                    return;
                }

                byte[] existingSgn = decodeB64(existingB64);
                byte[] newSgn = decodeB64(newB64);

                byte[] combined = combineSignatures(existingSgn, newSgn);
                String combinedB64 = Base64.getEncoder().encodeToString(combined);

                sendJsonResponse(exchange, 200, "{\"status\":\"SUCCESS\",\"combinedSgn\":" + quote(combinedB64) + "}");
            } catch (Exception e) {
                e.printStackTrace();
                sendJsonResponse(exchange, 500, "{\"status\":\"ERROR\",\"message\":" + quote("İmza birleştirme hatası: " + e.getMessage()) + "}");
            }
        }
    }

    public static byte[] combineSignatures(byte[] existingSgn, byte[] newSgn) throws Exception {
        if (existingSgn == null || existingSgn.length == 0) return newSgn;
        if (newSgn == null || newSgn.length == 0) return existingSgn;

        BaseSignedData base1 = new BaseSignedData(existingSgn);
        BaseSignedData base2 = new BaseSignedData(newSgn);

        ESignedData sd1 = base1.getSignedData();
        ESignedData sd2 = base2.getSignedData();

        // 1. Yeni sertifikaları ekle
        ECertificateSet certSet2 = sd2.getCertificateSet();
        if (certSet2 != null) {
            int count = certSet2.getCertificateChoicesCount();
            for (int i = 0; i < count; i++) {
                ECertificateChoices choice = certSet2.getCertificateChoices(i);
                try {
                    sd1.addCertificateChoices(choice);
                } catch (Exception ignored) {}
            }
        }

        // 2. Digest algoritmalarını ekle
        List<EAlgorithmIdentifier> algs2 = sd2.getDigestAlgorithmList();
        List<EAlgorithmIdentifier> algs1 = sd1.getDigestAlgorithmList();
        if (algs2 != null) {
            for (EAlgorithmIdentifier alg : algs2) {
                boolean found = false;
                if (algs1 != null) {
                    for (EAlgorithmIdentifier a1 : algs1) {
                        if (a1.getAlgorithm().equals(alg.getAlgorithm())) {
                            found = true;
                            break;
                        }
                    }
                }
                if (!found) {
                    sd1.addDigestAlgorithmIdentifier(alg);
                }
            }
        }

        // 3. SignerInfo'ları ekle (mükerrerliği önle)
        List<ESignerInfo> signers2 = sd2.getSignerInfos();
        List<ESignerInfo> signers1 = sd1.getSignerInfos();
        if (signers2 != null) {
            for (ESignerInfo si : signers2) {
                boolean exists = false;
                if (signers1 != null) {
                    for (ESignerInfo s1 : signers1) {
                        if (Arrays.equals(s1.getEncoded(), si.getEncoded())) {
                            exists = true;
                            break;
                        }
                    }
                }
                if (!exists) {
                    sd1.addSignerInfo(si);
                }
            }
        }

        return base1.getEncoded();
    }
}
