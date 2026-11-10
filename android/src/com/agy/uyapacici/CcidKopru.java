package com.agy.uyapacici;

import android.content.Context;
import android.hardware.usb.UsbConstants;
import android.hardware.usb.UsbDevice;
import android.hardware.usb.UsbDeviceConnection;
import android.hardware.usb.UsbEndpoint;
import android.hardware.usb.UsbInterface;
import android.hardware.usb.UsbManager;
import android.util.Log;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Arrays;

/**
 * USB CCID akıllı kart okuyucu köprüsü (Termux'suz; uyap-termux-pro ccid_bridge.py'nin Android karşılığı).
 *
 * Gömülü Java'da çalışan resmi Adalet E-İmza uygulaması kartı javax.smartcardio ile görür; ajanımızdaki
 * sağlayıcı (eimza.TermuxCcidProvider) bu köprüye 127.0.0.1 üzerinden bağlanır (bridge.json: port + jeton).
 *
 * Protokol (satır tabanlı): AUTH jeton | INFO | STATUS | CONNECT | TRANSMIT hex | DISCONNECT [1] | PIN hex(başlık)
 * Cevaplar: "OK ..." ya da "ERR KOD açıklama" (REMOVED, NO_CARD, PROTO, USB, IPTAL).
 *
 * Okuyucu türleri: APDU seviyeli (kısa/uzun, zincirleme) ve TPDU seviyeli (T=1 blok protokolü burada yapılır).
 * PIN ve APDU içerikleri günlüğe YAZILMAZ.
 */
public class CcidKopru {
    private static final String TAG = "CcidKopru";
    static final int LEVEL_TPDU = 0x10000, LEVEL_SHORT = 0x20000, LEVEL_EXT = 0x40000;

    /** PIN isteklerini karşılayan (Android penceresi) arayüz. null dönerse iptal. */
    public interface PinSaglayici {
        String pinIste(String baslik);
    }

    private final Context ctx;
    private final File durumDizini;
    private final PinSaglayici pin;
    private ServerSocket sunucu;
    private String jeton;
    private volatile boolean calisiyor;
    private Okuyucu okuyucu;            // bağlı okuyucu (yoksa null)
    private int istemci = 0;
    private final Object kilit = new Object();

    public CcidKopru(Context ctx, File durumDizini, PinSaglayici pin) {
        this.ctx = ctx.getApplicationContext();
        this.durumDizini = durumDizini;
        this.pin = pin;
    }

    // ------------------------------------------------------------------------------------ sunucu
    public synchronized void baslat() throws IOException {
        if (calisiyor) return;
        durumDizini.mkdirs();
        byte[] r = new byte[16];
        new SecureRandom().nextBytes(r);
        jeton = hex(r).toLowerCase();
        sunucu = new ServerSocket(0, 8, InetAddress.getByName("127.0.0.1"));
        File f = new File(durumDizini, "bridge.json");
        File tmp = new File(durumDizini, "bridge.json.tmp");
        try (FileOutputStream o = new FileOutputStream(tmp)) {
            o.write(("{\"port\": " + sunucu.getLocalPort() + ", \"token\": \"" + jeton + "\", \"name\": \"UdeMobile USB\"}")
                    .getBytes(StandardCharsets.UTF_8));
        }
        tmp.setReadable(false, false);
        tmp.setReadable(true, true);
        if (!tmp.renameTo(f)) throw new IOException("bridge.json yazılamadı");
        calisiyor = true;
        Thread t = new Thread(new Runnable() {
            @Override public void run() { dinle(); }
        }, "ccid-kopru");
        t.setDaemon(true);
        t.start();
        Log.i(TAG, "köprü 127.0.0.1:" + sunucu.getLocalPort());
    }

    public synchronized void durdur() {
        calisiyor = false;
        try { if (sunucu != null) sunucu.close(); } catch (IOException ignored) { }
        synchronized (kilit) { okuyucuKapat(); }
        new File(durumDizini, "bridge.json").delete();
    }

    private void dinle() {
        while (calisiyor) {
            try {
                final Socket s = sunucu.accept();
                Thread t = new Thread(new Runnable() {
                    @Override public void run() { istemciIsle(s); }
                }, "ccid-istemci");
                t.setDaemon(true);
                t.start();
            } catch (IOException e) {
                if (!calisiyor) return;
            }
        }
    }

