// CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
// CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
// CKZ-MUHUR/1 MUHURSUZ
package eimza;

/** Yazar / telif kimligi. © 2026 Av. Can KIZILYAR — Tüm hakları saklıdır. Bkz. LICENSE.txt */
public final class Kimlik {
    public static final String YAZAR = "Av. Can KIZILYAR";
    public static final String SURUM = "1.0";
    public static final String IZ = "⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠";

    private Kimlik() { }

    public static String satir() {
        return "[UYAP-Termux " + SURUM + "] \u00a9 2026 " + YAZAR + " \u2014 T\u00fcm haklar\u0131 sakl\u0131d\u0131r." + IZ;
    }
}
