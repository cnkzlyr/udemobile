package javax.smartcardio;

import java.io.ByteArrayOutputStream;

public final class CommandAPDU {
    private final byte[] bytes;
    public CommandAPDU(byte[] apdu) { if (apdu == null || apdu.length < 4) throw new IllegalArgumentException("invalid APDU"); bytes = apdu.clone(); }
    public CommandAPDU(byte[] apdu, int offset, int length) {
        if (apdu == null || offset < 0 || length < 4 || offset + length > apdu.length) throw new IllegalArgumentException("invalid APDU range");
        bytes = new byte[length]; System.arraycopy(apdu, offset, bytes, 0, length);
    }
    public CommandAPDU(int cla, int ins, int p1, int p2) { this(cla, ins, p1, p2, null, 256); }
    public CommandAPDU(int cla, int ins, int p1, int p2, int ne) { this(cla, ins, p1, p2, null, ne); }
    public CommandAPDU(int cla, int ins, int p1, int p2, byte[] data) { this(cla, ins, p1, p2, data, 0); }
    public CommandAPDU(int cla, int ins, int p1, int p2, byte[] data, int dataOffset, int dataLength) {
        this(cla, ins, p1, p2, slice(data, dataOffset, dataLength), 0);
    }
    public CommandAPDU(int cla, int ins, int p1, int p2, byte[] data, int dataOffset, int dataLength, int ne) {
        this(cla, ins, p1, p2, slice(data, dataOffset, dataLength), ne);
    }
    public CommandAPDU(int cla, int ins, int p1, int p2, byte[] data, int ne) {
        checkByte(cla); checkByte(ins); checkByte(p1); checkByte(p2);
        int nc = data == null ? 0 : data.length;
        if (nc > 65535 || ne < 0 || ne > 65536) throw new IllegalArgumentException("APDU length out of range");
        ByteArrayOutputStream out = new ByteArrayOutputStream(); out.write(cla); out.write(ins); out.write(p1); out.write(p2);
        boolean extended = nc > 255 || ne > 256;
        if (nc == 0 && ne == 0) { /* case 1 */ }
        else if (!extended) {
            if (nc > 0) { out.write(nc); out.write(data, 0, nc); if (ne > 0) out.write(ne == 256 ? 0 : ne); }
            else out.write(ne == 256 ? 0 : ne);
        } else {
            out.write(0);
            if (nc > 0) { out.write((nc >>> 8) & 255); out.write(nc & 255); out.write(data, 0, nc); }
            if (ne > 0) { out.write((ne >>> 8) & 255); out.write(ne & 255); }
        }
        bytes = out.toByteArray();
    }
    private static void checkByte(int v) { if ((v & ~255) != 0) throw new IllegalArgumentException("byte value out of range"); }
    private static byte[] slice(byte[] d, int offset, int length) {
        if (d == null) { if (offset != 0 || length != 0) throw new IllegalArgumentException("invalid data range"); return null; }
        if (offset < 0 || length < 0 || offset + length > d.length) throw new IllegalArgumentException("invalid data range");
        return java.util.Arrays.copyOfRange(d, offset, offset + length);
    }
    public byte[] getBytes() { return bytes.clone(); }
    public int getCLA() { return bytes[0] & 255; }
    public int getINS() { return bytes[1] & 255; }
    public int getP1() { return bytes[2] & 255; }
    public int getP2() { return bytes[3] & 255; }
    private boolean extended() { return bytes.length > 4 && bytes[4] == 0 && bytes.length > 5; }
    public int getNc() {
        if (bytes.length < 6) return 0;
        if (!extended()) return bytes.length > 5 ? bytes[4] & 255 : 0;
        int n = ((bytes[5] & 255) << 8) | (bytes[6] & 255);
        return n > 0 && bytes.length >= 7 + n ? n : 0;
    }
    public int getNe() {
        int nc = getNc();
        if (bytes.length == 5) return (bytes[4] & 255) == 0 ? 256 : bytes[4] & 255;
        if (extended()) {
            if (nc > 0 && bytes.length == 7 + nc) { int n = ((bytes[bytes.length-2]&255)<<8)|(bytes[bytes.length-1]&255); return n == 0 ? 65536 : n; }
            if (nc == 0 && bytes.length == 7) { int n = ((bytes[5]&255)<<8)|(bytes[6]&255); return n == 0 ? 65536 : n; }
            return 0;
        }
        if (nc > 0 && bytes.length == 6 + nc) return (bytes[bytes.length - 1] & 255) == 0 ? 256 : bytes[bytes.length - 1] & 255;
        return 0;
    }
    public byte[] getData() {
        int n = getNc(); if (n == 0) return new byte[0];
        int start = extended() ? 7 : 5;
        return java.util.Arrays.copyOfRange(bytes, start, start + n);
    }
}