    private void istemciIsle(Socket s) {
        try {
            s.setTcpNoDelay(true);
            BufferedReader in = new BufferedReader(new InputStreamReader(s.getInputStream(), StandardCharsets.UTF_8));
            OutputStream out = s.getOutputStream();
            String ilk = in.readLine();
            if (ilk == null || !ilk.startsWith("AUTH ") || !MessageDigest.isEqual(ilk.substring(5).trim().getBytes(StandardCharsets.UTF_8),
                    jeton.getBytes(StandardCharsets.UTF_8))) {
                yaz(out, "ERR AUTH yetkisiz");
                s.close();
                return;
            }
            yaz(out, "OK");
            synchronized (kilit) { istemci++; }
            try {
                String satir;
                while ((satir = in.readLine()) != null) {
                    satir = satir.trim();
                    if (satir.isEmpty()) continue;
                    if (satir.equals("QUIT")) break;
                    yaz(out, isle(satir));
                }
            } finally {
                synchronized (kilit) {
                    istemci--;
                    if (istemci <= 0 && okuyucu != null && okuyucu.powered) {
                        // son istemci gitti: kartta açık PIN oturumu bırakma
                        try { okuyucu.powerOff(); } catch (Exception ignored) { }
                    }
                }
            }
        } catch (IOException ignored) {
        } finally {
            try { s.close(); } catch (IOException ignored) { }
        }
    }

    private static void yaz(OutputStream out, String s) throws IOException {
        out.write((s + "\n").getBytes(StandardCharsets.UTF_8));
        out.flush();
    }

    String isle(String satir) {
        String op = satir, arg = "";
        int bos = satir.indexOf(' ');
        if (bos > 0) { op = satir.substring(0, bos); arg = satir.substring(bos + 1).trim(); }
        if (op.equals("PIN")) {              // kart kilidi tutulmaz: kullanıcı PIN yazarken kart işlemleri bekletilmez
            String baslik = new String(unhex(arg), StandardCharsets.UTF_8);
            String p = pin != null ? pin.pinIste(baslik) : null;
            return p == null ? "ERR IPTAL kullanıcı iptal etti" : "OK " + hex(p.getBytes(StandardCharsets.UTF_8));
        }
        synchronized (kilit) {
            try {
                Okuyucu rd = okuyucuAl();
                if (rd == null) return "ERR USB okuyucu yok";
                switch (op) {
                    case "INFO": return "OK " + rd.name;
                    case "STATUS": return "OK " + (rd.cardPresent() ? "1" : "0");
                    case "CONNECT": {
                        byte[] atr = rd.connect();
                        return "OK " + hex(atr) + " T=" + (rd.atrInfo != null ? rd.atrInfo.proto : 1);
                    }
                    case "TRANSMIT": return "OK " + hex(rd.transmit(unhex(arg)));
                    case "DISCONNECT":
                        if (arg.equals("1")) rd.powerOff();
                        return "OK";
                    default: return "ERR PROTO bilinmeyen komut";
                }
            } catch (KartYok e) {
                return "ERR REMOVED " + e.getMessage();
            } catch (ProtoHata e) {
                return "ERR PROTO " + e.getMessage();
            } catch (Exception e) {
                okuyucuKapat();                 // USB koptu: bir sonraki komutta yeniden açılır
                return "ERR USB " + e.getMessage();
            }
        }
    }

