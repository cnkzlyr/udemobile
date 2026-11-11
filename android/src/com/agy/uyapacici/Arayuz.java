package com.agy.uyapacici;

import android.animation.Animator;
import android.animation.AnimatorListenerAdapter;
import android.animation.ValueAnimator;
import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Build;
import android.text.InputType;
import android.text.TextUtils;
import android.util.Base64;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.animation.DecelerateInterpolator;
import android.view.animation.PathInterpolator;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * UYAP Editör — dokunmatik arayüz (3.23.0): CanEditor (UdeMobile) düzeni, içinde ORİJİNAL UYAP Editör.
 *
 *  ┌──────────────────────────────┐  üst çubuk: 🏛 · belge adı · [💾 Kaydet] · [📱 Mobil ⇄ 🖥 Sayfa] · ☰
 *  │ ↶ ↷ │ Times New R… ▾ │ 12 ▾ │ K T A S │ renk vurgu │ hizalama │ liste girinti │ ⌨
 *  │   SAYFA GÖRÜNÜMÜ: resmi editör (Java 14, köprü ile), başlık çubuğu gizli, üstte cetvel
 *  │                                 │  MOBİL GÖRÜNÜM: aynı belge CanEditor'ın akış editöründe (EditorActivity)
 *  │ [− %100 Sığdır + ↔ ↕]      (✏)  │  yakınlaştırma kapsülü (bulanık cam) · klavye düğmesi
 *  └──────────────────────────────┘  ☰: CanEditor menüsü (Kaydet, Aç, Farklı kaydet, Yazdır, E-imza) + tüm UYAP menüleri
 *
 * Komutlar editörün kendi menü öğelerine/araç düğmelerine tıklanarak çalışır (köprü: MN → MENU, MC/MS/MT),
 * yani davranış resmi editörle birebir aynıdır. Şerit menü varsayılan olarak gizlidir (SG).
 */
final class Arayuz {
    interface Uygulama {
        String[] uygulamaKomutlari();
        void uygulamaKomutu(int sira);
        void mobilGorunum(String yol);
    }

    private final Activity a;
    private final Uygulama uyg;
    private final SharedPreferences ayar;
    final FrameLayout kok;
    final EkranView ekran;
    private final Map<String, Bitmap> simgeler = new HashMap<>();
    private final Set<String> acikBolumler = new HashSet<>();

    static final int UST_YUKSEKLIK = 56 + 52;
    private FrameLayout ustKap, altKap;
    private TextView yuzdeTv, fontTv, boyutTv;
    private LinearLayout tusSatiri;
    private TextView baslikTv, altBaslikTv;
    private LinearLayout durumKart;
    private TextView durumTv;
    private ProgressBar durumCark;
    private final Map<String, ImageView> bicimDugmeleri = new HashMap<>();
    private TextView ctrlTv, altTv, shiftTv, kipTv;

    private JSONObject son;
    private int bosYanit;
    /** Giriş araç çubuklarından tanınan düğmeler: ad → {id, etkin, seçili}. */
    private final Map<String, int[]> komut = new HashMap<>();
    private final List<JSONObject> combolar = new ArrayList<>();
    private String belgeAdi = "UYAP Editör", belgeYolu;
    private long acilisBekleme;

    private FrameLayout cekmece, sayfa;
    private LinearLayout cekmeceIcerik;
    private Runnable sayfaKapaninca;

