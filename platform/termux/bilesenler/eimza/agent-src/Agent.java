// CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
// CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
// CKZ-MUHUR/1 MUHURSUZ
package eimza;

import java.lang.instrument.Instrumentation;
import java.security.Security;

/**
 * -javaagent giris noktasi: JVM'in varsayilan javax.smartcardio TerminalFactory'sini Termux CCID koprusune baglar.
 * JAVA_TOOL_OPTIONS ile verilirse Adalet E-Imza uygulamasinin kart tarayan ALT SURECLERINE de otomatik uygulanir.
 */
public final class Agent {
    private Agent() { }

    public static void premain(String args, Instrumentation inst) {
        System.err.println(Kimlik.satir());
        try {
            if (System.getProperty("eimza.dir") == null) {
                String d = System.getenv("EIMZA_DIR");
                if (d == null || d.isEmpty()) d = System.getProperty("user.home") + "/.eimza";
                System.setProperty("eimza.dir", d);
            }
            Security.addProvider(new TermuxCcidProvider());
            System.setProperty("javax.smartcardio.TerminalFactory.DefaultType", TermuxCcidProvider.TYPE);
            System.err.println("[EIMZA-AGENT] Termux CCID saglayicisi etkin (" + System.getProperty("eimza.dir") + ")");
        } catch (Throwable t) {
            System.err.println("[EIMZA-AGENT] saglayici yuklenemedi: " + t);
        }
    }
}
