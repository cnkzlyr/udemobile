package javax.smartcardio;

import java.io.Serializable;
import java.util.Arrays;

public final class ATR implements Serializable {
    private static final long serialVersionUID = 1L;
    private final byte[] bytes;
    public ATR(byte[] bytes) {
        if (bytes == null || bytes.length < 2) throw new IllegalArgumentException("ATR must have at least two bytes");
        this.bytes = bytes.clone();
    }
    public byte[] getBytes() { return bytes.clone(); }
    public byte[] getHistoricalBytes() {
        int start = historicalOffset();
        int length = bytes[1] & 0x0f;
        if (start < 0 || start + length > bytes.length) return new byte[0];
        return Arrays.copyOfRange(bytes, start, start + length);
    }
    public byte[] getInterfaceBytes() {
        int end = historicalOffset();
        return end < 2 ? new byte[0] : Arrays.copyOfRange(bytes, 2, end);
    }

    /** ISO/IEC 7816-3: walk every Y group before the K historical bytes. */
    private int historicalOffset() {
        int offset = 2;
        int y = (bytes[1] >>> 4) & 0x0f;
        while (true) {
            if ((y & 0x1) != 0 && ++offset > bytes.length) return -1; // TAi
            if ((y & 0x2) != 0 && ++offset > bytes.length) return -1; // TBi
            if ((y & 0x4) != 0 && ++offset > bytes.length) return -1; // TCi
            if ((y & 0x8) == 0) return offset;
            if (offset >= bytes.length) return -1;
            int td = bytes[offset++] & 0xff;
            y = (td >>> 4) & 0x0f;
        }
    }
    @Override public boolean equals(Object other) { return other instanceof ATR && Arrays.equals(bytes, ((ATR) other).bytes); }
    @Override public int hashCode() { return Arrays.hashCode(bytes); }
    @Override public String toString() {
        StringBuilder s = new StringBuilder();
        for (byte b : bytes) s.append(String.format(java.util.Locale.ROOT, "%02X ", b & 255));
        return s.toString().trim();
    }
}
