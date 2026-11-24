package app.eimza.mobile;

import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/** Wire bootstrap used by the supplied ArkSigner JavaScript resource. */
/*final class ArkBootstrap {
    private static final SecureRandom RANDOM = new SecureRandom();
    static String nonce() {
        int step = 2 + RANDOM.nextInt(7);
        StringBuilder n = new StringBuilder().append(step);
        String alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
        for (int i = 0; i < 140; i++) n.append(alphabet.charAt(RANDOM.nextInt(alphabet.length())));
        String time = new SimpleDateFormat("yyyyMMddHHmmss", Locale.ROOT).format(new Date());
        for (int i = 0; i < time.length(); i++) n.setCharAt((i + 1) * step, (char)('9' - (time.charAt(i) - '0')));
        return n.toString();
    }
    static String cypher(String text, String key) {
        StringBuilder result = new StringBuilder(text.length());
        for (int i = 0; i < text.length(); i++) result.append((char)(text.charAt(i) ^ key.charAt(i % key.length())));
        return java.util.Base64.getEncoder().encodeToString(result.toString().getBytes(StandardCharsets.UTF_8));
    }
}*/

final class ArkBootstrap {
    private static final SecureRandom RANDOM = new SecureRandom();
    
    static String nonce() {
        int step = 2 + RANDOM.nextInt(7);
        StringBuilder n = new StringBuilder().append(step);
        String alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
        for (int i = 0; i < 140; i++) n.append(alphabet.charAt(RANDOM.nextInt(alphabet.length())));
        String time = new SimpleDateFormat("yyyyMMddHHmmss", Locale.ROOT).format(new Date());
        for (int i = 0; i < time.length(); i++) n.setCharAt((i + 1) * step, (char)('9' - (time.charAt(i) - '0')));
        return n.toString();
    }

    // GÜNCELLENEN VE HATAYI DÜZELTEN METOD
    static String cypher(String text, String key) {
        if (text == null || key == null || key.isEmpty()) return "";
        
        // String'leri güvenli bir şekilde byte dizilerine dönüştürüyoruz
        byte[] textBytes = text.getBytes(StandardCharsets.UTF_8);
        byte[] keyBytes = key.getBytes(StandardCharsets.UTF_8);
        byte[] resultBytes = new byte[textBytes.length];
        
        // XOR işlemini doğrudan byte'lar üzerinde yapıyoruz (karakterler bozulmaz)
        for (int i = 0; i < textBytes.length; i++) {
            resultBytes[i] = (byte) (textBytes[i] ^ keyBytes[i % keyBytes.length]);
        }
        
        // Bozuk string üretmeden direkt ham byte dizisini Base64 yapıyoruz
        return java.util.Base64.getEncoder().encodeToString(resultBytes);
    }
}
