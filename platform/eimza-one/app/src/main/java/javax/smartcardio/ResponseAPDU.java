package javax.smartcardio;

public final class ResponseAPDU {
    private final byte[] bytes;
    public ResponseAPDU(byte[] apdu) { if (apdu == null || apdu.length < 2) throw new IllegalArgumentException("invalid response APDU"); bytes = apdu.clone(); }
    public byte[] getBytes() { return bytes.clone(); }
    public int getSW1() { return bytes[bytes.length - 2] & 255; }
    public int getSW2() { return bytes[bytes.length - 1] & 255; }
    public int getSW() { return (getSW1() << 8) | getSW2(); }
    public byte[] getData() { return java.util.Arrays.copyOf(bytes, bytes.length - 2); }
}
