package app.eimza.mobile;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import javax.crypto.Cipher;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.SecretKeySpec;

/** Reads the encrypted ESYA configuration shipped with the supplied Adalet client. */
final class AdaletEsyaConfig {
    private static final byte[] KEY = {(byte)0xC0,(byte)0xA3,0x45,(byte)0x88,0x47,(byte)0xD7,(byte)0xFA,(byte)0xD2,
            (byte)0xAA,(byte)0xAE,0x38,(byte)0xDF,(byte)0x9A,(byte)0x81,0x50,0x64};
    private static final byte[] IV = {(byte)0xD9,0x4F,0x55,(byte)0x8D,(byte)0xB1,0x38,0x16,0x51,
            (byte)0xBC,(byte)0xBF,(byte)0xEA,(byte)0xA8,(byte)0xCE,0x06,(byte)0xC1,0x51};

    private AdaletEsyaConfig() { }

    static InputStream decrypt(InputStream encrypted) throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        byte[] buffer = new byte[4096];
        int count;
        while ((count = encrypted.read(buffer)) != -1) bytes.write(buffer, 0, count);
        Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
        cipher.init(Cipher.DECRYPT_MODE, new SecretKeySpec(KEY, "AES"), new IvParameterSpec(IV));
        return new ByteArrayInputStream(cipher.doFinal(bytes.toByteArray()));
    }
}
