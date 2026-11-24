#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/src/android/hardware/usb" "$TMP/src/app/eimza/mobile" "$TMP/classes"
cat > "$TMP/src/android/hardware/usb/UsbEndpoint.java" <<'JAVA'
package android.hardware.usb;
public class UsbEndpoint { public int getMaxPacketSize() { return 64; } }
JAVA
cat > "$TMP/src/android/hardware/usb/UsbDeviceConnection.java" <<'JAVA'
package android.hardware.usb;
import java.util.*;
public class UsbDeviceConnection {
  private final ArrayDeque<byte[]> replies = new ArrayDeque<>();
  public int bulkTransfer(UsbEndpoint ep, byte[] data, int length, int timeout) {
    if (ep == OUT) { handle(Arrays.copyOf(data, length)); return length; }
    byte[] r = replies.poll(); if (r == null) return -1;
    int n = Math.min(length, r.length); System.arraycopy(r, 0, data, 0, n);
    if (n != r.length) replies.addFirst(Arrays.copyOfRange(r, n, r.length));
    return n;
  }
  public static final UsbEndpoint IN = new UsbEndpoint(), OUT = new UsbEndpoint();
  private void handle(byte[] m) {
    int type = m[0] & 255, seq = m[6] & 255;
    if (type == 0x6f) {
      int n = m[10] & 255, pcb = m[11] & 255;
      byte[] inf = new byte[n]; System.arraycopy(m, 13, inf, 0, n);
      byte[] block;
      if (pcb == 0xc1) block = t1(0xe1, inf);
      else if ((pcb & 0x20) != 0) block = t1(0x80 | ((((pcb >>> 6) & 1) ^ 1) << 4), new byte[0]);
      else block = t1(0, new byte[]{(byte)0x90, 0});
      reply(0x80, seq, block);
    } else if (type == 0x65) reply(0x81, seq, new byte[0]);
    else if (type == 0x62) reply(0x80, seq, new byte[]{0x3b,(byte)0x9f,(byte)0x97,(byte)0x81,0x31,(byte)0xfe,0x45,(byte)0x80,0x65,0x54,0x43,(byte)0xd3,0x23,0x02,0x31,(byte)0xc0,0x73,(byte)0xf6,0x21,(byte)0x80,(byte)0x81,0x05,0x52});
    else reply(0x81, seq, new byte[0]);
  }
  private void reply(int type, int seq, byte[] d) {
    byte[] r = new byte[10+d.length]; r[0]=(byte)type; r[1]=(byte)d.length; r[5]=0; r[6]=(byte)seq;
    System.arraycopy(d,0,r,10,d.length); replies.add(r);
  }
  private static byte[] t1(int pcb, byte[] inf) {
    byte[] b=new byte[4+inf.length]; b[1]=(byte)pcb; b[2]=(byte)inf.length; System.arraycopy(inf,0,b,3,inf.length);
    for(int i=0;i<b.length-1;i++) b[b.length-1]^=b[i]; return b;
  }
}
JAVA
cat > "$TMP/src/app/eimza/mobile/CcidTransportHarness.java" <<'JAVA'
package app.eimza.mobile;
import android.hardware.usb.*;
import java.util.Arrays;
public final class CcidTransportHarness {
  public static void main(String[] args) throws Exception {
    UsbCcidTransport t = new UsbCcidTransport(new UsbDeviceConnection(), UsbDeviceConnection.IN, UsbDeviceConnection.OUT);
    if (t.slotStatus() != 0) throw new AssertionError("slot state");
    byte[] atr=t.powerOn(); if (atr.length != 23) throw new AssertionError("ATR length="+atr.length);
    byte[] r=t.transmitT1(new byte[]{0, (byte)0xa4, 4, 0, 0});
    if (!Arrays.equals(r,new byte[]{(byte)0x90,0})) throw new AssertionError("APDU="+UsbCcidTransport.hex(r));
    byte[] longApdu=new byte[500]; longApdu[0]=(byte)0x80;
    r=t.transmitT1(longApdu);
    if (!Arrays.equals(r,new byte[]{(byte)0x90,0})) throw new AssertionError("chained APDU="+UsbCcidTransport.hex(r));
    System.out.println("PASS: slot status, ATR activation, T=1 APDU response, host APDU chaining");
  }
}
JAVA
JAVA_COMPILER=${JAVA_COMPILER:-jdk.compiler/com.sun.tools.javac.Main}
java -m "$JAVA_COMPILER" -d "$TMP/classes" \
  "$TMP/src/android/hardware/usb/UsbEndpoint.java" \
  "$TMP/src/android/hardware/usb/UsbDeviceConnection.java" \
  "$ROOT/app/src/main/java/app/eimza/mobile/UsbCcidTransport.java" \
  "$TMP/src/app/eimza/mobile/CcidTransportHarness.java"
java -cp "$TMP/classes" app.eimza.mobile.CcidTransportHarness
