package eimzawin;

import com.sun.jna.Library;
import com.sun.jna.Memory;
import com.sun.jna.Native;
import com.sun.jna.NativeLibrary;
import com.sun.jna.NativeLong;
import com.sun.jna.Platform;
import com.sun.jna.Pointer;
import com.sun.jna.WString;
import com.sun.jna.ptr.LongByReference;
import com.sun.jna.ptr.NativeLongByReference;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * PC/SC (winscard.dll / libpcsclite) için ince JNA katmanı.
 *
 * Neden: JDK'nın kendi javax.smartcardio sağlayıcısı (SunPCSC) Windows'ta ANSI işlevlerini (SCardListReadersA,
 * SCardConnectA) çağırır ve okuyucu adlarını UTF-8'miş gibi çevirir (NewStringUTF / GetStringUTFChars). Türkçe
 * Windows'ta adında "ı" geçen okuyucular (ör. "Microsoft Usbccid Akıllı Kart Okuyucusu (WUDF) 0" — ArkSigner)
 * bozulur ve bağlanılamaz. Burada Windows'ta Unicode (…W) işlevleri kullanılır; adlar UTF-16 olarak taşınır.
 * Linux'ta (pcsclite) adlar zaten UTF-8'dir: aynı katman test için de kullanılır.
 *
 * Türler: SCARDCONTEXT/SCARDHANDLE 64 bit sistemlerde işaretçi boyutundadır (long); DWORD Windows'ta 32 bit,
 * pcsclite'ta (unsigned long) 64 bittir → ikisi de NativeLong ile doğru taşınır (Windows LLP64, Linux LP64).
 */
final class Pcsc {
    static final boolean WIN = Platform.isWindows();

    static final int SCARD_SCOPE_USER = 0;
    static final int SCARD_SHARE_SHARED = 2, SCARD_SHARE_DIRECT = 3;
    static final int SCARD_PROTOCOL_T0 = 1, SCARD_PROTOCOL_T1 = 2;
    static final int SCARD_LEAVE_CARD = 0, SCARD_RESET_CARD = 1;
    static final int SCARD_STATE_UNAWARE = 0, SCARD_STATE_CHANGED = 0x2, SCARD_STATE_PRESENT = 0x20;
    static final int ATR_LEN = WIN ? 36 : 33;

    interface Win extends Library {
        NativeLong SCardEstablishContext(NativeLong scope, Pointer r1, Pointer r2, LongByReference ctx);
        NativeLong SCardReleaseContext(long ctx);
        NativeLong SCardListReadersW(long ctx, WString groups, char[] readers, NativeLongByReference len);
        NativeLong SCardConnectW(long ctx, WString reader, NativeLong share, NativeLong proto, LongByReference card, NativeLongByReference active);
        NativeLong SCardGetStatusChangeW(long ctx, NativeLong timeout, Pointer states, NativeLong count);
        NativeLong SCardDisconnect(long card, NativeLong disposition);
        NativeLong SCardTransmit(long card, Pointer sendPci, byte[] send, NativeLong sendLen, Pointer recvPci, byte[] recv, NativeLongByReference recvLen);
        NativeLong SCardStatusW(long card, char[] names, NativeLongByReference namesLen, NativeLongByReference state, NativeLongByReference proto, byte[] atr, NativeLongByReference atrLen);
        NativeLong SCardBeginTransaction(long card);
        NativeLong SCardEndTransaction(long card, NativeLong disposition);
        NativeLong SCardControl(long card, NativeLong code, byte[] in, NativeLong inLen, byte[] out, NativeLong outLen, NativeLongByReference ret);
    }

    interface Lite extends Library {
        NativeLong SCardEstablishContext(NativeLong scope, Pointer r1, Pointer r2, LongByReference ctx);
        NativeLong SCardReleaseContext(long ctx);
        NativeLong SCardListReaders(long ctx, String groups, byte[] readers, NativeLongByReference len);
        NativeLong SCardConnect(long ctx, byte[] reader, NativeLong share, NativeLong proto, LongByReference card, NativeLongByReference active);
        NativeLong SCardGetStatusChange(long ctx, NativeLong timeout, Pointer states, NativeLong count);
        NativeLong SCardDisconnect(long card, NativeLong disposition);
        NativeLong SCardTransmit(long card, Pointer sendPci, byte[] send, NativeLong sendLen, Pointer recvPci, byte[] recv, NativeLongByReference recvLen);
        NativeLong SCardStatus(long card, byte[] names, NativeLongByReference namesLen, NativeLongByReference state, NativeLongByReference proto, byte[] atr, NativeLongByReference atrLen);
        NativeLong SCardBeginTransaction(long card);
        NativeLong SCardEndTransaction(long card, NativeLong disposition);
        NativeLong SCardControl(long card, NativeLong code, byte[] in, NativeLong inLen, byte[] out, NativeLong outLen, NativeLongByReference ret);
    }

