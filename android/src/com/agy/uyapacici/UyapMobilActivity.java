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
public class UyapMobilActivity extends Activity implements UyapMobilServisi.Dinleyici {
    private static final int SEC_BELGE = 41, SEC_PAKET = 42, SEC_FONT = 43;
    /** CanEditor'dan "Orijinal UYAP Editör'de aç": belge zaten belgeler/ klasöründe (EK_YOL). */
    public static final String EYLEM_AC = "com.agy.uyapacici.UYAP_EDITORDE_AC", EK_YOL = "yol";

    private EkranView ekran;
    private TextView durum;
    private Button ctrl, alt, shift, kip;
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

        LinearLayout kok = new LinearLayout(this);
        kok.setOrientation(LinearLayout.VERTICAL);
        kok.setBackgroundColor(Color.rgb(46, 52, 64));
        FrameLayout alan = new FrameLayout(this);
        ekran = new EkranView(this);
        alan.addView(ekran, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        durum = new TextView(this);
        durum.setTextColor(Color.WHITE);
        durum.setBackgroundColor(0xCC1E2430);
        durum.setPadding(dp(16), dp(12), dp(16), dp(12));
        durum.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        durum.setGravity(Gravity.CENTER);
        FrameLayout.LayoutParams dl = new FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.CENTER);
        alan.addView(durum, dl);
        kok.addView(alan, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        kok.addView(tusCubugu(), new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(46)));
        setContentView(kok);
        ekran.degistiriciDinleyici = y -> runOnUiThread(this::degistiricileriGoster);

