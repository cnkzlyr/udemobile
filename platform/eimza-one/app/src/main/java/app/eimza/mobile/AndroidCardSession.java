package app.eimza.mobile;

import java.io.IOException;

/** Process-wide card session shared by the in-app SmartcardIO adapter and portal service layers. */
final class AndroidCardSession {
    private static volatile UsbCcidProbe owner;
    private AndroidCardSession() { }
    static void attach(UsbCcidProbe probe) { owner = probe; }
    static void detach(UsbCcidProbe probe) { if (owner == probe) owner = null; }
    static String readerName() { UsbCcidProbe p = owner; return p == null ? null : p.activeReaderName(); }
    static byte[] atr() { UsbCcidProbe p = owner; return p == null ? null : p.activeAtr(); }
    static boolean present() throws javax.smartcardio.CardException {
        UsbCcidProbe p = owner;
        if (p == null || p.activeReaderName() == null) return false;
        try { return p.isCardPresent(); }
        catch (IOException e) { throw new javax.smartcardio.CardException("USB reader status failed", e); }
    }
    static boolean presentQuietly() {
        try { return present(); }
        catch (javax.smartcardio.CardException e) { return false; }
    }
    static byte[] transmit(byte[] apdu) throws javax.smartcardio.CardException {
        UsbCcidProbe p = owner;
        if (p == null) throw new javax.smartcardio.CardException("No USB CCID session");
        try { return p.transmit(apdu); }
        catch (IOException e) { throw new javax.smartcardio.CardException("USB APDU exchange failed", e); }
    }
}
