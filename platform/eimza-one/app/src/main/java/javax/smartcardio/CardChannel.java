package javax.smartcardio;

import java.nio.ByteBuffer;

public abstract class CardChannel implements AutoCloseable {
    public abstract Card getCard();
    public abstract int getChannelNumber();
    public abstract ResponseAPDU transmit(CommandAPDU command) throws CardException;
    public abstract int transmit(ByteBuffer command, ByteBuffer response) throws CardException;
    @Override public abstract void close() throws CardException;
}
