package app.eimza.mobile;

import android.hardware.usb.UsbDeviceConnection;
import android.hardware.usb.UsbEndpoint;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.Arrays;
import java.util.Locale;

/**
 * CCID bulk transport supporting both T=1 TPDU block layer and direct APDU exchange.
 * Automatically adapts to CCID reader features (dwFeatures) and card protocols.
 */
final class UsbCcidTransport {
    private static final int MAX_CCID_MESSAGE = 4096;
    private final UsbDeviceConnection connection;
    private final UsbEndpoint input;
    private final UsbEndpoint output;
    private int sequence;
    private int ns;
    private int cardNs;
    private boolean apduLevel;
    private int lastResponsePcb;

    UsbCcidTransport(UsbDeviceConnection connection, UsbEndpoint input, UsbEndpoint output) {
        this.connection = connection;
        this.input = input;
        this.output = output;
    }

    void setApduLevel(boolean apduLevel) {
        this.apduLevel = apduLevel;
    }

    boolean isApduLevel() {
        return apduLevel;
    }

    int slotStatus() throws IOException {
        byte[] r = command(0x65, new byte[0], new byte[3], 5000);
        if ((r[0] & 0xff) != 0x81) throw new IOException("CCID slot-status yanıtı hatalı");
        return r[7] & 3; // 0 active, 1 inactive, 2 no card
    }

    byte[] powerOn() throws IOException {
        byte[] atr = command(0x62, new byte[0], new byte[]{0, 0, 0}, 15000);
        if ((atr[0] & 0xff) != 0x80 || atr.length < 12)
            throw new IOException("Kart ATR yanıtı alınamadı");
        ns = cardNs = 0;
        byte[] cardAtr = Arrays.copyOfRange(atr, 10, atr.length);

        // Attempt IFSD negotiation only in T=1 TPDU mode (ATR19 advertises max_ifsd=254)
        if (!apduLevel) {
            try {
                byte[] ifs = exchange(t1Block(0xc1, new byte[]{(byte) 254}));
                if ((ifs[1] & 255) != 0xe1 || (ifs[2] & 255) != 1 || (ifs[3] & 255) != 254) {
                    // IFSD negotiation was not accepted by card, ignore
                }
            } catch (IOException ignored) {
                // Some card/reader combinations reject host initiated IFS; default IFSD remains valid.
            }
        }
        ns = cardNs = 0;
        return cardAtr;
    }

    void powerOff() {
        try { command(0x63, new byte[0], new byte[]{0, 0, 0}, 3000); }
        catch (IOException ignored) { }
    }

    /**
     * Unified APDU transmission method. Chooses between direct APDU and T=1 framing.
     */
    byte[] transmit(byte[] apdu) throws IOException {
        if (apduLevel) {
            try {
                return transmitApduDirect(apdu);
            } catch (IOException e) {
                return transmitT1(apdu);
            }
        } else {
            try {
                return transmitT1(apdu);
            } catch (IOException e) {
                return transmitApduDirect(apdu);
            }
        }
    }

