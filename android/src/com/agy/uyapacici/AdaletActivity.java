package com.agy.uyapacici;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;
import java.io.InputStream;
import java.io.RandomAccessFile;

/**
 * 🏛️ Adalet E-İmza yönetim ekranı: kurulum, başlat/durdur, PIN penceresi izni, günlük.
 * Termux gerekmez: Java 21 uygulamanın içindedir; resmi Adalet E-İmza Adalet'in sunucusundan indirilir.
 */
public class AdaletActivity extends Activity {
    private static final int DOSYA_SEC = 7101;
    private TextView tvDurum, tvKurulum;
    private final Handler h = new Handler(Looper.getMainLooper());
    private final Runnable yenile = new Runnable() {
        @Override public void run() { durumuGoster(); h.postDelayed(this, 2000); }
    };

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        Tani.baglam(this);
        float d = getResources().getDisplayMetrics().density;
        ScrollView sv = new ScrollView(this);
        LinearLayout k = new LinearLayout(this);
        k.setOrientation(LinearLayout.VERTICAL);
        int p = (int) (18 * d);
        k.setPadding(p, p, p, p);
        sv.addView(k);

        TextView baslik = new TextView(this);
        baslik.setText("🏛️ Adalet E-İmza (Termux'suz)");
        baslik.setTextSize(22);
        k.addView(baslik);
        TextView aciklama = new TextView(this);
        aciklama.setText("UYAP Avukat Portalı'na Chrome'dan e-imza ile giriş ve imzalama için resmi Adalet E-İmza "
                + "uygulaması bu telefonda, UdeMobile'ın içindeki Java ile çalışır (127.0.0.1:5975). "
                + "E-imza okuyucunuzu OTG ile takın; kart, UdeMobile'ın USB köprüsünden okunur.\n\n"
                + "Resmi uygulama UdeMobile'a gömülü değildir; ilk kurulumda Adalet Bakanlığı'nın sunucusundan "
                + "(cdn.uyap.gov.tr) indirilir.");
        aciklama.setPadding(0, (int) (8 * d), 0, (int) (12 * d));
        k.addView(aciklama);

        // 🐞 Ayrıntılı tanı günlüğü: en üstte (sorun bildirmek için önce bunu başlatın)
        btnTani = dugme("", v -> taniDegistir());
        k.addView(btnTani);
        tvTani = new TextView(this);
        tvTani.setTextSize(12);
        k.addView(tvTani);
        taniGoster();

        tvKurulum = new TextView(this);
        tvKurulum.setTextSize(15);
        k.addView(tvKurulum);
        tvDurum = new TextView(this);
        tvDurum.setTextSize(15);
        tvDurum.setPadding(0, (int) (6 * d), 0, (int) (12 * d));
        k.addView(tvDurum);

