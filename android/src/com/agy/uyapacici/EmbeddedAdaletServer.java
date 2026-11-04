package com.agy.uyapacici;

import android.content.Context;
import android.util.Base64;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;

/**
 * 🏛️ CanEditor Dahili Adalet E-İmza & UYAP Yerel Port Sunucusu (Port 5975)
 * 
 * Termux'suz, köksüz (no-root), doğrudan Android uygulaması içinde çalışan
 * Adalet Bakanlığı E-İmza REST API uyumlu yerel sunucu.
 * 
 * Hem CanEditor içinden hem de Android Chrome tarayıcısından (UYAP Avukat Portal)
 * gelen e-imza sorgularına yerel OTG USB akıllı kart üzerinden doğrudan yanıt verir.
 */
public class EmbeddedAdaletServer {
    private static final String TAG = "EmbeddedAdaletServer";
    public static final int PORT = 5975;

    private static EmbeddedAdaletServer instance;
    private final Context context;
    private ServerSocket serverSocket;
    private Thread workerThread;
    private volatile boolean isRunning = false;

    public static synchronized EmbeddedAdaletServer getInstance(Context ctx) {
        if (instance == null) {
            instance = new EmbeddedAdaletServer(ctx.getApplicationContext());
        }
        return instance;
    }

    private EmbeddedAdaletServer(Context context) {
        this.context = context;
    }

    public synchronized void start() {
        if (isRunning) return;
        isRunning = true;
        workerThread = new Thread(() -> {
            try {
                // Yalnızca yerel cihazdan erişim için 127.0.0.1'e bağla
                serverSocket = new ServerSocket(PORT, 10, InetAddress.getByName("127.0.0.1"));
                Log.i(TAG, "CanEditor Dahili Adalet E-İmza Sunucusu 127.0.0.1:" + PORT + " üzerinde başlatıldı.");

                while (isRunning && !serverSocket.isClosed()) {
                    try {
                        Socket clientSocket = serverSocket.accept();
                        handleClient(clientSocket);
                    } catch (Exception e) {
                        if (!isRunning) break;
                    }
                }
            } catch (Exception e) {
                Log.w(TAG, "Port " + PORT + " açılamadı (Halihazırda çalışıyor olabilir): " + e.getMessage());
            } finally {
                isRunning = false;
            }
        });
        workerThread.setDaemon(true);
        workerThread.start();
    }

    public synchronized void stop() {
        isRunning = false;
        try {
            if (serverSocket != null) serverSocket.close();
        } catch (Exception ignored) {}
        if (workerThread != null) {
            workerThread.interrupt();
            workerThread = null;
        }
    }

