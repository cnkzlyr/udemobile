package javax.smartcardio;

public abstract class TerminalFactorySpi {
    protected TerminalFactorySpi(Object parameters) { }
    protected abstract CardTerminals engineTerminals();
}