    // ------------------------------------------------------------------------------------ USB
    /** Takılı (ve izni verilmiş) ilk CCID okuyucuyu açar; zaten açıksa onu döndürür. */
    private Okuyucu okuyucuAl() throws IOException {
        if (okuyucu != null) {
            if (okuyucuHalaTakili(okuyucu.device)) return okuyucu;
            okuyucuKapat();
        }
        UsbManager um = (UsbManager) ctx.getSystemService(Context.USB_SERVICE);
        if (um == null) return null;
        for (UsbDevice d : um.getDeviceList().values()) {
            UsbInterface ifc = ccidArayuzu(d);
            if (ifc == null) continue;
            if (!um.hasPermission(d)) {
                // Sistem izin penceresi: her takılışta BİR kez (Adalet uygulaması sık yokladığı için tekrar açılmasın)
                String anahtar = d.getDeviceName() + "/" + d.getDeviceId();
                if (izinIstenen.add(anahtar)) CcidDriver.getInstance(ctx).requestPermission(d);
                continue;
            }
            UsbDeviceConnection c = um.openDevice(d);
            if (c == null) continue;
            if (!c.claimInterface(ifc, true)) { c.close(); continue; }
            okuyucu = new Okuyucu(d, c, ifc);
            Log.i(TAG, "okuyucu: " + okuyucu.name + " seviye=" + Integer.toHexString(okuyucu.level));
            return okuyucu;
        }
        return null;
    }

    private boolean okuyucuHalaTakili(UsbDevice d) {
        UsbManager um = (UsbManager) ctx.getSystemService(Context.USB_SERVICE);
        return um != null && um.getDeviceList().containsKey(d.getDeviceName());
    }

    private void okuyucuKapat() {
        if (okuyucu != null) {
            try { okuyucu.conn.releaseInterface(okuyucu.ifc); } catch (Exception ignored) { }
            try { okuyucu.conn.close(); } catch (Exception ignored) { }
            okuyucu = null;
        }
    }

    public String okuyucuAdi() {
        synchronized (kilit) {
            try { Okuyucu r = okuyucuAl(); return r == null ? null : r.name; } catch (Exception e) { return null; }
        }
    }

    /** Bilinen e-imza okuyucu/token üreticileri (bazı tokenlar CCID'yi üreticiye özel sınıfla, 0xFF, bildirir). */
    static final int[] BILINEN_URETICI = {0x072F /* ACS ACR38/39 */, 0x2CE3 /* ArkSigner */, 0x0529 /* SafeNet */,
            0x08E6 /* Gemalto */, 0x04E6 /* Identiv/SCM */, 0x076B /* Omnikey */, 0x096E /* Feitian */, 0x058F /* Alcor */};

    static UsbInterface ccidArayuzu(UsbDevice d) {
        for (int i = 0; i < d.getInterfaceCount(); i++) {
            UsbInterface f = d.getInterface(i);
            if (f.getInterfaceClass() == 0x0B) return f;
        }
        boolean bilinen = false;
        for (int v : BILINEN_URETICI) if (d.getVendorId() == v) bilinen = true;
        if (!bilinen) return null;
        for (int i = 0; i < d.getInterfaceCount(); i++) {           // üreticiye özel sınıf + bulk giriş/çıkış
            UsbInterface f = d.getInterface(i);
            if (f.getInterfaceClass() != 0xFF) continue;
            boolean in = false, out = false;
            for (int k = 0; k < f.getEndpointCount(); k++) {
                UsbEndpoint e = f.getEndpoint(k);
                if (e.getType() != UsbConstants.USB_ENDPOINT_XFER_BULK) continue;
                if (e.getDirection() == UsbConstants.USB_DIR_IN) in = true; else out = true;
            }
            if (in && out) return f;
        }
        return null;
    }

    private final java.util.Set<String> izinIstenen = new java.util.HashSet<>();

    // ------------------------------------------------------------------------------------ istisnalar
    static class KartYok extends IOException { KartYok(String m) { super(m); } }
    static class ProtoHata extends IOException { ProtoHata(String m) { super(m); } }
    static class CcidHata extends IOException { int err; CcidHata(String m, int e) { super(m); err = e; } }

    // ------------------------------------------------------------------------------------ ATR
    static class AtrInfo {
        int proto = 0, ifsc = 32, bwiCwi = 0x4D;
        boolean crc = false;
        int tc1 = 0;

