package com.agy.uyapacici;

import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.util.Base64;
import android.util.Log;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * UYAP Mobil İmza İletişim İstemcisi
 * 
 * 1. Katman: Termux içindeki yerel Havelsan UYAP Headless Sunucusu (Port 5976)
 *    - Otomatik arka plan uyandırma (Termux RUN_COMMAND intent).
 *    - Resmi Havelsan MobilImzaSigner ve TÜBİTAK UEKAE BaseSignedData motoru.
 * 
 * 2. Katman: Doğrudan Resmi UYAP Mobil İmza Ağ Geçidi (SOAP 1.1)
 *    - Yerel sunucu veya Termux kapalıysa devreye girer.
 *    - http://vatandas.uyap.gov.tr/mimzaclient/services/MImzaSigner ile doğrudan konuşur.
 *    - Asla "Failed to connect to 127.0.0.1:5976" hatası vermez; her koşulda çalışır.
 */
public class UyapMobileSignClient {
    private static final String TAG = "UyapMobileSignClient";
    private static final String LOCAL_SERVER_BASE = "http://127.0.0.1:5976";
    private static final String UYAP_SOAP_ENDPOINT = "http://vatandas.uyap.gov.tr/mimzaclient/services/MImzaSigner";

    public static class InitResult {
        public boolean success;
        public String fingerPrint = "";
        public String apTransId = "";
        public String message = "";
        public int resultCode = -1;
        public boolean isLocal = false;
    }

    public static class PollResult {
        public boolean success;
        public boolean waiting;
        public byte[] signedData;
        public String signerName = "";
        public String identityNo = "";
        public String signatureDate = "";
        public String message = "";
        public int resultCode = -1;
    }

    /**
     * Yerel Havelsan sunucusunun canlılığını kontrol eder.
     */
    public static boolean isLocalServerHealthy(int timeoutMs) {
        HttpURLConnection conn = null;
        try {
            URL url = new URL(LOCAL_SERVER_BASE + "/health");
            conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("GET");
            conn.setConnectTimeout(timeoutMs);
            conn.setReadTimeout(timeoutMs);
            int code = conn.getResponseCode();
            return (code == 200);
        } catch (Exception e) {
            return false;
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    /**
     * Termux arka planında Havelsan UYAP headless sunucusunu başlatmak için intent gönderir.
     */
    public static void wakeTermuxServer(Context context) {
        if (context == null) return;
        try {
            Intent intent = new Intent();
            intent.setClassName("com.termux", "com.termux.app.RunCommandService");
            intent.putExtra("com.termux.RUN_COMMAND_PATH", "/data/data/com.termux/files/usr/bin/bash");
            intent.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", new String[]{"-c", "bash ~/eimza/udemobile_baslat.sh ensure >/dev/null 2>&1"});
            intent.putExtra("com.termux.RUN_COMMAND_WORKDIR", "/data/data/com.termux/files/home");
            intent.putExtra("com.termux.RUN_COMMAND_BACKGROUND", true);
            intent.putExtra("com.termux.RUN_COMMAND_SESSION_ACTION", "0");

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent);
            } else {
                context.startService(intent);
            }
            Log.i(TAG, "Termux RUN_COMMAND ile UdeMobileServer uyandırıldı.");
        } catch (Throwable t) {
            Log.w(TAG, "Termux uyandırma intenti iletilemedi (Termux yüklü olmayabilir): " + t.getMessage());
        }
    }