        bekleyenDosya = gelenBelge(getIntent());
        UyapMobilServisi.dinleyiciAyarla(this);
        if (izinIste()) ekran.post(this::basla);
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
            durum.setVisibility(View.GONE);
            ekran.requestFocus();
            if (!ayar().getBoolean("ipucu", false)) {
                ayar().edit().putBoolean("ipucu", true).apply();
                Toast.makeText(this, "İpucu: iki parmakla yakınlaştırın · uzun basış = sağ tık · ⋮ > Ekran ölçeği", Toast.LENGTH_LONG).show();
            }
        });
    }

    @Override public void kapandi(final String neden) {
        runOnUiThread(() -> {
            ekran.kapat();
            if (baslatildi && !"kurulu değil".equals(neden)) durumGoster("UYAP Editör kapandı. Yeniden açmak için ⟳");
        });
    }

    private void durumGoster(String m) {
        durum.setText(m);
        durum.setVisibility(View.VISIBLE);
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

    // ------------------------------------------------------------------------------------ ek tuş çubuğu
    private View tusCubugu() {
        HorizontalScrollView hs = new HorizontalScrollView(this);
        hs.setBackgroundColor(Color.rgb(30, 34, 42));
        hs.setHorizontalScrollBarEnabled(false);
        LinearLayout s = new LinearLayout(this);
        s.setOrientation(LinearLayout.HORIZONTAL);
        hs.addView(s);
        s.addView(dugme("⌨", v -> ekran.klavyeAcKapa()));
        kip = dugme("✋", v -> { ekran.kaydirKipi = !ekran.kaydirKipi; kipGoster(true); });
        s.addView(kip);
        s.addView(dugme("Esc", v -> ekran.tus(27, 0)));
        s.addView(dugme("Tab", v -> ekran.tus(9, 0)));
        ctrl = dugme("Ctrl", v -> yapiskanDegis(EkranView.CTRL));
        alt = dugme("Alt", v -> yapiskanDegis(EkranView.ALT));
        shift = dugme("⇧", v -> yapiskanDegis(EkranView.SHIFT));
        s.addView(ctrl);
        s.addView(alt);
        s.addView(shift);
        s.addView(dugme("←", v -> ekran.tus(37, 0)));
        s.addView(dugme("↑", v -> ekran.tus(38, 0)));
        s.addView(dugme("↓", v -> ekran.tus(40, 0)));
        s.addView(dugme("→", v -> ekran.tus(39, 0)));
        s.addView(dugme("Home", v -> ekran.tus(36, 0)));
        s.addView(dugme("End", v -> ekran.tus(35, 0)));
        s.addView(dugme("Del", v -> ekran.tus(127, 0)));
        s.addView(dugme("💾", v -> ekran.tus('S', EkranView.CTRL)));
        s.addView(dugme("↶", v -> ekran.tus('Z', EkranView.CTRL)));
        s.addView(dugme("↷", v -> ekran.tus('Y', EkranView.CTRL)));
        s.addView(dugme("📋", v -> yapistir()));
        s.addView(dugme("⤢", v -> ekran.sigdir()));
        s.addView(dugme("⋮", v -> menu()));
        kipGoster(false);
        return hs;
    }

    private Button dugme(String y, View.OnClickListener l) {
        Button b = new Button(this);
        b.setText(y);
        b.setAllCaps(false);
        b.setTextColor(Color.WHITE);
        b.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        b.setTypeface(Typeface.DEFAULT_BOLD);
        b.setBackgroundColor(Color.TRANSPARENT);
        b.setMinWidth(dp(48));
        b.setMinimumWidth(dp(48));
        b.setPadding(dp(10), 0, dp(10), 0);
        b.setOnClickListener(l);
        b.setFocusable(false);     // odak editör ekranında kalsın (klavye kapanmasın)
        return b;
    }

    private void yapiskanDegis(int bit) {
        ekran.yapiskan ^= bit;
        degistiricileriGoster();
    }

    private void degistiricileriGoster() {
        int y = ekran.yapiskan;
        ctrl.setTextColor((y & EkranView.CTRL) != 0 ? Color.rgb(255, 196, 0) : Color.WHITE);
        alt.setTextColor((y & EkranView.ALT) != 0 ? Color.rgb(255, 196, 0) : Color.WHITE);
        shift.setTextColor((y & EkranView.SHIFT) != 0 ? Color.rgb(255, 196, 0) : Color.WHITE);
    }

    private void kipGoster(boolean bildir) {
        kip.setText(ekran.kaydirKipi ? "✋" : "🖱");
        if (bildir) Toast.makeText(this, ekran.kaydirKipi ? "Kaydırma: tek parmak belgeyi kaydırır" : "Seçim: tek parmak metin seçer / sürükler", Toast.LENGTH_SHORT).show();
    }

    private void yapistir() {
        ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        if (cm == null || !cm.hasPrimaryClip()) return;
        ClipData c = cm.getPrimaryClip();
        if (c == null || c.getItemCount() == 0) return;
        CharSequence t = c.getItemAt(0).coerceToText(this);
        if (t == null) return;
        UyapMobilServisi.gonder("Y " + UyapMobilServisi.hex(t.toString().getBytes(StandardCharsets.UTF_8)));
        ekran.postDelayed(() -> ekran.tus('V', EkranView.CTRL), 120);
    }

    // ------------------------------------------------------------------------------------ menü
    private void menu() {
        String[] s = {"Belge aç…", "Yeniden aç ⟳", "Ekran ölçeği…", "Yazı tipi ekle (TTF, ör. Times New Roman)…",
                "Resmi editörü kur / güncelle", "Günlüğü paylaş", "Editörü kapat"};
        new AlertDialog.Builder(this).setTitle("UYAP Editör " + UyapMobil.editorSurumu(this)).setItems(s, (d, w) -> {
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
        }).show();
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
                if (UyapMobilServisi.calisiyor()) UyapMobilServisi.ac(this, f, 0, 0); else { bekleyenDosya = f; basla(); }
            } catch (Exception e) { Toast.makeText(this, "Açılamadı: " + e.getMessage(), Toast.LENGTH_LONG).show(); }
        }
    }

    private void gunlukPaylas() {
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

    private int dp(int v) { return Math.round(v * getResources().getDisplayMetrics().density); }
}