        AtrInfo(byte[] atr) {
            if (atr == null || atr.length < 2) return;
            int y = (atr[1] & 0xFF) >> 4, i = 2, n = 1;
            int[] ta = new int[16], tb = new int[16], tc = new int[16];
            Arrays.fill(ta, -1); Arrays.fill(tb, -1); Arrays.fill(tc, -1);
            int ilkProto = -1;
            while (i < atr.length && n < 15) {
                if ((y & 1) != 0 && i < atr.length) ta[n] = atr[i++] & 0xFF;
                if ((y & 2) != 0 && i < atr.length) tb[n] = atr[i++] & 0xFF;
                if ((y & 4) != 0 && i < atr.length) tc[n] = atr[i++] & 0xFF;
                if ((y & 8) != 0 && i < atr.length) {
                    int td = atr[i++] & 0xFF;
                    if (ilkProto < 0) ilkProto = td & 0x0F;
                    y = td >> 4;
                    n++;
                } else break;
            }
            proto = ilkProto < 0 ? 0 : ilkProto;
            for (int k = 3; k < 16; k++) if (ta[k] >= 0) { ifsc = ta[k]; break; }
            if (ifsc == 0 || ifsc == 0xFF) ifsc = 32;
            for (int k = 3; k < 16; k++) if (tb[k] >= 0) { bwiCwi = tb[k]; break; }
            for (int k = 3; k < 16; k++) if (tc[k] >= 0) { crc = (tc[k] & 1) != 0; break; }
            tc1 = tc[1] < 0 ? 0 : tc[1];
        }
    }

    // ------------------------------------------------------------------------------------ CCID okuyucu
    static class Okuyucu {
        final UsbDevice device;
        final UsbDeviceConnection conn;
        final UsbInterface ifc;
        UsbEndpoint epOut, epIn;
        int features = LEVEL_TPDU | 0x02, maxMsg = 271, maxIfsd = 254, voltage = 7;
        final int level;
        final String name;
        int seq = 0;
        boolean powered = false;
        byte[] atr = new byte[0];
        AtrInfo atrInfo;
        T1 t1;

        Okuyucu(UsbDevice d, UsbDeviceConnection c, UsbInterface f) {
            device = d; conn = c; ifc = f;
            for (int i = 0; i < f.getEndpointCount(); i++) {
                UsbEndpoint e = f.getEndpoint(i);
                if (e.getType() != UsbConstants.USB_ENDPOINT_XFER_BULK) continue;
                if (e.getDirection() == UsbConstants.USB_DIR_IN) epIn = e; else epOut = e;
            }
            sinifTanimlayicisi(c.getRawDescriptors(), f.getId());
            int lvl = features & 0x70000;
            level = lvl == 0 ? LEVEL_TPDU : lvl;
            String urun = d.getProductName() != null ? d.getProductName() : "USB CCID Reader";
            name = String.format("%s %04X:%04X", urun, d.getVendorId(), d.getProductId());
        }

        /** Yapılandırma tanımlayıcısında CCID sınıf tanımlayıcısını (0x21) okur. */
        private void sinifTanimlayicisi(byte[] raw, int ifaceNo) {
            if (raw == null) return;
            int i = 0;
            boolean bizim = false;
            while (i + 2 <= raw.length) {
                int ln = raw[i] & 0xFF, typ = raw[i + 1] & 0xFF;
                if (ln < 2 || i + ln > raw.length) break;
                if (typ == 4) bizim = (raw[i + 2] & 0xFF) == ifaceNo && (raw[i + 5] & 0xFF) == 0x0B;
                else if (typ == 0x21 && bizim && ln >= 54) {
                    voltage = raw[i + 5] & 0xFF;
                    maxIfsd = le32(raw, i + 28);
                    features = le32(raw, i + 40);
                    maxMsg = le32(raw, i + 44);
                    if (maxMsg <= 0) maxMsg = 271;
                    if (maxIfsd <= 0) maxIfsd = 254;
                    if (voltage == 0) voltage = 7;
                    return;
                }
                i += ln;
            }
        }

        private void send(int mtype, byte[] data, byte[] rfu3) throws IOException {
            seq = (seq + 1) & 0xFF;
            byte[] m = new byte[10 + data.length];
            m[0] = (byte) mtype;
            m[1] = (byte) data.length; m[2] = (byte) (data.length >> 8); m[3] = (byte) (data.length >> 16); m[4] = (byte) (data.length >> 24);
            m[5] = 0; m[6] = (byte) seq;
            m[7] = rfu3[0]; m[8] = rfu3[1]; m[9] = rfu3[2];
            System.arraycopy(data, 0, m, 10, data.length);
            int r = conn.bulkTransfer(epOut, m, m.length, 5000);
            if (r != m.length) throw new IOException("USB yazma hatası (" + r + ")");
            int mps = epOut.getMaxPacketSize();
            if (mps > 0 && m.length % mps == 0) conn.bulkTransfer(epOut, new byte[0], 0, 1000);   // ZLP
        }

