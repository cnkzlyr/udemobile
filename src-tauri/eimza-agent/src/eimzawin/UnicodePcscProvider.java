package eimzawin;

import javax.smartcardio.ATR;
import javax.smartcardio.Card;
import javax.smartcardio.CardChannel;
import javax.smartcardio.CardException;
import javax.smartcardio.CardNotPresentException;
import javax.smartcardio.CardTerminal;
import javax.smartcardio.CardTerminals;
import javax.smartcardio.CommandAPDU;
import javax.smartcardio.ResponseAPDU;
import javax.smartcardio.TerminalFactorySpi;
import java.nio.ByteBuffer;
import java.security.Provider;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * "UnicodePCSC" TerminalFactory: JDK'nın SunPCSC sağlayıcısının davranışını (T=0 GET RESPONSE / 6Cxx yeniden gönderim,
 * PCSCException metinleri, kart durum olayları) birebir izler; tek farkı okuyucu adlarını Unicode taşımasıdır.
 * Windows'ta adında Türkçe karakter olan okuyucular (ArkSigner: "Microsoft Usbccid Akıllı Kart Okuyucusu (WUDF) 0")
 * SunPCSC ile hiç açılamıyordu; bu sağlayıcıyla açılır.
 */
public final class UnicodePcscProvider extends Provider {
    private static final long serialVersionUID = 1L;
    public static final String TYPE = "UnicodePCSC";

    public UnicodePcscProvider() {
        super("UnicodePCSCProvider", "1.0", "PC/SC (Unicode okuyucu adlari) - CanEditor");
        put("TerminalFactory." + TYPE, "eimzawin.UnicodePcscProvider$Factory");
    }

    static CardException hata(PcscHata e) { return new CardException(e.toString(), e); }

    public static final class Factory extends TerminalFactorySpi {
        private final long ctx;

        public Factory(Object params) throws PcscHata { ctx = Pcsc.baglamAc(); }

        @Override protected CardTerminals engineTerminals() { return new Terminals(ctx); }
    }

    // ------------------------------------------------------------------------------------ okuyucular
    static final class Terminals extends CardTerminals {
        private final long ctx;
        private final Map<String, Term> terimler = new HashMap<>();
        private final Map<String, Long> sonDurum = new HashMap<>();   // okuyucu → son bilinen SCARD_STATE_*

        Terminals(long ctx) { this.ctx = ctx; }

        private synchronized Term terim(String ad) {
            Term t = terimler.get(ad);
            if (t == null) { t = new Term(ctx, ad); terimler.put(ad, t); }
            return t;
        }

        @Override public synchronized List<CardTerminal> list(State state) throws CardException {
            if (state == null) throw new NullPointerException();
            List<String> adlar;
            try { adlar = Pcsc.okuyucular(ctx); } catch (PcscHata e) { throw hata(e); }
            List<CardTerminal> out = new ArrayList<>();
            for (String ad : adlar) {
                boolean var;
                Long once = sonDurum.get(ad);
                long simdi;
                try { simdi = Pcsc.durum(ctx, ad, Pcsc.SCARD_STATE_UNAWARE, 0)[0]; } catch (PcscHata e) { continue; }
                var = (simdi & Pcsc.SCARD_STATE_PRESENT) != 0;
                boolean onceVar = once != null && (once & Pcsc.SCARD_STATE_PRESENT) != 0;
                boolean al;
                switch (state) {
                    case ALL: al = true; break;
                    case CARD_PRESENT: al = var; break;
                    case CARD_ABSENT: al = !var; break;
                    case CARD_INSERTION: al = var && !onceVar; sonDurum.put(ad, simdi); break;
                    case CARD_REMOVAL: al = !var && onceVar; sonDurum.put(ad, simdi); break;
                    default: al = false;
                }
                if (al) out.add(terim(ad));
            }
            return Collections.unmodifiableList(out);
        }

        @Override public boolean waitForChange(long timeout) throws CardException {
            if (timeout < 0) throw new IllegalArgumentException("timeout < 0");
            long son = timeout == 0 ? Long.MAX_VALUE : System.currentTimeMillis() + timeout;
            Map<String, Boolean> ilk = durumlar();
            synchronized (this) {
                if (sonDurum.isEmpty()) for (Map.Entry<String, Boolean> e : ilk.entrySet())
                    sonDurum.put(e.getKey(), e.getValue() ? (long) Pcsc.SCARD_STATE_PRESENT : 0L);
            }
            while (true) {
                Map<String, Boolean> simdi = durumlar();
                if (!simdi.equals(ilk)) return true;
                if (System.currentTimeMillis() >= son) return false;
                try { Thread.sleep(300); } catch (InterruptedException e) { Thread.currentThread().interrupt(); return false; }
            }
        }

