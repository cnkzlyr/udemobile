package eimzawin;

import java.lang.instrument.Instrumentation;
import java.security.Security;
import java.util.List;

/**
 * CanEditor masaüstü (Windows) -javaagent: Adalet E-İmza'nın (ve kart tarayan alt süreçlerinin) varsayılan
 * javax.smartcardio sağlayıcısını Unicode okuyucu adlarını doğru taşıyan UnicodePCSC ile değiştirir.
 * JAVA_TOOL_OPTIONS ile verilir; sağlayıcı açılamazsa JDK'nın kendi sağlayıcısı (SunPCSC) olduğu gibi kalır.
 * PIN penceresine, sertifikalara ya da imza akışına dokunmaz.
 */
public final class Agent {
    private Agent() { }

    public static void premain(String args, Instrumentation inst) {
        if ("0".equals(System.getenv("CANEDITOR_UNICODE_PCSC"))) return;
        try {
            if (System.getProperty("jna.tmpdir") == null && System.getProperty("java.io.tmpdir") != null)
                System.setProperty("jna.tmpdir", System.getProperty("java.io.tmpdir"));
            long ctx = Pcsc.baglamAc();                    // winscard.dll yüklenebiliyor ve hizmet çalışıyor mu
            List<String> okuyucular;
            try { okuyucular = Pcsc.okuyucular(ctx); } finally { Pcsc.baglamKapat(ctx); }
            Security.insertProviderAt(new UnicodePcscProvider(), 1);
            System.setProperty("javax.smartcardio.TerminalFactory.DefaultType", UnicodePcscProvider.TYPE);
            System.err.println("[CANEDITOR-PCSC] Unicode PC/SC sağlayıcısı etkin · okuyucular=" + okuyucular);
        } catch (Throwable t) {
            System.err.println("[CANEDITOR-PCSC] etkinleştirilemedi, JDK sağlayıcısı kullanılacak: " + t);
        }
    }
}
