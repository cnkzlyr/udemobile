package com.agy.uyapacici;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

/**
 * UYAP Editör (orijinal) — Termux / X11 / Termux:API olmadan, dokunmatik.
 *
 * .udf / .usf: dosya yöneticisi, WhatsApp, Celse, tarayıcı, e-posta… "Birlikte aç" / "Paylaş" ile gelen belge doğrudan
 * resmi editörde açılır; bu ekran .udf/.usf için varsayılan uygulama yapılabilir. Kaydedince belge geldiği yere (yazılabiliyorsa)
 * ya da İndirilenler/UYAP klasörüne yazılır.
 */
public class UyapMobilActivity extends Activity implements UyapMobilServisi.Dinleyici, Arayuz.Uygulama {
    private static final int SEC_BELGE = 41, SEC_PAKET = 42, SEC_FONT = 43, SEC_EDITOR = 44;
    /** Editörün Aç/Kaydet penceresi için açılan Android seçicisi (etkinlik yeniden kurulsa da kaybolmasın). */
    private static int seciciNo = -1;
    private static boolean seciciKaydet;
    private static String seciciUzanti = "";
    private Arayuz ui;
    private static final int MOBIL_GORUNUM = 45;
    private static String mobilYol;
    private static long mobilZaman;
    /** CanEditor'dan "Orijinal UYAP Editör'de aç": belge zaten belgeler/ klasöründe (EK_YOL). */
    public static final String EYLEM_AC = "com.agy.uyapacici.UYAP_EDITORDE_AC", EK_YOL = "yol";

    private EkranView ekran;
    private static final int IZIN_DEPOLAMA = 51;
    private String bekleyenDosya;
    private boolean baslatildi;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        Tani.baglam(this);
        com.agy.telemetry.CrashReporter.install(this);   // çökme olursa İndirilenler/com.agy.uyapacici_crash.log
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        ui = new Arayuz(this, ayar(), this);
        ekran = ui.ekran;
        setContentView(ui.kok);