        private Map<String, Boolean> durumlar() throws CardException {
            Map<String, Boolean> m = new HashMap<>();
            try {
                for (String ad : Pcsc.okuyucular(ctx)) {
                    try { m.put(ad, (Pcsc.durum(ctx, ad, Pcsc.SCARD_STATE_UNAWARE, 0)[0] & Pcsc.SCARD_STATE_PRESENT) != 0); }
                    catch (PcscHata ignored) { }
                }
            } catch (PcscHata e) { throw hata(e); }
            return m;
        }

        @Override public CardTerminal getTerminal(String name) {
            if (name == null) throw new NullPointerException();
            try {
                for (String ad : Pcsc.okuyucular(ctx)) if (ad.equals(name)) return terim(ad);
            } catch (PcscHata ignored) { }
            return null;
        }
    }

    // ------------------------------------------------------------------------------------ okuyucu
    static final class Term extends CardTerminal {
        private final long ctx;
        private final String ad;
        private Crd kart;

        Term(long ctx, String ad) { this.ctx = ctx; this.ad = ad; }

        @Override public String getName() { return ad; }

        @Override public synchronized Card connect(String protocol) throws CardException {
            if (protocol == null) throw new NullPointerException();
            if (kart != null && kart.acik()) {
                if (kart.istenen.equals(protocol) || "*".equals(protocol)) return kart;
                throw new CardException("Kart başka bir protokolle bağlı: " + kart.getProtocol());
            }
            int paylasim = Pcsc.SCARD_SHARE_SHARED, proto;
            switch (protocol) {
                case "*": proto = Pcsc.SCARD_PROTOCOL_T0 | Pcsc.SCARD_PROTOCOL_T1; break;
                case "T=0": proto = Pcsc.SCARD_PROTOCOL_T0; break;
                case "T=1": proto = Pcsc.SCARD_PROTOCOL_T1; break;
                case "DIRECT": proto = 0; paylasim = Pcsc.SCARD_SHARE_DIRECT; break;
                default: throw new IllegalArgumentException("Desteklenmeyen protokol " + protocol);
            }
            try {
                long[] r = Pcsc.baglan(ctx, ad, paylasim, proto);
                byte[] atr = new byte[0];
                int etkin = (int) r[1];
                try { Object[] d = Pcsc.kartDurumu(r[0]); atr = (byte[]) d[0]; if (etkin == 0) etkin = (Integer) d[1]; } catch (PcscHata ignored) { }
                kart = new Crd(r[0], etkin, new ATR(atr), protocol);
                return kart;
            } catch (PcscHata e) {
                if (e.kod == PcscHata.SCARD_E_NO_SMARTCARD || e.kod == PcscHata.SCARD_W_REMOVED_CARD)
                    throw new CardNotPresentException("Kart yok: " + ad, e);
                throw hata(e);
            }
        }

        @Override public boolean isCardPresent() throws CardException {
            try { return (Pcsc.durum(ctx, ad, Pcsc.SCARD_STATE_UNAWARE, 0)[0] & Pcsc.SCARD_STATE_PRESENT) != 0; }
            catch (PcscHata e) { throw hata(e); }
        }

        private boolean bekle(boolean var, long timeout) throws CardException {
            if (timeout < 0) throw new IllegalArgumentException("timeout < 0");
            long son = timeout == 0 ? Long.MAX_VALUE : System.currentTimeMillis() + timeout;
            while (true) {
                if (isCardPresent() == var) return true;
                if (System.currentTimeMillis() >= son) return false;
                try { Thread.sleep(250); } catch (InterruptedException e) { Thread.currentThread().interrupt(); return false; }
            }
        }

        @Override public boolean waitForCardPresent(long timeout) throws CardException { return bekle(true, timeout); }
        @Override public boolean waitForCardAbsent(long timeout) throws CardException { return bekle(false, timeout); }
        @Override public String toString() { return "PC/SC terminal " + ad; }
    }

    // ------------------------------------------------------------------------------------ kart
    static final class Crd extends Card {
        final long h;
        final int proto;
        final ATR atr;
        final String istenen;
        private volatile boolean kapali;
        private final Chan temel = new Chan(this);

        Crd(long h, int proto, ATR atr, String istenen) { this.h = h; this.proto = proto; this.atr = atr; this.istenen = istenen; }

        boolean acik() { return !kapali; }

        void denetle() { if (kapali) throw new IllegalStateException("Card has been disconnected"); }