        /** Cevap: [0]=mtype [1]=status [2]=error [3]=rfu  + veri (byte[][]{başlık, veri}). */
        private byte[][] recv(int timeoutMs) throws IOException {
            byte[] buf = new byte[Math.max(maxMsg, 271) + 16];
            long son = System.currentTimeMillis() + timeoutMs;
            while (true) {
                int kalan = (int) Math.max(1000, son - System.currentTimeMillis());
                int n = conn.bulkTransfer(epIn, buf, buf.length, Math.min(kalan, 60000));
                if (n < 0) {
                    if (System.currentTimeMillis() > son) throw new IOException("USB zaman aşımı");
                    continue;
                }
                if (n < 10) throw new IOException("CCID: kısa cevap (" + n + " bayt)");
                int ln = le32(buf, 1);
                int sq = buf[6] & 0xFF, st = buf[7] & 0xFF, err = buf[8] & 0xFF, rfu = buf[9] & 0xFF;
                ByteArrayOutputStream veri = new ByteArrayOutputStream();
                veri.write(buf, 10, Math.min(ln, n - 10));
                while (veri.size() < ln) {             // birden çok USB paketine bölünmüş
                    int k = conn.bulkTransfer(epIn, buf, buf.length, 5000);
                    if (k <= 0) throw new IOException("CCID: eksik cevap");
                    veri.write(buf, 0, Math.min(k, ln - veri.size()));
                }
                if (sq != seq) continue;               // eski mesaj
                if ((st >> 6) == 2) continue;          // zaman uzatımı: okuyucu çalışıyor
                return new byte[][]{new byte[]{buf[0], (byte) st, (byte) err, (byte) rfu}, veri.toByteArray()};
            }
        }

        private byte[][] cmd(int mtype, byte[] data, byte[] rfu3, int timeoutMs, boolean kartsizOlur) throws IOException {
            send(mtype, data, rfu3);
            byte[][] r = recv(timeoutMs);
            int st = r[0][1] & 0xFF;
            if ((st & 3) == 2 && !kartsizOlur) { powered = false; throw new KartYok("kart yok/çıkarıldı"); }
            if ((st >> 6) == 1) throw new CcidHata(String.format("CCID komut hatası (bError=0x%02X)", r[0][2] & 0xFF), r[0][2] & 0xFF);
            return r;
        }

        int slotStatus() throws IOException {
            byte[][] r = cmd(0x65, new byte[0], new byte[3], 5000, true);
            return r[0][1] & 3;
        }

        boolean cardPresent() throws IOException { return slotStatus() != 2; }

        void powerOff() {
            try { cmd(0x63, new byte[0], new byte[3], 5000, true); } catch (Exception ignored) { }
            powered = false;
            t1 = null;
        }

        byte[] powerOn() throws IOException {
            int[] voltajlar;
            if ((features & 0x08) != 0) voltajlar = new int[]{0};
            else {
                int[] tmp = new int[3]; int k = 0;
                if ((voltage & 1) != 0) tmp[k++] = 1;
                if ((voltage & 2) != 0) tmp[k++] = 2;
                if ((voltage & 4) != 0) tmp[k++] = 3;
                voltajlar = k == 0 ? new int[]{0} : Arrays.copyOf(tmp, k);
            }
            IOException son = null;
            boolean oldu = false;
            for (int v : voltajlar) {
                try {
                    atr = cmd(0x62, new byte[0], new byte[]{(byte) v, 0, 0}, 60000, false)[1];
                    oldu = true;
                    break;
                } catch (KartYok e) {
                    throw e;
                } catch (CcidHata e) {
                    son = e;
                }
            }
            if (!oldu) throw son != null ? son : new CcidHata("ATR alınamadı", 0);
            atrInfo = new AtrInfo(atr);
            powered = true;
            t1 = null;
            if (level == LEVEL_TPDU) {
                if (atrInfo.proto != 1) throw new ProtoHata("TPDU seviyeli okuyucuda T=0 kart desteklenmiyor");
                parametreAyarla();
                t1 = new T1(this, atrInfo);
                t1.setup();
            }
            return atr;
        }

