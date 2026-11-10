// CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
// CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
// CKZ-MUHUR/1 MUHURSUZ
package tr.gov.adalet.service.framework.adalet.eimza.eimzatray.gui;

import java.awt.Component;

/**
 * UdeMobile (Android): web sayfasi PIN gondermediginde Adalet E-Imza uygulamasi bu sinifla PIN ister.
 * Android'de Java penceresi gorunmez (ekran yok); PIN, UdeMobile'in kendi Android penceresinden kopru uzerinden
 * alinir ("PIN" komutu). Kullanici iptal ederse ya da 120 sn icinde girilmezse null doner (islem iptal olur).
 * PIN hicbir yere yazilmaz/loglanmaz.
 *
 * (c) 2026 Av. Can KIZILYAR - Tum haklari saklidir. Bkz. LICENSE.txt
 */
public class e {
    public static String a(Component parent) {
        return eimza.TermuxCcidProvider.pinIste("E-imza \u015fifrenizi (PIN) girin");
    }
}