        @Override public ATR getATR() { return atr; }
        @Override public String getProtocol() { return proto == Pcsc.SCARD_PROTOCOL_T0 ? "T=0" : proto == Pcsc.SCARD_PROTOCOL_T1 ? "T=1" : "DIRECT"; }
        @Override public CardChannel getBasicChannel() { denetle(); return temel; }
        @Override public CardChannel openLogicalChannel() throws CardException {
            denetle();
            // MANAGE CHANNEL OPEN
            byte[] r = temel.ham(new byte[]{0x00, 0x70, 0x00, 0x00, 0x01});
            if (r.length != 3 || r[1] != (byte) 0x90 || r[2] != 0) throw new CardException("openLogicalChannel() başarısız");
            return new Chan(this, r[0]);
        }
        @Override public void beginExclusive() throws CardException {
            denetle();
            try { Pcsc.islemBasla(h); } catch (PcscHata e) { throw hata(e); }
        }
        @Override public void endExclusive() throws CardException {
            denetle();
            try { Pcsc.islemBitir(h); } catch (PcscHata e) { throw hata(e); }
        }
        @Override public byte[] transmitControlCommand(int code, byte[] cmd) throws CardException {
            denetle();
            try { return Pcsc.denetim(h, code, cmd); } catch (PcscHata e) { throw hata(e); }
        }
        @Override public void disconnect(boolean reset) throws CardException {
            if (kapali) return;
            kapali = true;
            try { Pcsc.ayril(h, reset ? Pcsc.SCARD_RESET_CARD : Pcsc.SCARD_LEAVE_CARD); } catch (PcscHata e) { throw hata(e); }
        }
        @Override public String toString() { return "PC/SC card in " + getProtocol() + ", ATR " + atr.getBytes().length + " bytes"; }
    }

    // ------------------------------------------------------------------------------------ kanal
    static final class Chan extends CardChannel {
        private final Crd kart;
        private final int no;

        Chan(Crd kart) { this(kart, 0); }
        Chan(Crd kart, int no) { this.kart = kart; this.no = no; }

        @Override public Card getCard() { return kart; }
        @Override public int getChannelNumber() { return no; }

        /** Kanal numarasını CLA'ya işler (ISO 7816-4; 0-3 temel, 4-19 genişletilmiş). */
        private void kanalAyarla(byte[] c) {
            if (no == 0 || c.length == 0) return;
            int cla = c[0] & 0xFF;
            if ((cla & 0x80) != 0) return;
            if (no <= 3) c[0] = (byte) ((cla & 0xBC) | no);
            else c[0] = (byte) ((cla & 0xB0) | 0x40 | (no - 4));
        }

        /** JDK ChannelImpl.doTransmit ile aynı: T=0'da Le kırpma, 6Cxx'te Le ile yeniden gönderim, 61xx'te GET RESPONSE. */
        byte[] ham(byte[] komut0) throws CardException {
            kart.denetle();
            byte[] komut = komut0.clone();
            kanalAyarla(komut);
            int n = komut.length;
            boolean t0 = kart.proto == Pcsc.SCARD_PROTOCOL_T0;
            if (t0 && n >= 7 && komut[4] == 0) throw new CardException("Extended length forms not supported for T=0");
            if (t0 && n >= 7) {
                int lc = komut[4] & 0xFF;
                if (lc != 0 && n == lc + 6) n--;
            }
            byte[] sonuc = new byte[0];
            for (int k = 1; ; k++) {
                if (k > 256) throw new CardException("Number of response iterations exceeded maximum 256");
                byte[] r;
                try { r = Pcsc.gonder(kart.h, kart.proto, komut, n); } catch (PcscHata e) { throw hata(e); }
                int rn = r.length;
                if (rn >= 2 && n >= 1) {
                    if (rn == 2 && r[0] == 0x6C) { komut[n - 1] = r[1]; continue; }
                    if (r[rn - 2] == 0x61) {
                        if (rn > 2) sonuc = birlestir(sonuc, r, rn - 2);
                        if (komut.length < 5) { byte cla = komut[0]; komut = new byte[5]; komut[0] = cla; }
                        komut[1] = (byte) 0xC0; komut[2] = 0; komut[3] = 0; komut[4] = r[rn - 1];
                        n = 5;
                        continue;
                    }
                }
                return birlestir(sonuc, r, rn);
            }
        }

        private static byte[] birlestir(byte[] a, byte[] b, int bn) {
            byte[] c = new byte[a.length + bn];
            System.arraycopy(a, 0, c, 0, a.length);
            System.arraycopy(b, 0, c, a.length, bn);
            return c;
        }

        @Override public ResponseAPDU transmit(CommandAPDU command) throws CardException {
            return new ResponseAPDU(ham(command.getBytes()));
        }

        @Override public int transmit(ByteBuffer command, ByteBuffer response) throws CardException {
            byte[] c = new byte[command.remaining()];
            command.get(c);
            byte[] r = ham(c);
            if (response.remaining() < r.length) throw new IllegalStateException("Yanıt arabelleği yetersiz");
            response.put(r);
            return r.length;
        }

        @Override public void close() throws CardException {
            if (no == 0) throw new IllegalStateException("Cannot close basic logical channel");
            ham(new byte[]{0x00, 0x70, (byte) 0x80, (byte) no});
        }
    }
}
