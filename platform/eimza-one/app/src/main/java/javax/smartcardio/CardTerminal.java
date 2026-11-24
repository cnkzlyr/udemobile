package javax.smartcardio;

public abstract class CardTerminal {
    protected CardTerminal() { }
    public abstract String getName();
    public abstract Card connect(String protocol) throws CardException;
    public abstract boolean isCardPresent() throws CardException;
    public abstract boolean waitForCardPresent(long timeout) throws CardException;
    public abstract boolean waitForCardAbsent(long timeout) throws CardException;
    public boolean waitForCardPresent() throws CardException { return waitForCardPresent(0); }
    public boolean waitForCardAbsent() throws CardException { return waitForCardAbsent(0); }
}