    private static final String KUTUPHANE = WIN ? "winscard" : "pcsclite";
    private static Win win;
    private static Lite lite;
    private static Pointer t0Pci, t1Pci;

    static synchronized void yukle() {
        if (win != null || lite != null) return;
        NativeLibrary nl = NativeLibrary.getInstance(KUTUPHANE);
        if (WIN) win = Native.load(KUTUPHANE, Win.class);
        else lite = Native.load(KUTUPHANE, Lite.class);
        t0Pci = nl.getGlobalVariableAddress("g_rgSCardT0Pci");
        t1Pci = nl.getGlobalVariableAddress("g_rgSCardT1Pci");
    }

    static NativeLong nl(long v) { return new NativeLong(v); }

    static void kontrol(NativeLong rv, String islem) throws PcscHata {
        long r = rv.longValue() & 0xFFFFFFFFL;
        if (r != 0) throw new PcscHata(r, islem);
    }

    static long baglamAc() throws PcscHata {
        yukle();
        LongByReference c = new LongByReference();
        kontrol(WIN ? win.SCardEstablishContext(nl(SCARD_SCOPE_USER), null, null, c)
                : lite.SCardEstablishContext(nl(SCARD_SCOPE_USER), null, null, c), "SCardEstablishContext");
        return c.getValue();
    }

    static void baglamKapat(long ctx) {
        try { if (WIN) win.SCardReleaseContext(ctx); else lite.SCardReleaseContext(ctx); } catch (Throwable ignored) { }
    }

    /** Okuyucu adları (Unicode, doğru). Okuyucu yoksa boş liste. */
    static List<String> okuyucular(long ctx) throws PcscHata {
        NativeLongByReference len = new NativeLongByReference();
        List<String> out = new ArrayList<>();
        NativeLong rv = WIN ? win.SCardListReadersW(ctx, null, null, len) : lite.SCardListReaders(ctx, null, null, len);
        long r = rv.longValue() & 0xFFFFFFFFL;
        if (r == PcscHata.SCARD_E_NO_READERS_AVAILABLE) return out;
        kontrol(rv, "SCardListReaders");
        int n = (int) len.getValue().longValue();
        if (n <= 0) return out;
        String hepsi;
        if (WIN) {
            char[] b = new char[n];
            rv = win.SCardListReadersW(ctx, null, b, len);
            if ((rv.longValue() & 0xFFFFFFFFL) == PcscHata.SCARD_E_NO_READERS_AVAILABLE) return out;
            kontrol(rv, "SCardListReaders");
            hepsi = new String(b, 0, Math.min(b.length, (int) len.getValue().longValue()));
        } else {
            byte[] b = new byte[n];
            rv = lite.SCardListReaders(ctx, null, b, len);
            if ((rv.longValue() & 0xFFFFFFFFL) == PcscHata.SCARD_E_NO_READERS_AVAILABLE) return out;
            kontrol(rv, "SCardListReaders");
            hepsi = new String(b, 0, Math.min(b.length, (int) len.getValue().longValue()), StandardCharsets.UTF_8);
        }
        for (String s : hepsi.split("\u0000")) if (!s.isEmpty()) out.add(s);
        return out;
    }

    private static byte[] c(String s) {
        byte[] u = s.getBytes(StandardCharsets.UTF_8);
        byte[] b = new byte[u.length + 1];
        System.arraycopy(u, 0, b, 0, u.length);
        return b;
    }

    /** {kart tutamacı, etkin protokol} */
    static long[] baglan(long ctx, String okuyucu, int paylasim, int protokol) throws PcscHata {
        LongByReference h = new LongByReference();
        NativeLongByReference p = new NativeLongByReference();
        kontrol(WIN ? win.SCardConnectW(ctx, new WString(okuyucu), nl(paylasim), nl(protokol), h, p)
                : lite.SCardConnect(ctx, c(okuyucu), nl(paylasim), nl(protokol), h, p), "SCardConnect");
        return new long[]{h.getValue(), p.getValue().longValue()};
    }

    static void ayril(long kart, int eylem) throws PcscHata {
        kontrol(WIN ? win.SCardDisconnect(kart, nl(eylem)) : lite.SCardDisconnect(kart, nl(eylem)), "SCardDisconnect");
    }

    /** SCARD_READERSTATE: {szReader, pvUserData, dwCurrentState, dwEventState, cbAtr, rgbAtr[ATR_LEN]} */
    private static final int PTR = Native.POINTER_SIZE, DW = NativeLong.SIZE;
    private static final int OFS_CUR = 2 * PTR, OFS_EVT = OFS_CUR + DW, OFS_CBATR = OFS_EVT + DW, OFS_ATR = OFS_CBATR + DW;
    private static final int DURUM_BOYU;
    static {
        int ham = OFS_ATR + ATR_LEN;
        int hiza = Math.max(PTR, DW);
        DURUM_BOYU = (ham + hiza - 1) / hiza * hiza;
    }

