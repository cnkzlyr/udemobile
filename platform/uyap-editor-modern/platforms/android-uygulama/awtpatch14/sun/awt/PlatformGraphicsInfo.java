package sun.awt;

import java.awt.GraphicsEnvironment;
import java.awt.Toolkit;

/**
 * UdeMobile (Android): X sunucusu yok. AWT/Swing pencereleri Caciocavallo (CTC) ile bellekte cizilir;
 * boylece masaustu penceresi acmaya calisan uygulamalar (Adalet E-Imza) "HeadlessException" ile cokmez.
 */
public class PlatformGraphicsInfo {
    public static GraphicsEnvironment createGE() {
        try {   // Caciocavallo kendi yuzey yoneticisini kurar; once bosaltilir (CacioExtension ile ayni)
            java.lang.reflect.Field f = sun.java2d.SurfaceManagerFactory.class.getDeclaredField("instance");
            f.setAccessible(true);
            f.set(null, null);
        } catch (ReflectiveOperationException e) { }
        return new com.github.caciocavallosilano.cacio.ctc.CTCGraphicsEnvironment();
    }
    public static Toolkit createToolkit() {
        return new com.github.caciocavallosilano.cacio.ctc.MobilToolkit();
    }
    public static boolean getDefaultHeadlessProperty() { return false; }
    public static String getDefaultHeadlessMessage() { return "UdeMobile: ekran yok (Caciocavallo)"; }
}
