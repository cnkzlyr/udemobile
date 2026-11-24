package app.eimza.mobile;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Minimal local ArkSigner HTTP transport for browsers on this same device. */
final class ArkLoopbackServer implements AutoCloseable {
    interface Handler { String handle(String encodedTask); }

    private final Handler handler;
    private final ExecutorService workers = Executors.newCachedThreadPool();
    private volatile boolean running;
    private ServerSocket socket32, socket64;

    ArkLoopbackServer(Handler handler) { this.handler = handler; }

    void start() {
        if (running) return;
        running = true;
        workers.execute(() -> serve(16356));
        workers.execute(() -> serve(16357));
    }

    private void serve(int port) {
        try {
            ServerSocket server = new ServerSocket(port, 32, InetAddress.getByName("127.0.0.1"));
            if (port == 16356) socket32 = server; else socket64 = server;
            while (running) {
                Socket client = server.accept();
                workers.execute(() -> handle(client));
            }
        } catch (Exception ignored) { }
    }

    private void handle(Socket client) {
        try (Socket ignoredClient = client) {
            client.setSoTimeout(15000);
            InputStream input = client.getInputStream();
            ByteArrayOutputStream headerBytes = new ByteArrayOutputStream();
            int state = 0, value;
            while ((value = input.read()) >= 0 && headerBytes.size() < 32768) {
                headerBytes.write(value);
                if ((state == 0 && value == '\r') || (state == 2 && value == '\r')) state++;
                else if ((state == 1 && value == '\n') || (state == 3 && value == '\n')) state++;
                else if (state == 4) break;
                else state = 0;
                if (state == 4) break;
            }
            String headers = headerBytes.toString("ISO-8859-1");
            String request = headers.split("\\r\\n", 2)[0];
            if (request == null) return;
            int length = 0;
            for (String line : headers.split("\\r\\n")) {
                int colon = line.indexOf(':');
                if (colon > 0 && "content-length".equalsIgnoreCase(line.substring(0, colon).trim())) {
                    try { length = Integer.parseInt(line.substring(colon + 1).trim()); } catch (NumberFormatException ignored) { }
                }
            }
            byte[] body = new byte[Math.max(0, Math.min(length, 4 * 1024 * 1024))];
            int offset = 0;
            while (offset < body.length) {
                int n = input.read(body, offset, body.length - offset);
                if (n < 0) break;
                offset += n;
            }
            String[] requestParts = request.split(" ", 3);
            String method = requestParts.length == 0 ? "" : requestParts[0];
            String target = requestParts.length > 1 ? requestParts[1] : "/";
            boolean options = "OPTIONS".equalsIgnoreCase(method);
            String form = new String(body, 0, offset, StandardCharsets.UTF_8);
            String encoded = "GET".equalsIgnoreCase(method) ? queryValue(target, "parameters") : extractParameters(form);
            if (encoded.isEmpty()) encoded = queryValue(target, "parameters");
            // Browsers and extensions probe the loopback ports with empty requests.
            // Those probes are health checks, not ArkSigner jobs; do not feed them to
            // the JSON task parser (which previously produced repeated JSONException logs).
            String response = options ? "" : (encoded.isEmpty() ? "[]" : handler.handle(encoded));
            String callback = queryValue(target, "callback");
            if (!callback.isEmpty() && callback.matches("[A-Za-z_$][A-Za-z0-9_$.]*"))
                response = callback + "(" + response + ");";
            else if (!options) response = "(" + response + ")";
            byte[] out = response.getBytes(StandardCharsets.UTF_8);
            String contentType = callback.isEmpty() ? "application/json" : "application/javascript";
            OutputStream stream = client.getOutputStream();
            stream.write(("HTTP/1.1 " + (options ? "204 No Content" : "200 OK") + "\r\n"
                    + "Content-Type: " + contentType + "; charset=utf-8\r\n"
                    + "Access-Control-Allow-Origin: *\r\nAccess-Control-Allow-Headers: Content-Type\r\n"
                    + "Access-Control-Allow-Methods: POST, GET, OPTIONS\r\nContent-Length: " + out.length
                    + "\r\nConnection: close\r\n\r\n").getBytes(StandardCharsets.US_ASCII));
            if (!options) stream.write(out);
            stream.flush();
        } catch (Exception ignored) { }
    }

    private static String extractParameters(String body) {
        if (body == null || body.trim().isEmpty()) return "";
        for (String part : body.split("&")) {
            String[] pair = part.split("=", 2);
            if (pair.length == 2 && "parameters".equalsIgnoreCase(pair[0])) {
                try { return URLDecoder.decode(pair[1], "UTF-8"); } catch (Exception ignored) { return pair[1]; }
            }
        }
        String trimmed = body.trim();
        try {
            org.json.JSONObject json = new org.json.JSONObject(trimmed);
            String parameters = json.optString("parameters", "");
            if (!parameters.isEmpty()) return parameters;
            // Some Firefox integrations POST the task JSON directly rather than
            // application/x-www-form-urlencoded. Normalize that form to the native
            // service's Base64 contract.
            if (json.has("action")) return Base64.getEncoder().encodeToString(
                    trimmed.getBytes(StandardCharsets.UTF_8));
        } catch (Exception ignored) { }
        // A raw Base64 payload is valid. Random browser probe bodies are ignored.
        if (trimmed.matches("[A-Za-z0-9+/=_-]{16,}")) return trimmed;
        return "";
    }

    private static String queryValue(String target, String key) {
        int q = target.indexOf('?');
        if (q < 0) return "";
        for (String part : target.substring(q + 1).split("&")) {
            String[] pair = part.split("=", 2);
            if (pair.length == 2 && key.equalsIgnoreCase(pair[0])) {
                try { return URLDecoder.decode(pair[1], StandardCharsets.UTF_8.name()); }
                catch (Exception ignored) { return pair[1]; }
            }
        }
        return "";
    }

    @Override public void close() {
        running = false;
        try { if (socket32 != null) socket32.close(); } catch (Exception ignored) { }
        try { if (socket64 != null) socket64.close(); } catch (Exception ignored) { }
        workers.shutdownNow();
    }
}
