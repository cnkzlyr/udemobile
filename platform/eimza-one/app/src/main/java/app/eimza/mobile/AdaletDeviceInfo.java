package app.eimza.mobile;

import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Base64;
import org.bouncycastle.crypto.digests.SHA512Digest;
import org.bouncycastle.crypto.engines.AESEngine;
import org.bouncycastle.crypto.generators.PKCS5S2ParametersGenerator;
import org.bouncycastle.crypto.modes.CBCBlockCipher;
import org.bouncycastle.crypto.paddings.PaddedBufferedBlockCipher;
import org.bouncycastle.crypto.params.ParametersWithIV;

/** DeviceServiceImpl / JasyptConfig wire format from the supplied Adalet tray.
 * This is protocol compatibility, not encryption for protecting local secrets. */
final class AdaletDeviceInfo {
    // The supplied JAR's JasyptConfig.P public protocol constant, retained verbatim.
    private static final byte[] P = {90,71,84,108,66,72,98,87,57,80,83,107,64,112,
            89,88,81,105,79,106,69,50,78,84,81,121,77,122,77,48,78,68,73,115};
    private static final SecureRandom RANDOM = new SecureRandom();

    static String encrypt(String json) throws Exception {
        byte[] salt = new byte[16], iv = new byte[16];
        RANDOM.nextBytes(salt); RANDOM.nextBytes(iv);
        return encrypt(json, salt, iv);
    }

    static String encrypt(String json, byte[] salt, byte[] iv) throws Exception {
        if (salt.length != 16 || iv.length != 16) throw new IllegalArgumentException("PBE parameters");
        PKCS5S2ParametersGenerator kdf = new PKCS5S2ParametersGenerator(new SHA512Digest());
        kdf.init(P, salt, 1000);
        PaddedBufferedBlockCipher cipher = new PaddedBufferedBlockCipher(new CBCBlockCipher(new AESEngine()));
        cipher.init(true, new ParametersWithIV(kdf.generateDerivedParameters(256), iv));
        byte[] input = json.getBytes(StandardCharsets.UTF_8);
        byte[] output = new byte[cipher.getOutputSize(input.length)];
        int length = cipher.processBytes(input, 0, input.length, output, 0);
        length += cipher.doFinal(output, length);
        byte[] envelope = new byte[32 + length];
        System.arraycopy(salt, 0, envelope, 0, 16);
        System.arraycopy(iv, 0, envelope, 16, 16);
        System.arraycopy(output, 0, envelope, 32, length);
        return "ENC(" + Base64.getEncoder().encodeToString(envelope) + ")";
    }
}