    private static void dwYaz(Memory m, long ofs, long v) {
        if (DW == 8) m.setLong(ofs, v); else m.setInt(ofs, (int) v);
    }

    private static long dwOku(Memory m, long ofs) {
        return DW == 8 ? m.getLong(ofs) : (m.getInt(ofs) & 0xFFFFFFFFL);
    }

    /** Okuyucunun olay durumu (SCARD_STATE_*); zaman aşımında mevcut durum ile döner. {olayDurumu, değişti mi} */
    static long[] durum(long ctx, String okuyucu, long mevcut, long zamanAsimiMs) throws PcscHata {
        Memory ad;
        if (WIN) {
            char[] ch = (okuyucu + "\u0000").toCharArray();
            ad = new Memory(ch.length * 2L);
            ad.write(0, ch, 0, ch.length);
        } else {
            byte[] b = c(okuyucu);
            ad = new Memory(b.length);
            ad.write(0, b, 0, b.length);
        }
        Memory st = new Memory(DURUM_BOYU);
        st.clear();
        st.setPointer(0, ad);
        dwYaz(st, OFS_CUR, mevcut);
        NativeLong rv = WIN ? win.SCardGetStatusChangeW(ctx, nl(zamanAsimiMs), st, nl(1))
                : lite.SCardGetStatusChange(ctx, nl(zamanAsimiMs), st, nl(1));
        long r = rv.longValue() & 0xFFFFFFFFL;
        if (r == PcscHata.SCARD_E_TIMEOUT) return new long[]{mevcut, 0};
        kontrol(rv, "SCardGetStatusChange");
        long olay = dwOku(st, OFS_EVT);
        return new long[]{olay, (olay & SCARD_STATE_CHANGED) != 0 ? 1 : 0};
    }

    static byte[] gonder(long kart, int protokol, byte[] apdu, int n) throws PcscHata {
        Pointer pci = protokol == SCARD_PROTOCOL_T0 ? t0Pci : t1Pci;
        byte[] cevap = new byte[65536 + 2];
        NativeLongByReference len = new NativeLongByReference(nl(cevap.length));
        byte[] gonderilen = n == apdu.length ? apdu : java.util.Arrays.copyOf(apdu, n);
        kontrol(WIN ? win.SCardTransmit(kart, pci, gonderilen, nl(n), null, cevap, len)
                : lite.SCardTransmit(kart, pci, gonderilen, nl(n), null, cevap, len), "SCardTransmit");
        return java.util.Arrays.copyOf(cevap, (int) len.getValue().longValue());
    }

    /** {ATR, protokol} */
    static Object[] kartDurumu(long kart) throws PcscHata {
        NativeLongByReference adLen = new NativeLongByReference(nl(0));
        NativeLongByReference st = new NativeLongByReference(), pr = new NativeLongByReference();
        byte[] atr = new byte[ATR_LEN];
        NativeLongByReference atrLen = new NativeLongByReference(nl(atr.length));
        if (WIN) {
            char[] ad = new char[1024];
            adLen.setValue(nl(ad.length));
            kontrol(win.SCardStatusW(kart, ad, adLen, st, pr, atr, atrLen), "SCardStatus");
        } else {
            byte[] ad = new byte[1024];
            adLen.setValue(nl(ad.length));
            kontrol(lite.SCardStatus(kart, ad, adLen, st, pr, atr, atrLen), "SCardStatus");
        }
        return new Object[]{java.util.Arrays.copyOf(atr, (int) atrLen.getValue().longValue()), (int) pr.getValue().longValue()};
    }

    static void islemBasla(long kart) throws PcscHata {
        kontrol(WIN ? win.SCardBeginTransaction(kart) : lite.SCardBeginTransaction(kart), "SCardBeginTransaction");
    }

    static void islemBitir(long kart) throws PcscHata {
        kontrol(WIN ? win.SCardEndTransaction(kart, nl(SCARD_LEAVE_CARD)) : lite.SCardEndTransaction(kart, nl(SCARD_LEAVE_CARD)), "SCardEndTransaction");
    }

    static byte[] denetim(long kart, int kod, byte[] veri) throws PcscHata {
        byte[] out = new byte[8192];
        NativeLongByReference ret = new NativeLongByReference();
        kontrol(WIN ? win.SCardControl(kart, nl(kod), veri, nl(veri.length), out, nl(out.length), ret)
                : lite.SCardControl(kart, nl(kod), veri, nl(veri.length), out, nl(out.length), ret), "SCardControl");
        return java.util.Arrays.copyOf(out, (int) ret.getValue().longValue());
    }

    private Pcsc() { }
}
