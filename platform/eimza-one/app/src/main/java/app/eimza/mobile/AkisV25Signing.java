package app.eimza.mobile;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import tubitak.akis.cif.commands.AbstractAkisCommands;
import tubitak.akis.cif.akisExceptions.AkisSWException;

/** Modern AKİS (V20/V25/Gezgin) PKCS#15 authentication and signing path. */
final class AkisV25Signing {
    private AkisV25Signing() { }
    static byte prepare(AbstractAkisCommands commands, char[] pin, byte[] certificateFile) throws Exception {
        authenticate(commands, pin);
        byte[] cdf = commands.readFileBySelectingUnderActiveDF(new byte[]{0x2F, 0x04});
        byte[] prkdf = commands.readFileBySelectingUnderActiveDF(new byte[]{0x2F, 0x01});
        return AkisPkcs15.keyReference(cdf, prkdf, certificateFile);
    }
    static byte[] sign(AbstractAkisCommands commands, byte key, byte[] input) throws Exception {
        // Native ArkSigner first uses AKIS's legacy key-index MSE. If that format
        // is unsupported, it selects RSA PKCS#1 with algorithm 0x92 and a LOCAL
        // key reference (0x80 + index). CIF's generic sign uses 0x82/plain index.
        try { commands.sendCommand(new byte[]{0,0x22,(byte)0xC3,0x22,key}); }
        catch (AkisSWException e) {
            long sw = e.getErrorCode();
            if (sw != 0x6A86 && sw != 0x6D00 && sw != 0x6A80 && sw != 0x6A88) throw e;
            commands.mseSet((byte)0x41,(byte)0xB6,new byte[]{(byte)0x80,1,(byte)0x92,(byte)0x84,1,(byte)(0x80 | (key & 0x7F))});
        }
        // Never retry a failed PSO or a PIN. Verify the signature in the caller.
        return commands.pso(commands.pso_param.cds, input);
    }

    static byte[] signEcc(AbstractAkisCommands commands, byte key, byte[] input) throws Exception {
        // The CIF exposes the same explicit mechanism API for ECC. Unlike the
        // RSA V25 fallback above, do not send an RSA MSE or DigestInfo.
        return commands.sign(
                tubitak.akis.cif.dataStructures.Algorithm.ECC,
                tubitak.akis.cif.dataStructures.Algorithm.SHA_256,
                key,
                input);
    }
    static void authenticate(AbstractAkisCommands commands, char[] pin) throws Exception {
        commands.selectDFByName("PKCS-15".getBytes(StandardCharsets.US_ASCII));
        byte[] secret = new byte[pin.length];
        try {
            for (int i = 0; i < pin.length; i++) {
                if (pin[i] < '0' || pin[i] > '9') throw new IllegalArgumentException("Kart PIN'i yalnız rakam içermeli");
                secret[i] = (byte) pin[i];
            }
            commands.verify((byte) 1, secret, false);
        } finally { Arrays.fill(secret, (byte) 0); }
    }
}
