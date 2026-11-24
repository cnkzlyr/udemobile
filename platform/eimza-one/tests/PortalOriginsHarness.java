package app.eimza.mobile;

public final class PortalOriginsHarness {
    private static void expect(boolean value, String label) {
        if (!value) throw new AssertionError(label);
    }

    public static void main(String[] args) {
        expect(PortalOrigins.mayBridge("https://ogn.saglik.gov.tr", "https://recetem.enabiz.gov.tr/"),
                "health iframe must bridge across the two approved health domains");
        expect(PortalOrigins.mayBridge("https://sub.enabiz.gov.tr", "https://enabiz.gov.tr/"),
                "e-Nabiz subdomain must bridge");
        expect(PortalOrigins.mayBridge("https://test.arksigner.com", "https://test.arksigner.com/"),
                "ArkSigner test host must bridge to itself");
        expect(!PortalOrigins.mayBridge("http://ogn.saglik.gov.tr", "https://recetem.enabiz.gov.tr/"),
                "plain HTTP must be rejected");
        expect(!PortalOrigins.mayBridge("https://evil.example", "https://recetem.enabiz.gov.tr/"),
                "unapproved origin must be rejected");
        expect(!PortalOrigins.mayBridge("https://test.arksigner.com", "https://enabiz.gov.tr/"),
                "test host must not be embedded into health portal");
        expect(PortalOrigins.mayBridge("https://avukat.uyap.gov.tr", "https://avukat.uyap.gov.tr/"),
                "same Adalet host must bridge");
        expect(!PortalOrigins.mayBridge("https://foo.uyap.gov.tr", "https://bar.uyap.gov.tr/"),
                "Adalet host boundary must remain narrow");
        expect(PortalOrigins.isEdevlet("https://giris.turkiye.gov.tr/Giris/Elektronik-Imza"),
                "official e-Devlet login must be recognized");
        expect(PortalOrigins.mayBridge("https://www.turkiye.gov.tr", "https://giris.turkiye.gov.tr/"),
                "official e-Devlet hosts must share the transaction bridge");
        expect(!PortalOrigins.isEdevlet("https://turkiye.gov.tr.evil.example/"),
                "lookalike e-Devlet host must be rejected");
        expect(PortalOrigins.requiresAttachedCades("https://ogn.saglik.gov.tr/Account/Login"),
                "OGN SSO must force embedded CMS content");
        expect(PortalOrigins.requiresAttachedCades("https://ognportal.saglik.gov.tr/sign"),
                "OGN portal SSO must force embedded CMS content");
        expect(!PortalOrigins.requiresAttachedCades("https://recetem.enabiz.gov.tr/"),
                "ordinary health pages must retain the portal's requested CMS mode");
        System.out.println("PASS: portal origin policy");
    }
}
