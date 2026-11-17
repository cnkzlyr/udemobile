package tr.gov.tubitak.uekae.esya.api.common.lcns;

import java.util.Date;
import java.util.List;

public class LV {
    public enum Urunler {
        SERTIFIKA_MAKAMI, KAYIT_MAKAMI, AltSM, OCSP, ZAMAN_DAMGASI, OCSP_SERVISI,
        ESYA_ISTEMCI, KERMEN, KERMEN_LIGHT, TEST, ESYA_SUNUCU, ORTAK, AKILLIKART,
        SERTIFIKADOGRULAMA, CMSIMZA, CMSIMZAGELISMIS, XMLIMZA, XMLIMZAGELISMIS,
        CMSZARF, MOBILIMZA, ANDROIDIMZA, KEYMANAGER, KARTILKLENDIRME, GUVENLIPDF,
        ZD_ISTEMCI, KARTILKLENDIRME_V2, POSTACI, IMZAGER, IMZAGER_KURUMSAL, ELIT;
        
        public int getID() { return ordinal(); }
    }

    private static LV B = new LV();

    public static synchronized LV getInstance() {
        return B;
    }

    public static void reset() {}

    public LV() {}

    public String getUrunAtt(LV.Urunler u, String s) { return ""; }
    public String getUrunAtt(int i, String s) { return ""; }
    public String getUrunAtt(LV.Urunler u, String s, String s1) { return ""; }
    public long getUrunLongAtt(LV.Urunler u, String s) { return 0L; }
    public long getUrunLongAtt(int i, String s) { return 0L; }
    public boolean isTL(LV.Urunler u) { return false; }
    public void checkVersion(int i, String s) {}
    public void checkLD(LV.Urunler u) {}
    public void checkAnyUrunLD(List<LV.Urunler> list) {}
    public List<LV.Urunler> filterByLicense(List<LV.Urunler> list) { return list; }
    public void checkLD(int i) {}
    public void checkIsItJava(int i) {}
    public int getLid() { return 1; }
    public String getKurumAdi() { return "UYAP"; }
    public String getYetkili() { return "UYAP"; }
    public String getEposta() { return "uyap@adalet.gov.tr"; }
    public String getTelno() { return ""; }
    public String getAdres() { return ""; }
    public String getFaks() { return ""; }
    public byte[] getLicenseData() { return new byte[0]; }
    public void setLicenseData(byte[] b) {}
    public Date getLicenseStartDate(int i) { return new Date(0); }
    public Date getLicenseExpirationDate(int i) { return new Date(System.currentTimeMillis() + 1000L * 3600 * 24 * 365 * 10); }
    public String getCertificateIssuer(LV.Urunler u) { return ""; }
    public boolean isPermissiveTimeStamp() { return true; }
}