    /**
     * Sends raw APDU directly to an APDU-level CCID device (dwFeatures 0x00040000 / 0x00080000).
     * Handles ISO 7816-4 GET RESPONSE (61 xx) and wrong length Le (6C xx) automatically.
     */
    byte[] transmitApduDirect(byte[] apdu) throws IOException {
        if (apdu == null || apdu.length == 0 || apdu.length > 65535)
            throw new IOException("APDU boyutu geçersiz");

        byte[] r = command(0x6f, apdu, new byte[]{0, 0, 0}, 60000);
        if (r.length < 12) throw new IOException("CCID APDU yanıtı kısa");
        long payloadLength = le32(r, 1);
        if (payloadLength > MAX_CCID_MESSAGE || r.length < 10 + payloadLength)
            throw new IOException("CCID APDU yanıtı eksik");

        int len = (int) payloadLength;
        byte[] response = Arrays.copyOfRange(r, 10, 10 + len);
        if (response.length < 2) return response;

        int sw1 = response[response.length - 2] & 0xFF;
        int sw2 = response[response.length - 1] & 0xFF;

        // SW 61 xx: More response bytes available -> send GET RESPONSE (00 C0 00 00 xx)
        if (sw1 == 0x61 && sw2 > 0) {
            byte[] getResponseApdu = new byte[]{0x00, (byte) 0xC0, 0x00, 0x00, (byte) sw2};
            byte[] rest = transmitApduDirect(getResponseApdu);
            byte[] combined = new byte[response.length - 2 + rest.length];
            System.arraycopy(response, 0, combined, 0, response.length - 2);
            System.arraycopy(rest, 0, combined, response.length - 2, rest.length);
            return combined;
        }

        // SW 6C xx: Wrong Le -> re-issue with exact Le requested by card
        if (sw1 == 0x6C && apdu.length >= 4) {
            byte[] correctedApdu = new byte[apdu.length];
            System.arraycopy(apdu, 0, correctedApdu, 0, apdu.length);
            correctedApdu[correctedApdu.length - 1] = (byte) sw2;
            return transmitApduDirect(correctedApdu);
        }

        return response;
    }

    /**
     * T=1 block layer transmission. Supports APDU chaining and multi-block responses.
     */
    byte[] transmitT1(byte[] apdu) throws IOException {
        if (apdu == null || apdu.length == 0 || apdu.length > 65535)
            throw new IOException("APDU boyutu geçersiz");
        int maxInf = 240; // ATR19 reports IFSC=254; leave room for CCID/T=1 framing.
        int offset = 0;
        byte[] reply = new byte[0];
        do {
            int n = Math.min(maxInf, apdu.length - offset);
            boolean more = offset + n < apdu.length;
            byte[] block = t1Block((ns << 6) | (more ? 0x20 : 0), Arrays.copyOfRange(apdu, offset, offset + n));
            byte[] response = exchange(block);
            int pcb = response[1] & 0xff;
            if (more) {
                if ((pcb & 0xc0) != 0x80 || ((pcb >>> 4) & 1) != (ns ^ 1))
                    throw new IOException("Kart T=1 zincir bloğunu onaylamadı");
            } else {
                if ((pcb & 0x80) != 0) throw new IOException("Kart T=1 yanıt bloğu bekleniyordu");
                reply = Arrays.copyOfRange(response, 3, 3 + (response[2] & 0xff));
            }
            ns ^= 1;
            offset += n;
        } while (offset < apdu.length);

        int pcb = lastResponsePcb;
        while ((pcb & 0x20) != 0) {
            cardNs ^= 1;
            byte[] ack = t1Block(0x80 | (cardNs << 4), new byte[0]);
            byte[] response = exchange(ack);
            pcb = response[1] & 0xff;
            if ((pcb & 0x80) != 0) throw new IOException("Kart T=1 I-blok yanıtı bekleniyordu");
            int n = response[2] & 0xff;
            reply = concat(reply, Arrays.copyOfRange(response, 3, 3 + n));
        }
        cardNs ^= 1;
        return reply;
    }

    private byte[] exchange(byte[] block) throws IOException {
        byte[] current = block;
        int bwi = 0;
        for (int attempt = 0; attempt < 3; attempt++) {
            byte[] r = command(0x6f, current, new byte[]{(byte)bwi, 0, 0}, 60000);
            if (r.length < 4) throw new IOException("CCID T=1 yanıtı kısa");
            long payloadLength = le32(r, 1);
            if (payloadLength > MAX_CCID_MESSAGE || r.length < 10 + payloadLength)
                throw new IOException("CCID T=1 yanıtı eksik");
            int len = (int) payloadLength;
            byte[] b = Arrays.copyOfRange(r, 10, 10 + len);
            if (!validT1(b)) {
                current = t1Block(0x80 | (cardNs << 4) | 1, new byte[0]); // R-block: EDC error
                continue;
            }
            int pcb = b[1] & 0xff;
            if (pcb == 0xc3) { // WTX request: acknowledge then receive the pending card block.
                byte[] inf = Arrays.copyOfRange(b, 3, b.length - 1);
                current = t1Block(0xe3, inf);
                bwi = inf.length == 0 ? 1 : inf[0] & 255;
                continue;
            }
            if (pcb == 0xc1) { // card requests a new IFSC
                current = t1Block(0xe1, Arrays.copyOfRange(b, 3, b.length - 1));
                continue;
            }
            if (pcb == 0xc2) { // card abort request
                current = t1Block(0xe2, Arrays.copyOfRange(b, 3, b.length - 1));
                continue;
            }
            lastResponsePcb = pcb;
            return b;
        }
        throw new IOException("T=1 blok hatası (3 deneme başarısız)");
    }

