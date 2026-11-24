package app.eimza.mobile;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;

import org.json.JSONObject;
import org.json.JSONArray;

/** Minimal client for the protocol used by the official e-Devlet e-signature JNLP. */
final class EdevletClient {
    private static final String FETCH_URL =
            "https://www.turkiye.gov.tr/elektronik-imza-yeni?actionName=kayitKontrol&lan=tr";
    private static final String LOGIN_SUBMIT_URL =
            "https://giris.turkiye.gov.tr/Giris/Elektronik-Imza?actionName=imzala";
    private static final int MAX_RESPONSE = 2 * 1024 * 1024;
    EdevletClient() { }

    static final class SigningRequest {
        final String contentBase64;
        final String mimeType;
        final String operationType;

        SigningRequest(String contentBase64, String mimeType, String operationType) {
            this.contentBase64 = contentBase64;
            this.mimeType = mimeType == null ? "" : mimeType;
            this.operationType = operationType == null ? "" : operationType;
        }
    }

    SigningRequest fetchSigningRequest(String identityNumber, String transactionId) throws Exception {
        validateIdentity(identityNumber);
        validateTransactionId(transactionId);
        Map<String, String> fields = new LinkedHashMap<>();
        fields.put("kimlikNo", identityNumber);
        fields.put("transId", transactionId);
        JSONObject response = post(FETCH_URL, fields);
        requireSuccess(response, "İmzalanacak veri alınamadı");
        // `sozlesme` is only the human-readable agreement shown in the official
        // desktop UI. The bytes that must be signed are carried in `fileInput`.
        // Signing `sozlesme` produces a structurally valid CMS which e-Devlet
        // rejects as corrupted / NOT_TRUSTED.
        String content = response.optString("fileInput", "")
                .replace("\n", "").replace("\r", "");
        if (content.isEmpty())
            throw new java.io.IOException("e-Devlet fileInput imza verisini döndürmedi");
        return new SigningRequest(content, response.optString("mimeType", ""),
                response.optString("islemTip", ""));
    }

    String submitLogin(byte[] signedCms, String transactionId) throws Exception {
        if (signedCms == null || signedCms.length == 0)
            throw new IllegalArgumentException("e-Devlet imzası boş");
        validateTransactionId(transactionId);
        Map<String, String> fields = new LinkedHashMap<>();
        fields.put("signedData", android.util.Base64.encodeToString(signedCms, android.util.Base64.NO_WRAP));
        fields.put("transId", transactionId);
        JSONObject response = post(LOGIN_SUBMIT_URL, fields);
        requireSuccess(response, "e-Devlet imzayı kabul etmedi");
        JSONArray result = response.optJSONArray("sonuc");
        if (result == null || result.length() == 0 || result.optString(0, "").isEmpty())
            throw new java.io.IOException("e-Devlet başarı yanıtında oturum kodu yok");
        return result.getString(0);
    }

    static void validateTransactionId(String value) {
        if (value == null || !value.matches("[A-Za-z0-9]{6,10}"))
            throw new IllegalArgumentException("e-Devlet işlem kodu 6–10 harf/rakam olmalı");
    }

    private static void validateIdentity(String value) {
        if (value == null || !value.matches("[0-9]{11}"))
            throw new IllegalArgumentException("Sertifikada geçerli TCKN bulunamadı");
    }

    private static void requireSuccess(JSONObject response, String fallback) throws Exception {
        Object rawCode = response.opt("errorCode");
        int code = -1;
        if (rawCode instanceof Number) code = ((Number) rawCode).intValue();
        else if (rawCode != null) {
            try { code = Integer.parseInt(String.valueOf(rawCode)); }
            catch (NumberFormatException ignored) { }
        }
        if (code != 0) {
            String message = response.optString("errorMessage", "");
            if (message.isEmpty()) message = response.optString("message", "");
            if (message.isEmpty() && response.has("errorExplanation")
                    && !response.isNull("errorExplanation"))
                message = String.valueOf(response.opt("errorExplanation"));
            if (message.isEmpty()) message = fallback + " (kod " + code + ")";
            throw new java.io.IOException(message);
        }
    }

    private JSONObject post(String rawUrl, Map<String, String> fields) throws Exception {
        URL url = new URL(rawUrl);
        String host = url.getHost();
        if (!("https".equalsIgnoreCase(url.getProtocol())
                && ("www.turkiye.gov.tr".equalsIgnoreCase(host)
                || "giris.turkiye.gov.tr".equalsIgnoreCase(host))))
            throw new SecurityException("İzin verilmeyen e-Devlet uç noktası");

        StringBuilder encoded = new StringBuilder();
        for (Map.Entry<String, String> field : fields.entrySet()) {
            if (encoded.length() > 0) encoded.append('&');
            encoded.append(URLEncoder.encode(field.getKey(), "UTF-8")).append('=')
                    .append(URLEncoder.encode(field.getValue(), "UTF-8"));
        }
        byte[] request = encoded.toString().getBytes(StandardCharsets.UTF_8);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        try {
            connection.setRequestMethod("POST");
            connection.setConnectTimeout(15000);
            connection.setReadTimeout(30000);
            connection.setDoOutput(true);
            connection.setInstanceFollowRedirects(false);
            connection.setFixedLengthStreamingMode(request.length);
            connection.getOutputStream().write(request);
            int status = connection.getResponseCode();
            InputStream input = status >= 200 && status < 300
                    ? connection.getInputStream() : connection.getErrorStream();
            byte[] body = readLimited(input);
            if (status < 200 || status >= 300)
                throw new java.io.IOException("e-Devlet HTTP " + status);
            return new JSONObject(new String(body, StandardCharsets.UTF_8));
        } finally {
            connection.disconnect();
        }
    }

    private static byte[] readLimited(InputStream input) throws Exception {
        if (input == null) return new byte[0];
        try (InputStream in = input; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int count, total = 0;
            while ((count = in.read(buffer)) >= 0) {
                total += count;
                if (total > MAX_RESPONSE) throw new java.io.IOException("e-Devlet yanıtı çok büyük");
                out.write(buffer, 0, count);
            }
            return out.toByteArray();
        }
    }
}