        k.addView(dugme("⬇️ Resmi uygulamayı indir / güncelle", v -> indir()));
        k.addView(dugme("📂 Dosyadan kur (.zip / .jar)", v -> {
            Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*");
            startActivityForResult(i, DOSYA_SEC);
        }));
        k.addView(dugme("▶️ Başlat", v -> { AdaletServisi.baslat(this); Toast.makeText(this, "Başlatılıyor…", Toast.LENGTH_SHORT).show(); }));
        k.addView(dugme("⏹️ Durdur", v -> AdaletServisi.durdur(this)));
        k.addView(dugme("🔐 PIN penceresi izni (diğer uygulamaların üzerinde göster)", v -> {
            if (Build.VERSION.SDK_INT >= 23) {
                startActivity(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:" + getPackageName())));
            }
        }));
        k.addView(dugme("🌐 UYAP Avukat Portalı'nı aç (Chrome)", v ->
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse("https://avukat.uyap.gov.tr")))));
        k.addView(dugme("📜 Günlük (son satırlar)", v -> gunlukGoster()));

        TextView not = new TextView(this);
        not.setText("\nNotlar:\n• Chrome \"yerel ağdaki cihazlara erişim\" izni sorarsa İzin Ver deyin.\n"
                + "• Sayfa PIN'i kendisi sormazsa UdeMobile'ın PIN penceresi açılır (yukarıdaki izni verin).\n"
                + "• Kart türleri: resmi uygulamanın USB üzerinden doğrudan konuştuğu kartlar (AKİS / Kamu SM) desteklenir. "
                + "Üretici sürücüsü (PKCS#11) isteyen tokenlar (bazı SafeNet/ArkSigner modelleri) Android'de çalışmayabilir.\n"
                + "• Pil tasarrufu UdeMobile'ı kapatmasın diye bildirimdeki servis açık kalır; işiniz bitince Durdur'a basın.");
        not.setTextSize(13);
        k.addView(not);
        setContentView(sv);
        if (Build.VERSION.SDK_INT >= 33) requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"}, 1);
    }

    private Button btnTani;
    private TextView tvTani;

    private void taniGoster() {
        java.io.File f = Tani.dosya();
        btnTani.setText(f == null ? "🔴 Ayrıntılı tanı günlüğünü BAŞLAT" : "⏹ Günlüğü DURDUR ve gönder");
        tvTani.setText(f == null ? "Sorun bildirmek için: başlatın → sorunu yaşayın (kart takma, imza, Chrome girişi) → durdurup gönderin."
                : "Kayıt sürüyor: " + f.getAbsolutePath() + "\nPIN ve belge içerikleri yazılmaz.");
    }

    private void taniDegistir() {
        if (Tani.dosya() == null) {
            java.io.File f = Tani.baslat(this);
            Toast.makeText(this, "Tanı günlüğü başladı: " + f.getName(), Toast.LENGTH_LONG).show();
            // Resmi uygulama DEBUG düzeyinde yeniden başlasın
            if (AdaletKurulum.jarDosyasi(this).exists()) { AdaletServisi.durdur(this); AdaletServisi.baslat(this); }
        } else {
            Tani.ozet(this);
            java.io.File f = Tani.durdur(this);
            Tani.paylas(this, f);
        }
        taniGoster();
    }

    private Button dugme(String metin, View.OnClickListener l) {
        Button b = new Button(this);
        b.setText(metin);
        b.setAllCaps(false);
        b.setOnClickListener(l);
        return b;
    }

    @Override protected void onResume() { super.onResume(); h.post(yenile); }

    @Override protected void onPause() { h.removeCallbacks(yenile); super.onPause(); }

    private volatile boolean denetimSuruyor = false;

    private void durumuGoster() {
        String s = AdaletKurulum.kuruluSurum(this);
        tvKurulum.setText(s == null ? "📦 Resmi uygulama: kurulu değil" : "📦 Resmi uygulama: Adalet E-İmza " + s + " (kurulu)");
        // Port denetimi ağ işlemidir: ana iş parçacığında yapılırsa Android uygulamayı kapatır (NetworkOnMainThread).
        if (denetimSuruyor) return;
        denetimSuruyor = true;
        new Thread(() -> {
            final boolean acik = AdaletServisi.portAcik();
            final String dur = AdaletServisi.durum();
            final boolean calisiyor = AdaletServisi.calisiyor();
            runOnUiThread(() -> {
                denetimSuruyor = false;
                if (!isFinishing()) tvDurum.setText((acik ? "🟢 " : calisiyor ? "🟡 " : "⚪ ") + dur);
            });
        }, "adalet-durum").start();
    }

    private void indir() {
        final AlertDialog ilerleme = new AlertDialog.Builder(this).setTitle("Adalet E-İmza").setMessage("Hazırlanıyor…")
                .setCancelable(false).create();
        ilerleme.show();
        new Thread(() -> {
            try {
                String surum = AdaletKurulum.indirKur(this, s -> runOnUiThread(() -> ilerleme.setMessage(s)));
                runOnUiThread(() -> {
                    ilerleme.dismiss();
                    Toast.makeText(this, "Adalet E-İmza " + surum + " kuruldu. Başlatılıyor…", Toast.LENGTH_LONG).show();
                    AdaletServisi.durdur(this);
                    AdaletServisi.baslat(this);
                });
            } catch (Exception e) {
                runOnUiThread(() -> { ilerleme.dismiss(); hata("İndirme/kurulum başarısız: " + e.getMessage()); });
            }
        }).start();
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req != DOSYA_SEC || res != RESULT_OK || data == null || data.getData() == null) return;
        final Uri u = data.getData();
        new Thread(() -> {
            try (InputStream in = getContentResolver().openInputStream(u)) {
                String ad = u.getLastPathSegment();
                String surum = AdaletKurulum.dosyadanKur(this, in, ad);
                runOnUiThread(() -> {
                    Toast.makeText(this, "Adalet E-İmza " + surum + " kuruldu.", Toast.LENGTH_LONG).show();
                    AdaletServisi.durdur(this);
                    AdaletServisi.baslat(this);
                });
            } catch (Exception e) {
                runOnUiThread(() -> hata("Kurulum başarısız: " + e.getMessage()));
            }
        }).start();
    }

    private void gunlukGoster() {
        File f = AdaletServisi.gunluk(this);
        String metin;
        try (RandomAccessFile r = new RandomAccessFile(f, "r")) {
            long boy = r.length(), bas = Math.max(0, boy - 12000);
            byte[] b = new byte[(int) (boy - bas)];
            r.seek(bas);
            r.readFully(b);
            metin = new String(b, "UTF-8");
        } catch (Exception e) {
            metin = "Günlük yok (servis henüz çalışmadı).";
        }
        TextView tv = new TextView(this);
        tv.setText(metin);
        tv.setTextSize(11);
        tv.setTextIsSelectable(true);
        ScrollView sv = new ScrollView(this);
        sv.addView(tv);
        new AlertDialog.Builder(this).setTitle("Adalet E-İmza günlüğü").setView(sv).setPositiveButton("Kapat", null).show();
    }

    private void hata(String m) {
        new AlertDialog.Builder(this).setTitle("Adalet E-İmza").setMessage(m).setPositiveButton("Tamam", null).show();
    }
}