        private void parametreAyarla() {
            if ((features & (0x02 | 0x40)) != 0) return;     // okuyucu parametreleri kendi ayarlıyor
            AtrInfo a = atrInfo;
            byte[] p = new byte[]{0x11, (byte) (0x10 | (a.crc ? 1 : 0)), (byte) (a.tc1 == 0xFF ? 0 : a.tc1),
                    (byte) a.bwiCwi, 0x00, (byte) Math.min(a.ifsc, 254), 0x00};
            try { cmd(0x61, p, new byte[]{1, 0, 0}, 5000, false); } catch (Exception e) { Log.w(TAG, "SetParameters reddedildi: " + e.getMessage()); }
        }

        byte[] connect() throws IOException {
            int st = slotStatus();
            if (st == 2) throw new KartYok("kart takılı değil");
            if (powered && st == 0) return atr;
            return powerOn();
        }

        byte[] xfrBlock(byte[] data, int bwi) throws IOException {
            return cmd(0x6F, data, new byte[]{(byte) bwi, 0, 0}, 60000, false)[1];
        }

        private byte[] xfrApdu(byte[] apdu) throws IOException {
            int maxd = maxMsg - 10;
            ByteArrayOutputStream sonuc = new ByteArrayOutputStream();
            int parca = (apdu.length + maxd - 1) / maxd;
            if (parca == 0) parca = 1;
            int zincir = 0;
            for (int idx = 0; idx < parca; idx++) {
                byte[] p = Arrays.copyOfRange(apdu, idx * maxd, Math.min(apdu.length, (idx + 1) * maxd));
                int lvl = parca == 1 ? 0 : idx == 0 ? 1 : idx == parca - 1 ? 2 : 3;
                byte[][] r = cmd(0x6F, p, new byte[]{0, (byte) lvl, (byte) (lvl >> 8)}, 60000, false);
                if (idx == parca - 1) { sonuc.write(r[1]); zincir = r[0][3] & 0xFF; }
            }
            while (zincir == 1 || zincir == 3 || zincir == 0x10) {
                byte[][] r = cmd(0x6F, new byte[0], new byte[]{0, 0x10, 0}, 60000, false);
                sonuc.write(r[1]);
                zincir = r[0][3] & 0xFF;
            }
            return sonuc.toByteArray();
        }

        byte[] transmit(byte[] apdu) throws IOException {
            if (!powered) throw new KartYok("kart aktif değil");
            if (level == LEVEL_TPDU) return t1.transmit(apdu);
            return xfrApdu(apdu);
        }
    }

    // ------------------------------------------------------------------------------------ T=1
    static class T1 {
        final Okuyucu r;
        final int ifsc;
        int ns = 0, cns = 0;

        T1(Okuyucu r, AtrInfo a) throws IOException {
            this.r = r;
            this.ifsc = Math.max(16, Math.min(Math.min(a.ifsc, 254), r.maxMsg - 14));
            if (a.crc) throw new ProtoHata("T=1 CRC (EDC) desteklenmiyor");
        }

        static int lrc(byte[] b, int n) { int x = 0; for (int i = 0; i < n; i++) x ^= b[i]; return x & 0xFF; }

        byte[] blok(int pcb, byte[] inf) {
            byte[] b = new byte[4 + inf.length];
            b[0] = 0; b[1] = (byte) pcb; b[2] = (byte) inf.length;
            System.arraycopy(inf, 0, b, 3, inf.length);
            b[b.length - 1] = (byte) lrc(b, b.length - 1);
            return b;
        }

        static int[] ayristir(byte[] raw) throws IOException {   // {pcb, inf uzunluğu}
            if (raw.length < 4 || raw.length != (raw[2] & 0xFF) + 4 || lrc(raw, raw.length - 1) != (raw[raw.length - 1] & 0xFF))
                throw new IOException("bozuk T=1 bloğu");
            return new int[]{raw[1] & 0xFF, raw[2] & 0xFF};
        }

