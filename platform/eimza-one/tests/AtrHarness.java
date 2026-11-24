import java.util.Arrays;
import javax.smartcardio.ATR;

public final class AtrHarness {
    public static void main(String[] args) {
        // T0: TA1+TD1, TD1: TB2+TD2, TD2: no more interface bytes; K=3.
        byte[] raw = new byte[]{0x3b, (byte)0x93, 0x11, (byte)0x91, 0x22,
                0x01, 0x55, 0x66, 0x77, 0x00};
        ATR atr = new ATR(raw);
        if (!Arrays.equals(atr.getInterfaceBytes(),
                new byte[]{0x11, (byte)0x91, 0x22, 0x01}))
            throw new AssertionError("interface byte walk");
        if (!Arrays.equals(atr.getHistoricalBytes(), new byte[]{0x55, 0x66, 0x77}))
            throw new AssertionError("historical byte offset");
        System.out.println("PASS: ISO 7816 ATR interface groups and historical bytes");
    }
}
