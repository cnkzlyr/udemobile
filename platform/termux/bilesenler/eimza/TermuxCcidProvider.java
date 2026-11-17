// CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
// CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
// CKZ-MUHUR/1 MUHURSUZ
package eimza;

import javax.smartcardio.ATR;
import javax.smartcardio.Card;
import javax.smartcardio.CardChannel;
import javax.smartcardio.CardException;
import javax.smartcardio.CardTerminal;
import javax.smartcardio.CardTerminals;
import javax.smartcardio.CommandAPDU;
import javax.smartcardio.ResponseAPDU;
import javax.smartcardio.TerminalFactorySpi;
import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.Provider;
import java.util.Collections;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * javax.smartcardio icin "TermuxCCID" TerminalFactory saglayicisi.
 * Rootsuz Android/Termux'ta USB okuyucuya dogrudan erisilemedigi icin, okuyucuyla
 * ccid_bridge.py (termux-usb + libusb) konusur; bu sinif ona 127.0.0.1 uzerinden baglanir.
 *
 * Kullanim (JVM baslarken, UYAP kodu TerminalFactory'ye dokunmadan ONCE):
 *   System.setProperty("eimza.dir", "/data/data/com.termux/files/home/.eimza");
 *   Security.addProvider(new eimza.TermuxCcidProvider());
 *   System.setProperty("javax.smartcardio.TerminalFactory.DefaultType", "TermuxCCID");
 */
public final class TermuxCcidProvider extends Provider {
    private static final long serialVersionUID = 1L;
    public static final String TYPE = "TermuxCCID";

    public TermuxCcidProvider() {
        super("TermuxCCIDProvider", "1.0", "Termux USB CCID koprusu");
        put("TerminalFactory." + TYPE, "eimza.TermuxCcidProvider$Factory");
    }

    public static final class Factory extends TerminalFactorySpi {
        public Factory(Object params) { }
        @Override protected CardTerminals engineTerminals() { return new Terminals(); }
    }

    // ------------------------------------------------------------------ PC/SC benzeri hata
    /** UYAP/ESYA kodu hata metinlerini "sun.security.smartcardio.PCSCException: SCARD_..." diye eslestiriyor. */
    static final class PcscLike extends IOException {
        private static final long serialVersionUID = 1L;
        private final String code;
        PcscLike(String code) { super(code); this.code = code; }
        @Override public String toString() { return "sun.security.smartcardio.PCSCException: " + code; }
    }

    static CardException pcsc(String code) { return new CardException(new PcscLike(code)); }

    // ------------------------------------------------------------------ kopruye baglanti
    static final class Link {
        private final File dir;
        private Socket sock;
        private BufferedReader in;
        private OutputStream out;

        Link(File dir) { this.dir = dir; }

        private void closeQuiet() {
            try { if (sock != null) sock.close(); } catch (IOException ignored) { }
            sock = null; in = null; out = null;
        }

        private boolean open() {
            closeQuiet();
            try {
                File f = new File(dir, "bridge.json");
                if (!f.isFile()) return false;
                String js = new String(Files.readAllBytes(f.toPath()), StandardCharsets.UTF_8);
                Matcher mp = Pattern.compile("\"port\"\\s*:\\s*(\\d+)").matcher(js);
                Matcher mt = Pattern.compile("\"token\"\\s*:\\s*\"([0-9a-fA-F]+)\"").matcher(js);
                if (!mp.find() || !mt.find()) return false;
                Socket s = new Socket();
                s.connect(new InetSocketAddress(InetAddress.getByName("127.0.0.1"), Integer.parseInt(mp.group(1))), 1500);
                s.setTcpNoDelay(true);
                sock = s;
                in = new BufferedReader(new InputStreamReader(s.getInputStream(), StandardCharsets.UTF_8));
                out = s.getOutputStream();
                out.write(("AUTH " + mt.group(1) + "\n").getBytes(StandardCharsets.UTF_8));
                out.flush();
                String r = in.readLine();
                if (r == null || !r.startsWith("OK")) { closeQuiet(); return false; }
                return true;
            } catch (IOException | RuntimeException e) {
                closeQuiet();
                return false;
            }
        }

        /** Kopruye bir komut yollar; "OK ..." ise geri kalan metni, yoksa CardException dondurur. */
        synchronized String call(String line) throws CardException {
            for (int attempt = 0; attempt < 2; attempt++) {
                if (sock == null && !open()) throw pcsc("SCARD_E_READER_UNAVAILABLE");
                try {
                    out.write((line + "\n").getBytes(StandardCharsets.UTF_8));
                    out.flush();
                    String r = in.readLine();
                    if (r == null) throw new IOException("baglanti kapandi");
                    if (r.startsWith("OK")) return r.length() > 3 ? r.substring(3) : "";
                    String[] p = r.split(" ", 3);
                    String code = p.length > 1 ? p[1] : "";
                    if (code.equals("REMOVED")) throw pcsc("SCARD_W_REMOVED_CARD");
                    if (code.equals("NO_CARD")) throw pcsc("SCARD_E_NO_SMARTCARD");
                    if (code.equals("PROTO")) throw pcsc("SCARD_E_PROTO_MISMATCH");
                    throw new CardException("kopru hatasi: " + r);
                } catch (IOException e) {
                    closeQuiet();       // koprü yeniden baslamis olabilir: bir kez daha dene
                    if (attempt == 1) throw pcsc("SCARD_E_READER_UNAVAILABLE");
                }
            }
            throw pcsc("SCARD_E_READER_UNAVAILABLE");
        }

        /** Kopru calisiyorsa okuyucu adi, degilse null. */
        synchronized String readerName() {
            try { return call("INFO"); } catch (CardException e) { return null; }
        }
    }

    private static volatile Link LINK;

    static Link link() {
        Link l = LINK;
        if (l == null) {
            synchronized (TermuxCcidProvider.class) {
                if (LINK == null) {
                    String d = System.getProperty("eimza.dir");
                    if (d == null || d.isEmpty()) d = System.getProperty("user.home") + File.separator + ".eimza";
                    LINK = new Link(new File(d));
                }
                l = LINK;
            }
        }
        return l;
    }

    // ------------------------------------------------------------------ javax.smartcardio nesneleri
    static String hex(byte[] b) {
        StringBuilder sb = new StringBuilder(b.length * 2);
        for (byte x : b) { sb.append(Character.forDigit((x >> 4) & 15, 16)).append(Character.forDigit(x & 15, 16)); }
        return sb.toString().toUpperCase();
    }

    static byte[] unhex(String s) {
        int n = s.length() / 2;
        byte[] b = new byte[n];
        for (int i = 0; i < n; i++) b[i] = (byte) Integer.parseInt(s.substring(2 * i, 2 * i + 2), 16);
        return b;
    }

    static final class Terminals extends CardTerminals {
        private Term term;
        private boolean lastPresent;

        private synchronized Term current() {
            String name = link().readerName();
            if (name == null) { term = null; return null; }
            if (term == null || !term.getName().equals(name)) { term = new Term(name); lastPresent = false; }
            return term;
        }

        @Override public synchronized List<CardTerminal> list(State state) throws CardException {
            if (state == null) throw new NullPointerException();
            Term t = current();
            if (t == null) return Collections.<CardTerminal>emptyList();
            boolean present = t.isCardPresent();
            boolean was = lastPresent;
            boolean hit;
            switch (state) {
                case ALL: hit = true; lastPresent = present; break;
                case CARD_PRESENT: hit = present; lastPresent = present; break;
                case CARD_ABSENT: hit = !present; lastPresent = present; break;
                case CARD_INSERTION: hit = present && !was; lastPresent = present; break;
                case CARD_REMOVAL: hit = !present && was; lastPresent = present; break;
                default: hit = false;
            }
            return hit ? Collections.<CardTerminal>singletonList(t) : Collections.<CardTerminal>emptyList();
        }

        @Override public boolean waitForChange(long timeout) throws CardException {
            long end = timeout > 0 ? System.currentTimeMillis() + timeout : Long.MAX_VALUE;
            Term t = current();
            boolean initial = t != null && t.isCardPresent();
            while (true) {
                try { Thread.sleep(300); } catch (InterruptedException e) { Thread.currentThread().interrupt(); return false; }
                Term n = current();
                boolean now = n != null && n.isCardPresent();
                if (now != initial) { synchronized (this) { lastPresent = initial; } return true; }
                if (System.currentTimeMillis() >= end) return false;
            }
        }
    }

    static final class Term extends CardTerminal {
        private final String name;
        Term(String name) { this.name = name; }

        @Override public String getName() { return name; }

        @Override public Card connect(String protocol) throws CardException {
            if (protocol == null) throw new NullPointerException();
            String r = link().call("CONNECT");           // "<ATR hex> <T=1>"
            String[] p = r.trim().split(" ");
            if (p.length < 2) throw new CardException("kopru: beklenmeyen CONNECT cevabi");
            return new Crd(new ATR(unhex(p[0])), p[1]);
        }

        @Override public boolean isCardPresent() throws CardException {
            return "1".equals(link().call("STATUS").trim());
        }

        @Override public boolean waitForCardPresent(long timeout) throws CardException { return waitFor(true, timeout); }

        @Override public boolean waitForCardAbsent(long timeout) throws CardException { return waitFor(false, timeout); }

        private boolean waitFor(boolean wantPresent, long timeout) throws CardException {
            long end = timeout > 0 ? System.currentTimeMillis() + timeout : Long.MAX_VALUE;
            while (true) {
                if (isCardPresent() == wantPresent) return true;
                if (System.currentTimeMillis() >= end) return false;
                try { Thread.sleep(300); } catch (InterruptedException e) { Thread.currentThread().interrupt(); return false; }
            }
        }
    }

    static final class Crd extends Card {
        private final ATR atr;
        private final String proto;
        private final Chan chan = new Chan(this);
        private volatile boolean closed;

        Crd(ATR atr, String proto) { this.atr = atr; this.proto = proto; }

        void check() throws CardException { if (closed) throw new IllegalStateException("Card object has been disconnected"); }

        @Override public ATR getATR() { return atr; }
        @Override public String getProtocol() { return proto; }
        @Override public CardChannel getBasicChannel() { return chan; }
        @Override public CardChannel openLogicalChannel() throws CardException { throw new CardException("mantiksal kanal desteklenmiyor"); }
        @Override public void beginExclusive() throws CardException { }
        @Override public void endExclusive() throws CardException { }
        @Override public byte[] transmitControlCommand(int code, byte[] cmd) throws CardException {
            throw new CardException("transmitControlCommand desteklenmiyor (PIN pad yok)");
        }
        @Override public void disconnect(boolean reset) throws CardException {
            if (closed) return;
            closed = true;
            try { link().call("DISCONNECT " + (reset ? "1" : "0")); } catch (CardException ignored) { }
        }
    }

    static final class Chan extends CardChannel {
        private final Crd card;
        Chan(Crd card) { this.card = card; }

        @Override public Card getCard() { return card; }
        @Override public int getChannelNumber() { return 0; }

        @Override public ResponseAPDU transmit(CommandAPDU command) throws CardException {
            card.check();
            String r = link().call("TRANSMIT " + hex(command.getBytes())).trim();
            byte[] resp = unhex(r);
            if (resp.length < 2) throw new CardException("kopru: kisa APDU cevabi");
            return new ResponseAPDU(resp);
        }

        @Override public int transmit(ByteBuffer command, ByteBuffer response) throws CardException {
            byte[] c = new byte[command.remaining()];
            command.get(c);
            ResponseAPDU r = transmit(new CommandAPDU(c));
            byte[] rb = r.getBytes();
            response.put(rb);
            return rb.length;
        }

        @Override public void close() throws CardException { }
    }
}