    Arayuz(Activity a, SharedPreferences ayar, Uygulama uyg) {
        this.a = a;
        this.ayar = ayar;
        this.uyg = uyg;
        String k = ayar.getString("menu_acik", "Dosya");
        for (String s : k.split("\n")) if (!s.isEmpty()) acikBolumler.add(s);

        kok = new FrameLayout(a);
        kok.setBackgroundColor(Color.rgb(232, 234, 237));
        ekran = new EkranView(a);
        ekran.setBackgroundColor(Color.rgb(232, 234, 237));
        FrameLayout.LayoutParams el = tam();
        el.topMargin = dp(UST_YUKSEKLIK);     // belge üst çubuğun altından başlar (cetvel görünür)
        kok.addView(ekran, el);
        ekran.degistiriciDinleyici = y -> a.runOnUiThread(this::degistiricileriGoster);

        ustKap = cubuk(true);
        kok.addView(ustKap, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.TOP));
        altKap = new FrameLayout(a);          // yüzen öğeler: tuş satırı, yakınlaştırma kapsülü, klavye düğmesi
        kok.addView(altKap, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM));
        ustDoldur();
        altDoldur();
        durumKartiKur();
        sistemCubuklari();
    }

    private void sistemCubuklari() {
        try {
            a.getWindow().setStatusBarColor(Color.WHITE);
            a.getWindow().setNavigationBarColor(Color.WHITE);
            int f = 0;
            if (Build.VERSION.SDK_INT >= 23) f |= View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
            if (Build.VERSION.SDK_INT >= 26) f |= View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
            a.getWindow().getDecorView().setSystemUiVisibility(f);
        } catch (Exception ignored) { }
    }

    // ==================================================================================== çubuklar (bulanık cam)
    /** Ekranın kendi altında kalan parçasını çizip bulanıklaştıran zemin (Android 12+ RenderEffect). */
    private final class BulanikZemin extends View {
        private final int[] ben = new int[2], o = new int[2];
        private final boolean bulanik = Build.VERSION.SDK_INT >= 31;

        BulanikZemin(Context c) {
            super(c);
            if (bulanik) {
                setRenderEffect(android.graphics.RenderEffect.createBlurEffect(dp(18), dp(18), android.graphics.Shader.TileMode.CLAMP));
                ekran.aynalar.add(this);
            }
        }

        /** Kendi boyutunu dayatmasın: View varsayılanı AT_MOST'ta tüm yüksekliği alıyordu (3.22.0'da çubuk bütün ekranı kapladı). */
        @Override protected void onMeasure(int w, int h) {
            setMeasuredDimension(View.MeasureSpec.getMode(w) == View.MeasureSpec.EXACTLY ? View.MeasureSpec.getSize(w) : 0,
                    View.MeasureSpec.getMode(h) == View.MeasureSpec.EXACTLY ? View.MeasureSpec.getSize(h) : 0);
        }

        @Override protected void onDraw(Canvas c) {
            if (bulanik) {
                getLocationInWindow(ben);
                ekran.getLocationInWindow(o);
                c.drawColor(Color.rgb(232, 234, 237));
                ekran.aynaCiz(c, ben[0] - o[0], ben[1] - o[1]);
                c.drawColor(Tasarim.CAM);
            } else c.drawColor(Tasarim.CAM_ESKI);
        }
    }

    private FrameLayout cubuk(boolean ust) {
        FrameLayout f = new FrameLayout(a);
        f.addView(new BulanikZemin(a), tam());
        View cizgi = new View(a);
        cizgi.setBackgroundColor(0x1F000000);
        f.addView(cizgi, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 1, ust ? Gravity.BOTTOM : Gravity.TOP));
        LinearLayout ic = new LinearLayout(a);
        ic.setOrientation(LinearLayout.VERTICAL);
        f.addView(ic, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        f.setClickable(true);    // çubuğa dokunmak belgeye geçmesin
        if (Build.VERSION.SDK_INT >= 21) f.setElevation(dp(ust ? 3 : 6));
        return f;
    }

    private LinearLayout ic(FrameLayout f) { return (LinearLayout) f.getChildAt(2); }

    private void ustDoldur() {
        // 1. satır: 🏛 · belge adı · Kaydet · Mobil/Sayfa · ☰  (CanEditor üst çubuğu)
        LinearLayout s = new LinearLayout(a);
        s.setOrientation(LinearLayout.HORIZONTAL);
        s.setGravity(Gravity.CENTER_VERTICAL);
        s.setPadding(dp(8), 0, dp(4), 0);
        TextView logo = metin("🏛️", 20, Tasarim.VURGU, false);
        logo.setPadding(dp(8), dp(8), dp(8), dp(8));
        logo.setBackground(Tasarim.dalga(null, dp(20)));
        logo.setOnClickListener(v -> cekmeceAc());
        s.addView(logo);
        LinearLayout yazi = new LinearLayout(a);
        yazi.setOrientation(LinearLayout.VERTICAL);
        yazi.setPadding(dp(4), 0, dp(4), 0);
        baslikTv = metin(belgeAdi, 15, Tasarim.METIN, true);
        baslikTv.setSingleLine(true);
        baslikTv.setEllipsize(TextUtils.TruncateAt.MIDDLE);
        altBaslikTv = metin("Orijinal UYAP Editör · Sayfa görünümü", 11, Tasarim.IKINCIL, false);
        altBaslikTv.setSingleLine(true);
        altBaslikTv.setEllipsize(TextUtils.TruncateAt.END);
        yazi.addView(baslikTv);
        yazi.addView(altBaslikTv);
        yazi.setOnClickListener(v -> cekmeceAc());
        s.addView(yazi, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        // mavi Kaydet
        ImageView kaydet = new ImageView(a);
        kaydet.setImageDrawable(Tasarim.simge(a, Tasarim.S.KAYDET, Color.WHITE));
        kaydet.setPadding(dp(10), dp(8), dp(10), dp(8));
        kaydet.setBackground(Tasarim.dalga(Tasarim.yuvarlak(Tasarim.VURGU, dp(10)), dp(10)));
        if (Build.VERSION.SDK_INT >= 21) kaydet.setElevation(dp(2));
        kaydet.setContentDescription("Kaydet");
        kaydet.setOnClickListener(v -> { pulse(v); kaydet(); });
        LinearLayout.LayoutParams kl = new LinearLayout.LayoutParams(dp(52), dp(40));
        kl.setMargins(dp(4), 0, dp(6), 0);
        s.addView(kaydet, kl);
        // Mobil ⇄ Sayfa
        TextView mobil = metin("📱", 19, Tasarim.METIN, false);
        mobil.setGravity(Gravity.CENTER);
        mobil.setBackground(Tasarim.dalga(Tasarim.yuvarlak(Color.rgb(241, 243, 244), dp(10)), dp(10)));
        mobil.setOnClickListener(v -> { pulse(v); mobilGorunum(); });
        mobil.setOnLongClickListener(v -> { Toast.makeText(a, "Mobil akış görünümü (CanEditor)", Toast.LENGTH_SHORT).show(); return true; });
        LinearLayout.LayoutParams ml = new LinearLayout.LayoutParams(dp(46), dp(40));
        ml.setMargins(0, 0, dp(2), 0);
        s.addView(mobil, ml);
        s.addView(ikonDugme(Tasarim.S.MENU, "Menü", v -> cekmeceAc()));
        ic(ustKap).addView(s, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(56)));

        // 2. satır: araç çubuğu (CanEditor gibi): ↶ ↷ │ yazı tipi │ boyut │ K T A S │ renk vurgu │ hizalama │ liste │ ⌨
        HorizontalScrollView bh = new HorizontalScrollView(a);
        bh.setHorizontalScrollBarEnabled(false);
        LinearLayout b = new LinearLayout(a);
        b.setOrientation(LinearLayout.HORIZONTAL);
        b.setGravity(Gravity.CENTER_VERTICAL);
        b.setPadding(dp(4), 0, dp(8), 0);
        bh.addView(b);
        b.addView(ikonDugme(Tasarim.S.GERI_AL, "Geri al", v -> ekran.tus('Z', EkranView.CTRL)));
        b.addView(ikonDugme(Tasarim.S.YINELE, "Yinele", v -> ekran.tus('Y', EkranView.CTRL)));
        b.addView(ayrac());
        fontTv = secimKutusu("Times New Roman", dp(128), v -> { if (combolar.size() > 1) listeSec("Yazı tipi", combolar.get(1)); else hazirlaniyor(); });
        b.addView(fontTv);
        boyutTv = secimKutusu("12", dp(58), v -> { if (combolar.size() > 2) listeSec("Boyut", combolar.get(2)); else hazirlaniyor(); });
        b.addView(boyutTv);
        b.addView(ayrac());
        bicimDugmesi(b, "kalin", Tasarim.S.KALIN, "Kalın");
        bicimDugmesi(b, "italik", Tasarim.S.ITALIK, "İtalik");
        bicimDugmesi(b, "alti", Tasarim.S.ALTI, "Altı çizili");
        bicimDugmesi(b, "ustu", Tasarim.S.USTU_CIZILI, "Üstü çizili");
        bicimDugmesi(b, "renk", Tasarim.S.RENK, "Metin rengi");
        bicimDugmesi(b, "vurgu", Tasarim.S.VURGULA, "Vurgu");
        b.addView(ayrac());
        bicimDugmesi(b, "sol", Tasarim.S.SOL, "Sola hizala");
        bicimDugmesi(b, "orta", Tasarim.S.ORTA, "Ortala");
        bicimDugmesi(b, "sag", Tasarim.S.SAG, "Sağa hizala");
        bicimDugmesi(b, "iki", Tasarim.S.IKI_YANA, "İki yana yasla");
        b.addView(ayrac());
        bicimDugmesi(b, "madde", Tasarim.S.MADDE, "Madde işaretli liste");
        bicimDugmesi(b, "numara", Tasarim.S.NUMARA, "Numaralı liste");
        bicimDugmesi(b, "girinti_az", Tasarim.S.GIRINTI_AZ, "Girintiyi azalt");
        bicimDugmesi(b, "girinti_cok", Tasarim.S.GIRINTI_COK, "Girintiyi artır");
        b.addView(ayrac());
        b.addView(ikonDugme(Tasarim.S.BICIM, "Tüm biçim seçenekleri", v -> bicimSayfasi(0)));
        b.addView(ikonDugme(Tasarim.S.TUSLAR, "Ek tuşlar (Esc, Ctrl, oklar…)", v -> tuslariAcKapa()));
        ic(ustKap).addView(bh, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(52)));
    }

    private void hazirlaniyor() {
        Toast.makeText(a, "Editör menüsü hazırlanıyor…", Toast.LENGTH_SHORT).show();
        iste(0);
    }

    private TextView secimKutusu(String m, int genislik, View.OnClickListener l) {
        TextView t = metin(m + "  ▾", 14, Tasarim.METIN, false);
        t.setSingleLine(true);
        t.setEllipsize(TextUtils.TruncateAt.END);
        t.setGravity(Gravity.CENTER_VERTICAL);
        t.setPadding(dp(10), 0, dp(8), 0);
        android.graphics.drawable.GradientDrawable g = Tasarim.yuvarlak(Color.WHITE, dp(8));
        g.setStroke(Math.max(1, dp(1)), Tasarim.CIZGI);
        t.setBackground(Tasarim.dalga(g, dp(8)));
        t.setOnClickListener(v -> { pulse(v); l.onClick(v); });
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(genislik, dp(38));
        lp.setMargins(dp(3), 0, dp(3), 0);
        t.setLayoutParams(lp);
        return t;
    }

    private void altDoldur() {
        // ek tuş satırı (bulanık cam, açılır/kapanır)
        FrameLayout tk = new FrameLayout(a);
        tk.addView(new BulanikZemin(a), tam());
        HorizontalScrollView th = new HorizontalScrollView(a);
        th.setHorizontalScrollBarEnabled(false);
        tusSatiri = new LinearLayout(a);
        tusSatiri.setOrientation(LinearLayout.HORIZONTAL);
        tusSatiri.setGravity(Gravity.CENTER_VERTICAL);
        tusSatiri.setPadding(dp(6), dp(6), dp(6), dp(6));
        th.addView(tusSatiri);
        tk.addView(th, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        tusSatiri.addView(tusCipi("Esc", v -> ekran.tus(27, 0)));
        tusSatiri.addView(tusCipi("Tab", v -> ekran.tus(9, 0)));
        ctrlTv = tusCipi("Ctrl", v -> yapiskan(EkranView.CTRL));
        altTv = tusCipi("Alt", v -> yapiskan(EkranView.ALT));
        shiftTv = tusCipi("⇧", v -> yapiskan(EkranView.SHIFT));
        tusSatiri.addView(ctrlTv);
        tusSatiri.addView(altTv);
        tusSatiri.addView(shiftTv);
        tusSatiri.addView(tusCipi("←", v -> ekran.tus(37, 0)));
        tusSatiri.addView(tusCipi("↑", v -> ekran.tus(38, 0)));
        tusSatiri.addView(tusCipi("↓", v -> ekran.tus(40, 0)));
        tusSatiri.addView(tusCipi("→", v -> ekran.tus(39, 0)));
        tusSatiri.addView(tusCipi("Home", v -> ekran.tus(36, 0)));
        tusSatiri.addView(tusCipi("End", v -> ekran.tus(35, 0)));
        tusSatiri.addView(tusCipi("Del", v -> ekran.tus(127, 0)));
        tusSatiri.addView(tusCipi("Yapıştır", v -> yapistir()));
        kipTv = tusCipi("", v -> { ekran.kaydirKipi = !ekran.kaydirKipi; kipGoster(true); });
        tusSatiri.addView(kipTv);
        kipGoster(false);
        tusKutusu = tk;
        tk.setVisibility(ayar.getBoolean("tuslar", false) ? View.VISIBLE : View.GONE);
        FrameLayout.LayoutParams tl = new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM);
        tl.bottomMargin = dp(72);
        altKap.addView(tk, tl);

        // yakınlaştırma kapsülü (CanEditor: − %50 Sığdır + ↔ Sığdır ↕ Sayfa) — bulanık cam
        FrameLayout kap = new FrameLayout(a);
        kap.setBackground(Tasarim.yuvarlak(0x00FFFFFF, dp(26)));
        if (Build.VERSION.SDK_INT >= 21) {
            kap.setClipToOutline(true);
            kap.setElevation(dp(6));
        }
        kap.addView(new BulanikZemin(a), tam());
        LinearLayout z = new LinearLayout(a);
        z.setOrientation(LinearLayout.HORIZONTAL);
        z.setGravity(Gravity.CENTER_VERTICAL);
        z.setPadding(dp(6), 0, dp(10), 0);
        z.addView(kucukIkon(Tasarim.S.EKSI, v -> ekran.yakinlastir(1 / 1.2f)));
        yuzdeTv = metin("%100 Sığdır", 14, Tasarim.VURGU, true);
        yuzdeTv.setPadding(dp(6), dp(10), dp(6), dp(10));
        yuzdeTv.setOnClickListener(v -> { pulse(v); ekran.sigdir(); });
        z.addView(yuzdeTv);
        z.addView(kucukIkon(Tasarim.S.ARTI, v -> ekran.yakinlastir(1.2f)));
        z.addView(kucukMetin("↔", "Sığdır", v -> ekran.sigdir()));
        z.addView(kucukMetin("↕", "Sayfa", v -> ekran.sayfaSigdir()));
        kap.addView(z, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, dp(52)));
        FrameLayout.LayoutParams kpl = new FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, dp(52), Gravity.BOTTOM | Gravity.START);
        kpl.setMargins(dp(14), 0, 0, dp(14));
        altKap.addView(kap, kpl);
        ekran.olcekDinleyici = () -> yuzdeTv.setText("%" + ekran.yuzde() + (ekran.yuzde() == 100 ? " Sığdır" : ""));

        // ✏ klavye düğmesi (yüzen, mavi)
        ImageView fab = new ImageView(a);
        fab.setImageDrawable(Tasarim.simge(a, Tasarim.S.KLAVYE, Color.WHITE));
        fab.setPadding(dp(16), dp(16), dp(16), dp(16));
        fab.setBackground(Tasarim.dalga(Tasarim.yuvarlak(Tasarim.VURGU, dp(30)), dp(30)));
        if (Build.VERSION.SDK_INT >= 21) fab.setElevation(dp(8));
        fab.setContentDescription("Klavye");
        fab.setOnClickListener(v -> { pulse(v); ekran.klavyeAcKapa(); });
        fab.setOnLongClickListener(v -> { tuslariAcKapa(); return true; });
        FrameLayout.LayoutParams fl = new FrameLayout.LayoutParams(dp(60), dp(60), Gravity.BOTTOM | Gravity.END);
        fl.setMargins(0, 0, dp(16), dp(10));
        altKap.addView(fab, fl);
    }

    private View tusKutusu;

    private ImageView kucukIkon(Tasarim.S s, View.OnClickListener l) {
        ImageView iv = new ImageView(a);
        iv.setImageDrawable(Tasarim.simge(a, s, Tasarim.METIN));
        iv.setPadding(dp(10), dp(10), dp(10), dp(10));
        iv.setBackground(Tasarim.dalga(null, dp(20)));
        iv.setOnClickListener(v -> { pulse(v); l.onClick(v); });
        iv.setLayoutParams(new LinearLayout.LayoutParams(dp(40), dp(40)));
        return iv;
    }

    private View kucukMetin(String ust, String alt, View.OnClickListener l) {
        LinearLayout k = new LinearLayout(a);
        k.setOrientation(LinearLayout.VERTICAL);
        k.setGravity(Gravity.CENTER);
        k.setPadding(dp(8), dp(2), dp(8), dp(2));
        TextView u = metin(ust, 14, Tasarim.METIN, true);
        u.setGravity(Gravity.CENTER);
        TextView t = metin(alt, 11, Tasarim.METIN, true);
        k.addView(u);
        k.addView(t);
        k.setBackground(Tasarim.dalga(null, dp(16)));
        k.setOnClickListener(v -> { pulse(v); l.onClick(v); });
        return k;
    }

    private void bicimDugmesi(LinearLayout b, String ad, Tasarim.S s, String ipucu) {
        ImageView iv = ikonDugme(s, ipucu, v -> komutCalistir(ad));
        bicimDugmeleri.put(ad, iv);
        b.addView(iv);
    }

    private void tuslariAcKapa() {
        final View th = tusKutusu;
        boolean ac = th.getVisibility() != View.VISIBLE;
        ayar.edit().putBoolean("tuslar", ac).apply();
        if (ac) {
            th.setVisibility(View.VISIBLE);
            th.setAlpha(0f);
            th.setTranslationY(dp(24));
            th.animate().alpha(1f).translationY(0).setDuration(240).setInterpolator(hareket()).start();
        } else {
            th.animate().alpha(0f).translationY(dp(24)).setDuration(180).withEndAction(() -> th.setVisibility(View.GONE)).start();
        }
    }

    // ==================================================================================== durum kartı
    private void durumKartiKur() {
        durumKart = new LinearLayout(a);
        durumKart.setOrientation(LinearLayout.HORIZONTAL);
        durumKart.setGravity(Gravity.CENTER_VERTICAL);
        durumKart.setPadding(dp(20), dp(16), dp(24), dp(16));
        durumKart.setBackground(Tasarim.yuvarlak(Color.WHITE, dp(16)));
        if (Build.VERSION.SDK_INT >= 21) durumKart.setElevation(dp(8));
        durumCark = new ProgressBar(a);
        durumKart.addView(durumCark, new LinearLayout.LayoutParams(dp(28), dp(28)));
        durumTv = metin("", 15, Tasarim.METIN, false);
        durumTv.setPadding(dp(16), 0, 0, 0);
        durumTv.setMaxWidth(dp(280));
        durumKart.addView(durumTv);
        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.CENTER);
        kok.addView(durumKart, lp);
        durumKart.setVisibility(View.GONE);
    }

    void durum(String m, boolean yukleniyor) {
        durumTv.setText(m);
        durumCark.setVisibility(yukleniyor ? View.VISIBLE : View.GONE);
        if (durumKart.getVisibility() != View.VISIBLE) {
            durumKart.setVisibility(View.VISIBLE);
            durumKart.setAlpha(0f);
            durumKart.setScaleX(0.92f);
            durumKart.setScaleY(0.92f);
            durumKart.animate().alpha(1f).scaleX(1f).scaleY(1f).setDuration(200).setInterpolator(new DecelerateInterpolator()).start();
        }
        durumKart.bringToFront();
    }

    void durumGizle() {
        if (durumKart.getVisibility() != View.VISIBLE) return;
        durumKart.animate().alpha(0f).scaleX(0.95f).scaleY(0.95f).setDuration(180).withEndAction(() -> durumKart.setVisibility(View.GONE)).start();
    }

    /** Bir belge açılıyor: belge başlığı değişene (BASLIK) ya da 60 sn dolana kadar gösterge. */
    void belgeAciliyor(String ad) {
        acilisBekleme = System.currentTimeMillis() + 60_000;
        durum("Belge açılıyor…\n" + ad, true);
        kok.postDelayed(() -> { if (acilisBekleme > 0 && System.currentTimeMillis() >= acilisBekleme) { acilisBekleme = 0; durumGizle(); } }, 60_500);
    }

    // ==================================================================================== editörden gelenler
    /** Editör bağlandı: şerit tercihini uygula, menüyü iste. */
    void hazir() {
        UyapMobilServisi.gonder("SG " + (seritGizli() ? "0" : "1"));
        iste(800);
    }

    /** Ön plandaki belge penceresinin başlığı: "Doküman Editörü v5.4.20 - ad.udf (/yol/ad.udf) (İmzalı doküman)". */
    void baslik(String t) {
        String ad = t, yol = null, ek = "";
        int tire = t.indexOf(" - ");
        if (tire >= 0) ad = t.substring(tire + 3);
        int p = ad.indexOf(" (");
        if (p > 0) {
            int q = ad.indexOf(')', p);
            if (q > p) { yol = ad.substring(p + 2, q); ek = ad.substring(q + 1).trim(); }
            ad = ad.substring(0, p);
        }
        belgeAdi = ad.trim().isEmpty() ? "UYAP Editör" : ad.trim();
        belgeYolu = yol != null && yol.contains("/.uki/") ? null : yol;   // .uki: kaydedilmemiş yeni belge
        baslikTv.setText(belgeAdi);
        altBaslikTv.setText((belgeYolu == null ? "Kaydedilmemiş belge" : "Orijinal UYAP Editör · Sayfa görünümü")
                + (ek.isEmpty() ? "" : " · " + ek.replace("(", "").replace(")", "")));
        if (acilisBekleme > 0 && !belgeAdi.toLowerCase(java.util.Locale.ROOT).startsWith("isimsiz")) { acilisBekleme = 0; durumGizle(); }
        iste(300);
    }

    void menuGeldi(String json) {
        JSONObject j;
        try { j = new JSONObject(json); } catch (Exception e) { Tani.hata("uyapmobil", "menü json", e); return; }
        JSONArray m = j.optJSONArray("m");
        if (m == null || m.length() == 0) { if (bosYanit++ < 60) iste(2000); return; }
        bosYanit = 0;
        son = j;
        komutlariTani();
        if (cekmece != null && cekmece.getParent() != null) cekmeceCiz();
        if (sayfaYenile != null) sayfaYenile.run();
    }

    private void iste(long gecikme) { kok.postDelayed(() -> UyapMobilServisi.gonder("MN"), gecikme); }

    /**
     * Giriş menüsündeki araç çubukları (UYAP Editör 5.4.x):
     *   12'li: A+ A- K T A(altı) S(üstü) x₂ x² temizle vurgu renk büyük/küçük
     *   11'li: madde numara çok-düzeyli girinti- girinti+ sol orta sağ iki-yana satır-aralığı ¶
     *   açılır listeler: stil, yazı tipi, boyut
     */
    private void komutlariTani() {
        komut.clear();
        combolar.clear();
        JSONArray m = son.optJSONArray("m");
        JSONObject giris = null;
        for (int i = 0; i < m.length(); i++) if ("Giriş".equals(m.optJSONObject(i).optString("t"))) giris = m.optJSONObject(i);
        if (giris == null) return;
        JSONArray o = giris.optJSONArray("o");
        String[] a12 = {"buyut", "kucult", "kalin", "italik", "alti", "ustu", "alt_simge", "ust_simge", "temizle", "vurgu", "renk", "harf"};
        String[] a11 = {"madde", "numara", "cok_duzey", "girinti_az", "girinti_cok", "sol", "orta", "sag", "iki", "satir", "paragraf_isareti"};
        for (int i = 0; o != null && i < o.length(); i++) {
            JSONObject e = o.optJSONObject(i);
            if (!"b".equals(e.optString("k"))) continue;
            JSONArray d = e.optJSONArray("o");
            if (d == null) continue;
            int dugme = 0;
            for (int j = 0; j < d.length(); j++) if ("t".equals(d.optJSONObject(j).optString("k"))) dugme++;
            String[] adlar = dugme == 12 ? a12 : dugme == 11 ? a11 : null;
            int n = 0;
            for (int j = 0; j < d.length(); j++) {
                JSONObject b = d.optJSONObject(j);
                if ("c".equals(b.optString("k"))) { combolar.add(b); continue; }
                if (adlar != null && n < adlar.length) komut.put(adlar[n], new int[]{b.optInt("id"), b.optInt("e"), b.optInt("s", -1)});
                n++;
            }
        }
        if (combolar.size() > 1) fontTv.setText(combolar.get(1).optString("t") + "  ▾");
        if (combolar.size() > 2) boyutTv.setText(combolar.get(2).optString("t") + "  ▾");
        for (Map.Entry<String, ImageView> e : bicimDugmeleri.entrySet()) {
            int[] k = komut.get(e.getKey());
            secili(e.getValue(), k != null && k[2] == 1);
            e.getValue().setAlpha(k == null || k[1] == 1 ? 1f : 0.35f);
        }
    }

    private void komutCalistir(String ad) {
        int[] k = komut.get(ad);
        if (k == null) {
            Toast.makeText(a, "Editör menüsü hazırlanıyor…", Toast.LENGTH_SHORT).show();
            iste(0);
            return;
        }
        UyapMobilServisi.gonder("MC " + k[0]);
        iste(350);    // seçili durumlar (K, T, hizalama) güncellensin
    }

    // ==================================================================================== şerit / mobil görünüm
    boolean seritGizli() { return ayar.getBoolean("serit_gizli", true); }

    void seritDegistir() {
        boolean gizle = !seritGizli();
        ayar.edit().putBoolean("serit_gizli", gizle).apply();
        UyapMobilServisi.gonder("SG " + (gizle ? "0" : "1"));
    }

    /** Menüde etkin bir öğenin kimliği (yoksa -1). */
    private int ogeKimligi(String menu, String ad) {
        if (son == null) return -1;
        JSONArray m = son.optJSONArray("m");
        for (int i = 0; i < m.length(); i++) {
            JSONObject b = m.optJSONObject(i);
            if (!menu.equals(b.optString("t"))) continue;
            JSONArray o = b.optJSONArray("o");
            for (int j = 0; o != null && j < o.length(); j++) {
                JSONObject e = o.optJSONObject(j);
                if ("i".equals(e.optString("k")) && ad.equals(e.optString("t"))) return e.optInt("e") == 1 ? e.optInt("id") : -1;
            }
        }
        return -1;
    }

    /** 💾: kayıtlı belgeyse Kaydet, yeni belgeyse Farklı kaydet (telefonun seçicisi açılır). */
    void kaydet() {
        if (son == null) { hazirlaniyor(); return; }
        int k = ogeKimligi("Dosya", "Kaydet");
        if (k >= 0) { UyapMobilServisi.gonder("MC " + k); kayitBildir(); return; }
        if (belgeYolu != null) { Toast.makeText(a, "✓ Belgede kaydedilmemiş değişiklik yok", Toast.LENGTH_SHORT).show(); return; }
        int f = ogeKimligi("Dosya", "Farklı Kaydet");
        if (f >= 0) UyapMobilServisi.gonder("MC " + f);
    }

    private void kayitBildir() {
        altBaslikTv.setText("Kaydediliyor…");
        kok.postDelayed(() -> { altBaslikTv.setText("✓ Kaydedildi · Orijinal UYAP Editör"); iste(0); }, 1500);
    }

    /**
     * 📱 Mobil akış görünümü: değişiklik varsa önce resmi editörde kaydedilir (dosya yazılana kadar beklenir), sonra
     * aynı belge CanEditor'ın akış editöründe açılır. Oradan "Sayfa görünümü" ile dönülünce belge yeniden yüklenir.
     */
    private void mobilGorunum() {
        if (belgeYolu == null) {
            Toast.makeText(a, "Mobil görünüm için önce belgeyi kaydedin (💾)", Toast.LENGTH_LONG).show();
            int f = ogeKimligi("Dosya", "Farklı Kaydet");
            if (f >= 0) UyapMobilServisi.gonder("MC " + f);
            return;
        }
        gecisRozeti("📱  Mobil Akış Görünümü");
        final java.io.File dosya = new java.io.File(belgeYolu);
        final long once = dosya.lastModified();
        int k = ogeKimligi("Dosya", "Kaydet");
        if (k < 0) { kok.postDelayed(() -> uyg.mobilGorunum(belgeYolu), 350); return; }
        UyapMobilServisi.gonder("MC " + k);
        final long son = System.currentTimeMillis() + 8000;
        kok.postDelayed(new Runnable() {
            @Override public void run() {
                if (dosya.lastModified() != once || System.currentTimeMillis() > son) kok.postDelayed(() -> uyg.mobilGorunum(belgeYolu), 400);
                else kok.postDelayed(this, 250);
            }
        }, 400);
    }

    /** Ortada kısa süre görünen geçiş rozeti (CanEditor'daki "Mobil Akış Görünümü" bildirimi gibi). */
    void gecisRozeti(String m) {
        final TextView t = metin(m, 15, Color.WHITE, true);
        t.setPadding(dp(20), dp(12), dp(20), dp(12));
        t.setBackground(Tasarim.yuvarlak(0xE6202124, dp(24)));
        if (Build.VERSION.SDK_INT >= 21) t.setElevation(dp(10));
        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
        lp.bottomMargin = dp(96);
        kok.addView(t, lp);
        t.setAlpha(0f);
        t.setTranslationY(dp(16));
        t.animate().alpha(1f).translationY(0).setDuration(220).setInterpolator(hareket()).start();
        kok.postDelayed(() -> t.animate().alpha(0f).setDuration(250).withEndAction(() -> kok.removeView(t)).start(), 1600);
    }

    // ==================================================================================== çekmece (☰)
    boolean acikMi() { return (cekmece != null && cekmece.getParent() != null) || (sayfa != null && sayfa.getParent() != null); }

    void kapatHepsi() { cekmeceKapat(); sayfaKapat(); }

    private void cekmeceAc() {
        if (cekmece == null) {
            cekmece = new FrameLayout(a);
            cekmece.setBackgroundColor(0x66000000);
            cekmece.setOnClickListener(v -> cekmeceKapat());
            ScrollView sv = new ScrollView(a);
            sv.setBackground(Tasarim.yuvarlak(Tasarim.YUZEY, 0));
            if (Build.VERSION.SDK_INT >= 21) sv.setElevation(dp(16));
            sv.setClickable(true);
            sv.setVerticalScrollBarEnabled(false);
            cekmeceIcerik = new LinearLayout(a);
            cekmeceIcerik.setOrientation(LinearLayout.VERTICAL);
            sv.addView(cekmeceIcerik);
            cekmece.addView(sv, new FrameLayout.LayoutParams(cekmeceGenisligi(), ViewGroup.LayoutParams.MATCH_PARENT, Gravity.START));
        }
        if (cekmece.getParent() != null) return;
        kok.addView(cekmece, tam());
        cekmeceCiz();
        View panel = cekmece.getChildAt(0);
        cekmece.setAlpha(0f);
        cekmece.animate().alpha(1f).setDuration(200).start();
        panel.setTranslationX(-cekmeceGenisligi());
        panel.animate().translationX(0).setDuration(280).setInterpolator(hareket()).start();
        UyapMobilServisi.gonder("MN");
    }

    private void cekmeceKapat() {
        if (cekmece == null || cekmece.getParent() == null) return;
        View panel = cekmece.getChildAt(0);
        panel.animate().translationX(-cekmeceGenisligi()).setDuration(200).setInterpolator(new DecelerateInterpolator()).start();
        cekmece.animate().alpha(0f).setDuration(200).withEndAction(() -> { if (cekmece.getParent() != null) kok.removeView(cekmece); }).start();
    }

    private int cekmeceGenisligi() { return Math.min(dp(360), Math.round(a.getResources().getDisplayMetrics().widthPixels * 0.86f)); }

    private void cekmeceCiz() {
        LinearLayout ic = cekmeceIcerik;
        ic.removeAllViews();
        // başlık: ⚖️ UYAP Editör Menü  ✕
        LinearLayout bas = new LinearLayout(a);
        bas.setOrientation(LinearLayout.HORIZONTAL);
        bas.setGravity(Gravity.CENTER_VERTICAL);
        bas.setPadding(dp(18), dp(16), dp(8), dp(12));
        TextView uy = metin("⚖️ UYAP Editör Menü", 19, Tasarim.METIN, true);
        bas.addView(uy, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        bas.addView(kucukIkon(Tasarim.S.KAPAT, v -> cekmeceKapat()));
        ic.addView(bas);
        TextView bt = metin(belgeAdi, 13, Tasarim.IKINCIL, false);
        bt.setPadding(dp(18), 0, dp(18), dp(10));
        bt.setSingleLine(true);
        bt.setEllipsize(TextUtils.TruncateAt.MIDDLE);
        ic.addView(bt);
        View c0 = new View(a);
        c0.setBackgroundColor(Tasarim.CIZGI);
        ic.addView(c0, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 1));
        // CanEditor'daki büyük düğmeler
        ic.addView(buyukDugme("💾  Açık Olan Belgeyi Kaydet (1-Tık)", Color.rgb(30, 142, 62), () -> { cekmeceKapat(); kaydet(); }));
        ic.addView(satir(null, null, "📂  Belge Aç (UDF, USF)", true, -1, () -> menuKomutu("Dosya", "Aç")));
        ic.addView(satir(null, null, "📄  Yeni Belge", true, -1, () -> menuKomutu("Dosya", "Yeni")));
        ic.addView(buyukDugme("📱  Mobil Akış Görünümünde Aç (CanEditor)", Color.rgb(121, 59, 34), () -> { cekmeceKapat(); mobilGorunum(); }));

        baslikEtiketi(ic, "FARKLI KAYDET");
        ic.addView(satir(null, null, "📄  Havelsan UDF (.udf)", true, -1, () -> menuKomutu("Dosya", "Farklı Kaydet")));
        ic.addView(satir(null, null, "📕  Adobe A4 PDF (.pdf)", true, -1, () -> menuKomutu("Dosya", "PDF Olarak Kaydet")));
        ic.addView(satir(null, null, "📗  OpenDocument (.odt)", true, -1, () -> menuKomutu("Dosya", "ODT Olarak Kaydet")));
        ic.addView(satir(null, null, "🗂️  Tümünü Farklı Kaydet", true, -1, () -> menuKomutu("Dosya", "Tümünü Farklı Kaydet")));

        baslikEtiketi(ic, "YAZDIR & GÖNDER");
        ic.addView(satir(null, null, "🖨️  Yazdır", true, -1, () -> menuKomutu("Dosya", "Yazdır")));
        ic.addView(satir(null, null, "👁️  Yazdırma Önizlemesi", true, -1, () -> menuKomutu("Dosya", "Yazdırma Önizlemesi")));
        ic.addView(satir(null, null, "📤  Dışa Aktar", true, -1, () -> menuKomutu("Dosya", "Dışa Aktar")));

        baslikEtiketi(ic, "HUKUK & E-İMZA ARAÇLARI");
        ic.addView(satir(null, null, "✍️  İmzala", true, -1, () -> menuKomutu("Araçlar", "İmzala")));
        ic.addView(satir(null, null, "📲  Dokümanı Mobil İmzala", true, -1, () -> menuKomutu("Araçlar", "Dokümanı Mobil İmzala")));
        ic.addView(satir(null, null, "🔏  İmzalar", true, -1, () -> menuKomutu("Araçlar", "İmzalar")));
        ic.addView(satir(null, null, "🪪  Sertifikalar", true, -1, () -> menuKomutu("Araçlar", "Sertifikalar")));
        ic.addView(satir(null, null, "🔍  Bul ve Değiştir", true, -1, () -> menuKomutu("Giriş", "Bul")));
        ic.addView(satir(null, null, "📑  Sayfa Düzenle", true, -1, () -> menuKomutu("Düzenle", "Sayfa Düzenle")));

        baslikEtiketi(ic, "TÜM UYAP EDİTÖR MENÜLERİ");
        if (son == null) {
            LinearLayout y = new LinearLayout(a);
            y.setGravity(Gravity.CENTER_VERTICAL);
            y.setPadding(dp(20), dp(12), dp(20), dp(12));
            y.addView(new ProgressBar(a), new LinearLayout.LayoutParams(dp(22), dp(22)));
            TextView t = metin("Editör menüsü yükleniyor…", 15, Tasarim.IKINCIL, false);
            t.setPadding(dp(12), 0, 0, 0);
            y.addView(t);
            ic.addView(y);
        } else {
            JSONArray m = son.optJSONArray("m");
            for (int i = 0; i < m.length(); i++) {
                JSONObject b = m.optJSONObject(i);
                bolum(ic, b.optString("t"), b.optJSONArray("o"), 0);
            }
        }
        baslikEtiketi(ic, "UYGULAMA");
        ic.addView(satir(null, null, seritGizli() ? "🎀  Resmi şerit menüyü göster" : "🎀  Resmi şerit menüyü gizle", true, -1, () -> { cekmeceKapat(); seritDegistir(); }));
        String[] k = uyg.uygulamaKomutlari();
        for (int i = 0; i < k.length; i++) {
            final int s = i;
            ic.addView(satir(null, null, k[i], true, -1, () -> { cekmeceKapat(); uyg.uygulamaKomutu(s); }));
        }
        View bos = new View(a);
        ic.addView(bos, new LinearLayout.LayoutParams(1, dp(48)));
    }

    private View buyukDugme(String m, int renk, Runnable r) {
        TextView t = metin(m, 15, Color.WHITE, true);
        t.setPadding(dp(16), dp(14), dp(16), dp(14));
        t.setBackground(Tasarim.dalga(Tasarim.yuvarlak(renk, dp(12)), dp(12)));
        if (Build.VERSION.SDK_INT >= 21) t.setElevation(dp(2));
        t.setOnClickListener(v -> { pulse(v); r.run(); });
        LinearLayout k = new LinearLayout(a);
        k.setPadding(dp(12), dp(8), dp(12), dp(4));
        k.addView(t, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        return k;
    }

    private void baslikEtiketi(LinearLayout ic, String m) {
        TextView t = metin(m, 12, Tasarim.IKINCIL, true);
        t.setLetterSpacing(0.06f);
        t.setPadding(dp(20), dp(18), dp(20), dp(6));
        ic.addView(t);
    }

    /** Menüde metniyle bir komutu bul ve çalıştır (ilk etkin olanı). */
    private void menuKomutu(String menu, String... adlar) {
        cekmeceKapat();
        if (son == null) { Toast.makeText(a, "Editör menüsü hazırlanıyor…", Toast.LENGTH_SHORT).show(); return; }
        JSONArray m = son.optJSONArray("m");
        for (String ad : adlar)
            for (int i = 0; i < m.length(); i++) {
                JSONObject b = m.optJSONObject(i);
                if (!menu.equals(b.optString("t"))) continue;
                JSONArray o = b.optJSONArray("o");
                for (int j = 0; o != null && j < o.length(); j++) {
                    JSONObject e = o.optJSONObject(j);
                    if ("i".equals(e.optString("k")) && ad.equals(e.optString("t")) && e.optInt("e") == 1) {
                        UyapMobilServisi.gonder("MC " + e.optInt("id"));
                        return;
                    }
                }
            }
        Toast.makeText(a, adlar[0] + " şu anda kullanılamıyor", Toast.LENGTH_SHORT).show();
    }

    private LinearLayout bolumBasligi(LinearLayout ust, final String ad, int girinti) {
        final boolean acik = acikBolumler.contains(ad);
        LinearLayout h = new LinearLayout(a);
        h.setOrientation(LinearLayout.HORIZONTAL);
        h.setGravity(Gravity.CENTER_VERTICAL);
        h.setPadding(dp(20 + girinti), 0, dp(12), 0);
        h.setMinimumHeight(dp(52));
        TextView t = metin(ad, girinti > 0 ? 15 : 16, Tasarim.METIN, true);
        h.addView(t, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        ImageView ok = new ImageView(a);
        ok.setImageDrawable(Tasarim.simge(a, Tasarim.S.ILERI, Tasarim.IKINCIL));
        ok.setRotation(acik ? 90 : 0);
        h.addView(ok, new LinearLayout.LayoutParams(dp(22), dp(22)));
        h.setBackground(Tasarim.dalga(null, 0));
        final LinearLayout[] k = new LinearLayout[1];
        h.setOnClickListener(v -> {
            boolean simdi = !acikBolumler.contains(ad);
            if (simdi) acikBolumler.add(ad); else acikBolumler.remove(ad);
            StringBuilder sb = new StringBuilder();
            for (String s : acikBolumler) sb.append(s).append('\n');
            ayar.edit().putString("menu_acik", sb.toString()).apply();
            ok.animate().rotation(simdi ? 90 : 0).setDuration(200).start();
            cekmeceCiz();
        });
        ust.addView(h);
        if (!acik) return null;
        k[0] = new LinearLayout(a);
        k[0].setOrientation(LinearLayout.VERTICAL);
        ust.addView(k[0]);
        k[0].setAlpha(0f);
        k[0].animate().alpha(1f).setDuration(180).start();
        return k[0];
    }

    private void bolum(LinearLayout ust, String ad, JSONArray o, int girinti) {
        LinearLayout k = bolumBasligi(ust, ad, girinti);
        if (k == null || o == null) return;
        for (int i = 0; i < o.length(); i++) {
            JSONObject e = o.optJSONObject(i);
            switch (e.optString("k")) {
                case "i": {
                    final int id = e.optInt("id");
                    k.addView(satir(e.optString("ic"), null, e.optString("t"), e.optInt("e") == 1, e.optInt("s", -1),
                            () -> { cekmeceKapat(); UyapMobilServisi.gonder("MC " + id); }));
                    break;
                }
                case "g": bolum(k, e.optString("t"), e.optJSONArray("o"), girinti + 16); break;
                case "b": {
                    JSONArray d = e.optJSONArray("o");
                    if (d == null || d.length() == 0) break;
                    LinearLayout izgara = new LinearLayout(a);
                    izgara.setOrientation(LinearLayout.VERTICAL);
                    izgara.setPadding(dp(14), dp(2), dp(14), dp(6));
                    LinearLayout s = null;
                    int sutun = 0, enFazla = Math.max(4, (cekmeceGenisligi() - dp(28)) / dp(50));
                    for (int j = 0; j < d.length(); j++) {
                        JSONObject b = d.optJSONObject(j);
                        if ("c".equals(b.optString("k"))) continue;    // listeler "A" biçim sayfasında
                        if (s == null || sutun >= enFazla) {
                            s = new LinearLayout(a);
                            s.setOrientation(LinearLayout.HORIZONTAL);
                            izgara.addView(s);
                            sutun = 0;
                        }
                        final int id = b.optInt("id");
                        ImageView iv = editorSimgesi(b, () -> { cekmeceKapat(); UyapMobilServisi.gonder("MC " + id); iste(350); });
                        s.addView(iv, new LinearLayout.LayoutParams(dp(48), dp(48)));
                        sutun++;
                    }
                    if (izgara.getChildCount() > 0) k.addView(izgara);
                    break;
                }
                case "-": {
                    View c = new View(a);
                    c.setBackgroundColor(Tasarim.CIZGI);
                    LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 1);
                    lp.setMargins(dp(64), dp(2), dp(16), dp(2));
                    k.addView(c, lp);
                    break;
                }
                default: break;
            }
        }
    }

    // ==================================================================================== alt sayfalar
    private Runnable sayfaYenile;

    /** Alttan kayan sayfa (yuvarlak köşeli, tutamaklı). */
    private LinearLayout sayfaAc(String baslik) {
        sayfaKapat0();
        sayfa = new FrameLayout(a);
        sayfa.setBackgroundColor(0x55000000);
        sayfa.setOnClickListener(v -> sayfaKapat());
        LinearLayout panel = new LinearLayout(a);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setBackground(Tasarim.ustYuvarlak(Tasarim.YUZEY, dp(24)));
        panel.setClickable(true);
        if (Build.VERSION.SDK_INT >= 21) panel.setElevation(dp(16));
        View tutamak = new View(a);
        tutamak.setBackground(Tasarim.yuvarlak(Tasarim.CIZGI, dp(3)));
        LinearLayout.LayoutParams tl = new LinearLayout.LayoutParams(dp(36), dp(5));
        tl.gravity = Gravity.CENTER_HORIZONTAL;
        tl.setMargins(0, dp(10), 0, dp(6));
        panel.addView(tutamak, tl);
        if (baslik != null) {
            TextView t = metin(baslik, 18, Tasarim.METIN, true);
            t.setPadding(dp(20), dp(6), dp(20), dp(10));
            panel.addView(t);
        }
        ScrollView sv = new ScrollView(a);
        sv.setVerticalScrollBarEnabled(false);
        LinearLayout ic = new LinearLayout(a);
        ic.setOrientation(LinearLayout.VERTICAL);
        ic.setPadding(0, 0, 0, dp(16));
        sv.addView(ic);
        panel.addView(sv, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        FrameLayout.LayoutParams pl = new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM);
        sayfa.addView(panel, pl);
        kok.addView(sayfa, tam());
        sayfa.setAlpha(0f);
        sayfa.animate().alpha(1f).setDuration(200).start();
        panel.setTranslationY(a.getResources().getDisplayMetrics().heightPixels * 0.5f);
        panel.animate().translationY(0).setDuration(300).setInterpolator(hareket()).start();
        // en fazla ekranın %70'i
        panel.post(() -> {
            int enFazla = Math.round(kok.getHeight() * 0.7f);
            if (panel.getHeight() > enFazla) { ViewGroup.LayoutParams lp = sv.getLayoutParams(); lp.height = enFazla - dp(60); sv.setLayoutParams(lp); }
        });
        return ic;
    }

    private void sayfaKapat() {
        if (sayfa == null || sayfa.getParent() == null) return;
        final FrameLayout s = sayfa;
        sayfaYenile = null;
        View panel = s.getChildAt(0);
        panel.animate().translationY(panel.getHeight()).setDuration(220).setInterpolator(new DecelerateInterpolator()).start();
        s.animate().alpha(0f).setDuration(220).withEndAction(() -> { if (s.getParent() != null) kok.removeView(s); }).start();
        if (sayfaKapaninca != null) { Runnable r = sayfaKapaninca; sayfaKapaninca = null; r.run(); }
    }

    private void sayfaKapat0() {
        if (sayfa != null && sayfa.getParent() != null) kok.removeView(sayfa);
        sayfaYenile = null;
    }

    /** "A" biçim sayfası: Metin / Paragraf sekmeleri (Google Dokümanlar gibi). */
    private void bicimSayfasi(final int sekme) {
        final LinearLayout ic = sayfaAc(null);
        sayfaYenile = () -> { if (sayfa != null && sayfa.getParent() != null) bicimSayfasiDoldur(ic, sekme); };
        bicimSayfasiDoldur(ic, sekme);
        iste(0);
    }

    private void bicimSayfasiDoldur(LinearLayout ic, final int sekme) {
        ic.removeAllViews();
        LinearLayout sekmeler = new LinearLayout(a);
        sekmeler.setOrientation(LinearLayout.HORIZONTAL);
        sekmeler.setPadding(dp(16), 0, dp(16), dp(8));
        String[] ad = {"Metin", "Paragraf"};
        for (int i = 0; i < 2; i++) {
            final int s = i;
            TextView t = metin(ad[i], 15, i == sekme ? Tasarim.VURGU : Tasarim.IKINCIL, true);
            t.setGravity(Gravity.CENTER);
            t.setPadding(0, dp(12), 0, dp(12));
            t.setBackground(i == sekme ? Tasarim.yuvarlak(Tasarim.VURGU_ACIK, dp(22)) : Tasarim.dalga(null, dp(22)));
            t.setOnClickListener(v -> { if (s != sekme) { sayfaYenile = () -> bicimSayfasiDoldur(ic, s); bicimSayfasiDoldur(ic, s); } });
            sekmeler.addView(t, agirlik());
        }
        ic.addView(sekmeler);
        if (son == null) {
            TextView t = metin("Editör menüsü yükleniyor…", 15, Tasarim.IKINCIL, false);
            t.setPadding(dp(20), dp(12), dp(20), dp(12));
            ic.addView(t);
            return;
        }
        if (sekme == 0) {
            if (combolar.size() > 1) ic.addView(listeSatiri("Yazı tipi", combolar.get(1)));
            if (combolar.size() > 2) ic.addView(boyutSatiri(combolar.get(2)));
            ic.addView(dugmeSatiri(new String[]{"kalin", "italik", "alti", "ustu"},
                    new Tasarim.S[]{Tasarim.S.KALIN, Tasarim.S.ITALIK, Tasarim.S.ALTI, Tasarim.S.USTU_CIZILI}));
            ic.addView(dugmeSatiri(new String[]{"alt_simge", "ust_simge", "renk", "vurgu", "temizle"},
                    new Tasarim.S[]{Tasarim.S.ALT_SIMGE, Tasarim.S.UST_SIMGE, Tasarim.S.RENK, Tasarim.S.VURGULA, Tasarim.S.TEMIZLE}));
            if (combolar.size() > 0) ic.addView(listeSatiri("Stil", combolar.get(0)));
        } else {
            ic.addView(dugmeSatiri(new String[]{"sol", "orta", "sag", "iki"},
                    new Tasarim.S[]{Tasarim.S.SOL, Tasarim.S.ORTA, Tasarim.S.SAG, Tasarim.S.IKI_YANA}));
            ic.addView(dugmeSatiri(new String[]{"madde", "numara", "girinti_az", "girinti_cok"},
                    new Tasarim.S[]{Tasarim.S.MADDE, Tasarim.S.NUMARA, Tasarim.S.GIRINTI_AZ, Tasarim.S.GIRINTI_COK}));
            ic.addView(dugmeSatiri(new String[]{"satir", "cok_duzey", "paragraf_isareti"},
                    new Tasarim.S[]{Tasarim.S.SATIR_ARALIGI, null, null}));
            ic.addView(satir(null, null, "Paragraf özellikleri…", true, -1, () -> { sayfaKapat(); menuKomutu("Biçim", "Paragraf Özellikleri"); }));
            ic.addView(satir(null, null, "Yazı özellikleri…", true, -1, () -> { sayfaKapat(); menuKomutu("Biçim", "Yazı Özellikleri"); }));
        }
    }

    /** Bölmeli düğme grubu: yuvarlak köşeli tek kutu içinde eşit genişlikte düğmeler. */
    private View dugmeSatiri(String[] adlar, Tasarim.S[] simge) {
        LinearLayout dis = new LinearLayout(a);
        dis.setPadding(dp(16), dp(6), dp(16), dp(6));
        LinearLayout g = new LinearLayout(a);
        g.setOrientation(LinearLayout.HORIZONTAL);
        g.setBackground(Tasarim.yuvarlak(Tasarim.ZEMIN, dp(14)));
        g.setPadding(dp(4), dp(4), dp(4), dp(4));
        for (int i = 0; i < adlar.length; i++) {
            final String ad = adlar[i];
            int[] k = komut.get(ad);
            ImageView iv = new ImageView(a);
            iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE);
            if (simge[i] != null) iv.setImageDrawable(Tasarim.simge(a, simge[i], Tasarim.METIN));
            else {
                Bitmap bm = editorSimgesiBitmap(ad);
                if (bm != null) iv.setImageBitmap(bm);
            }
            iv.setPadding(dp(10), dp(10), dp(10), dp(10));
            boolean sec = k != null && k[2] == 1;
            iv.setBackground(Tasarim.dalga(sec ? Tasarim.yuvarlak(Tasarim.SECILI, dp(10)) : null, dp(10)));
            iv.setAlpha(k == null || k[1] == 1 ? 1f : 0.35f);
            iv.setOnClickListener(v -> { pulse(v); komutCalistir(ad); });
            g.addView(iv, new LinearLayout.LayoutParams(0, dp(46), 1f));
        }
        dis.addView(g, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        return dis;
    }

    private Bitmap editorSimgesiBitmap(String ad) {
        int[] k = komut.get(ad);
        if (k == null || son == null) return null;
        String ic = simgeBul(son.optJSONArray("m"), k[0]);
        return ic == null ? null : simge(ic);
    }

    private String simgeBul(JSONArray o, int id) {
        for (int i = 0; o != null && i < o.length(); i++) {
            JSONObject e = o.optJSONObject(i);
            if (e.optInt("id", -1) == id && e.has("ic")) return e.optString("ic");
            String r = simgeBul(e.optJSONArray("o"), id);
            if (r != null) return r;
        }
        return null;
    }

    private View listeSatiri(final String ad, final JSONObject combo) {
        return satir(null, combo.optString("t"), ad, true, -1, () -> listeSec(ad, combo));
    }

    /** Açılır liste (yazı tipi / boyut / stil) alttan kayan sayfada; yazı tipleri kendi görünümleriyle. */
    private void listeSec(final String ad, final JSONObject combo) {
        final int id = combo.optInt("id");
        final JSONArray l = combo.optJSONArray("l");
        final LinearLayout ic = sayfaAc(ad);
        String simdiki = combo.optString("t");
        View secili = null;
        for (int i = 0; l != null && i < l.length(); i++) {
            final int s = i;
            String deger = l.optString(i);
            boolean bu = deger.equals(simdiki);
            TextView t = metin((bu ? "✓  " : "     ") + deger, 17, bu ? Tasarim.VURGU : Tasarim.METIN, bu);
            if ("Yazı tipi".equals(ad)) t.setTypeface(Typeface.create(deger, bu ? Typeface.BOLD : Typeface.NORMAL));
            t.setPadding(dp(20), dp(14), dp(24), dp(14));
            t.setBackground(bu ? Tasarim.yuvarlak(Tasarim.VURGU_ACIK, 0) : Tasarim.dalga(null, 0));
            t.setOnClickListener(v -> { sayfaKapat(); UyapMobilServisi.gonder("MS " + id + " " + s); iste(350); });
            ic.addView(t);
            if (bu) secili = t;
        }
        if ("Boyut".equals(ad) && combo.optInt("ed") == 1)
            ic.addView(satir(null, null, "Başka bir boyut yaz…", true, -1, () -> { sayfaKapat(); boyutYaz(id, combo.optString("t")); }));
        final View sc = secili;
        if (sc != null) ic.post(() -> { View p = (View) ic.getParent(); if (p instanceof ScrollView) ((ScrollView) p).smoothScrollTo(0, Math.max(0, sc.getTop() - dp(120))); });
    }

    private View boyutSatiri(final JSONObject combo) {
        final int id = combo.optInt("id");
        LinearLayout r = new LinearLayout(a);
        r.setOrientation(LinearLayout.HORIZONTAL);
        r.setGravity(Gravity.CENTER_VERTICAL);
        r.setPadding(dp(20), dp(6), dp(16), dp(6));
        TextView t = metin("Boyut", 16, Tasarim.METIN, false);
        r.addView(t, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        final String deger = combo.optString("t");
        LinearLayout g = new LinearLayout(a);
        g.setGravity(Gravity.CENTER_VERTICAL);
        g.setBackground(Tasarim.yuvarlak(Tasarim.ZEMIN, dp(14)));
        ImageView eksi = new ImageView(a);
        eksi.setImageDrawable(Tasarim.simge(a, Tasarim.S.EKSI, Tasarim.METIN));
        eksi.setPadding(dp(12), dp(12), dp(12), dp(12));
        eksi.setBackground(Tasarim.dalga(null, dp(14)));
        eksi.setOnClickListener(v -> boyutAyarla(id, deger, -1));
        TextView d = metin(deger, 17, Tasarim.METIN, true);
        d.setGravity(Gravity.CENTER);
        d.setMinWidth(dp(56));
        d.setOnClickListener(v -> boyutYaz(id, deger));
        ImageView arti = new ImageView(a);
        arti.setImageDrawable(Tasarim.simge(a, Tasarim.S.ARTI, Tasarim.METIN));
        arti.setPadding(dp(12), dp(12), dp(12), dp(12));
        arti.setBackground(Tasarim.dalga(null, dp(14)));
        arti.setOnClickListener(v -> boyutAyarla(id, deger, +1));
        g.addView(eksi, new LinearLayout.LayoutParams(dp(48), dp(48)));
        g.addView(d);
        g.addView(arti, new LinearLayout.LayoutParams(dp(48), dp(48)));
        r.addView(g);
        return r;
    }

    private void boyutAyarla(int id, String deger, int yon) {
        float v;
        try { v = Float.parseFloat(deger.replace(',', '.')); } catch (Exception e) { v = 12; }
        v = Math.max(1, Math.min(96, Math.round(v) + yon));
        String s = String.valueOf((int) v);
        UyapMobilServisi.gonder("MT " + id + " " + Base64.encodeToString(s.getBytes(StandardCharsets.UTF_8), Base64.NO_WRAP));
        iste(300);
    }

    private void boyutYaz(final int id, String deger) {
        final EditText e = new EditText(a);
        e.setText(deger);
        e.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL);
        e.setSelectAllOnFocus(true);
        new android.app.AlertDialog.Builder(a).setTitle("Yazı boyutu").setView(e).setPositiveButton("Tamam", (d, w) -> {
            String v = e.getText().toString().trim();
            if (!v.isEmpty()) UyapMobilServisi.gonder("MT " + id + " " + Base64.encodeToString(v.getBytes(StandardCharsets.UTF_8), Base64.NO_WRAP));
            iste(300);
        }).setNegativeButton("Vazgeç", null).show();
    }

    /** ⋮ — diğer işlemler sayfası. */
    private void digerSayfasi() {
        LinearLayout ic = sayfaAc(null);
        ic.addView(satir(null, null, seritGizli() ? "Resmi şerit menüyü göster" : "Resmi şerit menüyü gizle", true, -1, () -> { sayfaKapat(); seritDegistir(); }));
        ic.addView(satir(null, null, "Tüm editör menüsü (☰)", true, -1, () -> { sayfaKapat(); cekmeceAc(); }));
        ic.addView(satir(null, null, "Mobil görünüm", true, -1, () -> { sayfaKapat(); mobilGorunum(); }));
        String[] k = uyg.uygulamaKomutlari();
        for (int i = 0; i < k.length; i++) {
            final int s = i;
            ic.addView(satir(null, null, k[i], true, -1, () -> { sayfaKapat(); uyg.uygulamaKomutu(s); }));
        }
    }

    // ==================================================================================== ek tuşlar
    private void yapiskan(int bit) {
        ekran.yapiskan ^= bit;
        degistiricileriGoster();
    }

    void degistiricileriGoster() {
        int y = ekran.yapiskan;
        cipDurum(ctrlTv, (y & EkranView.CTRL) != 0);
        cipDurum(altTv, (y & EkranView.ALT) != 0);
        cipDurum(shiftTv, (y & EkranView.SHIFT) != 0);
    }

    private void kipGoster(boolean bildir) {
        kipTv.setText(ekran.kaydirKipi ? "Kaydırma" : "Seçim");
        cipDurum(kipTv, !ekran.kaydirKipi);
        if (bildir) Toast.makeText(a, ekran.kaydirKipi ? "Tek parmak belgeyi kaydırır" : "Tek parmak metin seçer / sürükler", Toast.LENGTH_SHORT).show();
    }

    private void yapistir() {
        ClipboardManager cm = (ClipboardManager) a.getSystemService(Context.CLIPBOARD_SERVICE);
        if (cm == null || !cm.hasPrimaryClip()) return;
        ClipData c = cm.getPrimaryClip();
        if (c == null || c.getItemCount() == 0) return;
        CharSequence t = c.getItemAt(0).coerceToText(a);
        if (t == null) return;
        UyapMobilServisi.gonder("Y " + UyapMobilServisi.hex(t.toString().getBytes(StandardCharsets.UTF_8)));
        ekran.postDelayed(() -> ekran.tus('V', EkranView.CTRL), 120);
    }

    // ==================================================================================== parçalar
    private ImageView ikonDugme(Tasarim.S s, String ipucu, View.OnClickListener l) {
        ImageView iv = new ImageView(a);
        iv.setImageDrawable(Tasarim.simge(a, s, Tasarim.METIN));
        iv.setScaleType(ImageView.ScaleType.CENTER_INSIDE);
        iv.setPadding(dp(12), dp(12), dp(12), dp(12));
        iv.setBackground(Tasarim.dalga(null, dp(24)));
        iv.setContentDescription(ipucu);
        iv.setOnClickListener(v -> { pulse(v); l.onClick(v); });
        iv.setOnLongClickListener(v -> { Toast.makeText(a, ipucu, Toast.LENGTH_SHORT).show(); return true; });
        iv.setFocusable(false);
        iv.setLayoutParams(new LinearLayout.LayoutParams(dp(48), dp(48)));
        return iv;
    }

    private void secili(ImageView iv, boolean s) {
        iv.setBackground(Tasarim.dalga(s ? Tasarim.yuvarlak(Tasarim.SECILI, dp(12)) : null, dp(24)));
        android.graphics.drawable.Drawable d = iv.getDrawable();
        if (d instanceof Tasarim.Cizim) ((Tasarim.Cizim) d).renk(s ? Tasarim.VURGU : Tasarim.METIN);
    }

    private ImageView editorSimgesi(JSONObject b, Runnable r) {
        ImageView iv = new ImageView(a);
        iv.setScaleType(ImageView.ScaleType.FIT_CENTER);
        iv.setPadding(dp(10), dp(10), dp(10), dp(10));
        Bitmap bm = simge(b.optString("ic"));
        if (bm != null) iv.setImageBitmap(bm);
        boolean etkin = b.optInt("e") == 1, sec = b.optInt("s", -1) == 1;
        iv.setBackground(Tasarim.dalga(sec ? Tasarim.yuvarlak(Tasarim.SECILI, dp(10)) : null, dp(10)));
        iv.setAlpha(etkin ? 1f : 0.35f);
        if (etkin) iv.setOnClickListener(v -> r.run());
        return iv;
    }

    private View hizliKart(Tasarim.S s, String ad, Runnable r) {
        LinearLayout k = new LinearLayout(a);
        k.setOrientation(LinearLayout.VERTICAL);
        k.setGravity(Gravity.CENTER);
        k.setPadding(0, dp(12), 0, dp(10));
        k.setBackground(Tasarim.dalga(Tasarim.yuvarlak(Tasarim.ZEMIN, dp(16)), dp(16)));
        ImageView iv = new ImageView(a);
        iv.setImageDrawable(Tasarim.simge(a, s, Tasarim.VURGU));
        k.addView(iv, new LinearLayout.LayoutParams(dp(26), dp(26)));
        TextView t = metin(ad, 13, Tasarim.METIN, true);
        t.setPadding(0, dp(6), 0, 0);
        k.addView(t);
        k.setOnClickListener(v -> { pulse(v); r.run(); });
        return k;
    }

    private View satir(String ic, String sag, String metin, boolean etkin, int secili, Runnable r) {
        LinearLayout s = new LinearLayout(a);
        s.setOrientation(LinearLayout.HORIZONTAL);
        s.setGravity(Gravity.CENTER_VERTICAL);
        s.setPadding(dp(20), 0, dp(20), 0);
        s.setMinimumHeight(dp(52));
        if (ic != null) {
            ImageView iv = new ImageView(a);
            Bitmap bm = simge(ic);
            if (bm != null) iv.setImageBitmap(bm);
            iv.setScaleType(ImageView.ScaleType.FIT_CENTER);
            s.addView(iv, new LinearLayout.LayoutParams(dp(24), dp(24)));
        }
        String on = secili == 1 ? "✓  " : "";
        TextView t = metin(on + metin, 16, secili == 1 ? Tasarim.VURGU : Tasarim.METIN, false);
        t.setPadding(ic != null ? dp(20) : 0, dp(12), 0, dp(12));
        s.addView(t, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        if (sag != null) {
            TextView sg = metin(sag + "  ›", 15, Tasarim.IKINCIL, false);
            s.addView(sg);
        }
        s.setAlpha(etkin ? 1f : 0.38f);
        if (etkin) {
            s.setBackground(Tasarim.dalga(null, 0));
            s.setOnClickListener(v -> r.run());
        }
        return s;
    }

    private TextView tusCipi(String m, View.OnClickListener l) {
        TextView t = metin(m, 14, Tasarim.METIN, true);
        t.setGravity(Gravity.CENTER);
        t.setPadding(dp(14), 0, dp(14), 0);
        t.setMinWidth(dp(44));
        cipDurum(t, false);
        t.setOnClickListener(v -> { pulse(v); l.onClick(v); });
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, dp(38));
        lp.setMargins(dp(3), 0, dp(3), 0);
        t.setLayoutParams(lp);
        return t;
    }

    private void cipDurum(TextView t, boolean acik) {
        t.setBackground(Tasarim.dalga(Tasarim.yuvarlak(acik ? Tasarim.VURGU : 0xFFFFFFFF, dp(19)), dp(19)));
        t.setTextColor(acik ? Color.WHITE : Tasarim.METIN);
        if (Build.VERSION.SDK_INT >= 21) t.setElevation(acik ? dp(2) : dp(1));
    }

    private View ayrac() {
        View v = new View(a);
        v.setBackgroundColor(Tasarim.CIZGI);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(1, dp(26));
        lp.setMargins(dp(6), 0, dp(6), 0);
        v.setLayoutParams(lp);
        return v;
    }

    private TextView metin(String m, int sp, int renk, boolean kalin) {
        TextView t = new TextView(a);
        t.setText(m);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setTextColor(renk);
        t.setTypeface(Typeface.create("sans-serif-medium", kalin ? Typeface.BOLD : Typeface.NORMAL));
        if (!kalin) t.setTypeface(Typeface.create("sans-serif", Typeface.NORMAL));
        return t;
    }

    /** Dokunuşta hafif "nefes" animasyonu. */
    private static void pulse(View v) {
        v.animate().cancel();
        v.setScaleX(0.9f);
        v.setScaleY(0.9f);
        v.animate().scaleX(1f).scaleY(1f).setDuration(180).setInterpolator(new DecelerateInterpolator()).start();
    }

    private static android.animation.TimeInterpolator hareket() {
        return Build.VERSION.SDK_INT >= 21 ? new PathInterpolator(0.2f, 0f, 0f, 1f) : new DecelerateInterpolator(2f);
    }

    private LinearLayout.LayoutParams agirlik() {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        lp.setMargins(dp(4), 0, dp(4), 0);
        return lp;
    }

    private static FrameLayout.LayoutParams tam() {
        return new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT);
    }

    private Bitmap simge(String b64) {
        if (b64 == null || b64.isEmpty()) return null;
        Bitmap b = simgeler.get(b64);
        if (b == null && !simgeler.containsKey(b64)) {
            try {
                byte[] d = Base64.decode(b64, Base64.DEFAULT);
                b = BitmapFactory.decodeByteArray(d, 0, d.length);
            } catch (Exception ignored) { }
            if (simgeler.size() > 400) simgeler.clear();
            simgeler.put(b64, b);
        }
        return b;
    }

    private int dp(float v) { return Tasarim.dp(a, v); }
}
