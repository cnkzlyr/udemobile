package app.eimza.mobile;

import javax.smartcardio.ATR;
import javax.smartcardio.Card;
import javax.smartcardio.CardChannel;
import javax.smartcardio.CardException;
import javax.smartcardio.CardTerminal;
import javax.smartcardio.CardTerminals;
import javax.smartcardio.CommandAPDU;
import javax.smartcardio.ResponseAPDU;
import javax.smartcardio.TerminalFactorySpi;
import java.nio.ByteBuffer;
import java.security.Provider;
import java.util.Collections;
import java.util.List;

/** SmartcardIO-compatible PC/SC terminal backed directly by Android USB Host CCID. */
public final class AndroidCcidProvider extends Provider {
    private static final long serialVersionUID = 1L;
    public AndroidCcidProvider() {
        super("AndroidCCID", 1.0, "Android USB Host CCID/T=1 adapter");
        put("TerminalFactory.PC/SC", Factory.class.getName());
        put("TerminalFactory.AndroidCCID", Factory.class.getName());
    }

    public static CardTerminal directTerminal() throws CardException {
        String name = AndroidCardSession.readerName();
        if (name == null || !AndroidCardSession.present()) {
            throw new CardException("USB e-imza okuyucusu veya kart bağlı değil");
        }
        return new Terminal(name);
    }

    public static Card directCard() throws CardException {
        return directTerminal().connect("*");
    }

    public static final class Factory extends TerminalFactorySpi {
        public Factory() { super(null); }
        public Factory(Object parameters) { super(parameters); }
        @Override protected CardTerminals engineTerminals() { return new Terminals(); }
    }
    private static final class Terminals extends CardTerminals {
        private boolean previous;
        @Override public List<CardTerminal> list(State state) throws CardException {
            if (state == null) throw new NullPointerException("state");
            String name = AndroidCardSession.readerName();
            // ALL is enumeration: avoid touching the USB reader until a caller asks for card state.
            boolean needsPresence = state != State.ALL;
            boolean present = needsPresence && AndroidCardSession.present();
            boolean hit;
            switch (state) {
                case ALL: hit = name != null; break;
                case CARD_PRESENT: hit = name != null && present; break;
                case CARD_ABSENT: hit = name != null && !present; break;
                case CARD_INSERTION: hit = name != null && present && !previous; break;
                case CARD_REMOVAL: hit = name != null && !present && previous; break;
                default: hit = false;
            }
            if (needsPresence) previous = present;
            return hit ? Collections.<CardTerminal>singletonList(new Terminal(name)) : Collections.<CardTerminal>emptyList();
        }
        @Override public boolean waitForChange(long timeout) throws CardException {
            boolean before = AndroidCardSession.present();
            long until = timeout > 0 ? System.currentTimeMillis() + timeout : Long.MAX_VALUE;
            do {
                try { Thread.sleep(250); } catch (InterruptedException e) { Thread.currentThread().interrupt(); return false; }
                if (AndroidCardSession.present() != before) return true;
            } while (System.currentTimeMillis() < until);
            return false;
        }
    }
    private static final class Terminal extends CardTerminal {
        private final String name;
        Terminal(String name) { this.name = name; }
        @Override public String getName() { return name; }
        @Override public Card connect(String protocol) throws CardException {
            if (!"*".equals(protocol) && !"T=1".equalsIgnoreCase(protocol) && !"T=0".equalsIgnoreCase(protocol)) {
                throw new CardException("Unsupported protocol: " + protocol + " (T=1, T=0 or * supported)");
            }
            if (!AndroidCardSession.present()) throw new CardException("No card present");
            byte[] atr = AndroidCardSession.atr();
            if (atr == null) throw new CardException("Card has not been activated");
            return new SessionCard(atr);
        }
        @Override public boolean isCardPresent() throws CardException { return AndroidCardSession.present(); }
        @Override public boolean waitForCardPresent(long timeout) throws CardException { return waitFor(true, timeout); }
        @Override public boolean waitForCardAbsent(long timeout) throws CardException { return waitFor(false, timeout); }
        private boolean waitFor(boolean wanted, long timeout) throws CardException {
            long until = timeout > 0 ? System.currentTimeMillis() + timeout : Long.MAX_VALUE;
            do { if (isCardPresent() == wanted) return true; try { Thread.sleep(250); } catch (InterruptedException e) { Thread.currentThread().interrupt(); return false; } }
            while (System.currentTimeMillis() < until);
            return false;
        }
    }
    private static final class SessionCard extends Card {
        private final ATR atr;
        private final CardChannel channel = new Channel(this);
        private volatile boolean closed;
        SessionCard(byte[] bytes) { atr = new ATR(bytes); }
        void ensureOpen() { if (closed) throw new IllegalStateException("Card session disconnected"); }
        @Override public ATR getATR() { return atr; }
        @Override public String getProtocol() { return "T=1"; }
        @Override public CardChannel getBasicChannel() { return channel; }
        @Override public CardChannel openLogicalChannel() throws CardException { throw new CardException("Logical channels are not supported by this reader session"); }
        @Override public void beginExclusive() { }
        @Override public void endExclusive() { }
        @Override public byte[] transmitControlCommand(int code, byte[] command) throws CardException { throw new CardException("Control commands are not supported"); }
        @Override public void disconnect(boolean reset) { closed = true; }
    }
    private static final class Channel extends CardChannel {
        private final SessionCard card;
        Channel(SessionCard card) { this.card = card; }
        @Override public Card getCard() { return card; }
        @Override public int getChannelNumber() { return 0; }
        @Override public ResponseAPDU transmit(CommandAPDU command) throws CardException { card.ensureOpen(); return new ResponseAPDU(AndroidCardSession.transmit(command.getBytes())); }
        @Override public int transmit(ByteBuffer command, ByteBuffer response) throws CardException {
            byte[] bytes = new byte[command.remaining()]; command.get(bytes); byte[] result = transmit(new CommandAPDU(bytes)).getBytes(); response.put(result); return result.length;
        }
        @Override public void close() { }
    }
}
