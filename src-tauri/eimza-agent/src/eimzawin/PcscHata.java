package eimzawin;

import java.io.IOException;

/**
 * PC/SC hata kodu. ESYA (TÜBİTAK MA3) ve Adalet E-İmza hata metinlerini JDK'nın
 * "sun.security.smartcardio.PCSCException: SCARD_..." biçimine göre eşleştirdiği için aynı metin üretilir.
 */
final class PcscHata extends IOException {
    private static final long serialVersionUID = 1L;
    static final long SCARD_E_TIMEOUT = 0x8010000AL, SCARD_E_NO_READERS_AVAILABLE = 0x8010002EL,
            SCARD_W_REMOVED_CARD = 0x80100069L, SCARD_E_NO_SMARTCARD = 0x8010000CL;
    final long kod;

    PcscHata(long kod, String islem) {
        super(ad(kod));
        this.kod = kod;
        addSuppressed(new IOException(islem));
    }

    static String ad(long k) {
        switch ((int) k) {
            case 0x80100001: return "SCARD_F_INTERNAL_ERROR";
            case 0x80100002: return "SCARD_E_CANCELLED";
            case 0x80100003: return "SCARD_E_INVALID_HANDLE";
            case 0x80100004: return "SCARD_E_INVALID_PARAMETER";
            case 0x80100006: return "SCARD_E_NO_MEMORY";
            case 0x80100008: return "SCARD_E_INSUFFICIENT_BUFFER";
            case 0x80100009: return "SCARD_E_UNKNOWN_READER";
            case 0x8010000A: return "SCARD_E_TIMEOUT";
            case 0x8010000B: return "SCARD_E_SHARING_VIOLATION";
            case 0x8010000C: return "SCARD_E_NO_SMARTCARD";
            case 0x8010000D: return "SCARD_E_UNKNOWN_CARD";
            case 0x8010000F: return "SCARD_E_PROTO_MISMATCH";
            case 0x80100010: return "SCARD_E_NOT_READY";
            case 0x80100011: return "SCARD_E_INVALID_VALUE";
            case 0x80100013: return "SCARD_F_COMM_ERROR";
            case 0x80100016: return "SCARD_E_NOT_TRANSACTED";
            case 0x80100017: return "SCARD_E_READER_UNAVAILABLE";
            case 0x8010001D: return "SCARD_E_NO_SERVICE";
            case 0x8010001E: return "SCARD_E_SERVICE_STOPPED";
            case 0x8010002E: return "SCARD_E_NO_READERS_AVAILABLE";
            case 0x80100066: return "SCARD_W_UNRESPONSIVE_CARD";
            case 0x80100067: return "SCARD_W_UNPOWERED_CARD";
            case 0x80100068: return "SCARD_W_RESET_CARD";
            case 0x80100069: return "SCARD_W_REMOVED_CARD";
            default: return String.format("SCARD_ERROR_0x%08X", k);
        }
    }

    @Override public String toString() { return "sun.security.smartcardio.PCSCException: " + getMessage(); }
}
