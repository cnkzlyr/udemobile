package app.eimza.mobile;

import java.net.URI;
import java.util.Locale;

/** Origin policy shared by the WebView portal bridges. */
final class PortalOrigins {
    private PortalOrigins() { }

    static boolean isAdalet(String url) {
        URI value = https(url);
        return value != null && isAdaletHost(host(value));
    }

    static boolean isEdevlet(String url) {
        URI value = https(url);
        return value != null && isEdevletHost(host(value));
    }

    /** OGN's signed login assertion must carry the original content in the CMS. */
    static boolean requiresAttachedCades(String url) {
        URI value = https(url);
        if (value == null) return false;
        String valueHost = host(value);
        return "ogn.saglik.gov.tr".equals(valueHost)
                || "ognportal.saglik.gov.tr".equals(valueHost);
    }

    static boolean mayBridge(String requestOrigin, String activePageUrl) {
        URI request = https(requestOrigin);
        URI active = https(activePageUrl);
        if (request == null || active == null) return false;
        String requestHost = host(request);
        String activeHost = host(active);

        // The health login and signer UI legitimately move between e-Nabiz and
        // Saglik subdomains. Keep that cross-origin allowance inside this pair.
        if (isHealthHost(requestHost) && isHealthHost(activeHost)) return true;
        if ("test.arksigner.com".equals(requestHost)) return requestHost.equals(activeHost);

        if (isEdevletHost(requestHost) && isEdevletHost(activeHost)) return true;

        // Adalet already works with same-host routing; do not broaden it.
        return isAdaletHost(requestHost) && requestHost.equals(activeHost);
    }

    private static URI https(String raw) {
        try {
            URI value = URI.create(raw == null ? "" : raw);
            return "https".equalsIgnoreCase(value.getScheme()) && value.getHost() != null ? value : null;
        } catch (RuntimeException ignored) {
            return null;
        }
    }

    private static String host(URI value) {
        return value.getHost().toLowerCase(Locale.ROOT);
    }

    private static boolean isHealthHost(String host) {
        return host.equals("enabiz.gov.tr") || host.endsWith(".enabiz.gov.tr")
                || host.equals("saglik.gov.tr") || host.endsWith(".saglik.gov.tr");
    }

    private static boolean isAdaletHost(String host) {
        return host.equals("uyap.gov.tr") || host.endsWith(".uyap.gov.tr")
                || host.equals("adalet.gov.tr") || host.endsWith(".adalet.gov.tr")
                || host.equals("yargitay.gov.tr") || host.endsWith(".yargitay.gov.tr")
                || host.equals("danistay.gov.tr") || host.endsWith(".danistay.gov.tr");
    }

    private static boolean isEdevletHost(String host) {
        return host.equals("turkiye.gov.tr") || host.endsWith(".turkiye.gov.tr");
    }
}