        bekleyenDosya = gelenBelge(getIntent());
        if (bekleyenDosya != null) bekleyenAd = new File(bekleyenDosya).getName();
        UyapMobilServisi.dinleyiciAyarla(this);
        ekran.post(this::basla);   // Aç/Kaydet telefonun kendi seçicisini kullanır: depolama izni istenmez
    }

    /**
     * Aç / Kaydet pencereleri telefonun depolamasında (/sdcard) başlasın diye depolama izni istenir (bir kez).
     * true: izin zaten var ya da daha önce sorulduysa hemen başla; false: yanıttan sonra başlanır.
     */
    private boolean izinIste() {
        if (android.os.Build.VERSION.SDK_INT < 23 || UyapMobil.depolamaIzniVar(this) || ayar().getBoolean("depolama_soruldu", false)) return true;
        ayar().edit().putBoolean("depolama_soruldu", true).apply();
        try {
            requestPermissions(new String[]{android.Manifest.permission.READ_EXTERNAL_STORAGE, android.Manifest.permission.WRITE_EXTERNAL_STORAGE}, IZIN_DEPOLAMA);
            return false;
        } catch (Exception e) { return true; }
    }

    @Override public void onRequestPermissionsResult(int kod, String[] izinler, int[] sonuclar) {
        super.onRequestPermissionsResult(kod, izinler, sonuclar);
        if (kod != IZIN_DEPOLAMA) return;
        if (!UyapMobil.depolamaIzniVar(this))
            Toast.makeText(this, "Depolama izni yok: Aç/Kaydet pencereleri uygulama klasöründe açılır (Ayarlar > Uygulamalar > UYAP Editör > İzinler)", Toast.LENGTH_LONG).show();
        ekran.post(this::basla);
    }

    @Override protected void onNewIntent(Intent i) {
        super.onNewIntent(i);
        String f = gelenBelge(i);
        if (f != null) {
            ui.belgeAciliyor(new File(f).getName());
            if (UyapMobilServisi.calisiyor()) UyapMobilServisi.ac(this, f, 0, 0);
            else { bekleyenDosya = f; basla(); }
        }
    }

    @Override protected void onDestroy() {
        UyapMobilServisi.dinleyiciAyarla(null);
        ekran.kapat();
        super.onDestroy();
    }

    // ------------------------------------------------------------------------------------ başlatma
    private SharedPreferences ayar() { return getSharedPreferences("uyapmobil", MODE_PRIVATE); }

    /** Mantıksal ekran: kısa kenar ~900 px (şerit menü sığar), ölçek ayarıyla büyütülüp küçültülebilir. */
    private int[] mantiksalBoyut() {
        int vw = Math.max(ekran.getWidth(), dp(320)), vh = Math.max(ekran.getHeight(), dp(320));
        float hedef = ayar().getFloat("kisa_kenar", 820f);
        float s = Math.max(0.75f, Math.min(vw, vh) / hedef);
        return new int[]{Math.round(vw / s), Math.round(vh / s)};
    }

    private void basla() {
        if (!UyapMobil.editorKurulu(this)) { kurulumSor(); return; }
        if (UyapMobilServisi.calisiyor()) {
            if (bekleyenDosya != null) { UyapMobilServisi.ac(this, bekleyenDosya, 0, 0); bekleyenDosya = null; }
            int[] e = UyapMobilServisi.ekranBoyutu();
            if (e != null && UyapMobilServisi.bagli()) hazir(e[0], e[1]);
            return;
        }
        int[] m = mantiksalBoyut();
        baslatildi = true;
        durumGoster("UYAP Editör açılıyor…");
        UyapMobilServisi.ac(this, bekleyenDosya, m[0], m[1]);
        bekleyenDosya = null;
    }

    private void kurulumSor() {
        new AlertDialog.Builder(this)
                .setTitle("Resmi UYAP Editör kurulsun mu?")
                .setMessage("Bu ekran resmi UYAP Doküman Editörü'nü (Java 14) telefonda Termux ve X11 olmadan çalıştırır.\n\n"
                        + "Resmi editör bir kez, YALNIZCA Adalet Bakanlığı'nın adresinden (rayp.adalet.gov.tr, ~43 MB) indirilir. "
                        + "İsterseniz elinizdeki resmi Linux paketini (uyapeditor_*.zip ya da .deb) seçebilirsiniz.")
                .setPositiveButton("İndir ve kur", (d, w) -> kur(null, null))
                .setNeutralButton("Dosyadan kur", (d, w) -> dosyaSec(SEC_PAKET, "*/*"))
                .setNegativeButton("Vazgeç", (d, w) -> durumGoster("Resmi editör kurulu değil. Menü > Resmi editörü kur"))
                .show();
    }

    private void kur(final Uri uri, final String ad) {
        durumGoster("Hazırlanıyor…");
        new Thread(() -> {
            try {
                UyapMobil.Ilerleme il = m -> runOnUiThread(() -> durumGoster(m));
                if (uri == null) UyapMobil.indirKur(this, il); else UyapMobil.dosyadanKur(this, uri, ad, il);
                UyapMobil.hazirla(this, il);
                runOnUiThread(this::basla);
            } catch (Exception e) {
                Tani.hata("uyapmobil", "kurulum", e);
                runOnUiThread(() -> durumGoster("Kurulum başarısız: " + e.getMessage()));
            }
        }, "uyapmobil-kur").start();
    }

    // ------------------------------------------------------------------------------------ servis dinleyicisi
    @Override public void durum(final String m) { runOnUiThread(() -> { if (!"Hazır".equals(m)) durumGoster(m); }); }

    @Override public void hazir(final int w, final int h) {
        runOnUiThread(() -> {
            ekran.baglan(UyapMobil.ekranDosyasi(this), w, h);
            ui.durumGizle();
            ekran.requestFocus();
            ui.hazir();
            if (bekleyenAd != null) { ui.belgeAciliyor(bekleyenAd); bekleyenAd = null; }
            if (!ayar().getBoolean("ipucu2", false)) {
                ayar().edit().putBoolean("ipucu2", true).apply();
                Toast.makeText(this, "İpucu: iki parmakla yakınlaştırın · uzun basış = sağ tık · ☰ tüm komutlar", Toast.LENGTH_LONG).show();
            }
        });
    }

    @Override public void kapandi(final String neden) {
        runOnUiThread(() -> {
            ekran.kapat();
            if (baslatildi && !"kurulu değil".equals(neden)) durumGoster("UYAP Editör kapandı. Yeniden açmak için ⟳");
        });
    }

    private String bekleyenAd;

    private void durumGoster(String m) {
        boolean yukleniyor = m.endsWith("…") || m.contains("açılıyor") || m.contains("Hazırlanıyor") || m.contains("İndiriliyor") || m.contains("%");
        ui.durum(m, yukleniyor);
    }

    @Override public void baslik(String t) { if (ui != null) ui.baslik(t); }

    /**
     * Mobil görünüm: belge UdeMobile'ın yeniden akışlı (telefon ekranına göre satır kıran) editöründe açılır. Orada
     * kaydedilirse UYAP Editör'e dönünce belge yeniden yüklenir (aynı dosya; asıl yere geri yazma sürer).
     */
    @Override public void mobilGorunum(String yol) {
        File f = new File(yol);
        if (!f.isFile()) { Toast.makeText(this, "Belge dosyası bulunamadı: " + yol, Toast.LENGTH_LONG).show(); return; }
        mobilYol = yol;
        mobilZaman = f.lastModified();
        Intent i = new Intent(this, EditorActivity.class).putExtra(EditorActivity.EXTRA_FILE_PATH, yol).putExtra(EditorActivity.EXTRA_UYAP_SAYFA, true);
        try {
            startActivityForResult(i, MOBIL_GORUNUM);
            overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
        } catch (Exception e) {
            Toast.makeText(this, "Mobil görünüm açılamadı: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    private void mobildenDonus() {
        String y = mobilYol;
        mobilYol = null;
        if (y == null) return;
        File f = new File(y);
        if (f.isFile() && f.lastModified() != mobilZaman) {
            UyapMobilServisi.gonder("YB " + android.util.Base64.encodeToString(y.getBytes(StandardCharsets.UTF_8), android.util.Base64.NO_WRAP));
            ui.belgeAciliyor(f.getName());
        } else if (ui != null) ui.gecisRozeti("🏛  Orijinal Sayfa Görünümü");
    }

    // ------------------------------------------------------------------------------------ gelen belge
    /** VIEW / SEND ile gelen .udf/.usf → belgeler/ klasörüne kopyala; yolu döndür. */
    private String gelenBelge(Intent i) {
        if (i == null) return null;
        if (EYLEM_AC.equals(i.getAction())) {
            String y = i.getStringExtra(EK_YOL);
            return y != null && new File(y).isFile() && y.startsWith(UyapMobil.belgeler(this).getAbsolutePath()) ? y : null;
        }
        Uri u = null;
        if (Intent.ACTION_VIEW.equals(i.getAction())) u = i.getData();
        else if (Intent.ACTION_SEND.equals(i.getAction())) u = i.getParcelableExtra(Intent.EXTRA_STREAM);
        if (u == null) return null;
        try { return belgeAl(u); } catch (Exception e) {
            Tani.hata("uyapmobil", "gelen belge", e);
            Toast.makeText(this, "Belge alınamadı: " + e.getMessage(), Toast.LENGTH_LONG).show();
            return null;
        }
    }

    private String belgeAl(Uri u) throws IOException {
        String ad = adBul(u);
        byte[] bas = new byte[4];
        File hedefDizin = UyapMobil.belgeler(this);
        hedefDizin.mkdirs();
        File gecici = new File(hedefDizin, ".gelen.tmp");
        try (InputStream in = getContentResolver().openInputStream(u); OutputStream o = new FileOutputStream(gecici)) {
            if (in == null) throw new IOException("okunamadı");
            byte[] b = new byte[1 << 16];
            int n, top = 0;
            while ((n = in.read(b)) > 0) {
                if (top < 4) System.arraycopy(b, 0, bas, top, Math.min(4 - top, n));
                o.write(b, 0, n);
                top += n;
            }
        }
        String kucuk = ad.toLowerCase(Locale.ROOT);
        if (!kucuk.endsWith(".udf") && !kucuk.endsWith(".usf")) {
            boolean zip = bas[0] == 'P' && bas[1] == 'K';
            if (!zip) { gecici.delete(); throw new IOException("bu bir UDF/USF belgesi değil"); }
            ad = ad.replaceAll("\\.[A-Za-z0-9]{1,5}$", "") + ".udf";
        }
        ad = ad.replaceAll("[\\\\/:*?\"<>|]", "_");
        File hedef = new File(hedefDizin, ad);
        if (hedef.exists() && !ayniMi(hedef, gecici)) {
            String kok = ad.substring(0, ad.lastIndexOf('.')), uz = ad.substring(ad.lastIndexOf('.'));
            for (int k = 2; hedef.exists(); k++) hedef = new File(hedefDizin, kok + " (" + k + ")" + uz);
        }
        if (hedef.exists()) gecici.delete(); else if (!gecici.renameTo(hedef)) throw new IOException("kopyalanamadı");
        UyapMobilServisi.iceAlindi(hedef);
        UyapMobilServisi.kaynakKaydet(this, hedef, u, yazilabilir(u));
        Tani.yaz("uyapmobil", "belge geldi: " + hedef.getName() + " (" + u.getScheme() + ")");
        return hedef.getAbsolutePath();
    }

    private boolean yazilabilir(Uri u) {
        if ("file".equals(u.getScheme())) return u.getPath() != null && new File(u.getPath()).canWrite();
        try (android.os.ParcelFileDescriptor p = getContentResolver().openFileDescriptor(u, "rw")) { return p != null; }
        catch (Exception e) { return false; }
    }

    private static boolean ayniMi(File a, File b) {
        if (a.length() != b.length()) return false;
        try { return java.util.Arrays.equals(AdaletServisi.okuHepsi(new java.io.FileInputStream(a)), AdaletServisi.okuHepsi(new java.io.FileInputStream(b))); }
        catch (IOException e) { return false; }
    }

    private String adBul(Uri u) {
        String ad = null;
        if ("content".equals(u.getScheme())) {
            try (Cursor c = getContentResolver().query(u, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
                if (c != null && c.moveToFirst()) ad = c.getString(0);
            } catch (Exception ignored) { }
        }
        if (ad == null) ad = u.getLastPathSegment();
        if (ad == null || ad.trim().isEmpty()) ad = "Belge.udf";
        int s = ad.lastIndexOf('/');
        return s >= 0 ? ad.substring(s + 1) : ad;
    }

    // ------------------------------------------------------------------------------------ menü
    private static final String[] UYGULAMA = {"Belge aç (telefondan)…", "Yeniden aç ⟳", "Ekran ölçeği…",
            "Yazı tipi ekle (TTF, ör. Times New Roman)…", "Resmi editörü kur / güncelle", "Günlüğü gönder", "Editörü kapat"};

    @Override public String[] uygulamaKomutlari() { return UYGULAMA; }

    private void uygulamaMenusu() {
        new AlertDialog.Builder(this).setTitle("UYAP Editör " + UyapMobil.editorSurumu(this)).setItems(UYGULAMA, (d, w) -> uygulamaKomutu(w)).show();
    }

    @Override public void uygulamaKomutu(int w) {
        {
            switch (w) {
                case 0: dosyaSec(SEC_BELGE, "*/*"); break;
                case 1: yenidenBaslat(); break;
                case 2: olcekSor(); break;
                case 3: dosyaSec(SEC_FONT, "*/*"); break;
                case 4: kurulumSor(); break;
                case 5: gunlukPaylas(); break;
                case 6: UyapMobilServisi.gonder("X"); break;
                default: break;
            }
        }
    }

    @Override public void onBackPressed() {
        if (ui != null && ui.acikMi()) { ui.kapatHepsi(); return; }
        super.onBackPressed();
    }

    // ------------------------------------------------------------------------------------ editörden gelenler
    @Override public void menu(String json) { if (ui != null) ui.menuGeldi(json); }

    /**
     * Editör Aç / Kaydet / Farklı kaydet / Resim ekle penceresi açtı: telefonun kendi dosya seçicisi gösterilir
     * (İndirilenler, sdcard, Drive, WhatsApp…; depolama izni gerekmez). Açılan dosya uygulama klasörüne kopyalanır;
     * kaydederken editör uygulama klasörüne yazar, UyapMobilServisi.geriYaz seçilen yere kopyalar.
     */
    @Override public void dosyaIste(int no, boolean kaydet, String ad, String uzantilar) {
        if (seciciNo >= 0) UyapMobilServisi.seciciYanit(seciciNo, null, false);   // yarım kalmış önceki istek
        seciciNo = no;
        seciciKaydet = kaydet;
        seciciUzanti = uzantilar == null ? "" : uzantilar;
        String ilkUz = seciciUzanti.split(",")[0].trim();
        Intent i = new Intent(kaydet ? Intent.ACTION_CREATE_DOCUMENT : Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE);
        if (kaydet) {
            i.setType(mimeTuru(ilkUz));
            String a = ad;
            if ((a == null || a.trim().isEmpty()) && ui != null) a = ui.belgeAdi();      // PDF/ODT olarak kaydet: belgenin adı
            if (a == null || a.trim().isEmpty() || a.toLowerCase(Locale.ROOT).startsWith("isimsiz") || "UYAP Editör".equals(a)) a = "Belge";
            a = a.trim();
            if (!ilkUz.isEmpty() && !a.toLowerCase(Locale.ROOT).endsWith("." + ilkUz)) a = a.replaceAll("\\.[A-Za-z0-9]{1,5}$", "") + "." + ilkUz;
            i.putExtra(Intent.EXTRA_TITLE, a);
        } else i.setType("*/*");
        try { startActivityForResult(i, SEC_EDITOR); }
        catch (Exception e) {
            Toast.makeText(this, "Telefonun dosya seçicisi açılamadı; editörün kendi penceresi kullanılıyor", Toast.LENGTH_LONG).show();
            UyapMobilServisi.seciciYanit(no, null, true);
            seciciNo = -1;
        }
    }

    private static String mimeTuru(String uz) {
        switch (uz.toLowerCase(Locale.ROOT)) {
            case "pdf": return "application/pdf";
            case "odt": return "application/vnd.oasis.opendocument.text";
            case "html": case "htm": return "text/html";
            case "txt": return "text/plain";
            case "png": return "image/png";
            case "jpg": case "jpeg": return "image/jpeg";
            default: return "application/octet-stream";
        }
    }

    private void editorSecimi(int sonuc, Intent veri) {
        final int no = seciciNo;
        seciciNo = -1;
        if (no < 0) return;
        Uri u = sonuc == RESULT_OK && veri != null ? veri.getData() : null;
        if (u == null) { UyapMobilServisi.seciciYanit(no, null, false); return; }
        try { getContentResolver().takePersistableUriPermission(u, Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION); } catch (Exception ignored) { }
        try {
            String ad = adBul(u).replaceAll("[\\\\/:*?\"<>|]", "_");
            if (seciciKaydet) {
                String ilkUz = seciciUzanti.split(",")[0].trim();
                if (!ilkUz.isEmpty() && !ad.contains(".")) ad = ad + "." + ilkUz;
                File d = UyapMobil.belgeler(this);
                d.mkdirs();
                File yerel = new File(d, ad);
                if (yerel.exists() && !yerel.delete()) throw new IOException("eski kopya silinemedi");
                UyapMobilServisi.kaynakKaydet(this, yerel, u, true);
                UyapMobilServisi.seciciYanit(no, yerel.getAbsolutePath(), false);
            } else {
                String k = ad.toLowerCase(Locale.ROOT);
                String yol;
                if (k.endsWith(".udf") || k.endsWith(".usf")) { yol = belgeAl(u); ui.belgeAciliyor(ad); }   // kaydedince asıl dosyaya geri yazılır
                else {
                    File d = new File(UyapMobil.kok(this), "gelen");
                    d.mkdirs();
                    File h = new File(d, ad);
                    try (InputStream in = getContentResolver().openInputStream(u); OutputStream o = new FileOutputStream(h)) {
                        if (in == null) throw new IOException("okunamadı");
                        o.write(AdaletServisi.okuHepsi(in));
                    }
                    yol = h.getAbsolutePath();
                }
                UyapMobilServisi.seciciYanit(no, yol, false);
            }
        } catch (Exception e) {
            Tani.hata("uyapmobil", "dosya seçici", e);
            Toast.makeText(this, "Dosya alınamadı: " + e.getMessage(), Toast.LENGTH_LONG).show();
            UyapMobilServisi.seciciYanit(no, null, false);
        }
    }

    private void yenidenBaslat() {
        UyapMobilServisi.kapat(this);
        ekran.kapat();
        ekran.postDelayed(this::basla, 1200);
    }

    private void olcekSor() {
        final String[] ad = {"Çok büyük", "Büyük", "Orta (önerilen)", "Küçük (şerit menü tam sığar)", "Çok küçük"};
        final float[] deger = {640f, 720f, 820f, 960f, 1200f};
        new AlertDialog.Builder(this).setTitle("Ekran ölçeği (editör yeniden açılır)").setItems(ad, (d, w) -> {
            ayar().edit().putFloat("kisa_kenar", deger[w]).apply();
            yenidenBaslat();
        }).show();
    }

    private void dosyaSec(int kod, String tur) {
        Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType(tur);
        try { startActivityForResult(i, kod); } catch (Exception e) { Toast.makeText(this, "Dosya seçici açılamadı", Toast.LENGTH_SHORT).show(); }
    }

    @Override protected void onActivityResult(int kod, int sonuc, Intent veri) {
        super.onActivityResult(kod, sonuc, veri);
        if (kod == SEC_EDITOR) { editorSecimi(sonuc, veri); return; }
        if (kod == MOBIL_GORUNUM) { mobildenDonus(); return; }
        if (sonuc != RESULT_OK || veri == null || veri.getData() == null) return;
        Uri u = veri.getData();
        try { getContentResolver().takePersistableUriPermission(u, Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION); } catch (Exception ignored) { }
        if (kod == SEC_PAKET) { kur(u, adBul(u)); return; }
        if (kod == SEC_FONT) {
            String ad = adBul(u);
            if (!ad.toLowerCase(Locale.ROOT).matches(".*\\.(ttf|otf|ttc)$")) { Toast.makeText(this, "TTF/OTF yazı tipi seçin", Toast.LENGTH_LONG).show(); return; }
            try (InputStream in = getContentResolver().openInputStream(u)) {
                File d = UyapMobil.yaziTipleri(this);
                d.mkdirs();
                try (OutputStream o = new FileOutputStream(new File(d, ad))) { o.write(AdaletServisi.okuHepsi(in)); }
                Toast.makeText(this, "Yazı tipi eklendi: " + ad + " (editör yeniden açılınca geçerli)", Toast.LENGTH_LONG).show();
            } catch (Exception e) { Toast.makeText(this, "Eklenemedi: " + e.getMessage(), Toast.LENGTH_LONG).show(); }
            return;
        }
        if (kod == SEC_BELGE) {
            try {
                String f = belgeAl(u);
                ui.belgeAciliyor(new File(f).getName());
                if (UyapMobilServisi.calisiyor()) UyapMobilServisi.ac(this, f, 0, 0); else { bekleyenDosya = f; basla(); }
            } catch (Exception e) { Toast.makeText(this, "Açılamadı: " + e.getMessage(), Toast.LENGTH_LONG).show(); }
        }
    }

    /** Günlük paylaşım menüsüyle (WhatsApp, e-posta…) gönderilir: köprü + editör günlüğünün son kısmı metin olarak. */
    @Override public void gunlukGonder() { gunlukPaylas(); }

    private void gunlukPaylas() {
        try {
            StringBuilder sb = new StringBuilder("UYAP Editör " + UyapMobil.editorSurumu(this) + " · uygulama " + BuildConfigSurum.surum(this)
                    + " · Android " + Build.VERSION.RELEASE + " · " + Build.MANUFACTURER + " " + Build.MODEL + "\n\n---- köprü ----\n");
            File k = new File(UyapMobil.kok(this), "kopru.log");
            if (k.isFile()) sb.append(sonu(k, 30000));
            sb.append("\n---- editör ----\n");
            File f = UyapMobil.gunluk(this);
            if (f.isFile()) sb.append(sonu(f, 60000));
            Intent i = new Intent(Intent.ACTION_SEND).setType("text/plain")
                    .putExtra(Intent.EXTRA_SUBJECT, "UYAP Editör günlüğü").putExtra(Intent.EXTRA_TEXT, sb.toString());
            startActivity(Intent.createChooser(i, "Günlüğü gönder"));
            return;
        } catch (Exception e) { Tani.hata("uyapmobil", "günlük paylaş", e); }
        try {
            File f = UyapMobil.gunluk(this);
            File d = new File(android.os.Environment.getExternalStoragePublicDirectory(android.os.Environment.DIRECTORY_DOWNLOADS), "CanEditor/tani");
            d.mkdirs();
            File h = new File(d, "uyap_editor_gunluk.txt");
            try (OutputStream o = new FileOutputStream(h)) {
                if (f.isFile()) o.write(AdaletServisi.okuHepsi(new java.io.FileInputStream(f)));
                File k = new File(UyapMobil.kok(this), "kopru.log");
                if (k.isFile()) { o.write("\n---- köprü ----\n".getBytes(StandardCharsets.UTF_8)); o.write(AdaletServisi.okuHepsi(new java.io.FileInputStream(k))); }
            }
            Toast.makeText(this, "Günlük: İndirilenler/CanEditor/tani/uyap_editor_gunluk.txt", Toast.LENGTH_LONG).show();
        } catch (Exception e) { Toast.makeText(this, "Günlük yazılamadı: " + e.getMessage(), Toast.LENGTH_LONG).show(); }
    }

    private static String sonu(File f, int enFazla) throws IOException {
        byte[] b = AdaletServisi.okuHepsi(new java.io.FileInputStream(f));
        int bas = Math.max(0, b.length - enFazla);
        return new String(b, bas, b.length - bas, StandardCharsets.UTF_8);
    }

    @Override public void mobil(String satir) { if (ui != null) ui.mobilSatir(satir); }

    @Override public void acilmadi(String neden) { if (ui != null) ui.acilmadi(neden); }

    private int dp(int v) { return Math.round(v * getResources().getDisplayMetrics().density); }
}
