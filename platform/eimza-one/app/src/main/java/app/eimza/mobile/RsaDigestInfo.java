package app.eimza.mobile;

/** Input for AKIS PSO:CDS when the card applies PKCS#1 v1.5 padding only. */
final class RsaDigestInfo {
    static byte[] sha256(byte[] content) throws java.security.NoSuchAlgorithmException {
        byte[] digest = java.security.MessageDigest.getInstance("SHA-256").digest(content);
        byte[] prefix = new byte[]{0x30,0x31,0x30,0x0d,0x06,0x09,0x60,(byte)0x86,
                0x48,0x01,0x65,0x03,0x04,0x02,0x01,0x05,0x00,0x04,0x20};
        byte[] result = java.util.Arrays.copyOf(prefix, prefix.length + digest.length);
        System.arraycopy(digest, 0, result, prefix.length, digest.length);
        return result;
    }
}