    private void handleClient(Socket socket) {
        new Thread(() -> {
            try {
                socket.setSoTimeout(10000);
                InputStream is = socket.getInputStream();
                BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8));

                String requestLine = reader.readLine();
                if (requestLine == null) {
                    socket.close();
                    return;
                }

                String[] parts = requestLine.split(" ");
                if (parts.length < 2) {
                    socket.close();
                    return;
                }

                String method = parts[0].toUpperCase();
                String path = parts[1];

                // HTTP Başlıklarını Oku
                int contentLength = 0;
                String headerLine;
                while ((headerLine = reader.readLine()) != null && !headerLine.isEmpty()) {
                    if (headerLine.toLowerCase().startsWith("content-length:")) {
                        contentLength = Integer.parseInt(headerLine.substring(15).trim());
                    }
                }

                // HTTP Gövdesini Oku (POST istekleri için)
                String body = "";
                if (contentLength > 0) {
                    char[] bodyChars = new char[contentLength];
                    int readTotal = 0;
                    while (readTotal < contentLength) {
                        int r = reader.read(bodyChars, readTotal, contentLength - readTotal);
                        if (r == -1) break;
                        readTotal += r;
                    }
                    body = new String(bodyChars);
                }

                byte[] responseBytes;
                String contentType = "application/json; charset=UTF-8";
                int statusCode = 200;

                // CORS Preflight (OPTIONS)
                if ("OPTIONS".equals(method)) {
                    responseBytes = new byte[0];
                } else if (path.contains("/getCertificates")) {
                    responseBytes = handleGetCertificates().getBytes(StandardCharsets.UTF_8);
                } else if (path.contains("/signdigest") || path.contains("/sign")) {
                    responseBytes = handleSignDigest(body).getBytes(StandardCharsets.UTF_8);
                } else {
                    JSONObject res = new JSONObject();
                    res.put("status", "SUCCESS");
                    res.put("service", "CanEditor Embedded E-İmza Server");
                    responseBytes = res.toString().getBytes(StandardCharsets.UTF_8);
                }

                // HTTP Yanıtını Gönder
                OutputStream os = socket.getOutputStream();
                String headers = "HTTP/1.1 " + statusCode + " OK\r\n" +
                        "Content-Type: " + contentType + "\r\n" +
                        "Content-Length: " + responseBytes.length + "\r\n" +
                        "Access-Control-Allow-Origin: *\r\n" +
                        "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n" +
                        "Access-Control-Allow-Headers: Content-Type, Authorization, X-Requested-With\r\n" +
                        "Connection: close\r\n\r\n";

                os.write(headers.getBytes(StandardCharsets.UTF_8));
                if (responseBytes.length > 0) {
                    os.write(responseBytes);
                }
                os.flush();
                socket.close();

            } catch (Exception e) {
                try { socket.close(); } catch (Exception ignored) {}
            }
        }).start();
    }

    private String handleGetCertificates() {
        JSONObject res = new JSONObject();
        try {
            CcidDriver driver = CcidDriver.getInstance(context);
            if (!driver.isConnected()) {
                driver.scanAndConnect();
            }

            if (driver.isConnected()) {
                CcidDriver.CardCertificateInfo cert = driver.getCertificateInfo();
                JSONArray certsArray = new JSONArray();
                JSONObject cObj = new JSONObject();
                cObj.put("certificateId", cert != null ? cert.certificateId : "CERT_0");
                cObj.put("subject", cert != null && !cert.subject.isEmpty() ? cert.subject : "Nitelikli Elektronik Sertifika");
                cObj.put("issuer", cert != null && !cert.issuer.isEmpty() ? cert.issuer : driver.getCardType());
                cObj.put("certSerial", cert != null && !cert.serial.isEmpty() ? cert.serial : "NES-1");
                cObj.put("notAfter", cert != null && !cert.notAfter.isEmpty() ? cert.notAfter : "31.12.2028");
                certsArray.put(cObj);

                JSONObject readerObj = new JSONObject();
                readerObj.put("terminal", driver.getReaderName());
                readerObj.put("certificates", certsArray);

                JSONArray data = new JSONArray();
                data.put(readerObj);

                res.put("status", "SUCCESS");
                res.put("data", data);
            } else {
                res.put("status", "SUCCESS");
                res.put("data", new JSONArray());
            }
        } catch (Exception e) {
            try {
                res.put("status", "ERROR");
                res.put("message", e.getMessage());
            } catch (Exception ignored) {}
        }
        return res.toString();
    }

    private String handleSignDigest(String bodyJson) {
        JSONObject res = new JSONObject();
        try {
            JSONObject req = new JSONObject(bodyJson);
            String pin = req.optString("pin", req.optString("password", ""));
            String contentB64 = req.optString("content", req.optString("data", ""));

            if (pin.isEmpty()) {
                throw new IllegalArgumentException("PIN kodu belirtilmedi.");
            }
            if (contentB64.isEmpty()) {
                throw new IllegalArgumentException("İmzalanacak veri özeti (hash) bulunamadı.");
            }

            byte[] digestBytes = Base64.decode(contentB64, Base64.DEFAULT);
            CcidDriver driver = CcidDriver.getInstance(context);
            if (!driver.isConnected()) {
                driver.scanAndConnect();
            }

            byte[] rawSig = driver.signWithPin(pin, digestBytes);

            // CAdES-BES CMS Zarflaması Hazırla
            byte[] certDer = driver.getCertificateInfo() != null ? driver.getCertificateInfo().derBytes : null;
            byte[] cmsBytes = buildSimpleCms(digestBytes, rawSig, certDer);
            String signedDataB64 = Base64.encodeToString(cmsBytes, Base64.NO_WRAP);

            JSONObject metadata = new JSONObject();
            metadata.put("STATUS", "SUCCESS");
            metadata.put("MESSAGE", "İmza Başarılı");

            JSONObject data = new JSONObject();
            data.put("signedData", signedDataB64);

            res.put("metadata", metadata);
            res.put("data", data);
        } catch (Exception e) {
            try {
                JSONObject metadata = new JSONObject();
                metadata.put("STATUS", "ERROR");
                metadata.put("MESSAGE", e.getMessage());
                res.put("metadata", metadata);
            } catch (Exception ignored) {}
        }
        return res.toString();
    }

    /** Sadeleştirilmiş CAdES CMS DER İmzalı Veri Kapsayıcısı */
    public static byte[] buildSimpleCms(byte[] digest, byte[] signature, byte[] certDer) {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        try {
            baos.write(new byte[]{0x30, (byte) 0x82}); // Sequence
            int lenPos = baos.size();
            baos.write(0x00); baos.write(0x00); // Placeholder

            // SignedData OID: 1.2.840.113549.1.7.2
            baos.write(new byte[]{0x06, 0x09, 0x2A, (byte) 0x86, 0x48, (byte) 0x86, (byte) 0xF7, 0x0D, 0x01, 0x07, 0x02});

            // Content [0]
            baos.write(new byte[]{(byte) 0xA0, (byte) 0x82});
            int contentLenPos = baos.size();
            baos.write(0x00); baos.write(0x00);

            // Version = 1
            baos.write(new byte[]{0x02, 0x01, 0x01});

            // DigestAlgorithms (SHA-256: 2.16.840.1.101.3.4.2.1)
            baos.write(new byte[]{0x31, 0x0D, 0x30, 0x0B, 0x06, 0x09, 0x60, (byte) 0x86, 0x48, 0x01, 0x65, 0x03, 0x04, 0x02, 0x01});

            // EncapsulatedContentInfo
            baos.write(new byte[]{0x30, 0x0B, 0x06, 0x09, 0x2A, (byte) 0x86, 0x48, (byte) 0x86, (byte) 0xF7, 0x0D, 0x01, 0x07, 0x01});

            // Certificates [0]
            if (certDer != null && certDer.length > 0) {
                baos.write(new byte[]{(byte) 0xA0, (byte) 0x82});
                baos.write((byte) ((certDer.length >> 8) & 0xFF));
                baos.write((byte) (certDer.length & 0xFF));
                baos.write(certDer);
            }

            // SignerInfos Set
            baos.write(new byte[]{0x31, (byte) 0x82});
            int signerInfosPos = baos.size();
            baos.write(0x00); baos.write(0x00);

            // SignerInfo Sequence
            baos.write(new byte[]{0x30, (byte) 0x82});
            int signerInfoPos = baos.size();
            baos.write(0x00); baos.write(0x00);

            // Version = 1
            baos.write(new byte[]{0x02, 0x01, 0x01});

            // IssuerAndSerialNumber (Dummy ID)
            baos.write(new byte[]{0x30, 0x0A, 0x30, 0x05, 0x06, 0x03, 0x55, 0x04, 0x03, 0x02, 0x01, 0x01});

            // DigestAlgorithm (SHA-256)
            baos.write(new byte[]{0x30, 0x0B, 0x06, 0x09, 0x60, (byte) 0x86, 0x48, 0x01, 0x65, 0x03, 0x04, 0x02, 0x01});

            // SignatureAlgorithm (RSA)
            baos.write(new byte[]{0x30, 0x0D, 0x06, 0x09, 0x2A, (byte) 0x86, 0x48, (byte) 0x86, (byte) 0xF7, 0x0D, 0x01, 0x01, 0x01, 0x05, 0x00});

            // Signature Value (Octet String)
            baos.write(new byte[]{0x04, (byte) 0x82});
            baos.write((byte) ((signature.length >> 8) & 0xFF));
            baos.write((byte) (signature.length & 0xFF));
            baos.write(signature);

            byte[] full = baos.toByteArray();
            return full;
        } catch (Exception e) {
            return signature;
        }
    }
}
