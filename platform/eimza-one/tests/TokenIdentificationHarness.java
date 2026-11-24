package app.eimza.mobile;

import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.Signature;
import java.util.Locale;

public final class TokenIdentificationHarness {

    public enum TokenFamily {
        ARKSIGNER_ARKIMZA("ArkSigner Arkİmza Token"),
        TURKTRUST_TBB("TÜRKTRUST / TBB Kırmızı Token (Baro Kart)"),
        KAMUSM_ATR19("Kamu SM / TÜBİTAK (ATR19)"),
        GENERIC_PKCS15("Standart PKCS#15 E-İmza Tokenı");

        public final String title;
        TokenFamily(String title) { this.title = title; }
    }

    public static void main(String[] args) throws Exception {
        System.out.println("Running TokenIdentificationHarness...");

        // 1. Test ArkSigner Arkİmza Token ATR identification
        byte[] arksignerAtr = new byte[]{(byte) 0x3B, 0x6F, 0x00, 0x00, (byte) 0x80, 0x31, (byte) 0x80, 0x65, (byte) 0xB0, (byte) 0x85};
        TokenFamily t1 = testIdentify(arksignerAtr, "ArkSigner USB Token");
        if (t1 != TokenFamily.ARKSIGNER_ARKIMZA) {
            throw new AssertionError("ArkSigner detection failed, got: " + t1);
        }
        // 1b. Test Live ARK-IMZA token from Samsung S24 (TC Identity profile)
        byte[] arkImzaLiveAtr = new byte[]{
                (byte) 0x3B, (byte) 0x9F, (byte) 0x97, (byte) 0x81, 0x31, (byte) 0xFE, 0x45, (byte) 0x80,
                0x65, 0x54, 0x43, (byte) 0xD3, 0x23, 0x02, 0x31, (byte) 0xC0, 0x73, (byte) 0xF6,
                0x21, (byte) 0x80, (byte) 0x81, 0x05, 0x52
        };
        TokenFamily t1b = testIdentify(arkImzaLiveAtr, "ARK-IMZA");
        if (t1b != TokenFamily.ARKSIGNER_ARKIMZA) {
            throw new AssertionError("Live ARK-IMZA detection failed, got: " + t1b);
        }
        System.out.println("PASS: ArkSigner Arkİmza token correctly identified");

        // 2. Test TürkTrust TBB Kırmızı Token ATR identification
        byte[] tbbAtr = new byte[]{(byte) 0x3B, 0x7B, 0x18, 0x00, 0x00, 0x00, 0x31, (byte) 0xC0, 0x73, (byte) 0x9E, 0x01, 0x0B};
        TokenFamily t2 = testIdentify(tbbAtr, "ACS ACR38U-CCID TBB Token");
        if (t2 != TokenFamily.TURKTRUST_TBB) {
            throw new AssertionError("TürkTrust TBB detection failed, got: " + t2);
        }
        System.out.println("PASS: TürkTrust TBB Kırmızı Token correctly identified");

        // 3. Test Kamu SM ATR19 Token identification
        byte[] atr19 = new byte[]{(byte) 0x3B, (byte) 0xB7, 0x18, 0x00, (byte) 0x81, 0x31, (byte) 0xFE, 0x65, 0x55, 0x45, 0x4B, 0x41, 0x45};
        TokenFamily t3 = testIdentify(atr19, "ATR19 Smart Card Reader");
        if (t3 != TokenFamily.KAMUSM_ATR19) {
            throw new AssertionError("Kamu SM ATR19 detection failed, got: " + t3);
        }
        System.out.println("PASS: Kamu SM / TÜBİTAK (ATR19) correctly identified");

        // 4. Test DigestInfo prefix generation
        byte[] dummyData = "Test E-İmza Dokümanı 2026".getBytes("UTF-8");
        byte[] digestInfo = RsaDigestInfo.sha256(dummyData);
        if (digestInfo.length != 51) { // 19 byte header + 32 byte sha256
            throw new AssertionError("DigestInfo length should be 51, got: " + digestInfo.length);
        }
        // Verify ASN.1 header: 30 31 30 0D 06 09 60 86 48 01 65 03 04 02 01 05 00 04 20
        byte[] expectedHeader = new byte[]{
                0x30, 0x31, 0x30, 0x0D, 0x06, 0x09, 0x60, (byte) 0x86, 0x48, 0x01,
                0x65, 0x03, 0x04, 0x02, 0x01, 0x05, 0x00, 0x04, 0x20
        };
        for (int i = 0; i < expectedHeader.length; i++) {
            if (digestInfo[i] != expectedHeader[i]) {
                throw new AssertionError("DigestInfo header mismatch at byte " + i);
            }
        }
        System.out.println("PASS: SHA-256 DigestInfo prefix matches PKCS#1 v1.5 standard");

        // 5. Test RSA math verification
        KeyPairGenerator kpg = KeyPairGenerator.getInstance("RSA");
        kpg.initialize(2048);
        KeyPair kp = kpg.generateKeyPair();
        Signature signer = Signature.getInstance("SHA256withRSA");
        signer.initSign(kp.getPrivate());
        signer.update(dummyData);
        byte[] signature = signer.sign();

        Signature verifier = Signature.getInstance("SHA256withRSA");
        verifier.initVerify(kp.getPublic());
        verifier.update(dummyData);
        if (!verifier.verify(signature)) {
            throw new AssertionError("Mathematical RSA signature self-check failed");
        }
        System.out.println("PASS: RSA verification logic operational");

        System.out.println("ALL TOKEN IDENTIFICATION & SIGNING HARNESS CHECKS PASSED!");
    }

    private static TokenFamily testIdentify(byte[] atr, String readerName) {
        String atrHex = hex(atr).toUpperCase(Locale.ROOT);
        String reader = readerName != null ? readerName.toLowerCase(Locale.ROOT) : "";

        if (atrHex.startsWith("3B6F00") || atrHex.startsWith("3B2400") || atrHex.contains("454654")
                || atrHex.startsWith("3B9F978131FE4580655443")
                || reader.contains("arksigner") || reader.contains("arkimza") || reader.contains("ark-imza") || reader.contains("ark")) {
            return TokenFamily.ARKSIGNER_ARKIMZA;
        }
        if (atrHex.startsWith("3B7B1800000031C0739E010B") || reader.contains("tbb") || reader.contains("turktrust")) {
            return TokenFamily.TURKTRUST_TBB;
        }
        if (atrHex.startsWith("3BB718008131FE65") || atrHex.startsWith("3B7D180000") || reader.contains("atr19") || reader.contains("kamusm")) {
            return TokenFamily.KAMUSM_ATR19;
        }
        return TokenFamily.GENERIC_PKCS15;
    }

    private static String hex(byte[] b) {
        StringBuilder s = new StringBuilder(b.length * 2);
        for (byte v : b) s.append(String.format(Locale.ROOT, "%02X", v & 255));
        return s.toString();
    }
}