    /**
     * Mobil imza başlatma (getHash)
     * Önce yerel Havelsan servisini dener. Kapalıysa otomatik uyandırır.
     * Uyanmazsa doğrudan resmi UYAP SOAP ağ geçidini kullanarak işlemi sürdürür.
     */
    public static InitResult initSign(Context context, String phone, int operator, byte[] contentXmlBytes) {
        // Havelsan UYAP Editörü telefon numarasını 11 hane "05XXXXXXXXX" olarak gönderir (baştaki 0 SİLİNMEZ)
        String cleanPhone = phone.replaceAll("[^0-9]", "");
        if (cleanPhone.startsWith("90") && cleanPhone.length() == 12) cleanPhone = cleanPhone.substring(2);
        if (cleanPhone.length() == 10 && cleanPhone.startsWith("5")) cleanPhone = "0" + cleanPhone;

        // 1. Yerel sunucuyu kontrol et / uyandır
        if (!isLocalServerHealthy(500)) {
            wakeTermuxServer(context);
            for (int i = 0; i < 6; i++) {
                try { Thread.sleep(400); } catch (InterruptedException ignored) {}
                if (isLocalServerHealthy(500)) break;
            }
        }

        // 2. Yerel Havelsan UYAP sunucusu aktifse onu kullan
        if (isLocalServerHealthy(800)) {
            try {
                InitResult localRes = initSignLocal(cleanPhone, operator, contentXmlBytes);
                if (localRes.success) {
                    localRes.isLocal = true;
                    return localRes;
                }
            } catch (Exception e) {
                Log.w(TAG, "Yerel Havelsan sunucusu hata verdi, doğrudan UYAP SOAP'a geçiliyor: " + e.getMessage());
            }
        }

        // 3. Fallback: Doğrudan Resmi UYAP SOAP Ağ Geçidi
        Log.i(TAG, "Doğrudan Resmi UYAP Mobil İmza SOAP Servisine bağlanılıyor...");
        return initSignSoap(cleanPhone, operator, contentXmlBytes);
    }

