// CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
// CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
// CKZ-MUHUR/1 MUHURSUZ
package eimza;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.lang.instrument.Instrumentation;
import java.security.KeyStore;
import java.security.Security;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;

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
            androidKokSertifikalari();
            Security.addProvider(new TermuxCcidProvider());
            System.setProperty("javax.smartcardio.TerminalFactory.DefaultType", TermuxCcidProvider.TYPE);
            System.err.println("[EIMZA-AGENT] Termux CCID saglayicisi etkin (" + System.getProperty("eimza.dir") + ")");
        } catch (Throwable t) {
            System.err.println("[EIMZA-AGENT] saglayici yuklenemedi: " + t);
        }
    }

    /**
     * UdeMobile (Android): Adalet E-Imza, sunucu sertifikasini "JVM cacerts + isletim sistemi kokleri" ile dogrular;
     * Linux'ta kokleri /etc/ssl/certs'ten okur, Android'de bu klasor yoktur. Android'in sistem kok sertifikalari
     * (Turk kokleri dahil) JVM deposuyla birlestirilip varsayilan guven deposu yapilir (javax.net.ssl.trustStore).
     */
    static void androidKokSertifikalari() {
        File[] dizinler = {new File("/apex/com.android.conscrypt/cacerts"), new File("/system/etc/security/cacerts")};
        File kaynak = null;
        for (File d : dizinler) if (d.isDirectory()) { kaynak = d; break; }
        if (kaynak == null || System.getProperty("javax.net.ssl.trustStore") != null) return;
        try {
            char[] sifre = "changeit".toCharArray();
            KeyStore ks = KeyStore.getInstance("PKCS12");
            File jvm = new File(System.getProperty("java.home"), "lib/security/cacerts");
            if (jvm.isFile()) {
                try (InputStream in = new FileInputStream(jvm)) { ks.load(in, sifre); }
            } else {
                ks.load(null, null);
            }
            CertificateFactory cf = CertificateFactory.getInstance("X.509");
            int n = 0;
            File[] dosyalar = kaynak.listFiles();
            if (dosyalar != null) {
                for (File f : dosyalar) {
                    try (InputStream in = new FileInputStream(f)) {
                        X509Certificate c = (X509Certificate) cf.generateCertificate(in);
                        ks.setCertificateEntry("android-" + f.getName(), c);
                        n++;
                    } catch (Exception ignored) { }
                }
            }
            File dizin = new File(System.getProperty("eimza.dir", System.getProperty("java.io.tmpdir")));
            dizin.mkdirs();
            File hedef = new File(dizin, "guven-deposu.p12");
            File gecici = new File(dizin, "guven-deposu.p12." + ProcessHandle.current().pid());
            try (OutputStream o = new FileOutputStream(gecici)) { ks.store(o, sifre); }
            if (!gecici.renameTo(hedef)) { hedef.delete(); gecici.renameTo(hedef); }
            System.setProperty("javax.net.ssl.trustStore", hedef.getAbsolutePath());
            System.setProperty("javax.net.ssl.trustStorePassword", "changeit");
            System.setProperty("javax.net.ssl.trustStoreType", "PKCS12");
            System.err.println("[EIMZA-AGENT] Android kok sertifikalari eklendi: " + n + " (" + kaynak + ")");
        } catch (Exception e) {
            System.err.println("[EIMZA-AGENT] Android kok sertifikalari eklenemedi: " + e);
        }
    }
}
