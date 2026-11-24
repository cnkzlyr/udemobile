package app.eimza.mobile;

import java.util.List;

/** Narrow native boundary for signer implementations. No raw APDU is exposed to page JavaScript. */
interface SignerBackend extends AutoCloseable {
    String id();
    String displayName();
    State state();
    List<CertificateSummary> certificates() throws SignerException;
    byte[] sign(byte[] payload, String certificateId, char[] pin) throws SignerException;
    default byte[] signRawPkcs1(byte[] digestInfo, String certificateId, char[] pin)
            throws SignerException {
        throw new SignerException("Ham RSA PKCS#1 imzası bu kart sağlayıcısında desteklenmiyor");
    }
    @Override void close();

    enum State { STOPPED, STARTING, WAITING_FOR_READER, READY, ERROR }

    /** Deliberately excludes subject data beyond a UI label and never contains private keys. */
    final class CertificateSummary {
        final String id;
        final String label;
        final String validUntil;

        CertificateSummary(String id, String label, String validUntil) {
            this.id = id;
            this.label = label;
            this.validUntil = validUntil;
        }
    }

    final class SignerException extends Exception {
        SignerException(String message) { super(message); }
        SignerException(String message, Throwable cause) { super(message, cause); }
    }
}