        void setup() {
            ns = cns = 0;
            if ((r.features & 0x400) != 0) return;             // IFSD'yi okuyucu yapıyor
            int istenen = Math.min(254, r.maxIfsd);
            if (istenen > 32) {
                try { r.xfrBlock(blok(0xC1, new byte[]{(byte) istenen}), 0); } catch (Exception e) { Log.w(TAG, "IFSD pazarlığı atlandı"); }
            }
        }

        /** I ya da R bloğu döndürür: {tür(0=I,1=R), pcb} + veri. */
        Object[] gonderAl(byte[] blk) throws IOException {
            int hata = 0, bwi = 0;
            while (true) {
                byte[] raw;
                int[] pa;
                try {
                    raw = r.xfrBlock(blk, bwi);
                    pa = ayristir(raw);
                } catch (KartYok e) {
                    throw e;
                } catch (IOException e) {
                    if (++hata > 2) throw new IOException("T=1: cevap alınamadı");
                    blk = blok(0x81 | (cns << 4), new byte[0]);
                    bwi = 0;
                    continue;
                }
                int pcb = pa[0];
                byte[] inf = Arrays.copyOfRange(raw, 3, 3 + pa[1]);
                if ((pcb & 0x80) == 0) return new Object[]{0, pcb, inf};
                if ((pcb & 0xC0) == 0x80) return new Object[]{1, pcb, inf};
                if (pcb == 0xC3) { blk = blok(0xE3, inf); bwi = inf.length > 0 ? inf[0] & 0xFF : 1; continue; }  // WTX
                if (pcb == 0xC1) { blk = blok(0xE1, inf); bwi = 0; continue; }
                if (pcb == 0xC2) { blk = blok(0xE2, inf); bwi = 0; continue; }
                throw new IOException(String.format("beklenmeyen S-blok 0x%02X", pcb));
            }
        }

        byte[] transmit(byte[] apdu) throws IOException {
            int parca = Math.max(1, (apdu.length + ifsc - 1) / ifsc);
            Object[] son = null;
            for (int idx = 0; idx < parca; idx++) {
                boolean sonParca = idx == parca - 1;
                byte[] ch = Arrays.copyOfRange(apdu, idx * ifsc, Math.min(apdu.length, (idx + 1) * ifsc));
                byte[] blk = blok((ns << 6) | (sonParca ? 0 : 0x20), ch);
                for (int deneme = 0; ; deneme++) {
                    son = gonderAl(blk);
                    int tur = (Integer) son[0], pcb = (Integer) son[1];
                    if (sonParca) { if (tur == 0) break; }
                    else if (tur == 1 && (pcb & 0x0F) == 0 && ((pcb >> 4) & 1) == (ns ^ 1)) break;
                    if (deneme == 2) throw new IOException("T=1: blok kabul edilmedi");
                }
                ns ^= 1;
            }
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            while (true) {
                cns ^= 1;
                out.write((byte[]) son[2]);
                if (((Integer) son[1] & 0x20) == 0) return out.toByteArray();
                son = gonderAl(blok(0x80 | (cns << 4), new byte[0]));
                if ((Integer) son[0] != 0) throw new IOException("T=1: I blok bekleniyordu");
            }
        }
    }

    // ------------------------------------------------------------------------------------ yardımcılar
    static int le32(byte[] b, int o) {
        return (b[o] & 0xFF) | ((b[o + 1] & 0xFF) << 8) | ((b[o + 2] & 0xFF) << 16) | ((b[o + 3] & 0xFF) << 24);
    }

    static String hex(byte[] b) {
        StringBuilder sb = new StringBuilder(b.length * 2);
        for (byte x : b) sb.append(String.format("%02X", x & 0xFF));
        return sb.toString();
    }

    static byte[] unhex(String s) {
        s = s.trim();
        byte[] b = new byte[s.length() / 2];
        for (int i = 0; i < b.length; i++) b[i] = (byte) Integer.parseInt(s.substring(2 * i, 2 * i + 2), 16);
        return b;
    }
}
