package javax.smartcardio;

import java.util.List;

public abstract class CardTerminals {
    public enum State { ALL, CARD_PRESENT, CARD_ABSENT, CARD_INSERTION, CARD_REMOVAL }
    public abstract List<CardTerminal> list(State state) throws CardException;
    public abstract boolean waitForChange(long timeout) throws CardException;
    public CardTerminals() { }
    public List<CardTerminal> list() throws CardException { return list(State.ALL); }
    public CardTerminal getTerminal(String name) throws CardException {
        if (name == null) throw new NullPointerException("name");
        for (CardTerminal terminal : list()) if (name.equals(terminal.getName())) return terminal;
        return null;
    }
    public void waitForChange() throws CardException {
        if (list().isEmpty()) throw new IllegalStateException("No card terminals available");
        waitForChange(0);
    }
}