    private static InitResult initSignLocal(String phone, int operator, byte[] contentXmlBytes) throws Exception {
        URL url = new URL(LOCAL_SERVER_BASE + "/api/v1/mimza/init");
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("POST");
        conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
        conn.setDoOutput(true);
        conn.setConnectTimeout(6000);
        conn.setReadTimeout(20000);

        JSONObject reqObj = new JSONObject();
        reqObj.put("content", Base64.encodeToString(contentXmlBytes, Base64.NO_WRAP));
        reqObj.put("msisdn", phone);
        reqObj.put("operator", operator);

        try (OutputStream os = conn.getOutputStream()) {
            os.write(reqObj.toString().getBytes(StandardCharsets.UTF_8));
            os.flush();
        }

        int code = conn.getResponseCode();
        InputStream is = (code >= 200 && code < 400) ? conn.getInputStream() : conn.getErrorStream();
        BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = reader.readLine()) != null) sb.append(line);
        reader.close();

        JSONObject res = new JSONObject(sb.toString());
        InitResult r = new InitResult();
        r.success = "SUCCESS".equalsIgnoreCase(res.optString("status"));
        r.resultCode = res.optInt("resultCode", r.success ? 0 : 1);
        r.message = res.optString("message", "");
        r.fingerPrint = res.optString("fingerPrint", "");
        r.apTransId = res.optString("apTransId", "");
        return r;
    }

    private static InitResult initSignSoap(String phone, int operator, byte[] contentXmlBytes) {
        InitResult r = new InitResult();
        r.isLocal = false;
        try {
            String base64Content = Base64.encodeToString(contentXmlBytes, Base64.NO_WRAP);
            String soapXml = "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
                    + "<soapenv:Envelope xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\" xmlns:cli=\"http://client.mimza.uyap.gov.tr\">\n"
                    + "   <soapenv:Header/>\n"
                    + "   <soapenv:Body>\n"
                    + "      <cli:getHash>\n"
                    + "         <dataToBeSigned>" + base64Content + "</dataToBeSigned>\n"
                    + "         <telNo>" + phone + "</telNo>\n"
                    + "         <gsmOperator>" + operator + "</gsmOperator>\n"
                    + "      </cli:getHash>\n"
                    + "   </soapenv:Body>\n"
                    + "</soapenv:Envelope>";

            URL url = new URL(UYAP_SOAP_ENDPOINT);
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "text/xml; charset=utf-8");
            conn.setRequestProperty("SOAPAction", "getHash");
            conn.setDoOutput(true);
            conn.setConnectTimeout(8000);
            conn.setReadTimeout(25000);

            try (OutputStream os = conn.getOutputStream()) {
                os.write(soapXml.getBytes(StandardCharsets.UTF_8));
                os.flush();
            }

            int code = conn.getResponseCode();
            InputStream is = (code >= 200 && code < 400) ? conn.getInputStream() : conn.getErrorStream();
            BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) sb.append(line);
            reader.close();

            String respXml = sb.toString();
            r.apTransId = extractXmlTag(respXml, "apTransId");
            r.fingerPrint = extractXmlTag(respXml, "fingerPrint");
            r.message = extractXmlTag(respXml, "message");
            String codeStr = extractXmlTag(respXml, "resultCode");
            try { r.resultCode = Integer.parseInt(codeStr); } catch (Exception ignored) { r.resultCode = -1; }

            if (r.resultCode == 0 && !r.apTransId.isEmpty()) {
                r.success = true;
            } else {
                r.success = false;
                if (r.message.contains("UNKNOWN_CLIENT")) {
                    r.message = phone + " numaralı hatta bu operatörde aktif bir Mobil İmza bulunamadı!";
                }
            }
        } catch (Exception e) {
            r.success = false;
            r.message = "UYAP Mobil İmza Ağ Geçidi Bağlantı Hatası: " + e.getMessage();
        }
        return r;
    }

    /**
     * Mobil imza sonucunu sorgulama (getSignature)
     */
    public static PollResult pollSign(String apTransId, String phone, boolean wasLocal) {
        if (wasLocal) {
            try {
                return pollSignLocal(apTransId, phone);
            } catch (Exception e) {
                Log.w(TAG, "Yerel poll başarısız, SOAP üzerinden deneniyor: " + e.getMessage());
            }
        }
        return pollSignSoap(apTransId);
    }

    private static PollResult pollSignLocal(String apTransId, String phone) throws Exception {
        URL pollUrl = new URL(LOCAL_SERVER_BASE + "/api/v1/mimza/poll");
        HttpURLConnection pollConn = (HttpURLConnection) pollUrl.openConnection();
        pollConn.setRequestMethod("POST");
        pollConn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
        pollConn.setDoOutput(true);
        pollConn.setConnectTimeout(5000);
        pollConn.setReadTimeout(12000);

        JSONObject pollReq = new JSONObject();
        pollReq.put("apTransId", apTransId);
        pollReq.put("msisdn", phone);

        try (OutputStream os = pollConn.getOutputStream()) {
            os.write(pollReq.toString().getBytes(StandardCharsets.UTF_8));
            os.flush();
        }

        PollResult pr = new PollResult();
        if (pollConn.getResponseCode() == 200) {
            BufferedReader r = new BufferedReader(new InputStreamReader(pollConn.getInputStream(), StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            String l;
            while ((l = r.readLine()) != null) sb.append(l);
            r.close();

            JSONObject pollRes = new JSONObject(sb.toString());
            String status = pollRes.optString("status", "");
            if ("SUCCESS".equalsIgnoreCase(status)) {
                String b64 = pollRes.optString("signedData", "");
                if (!b64.isEmpty()) {
                    pr.success = true;
                    pr.waiting = false;
                    pr.signedData = Base64.decode(b64, Base64.DEFAULT);
                    pr.signerName = pollRes.optString("signerName", "");
                    pr.identityNo = pollRes.optString("identityNo", "");
                    pr.signatureDate = pollRes.optString("signatureDate", "");
                    return pr;
                }
            } else if ("WAITING".equalsIgnoreCase(status)) {
                pr.waiting = true;
                pr.success = false;
                pr.message = pollRes.optString("message", "PIN onayı bekleniyor...");
                return pr;
            } else {
                pr.waiting = false;
                pr.success = false;
                pr.message = pollRes.optString("message", "Mobil imza tamamlanamadı.");
                return pr;
            }
        }
        pr.waiting = true;
        return pr;
    }

    private static PollResult pollSignSoap(String apTransId) {
        PollResult pr = new PollResult();
        try {
            String soapXml = "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
                    + "<soapenv:Envelope xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\" xmlns:cli=\"http://client.mimza.uyap.gov.tr\">\n"
                    + "   <soapenv:Header/>\n"
                    + "   <soapenv:Body>\n"
                    + "      <cli:getSignature>\n"
                    + "         <dataToBeDisplayed>Evrak Mobil Imza Talebi</dataToBeDisplayed>\n"
                    + "         <apTransId>" + apTransId + "</apTransId>\n"
                    + "      </cli:getSignature>\n"
                    + "   </soapenv:Body>\n"
                    + "</soapenv:Envelope>";

            URL url = new URL(UYAP_SOAP_ENDPOINT);
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "text/xml; charset=utf-8");
            conn.setRequestProperty("SOAPAction", "getSignature");
            conn.setDoOutput(true);
            conn.setConnectTimeout(8000);
            conn.setReadTimeout(110000); // Kullanıcı PIN onayı için 110 saniye bekleme süresi

            try (OutputStream os = conn.getOutputStream()) {
                os.write(soapXml.getBytes(StandardCharsets.UTF_8));
                os.flush();
            }

            int code = conn.getResponseCode();
            InputStream is = (code >= 200 && code < 400) ? conn.getInputStream() : conn.getErrorStream();
            BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) sb.append(line);
            reader.close();

            String respXml = sb.toString();
            String b64Data = extractXmlTag(respXml, "data");
            String codeStr = extractXmlTag(respXml, "resultCode");
            pr.signerName = extractXmlTag(respXml, "signerName");
            pr.identityNo = extractXmlTag(respXml, "identityNo");
            pr.signatureDate = extractXmlTag(respXml, "signatureDate");
            pr.message = extractXmlTag(respXml, "message");

            int resCode = -1;
            try { resCode = Integer.parseInt(codeStr); } catch (Exception ignored) {}
            pr.resultCode = resCode;

            if (resCode == 0 && !b64Data.isEmpty()) {
                pr.signedData = Base64.decode(b64Data, Base64.DEFAULT);
                pr.success = true;
                pr.waiting = false;
            } else {
                pr.success = false;
                pr.waiting = false;
                if (pr.message.isEmpty()) {
                    pr.message = "Mobil imza kullanıcı tarafından iptal edildi veya zaman aşımına uğradı.";
                }
            }
        } catch (java.net.SocketTimeoutException ste) {
            pr.waiting = true;
            pr.message = "Kullanıcı onayı bekleniyor...";
        } catch (Exception e) {
            pr.success = false;
            pr.waiting = false;
            pr.message = "İmza alma hatası: " + e.getMessage();
        }
        return pr;
    }

    private static String extractXmlTag(String xml, String tagName) {
        if (xml == null) return "";
        String openTag = "<" + tagName + ">";
        int start = xml.indexOf(openTag);
        if (start == -1) {
            // Namespace veya prefix olabilir, örn: <cli:data> veya <p122:data>
            int idx = xml.indexOf(":" + tagName + ">");
            if (idx != -1) {
                int tagStart = xml.lastIndexOf("<", idx);
                if (tagStart != -1) {
                    start = tagStart;
                    openTag = xml.substring(tagStart, idx + tagName.length() + 2);
                }
            }
        }
        if (start == -1) return "";

        int valStart = start + openTag.length();
        int end = xml.indexOf("</", valStart);
        if (end == -1) return "";
        return xml.substring(valStart, end).trim();
    }
}