    private byte[] command(int type, byte[] data, byte[] params, int timeout) throws IOException {
        int seq = sequence++ & 0xff;
        byte[] msg = new byte[10 + data.length];
        msg[0] = (byte) type;
        putLe32(msg, 1, data.length);
        msg[5] = 0; msg[6] = (byte) seq;
        System.arraycopy(params, 0, msg, 7, 3);
        System.arraycopy(data, 0, msg, 10, data.length);
        int sent = connection.bulkTransfer(output, msg, msg.length, timeout);
        if (sent != msg.length) throw new IOException("USB CCID gönderimi başarısız: " + sent);

        byte[] buf = new byte[Math.max(512, input.getMaxPacketSize())];
        for (;;) {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            int needed = 10;
            while (bytes.size() < needed) {
                int n = connection.bulkTransfer(input, buf, buf.length, timeout);
                if (n <= 0) throw new IOException("USB CCID yanıt zaman aşımı");
                bytes.write(buf, 0, n);
                byte[] soFar = bytes.toByteArray();
                if (soFar.length >= 10) {
                    long payload = le32(soFar, 1);
                    if (payload > MAX_CCID_MESSAGE) throw new IOException("CCID yanıtı çok büyük");
                    needed = 10 + (int) payload;
                }
            }
            byte[] response = bytes.toByteArray();
            if ((response[6] & 0xff) != seq) throw new IOException("CCID sıra numarası uyuşmuyor");
            int status = response[7] & 0xff;
            if ((status >>> 6) == 2) continue; // same command, same sequence; wait for next response
            if ((status >>> 6) == 1) throw new IOException(String.format("CCID hata kodu 0x%02X", response[8] & 255));
            return response;
        }
    }

    private static byte[] t1Block(int pcb, byte[] inf) {
        byte[] b = new byte[4 + inf.length];
        b[0] = 0; b[1] = (byte) pcb; b[2] = (byte) inf.length;
        System.arraycopy(inf, 0, b, 3, inf.length);
        b[b.length - 1] = (byte) lrc(b, b.length - 1);
        return b;
    }

    private static boolean validT1(byte[] b) {
        if (b.length < 4 || b.length != (b[2] & 0xff) + 4) return false;
        return lrc(b, b.length) == 0;
    }

    private static int lrc(byte[] b, int len) {
        int x = 0; for (int i = 0; i < len; i++) x ^= b[i] & 255; return x;
    }

    static String hex(byte[] b) {
        if (b == null) return "";
        StringBuilder s = new StringBuilder(b.length * 2);
        for (byte v : b) s.append(String.format(Locale.ROOT, "%02X", v & 255));
        return s.toString();
    }

    private static byte[] concat(byte[] a, byte[] b) {
        byte[] c = Arrays.copyOf(a, a.length + b.length);
        System.arraycopy(b, 0, c, a.length, b.length); return c;
    }

    private static void putLe32(byte[] b, int o, int n) {
        b[o] = (byte)n; b[o+1] = (byte)(n>>>8); b[o+2] = (byte)(n>>>16); b[o+3] = (byte)(n>>>24);
    }
    private static long le32(byte[] b, int o) {
        return (b[o]&255L) | ((b[o+1]&255L)<<8) | ((b[o+2]&255L)<<16) | ((b[o+3]&255L)<<24);
    }
}
